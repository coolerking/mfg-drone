/**
 * mfg-drone フロントエンド
 *
 * M1: 接続/切断 API 呼び出し、/ws/state で状態 push 受信・UI 反映
 * M2〜: 離陸/着陸/映像/移動操作（TODO コメントで記載）
 */

'use strict';

// ── DOM 参照 ──────────────────────────────────────────────────────────────────
const $state        = document.getElementById('val-state');
const $battery      = document.getElementById('val-battery');
const $height       = document.getElementById('val-height');
const $flighttime   = document.getElementById('val-flighttime');
const $modeBadge    = document.getElementById('mode-badge');
const $wsStatus     = document.getElementById('ws-status');
const $videoFrame   = document.getElementById('video-frame');
const $videoOverlay = document.getElementById('video-overlay');
const $btnEmergency  = document.getElementById('btn-emergency');
const $btnConnect    = document.getElementById('btn-connect');
const $btnDisconnect = document.getElementById('btn-disconnect');
const $btnTakeoff    = document.getElementById('btn-takeoff');
const $btnLand       = document.getElementById('btn-land');
const $btnTrackStart = document.getElementById('btn-track-start');
const $btnTrackStop  = document.getElementById('btn-track-stop');
const $btnTargetClear = document.getElementById('btn-target-clear');

// ── アプリ状態 ────────────────────────────────────────────────────────────────
/** @type {string} サーバ側の DroneState */
let droneState = 'DISCONNECTED';

/** @type {WebSocket|null} */
let wsState = null;

/** WebSocket 自動再接続タイマー ID */
let wsReconnectTimer = null;

// ── ユーティリティ ─────────────────────────────────────────────────────────────

/**
 * REST API を呼び出す共通関数。
 * @param {string} path   例: '/api/connect'
 * @param {string} [method='POST']
 * @param {object|null} [body=null]
 * @returns {Promise<object>}
 */
async function apiCall(path, method = 'POST', body = null) {
  const options = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== null) options.body = JSON.stringify(body);
  const res = await fetch(path, options);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

/** ボタンにスピナー的な "処理中" 表示を付けて操作を無効化し、終わったら戻す。 */
function withLoading(btn, label, fn) {
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = label;
  return fn().finally(() => {
    btn.textContent = orig;
    // ボタン有効/無効は applyState が管理するので、ここでは disabled を戻さない
    applyState({ state: droneState });
  });
}

// ── 状態の反映 ────────────────────────────────────────────────────────────────

/**
 * サーバから受け取った StatePayload でUIを更新する。
 * @param {{state: string, battery?: number, height?: number, flight_time?: number}} data
 */
function applyState(data) {
  if (data.state) droneState = data.state;

  $state.textContent      = droneState;
  $battery.textContent    = data.battery    != null ? `${data.battery}%`    : '—';
  $height.textContent     = data.height     != null ? `${data.height} cm`   : '—';
  $flighttime.textContent = data.flight_time != null ? `${data.flight_time}s` : '—';

  // 電池警告色（将来の S-6 実装でしきい値判定を追加）
  $battery.style.color = '';

  // 飛行中フラグ（緊急着陸ボタンの表示制御）
  const flying = ['MANUAL', 'TARGET_SELECTED', 'TRACKING', 'LANDING'].includes(droneState);
  document.body.classList.toggle('is-flying', flying);
  $btnEmergency.disabled = !flying;

  // 各ボタンの有効・無効
  $btnConnect.disabled    = droneState !== 'DISCONNECTED';
  $btnDisconnect.disabled = droneState === 'DISCONNECTED';
  $btnTakeoff.disabled    = droneState !== 'CONNECTED';
  $btnLand.disabled       = !['MANUAL', 'TARGET_SELECTED', 'TRACKING'].includes(droneState);

  document.querySelectorAll('.dpad__btn').forEach(btn => {
    btn.disabled = droneState !== 'MANUAL';
  });

  $btnTrackStart.disabled  = droneState !== 'TARGET_SELECTED';
  $btnTrackStop.disabled   = droneState !== 'TRACKING';
  $btnTargetClear.disabled = droneState !== 'TARGET_SELECTED';
}

// ── WebSocket /ws/state ───────────────────────────────────────────────────────

function openWsState() {
  if (wsState && wsState.readyState <= WebSocket.OPEN) return; // 接続済み or 接続中

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  wsState = new WebSocket(`${proto}//${location.host}/ws/state`);

  wsState.onopen = () => {
    $wsStatus.textContent = 'WebSocket: 接続中';
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  };

  wsState.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      applyState(data);
    } catch {
      console.warn('ws_state: JSON パース失敗', event.data);
    }
  };

  wsState.onclose = () => {
    $wsStatus.textContent = 'WebSocket: 再接続待ち…';
    // 3 秒後に再接続
    wsReconnectTimer = setTimeout(openWsState, 3000);
  };

  wsState.onerror = () => {
    $wsStatus.textContent = 'WebSocket: エラー';
  };
}

// ── キーボードショートカット ───────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
  // スペース → 緊急着陸（M3 で実体実装）
  if (e.code === 'Space' && !e.repeat) {
    e.preventDefault();
    if (!$btnEmergency.disabled) $btnEmergency.click();
  }
});

// ── イベントリスナー ──────────────────────────────────────────────────────────

$btnConnect.addEventListener('click', () => {
  withLoading($btnConnect, '接続中…', async () => {
    try {
      const data = await apiCall('/api/connect');
      applyState(data);
    } catch (err) {
      console.error('接続エラー:', err.message);
      alert(`接続エラー: ${err.message}`);
    }
  });
});

$btnDisconnect.addEventListener('click', () => {
  withLoading($btnDisconnect, '切断中…', async () => {
    try {
      const data = await apiCall('/api/disconnect');
      applyState(data);
    } catch (err) {
      console.error('切断エラー:', err.message);
      alert(`切断エラー: ${err.message}`);
    }
  });
});

$btnTakeoff.addEventListener('click', async () => {
  // TODO(M2): apiCall('/api/takeoff')
  console.log('[M2] takeoff');
});

$btnLand.addEventListener('click', async () => {
  // TODO(M2): apiCall('/api/land')
  console.log('[M2] land');
});

$btnEmergency.addEventListener('click', async () => {
  // TODO(M3): apiCall('/api/emergency') — 最優先・常時受理
  console.log('[M3] emergency land');
});

document.querySelectorAll('.dpad__btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const dir = btn.dataset.dir;
    // TODO(M2): apiCall('/api/move', 'POST', { direction: dir, value: MOVE_STEP })
    console.log(`[M2] move ${dir}`);
  });
});

$btnTrackStart.addEventListener('click', async () => {
  // TODO(M5): apiCall('/api/track/start')
  console.log('[M5] track start');
});

$btnTrackStop.addEventListener('click', async () => {
  // TODO(M5): apiCall('/api/track/stop')
  console.log('[M5] track stop');
});

$btnTargetClear.addEventListener('click', async () => {
  // TODO(M4): apiCall('/api/target/clear', 'POST')
  console.log('[M4] target clear');
});

// ── 初期化 ────────────────────────────────────────────────────────────────────

async function init() {
  // サーバのモード表示
  try {
    const health = await apiCall('/health', 'GET');
    $modeBadge.textContent = health.mode ?? 'unknown';
  } catch {
    $modeBadge.textContent = 'offline';
  }

  // 初期状態をポーリングで取得してから WebSocket を開く
  try {
    const data = await apiCall('/api/state', 'GET');
    applyState(data);
  } catch {
    applyState({ state: 'DISCONNECTED' });
  }

  openWsState();
}

init();
