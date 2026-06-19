# アーキテクチャ

## 全体像

```
┌─────────────── ブラウザ (frontend/) ───────────────┐
│  映像表示 + 矩形選択 / 操作ボタン / 状態・電池表示  │
└───────┬───────────────────────────────┬───────────┘
        │ REST (操作コマンド)            │ WebSocket (映像 + 状態 push)
┌───────▼───────────────────────────────▼───────────┐
│                FastAPI (backend/app/)               │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────┐ │
│  │ API ルーティング│→│ 状態機械       │→│セーフティ │ │
│  │ (routes.py)   │  │(state_machine)│  │ガバナー  │ │
│  └──────────────┘  └───────┬───────┘  └────┬─────┘ │
│  ┌──────────────┐          │                │       │
│  │ 追従ロジック  │◀─映像──┐ │                │       │
│  │ (tracker.py) │         │ ▼                ▼       │
│  └──────────────┘   ┌─────┴────────────────────┐    │
│                     │ ドローン制御 (drone/)      │    │
│                     │  TelloController          │    │
│                     │   ├ RealTello (djitellopy)│    │
│                     │   └ MockTello            │    │
│                     └───────────┬──────────────┘    │
└─────────────────────────────────┼───────────────────┘
                                   │ UDP (8889/8890/11111)
                            ┌──────▼──────┐
                            │  Tello EDU   │
                            └─────────────┘
```

## ディレクトリ構成

```
mfg-drone/
├── README.md
├── CLAUDE.md
├── pyproject.toml
├── .env.example
├── docs/
│   ├── spec.md
│   ├── architecture.md
│   ├── safety.md
│   └── milestones.md
├── reference/
│   └── tello-sdk2.md
├── backend/
│   └── app/
│       ├── main.py            # FastAPI エントリポイント / 静的配信
│       ├── config.py          # .env 読み込み (TELLO_IP, TELLO_MODE 等)
│       ├── routes.py          # REST / WebSocket エンドポイント
│       ├── state_machine.py   # 状態遷移の管理
│       ├── safety.py          # レート制限・ウォッチドッグ・フェイルセーフ
│       ├── tracker.py         # OpenCV トラッカー + 制御則 (ズレ→速度)
│       └── drone/
│           ├── base.py        # TelloController 抽象インターフェース
│           ├── real.py        # djitellopy 実装
│           └── mock.py        # モック実装（Webカメラ/ダミー映像）
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── tests/
    ├── test_state_machine.py
    ├── test_safety.py
    └── test_tracker.py
```

## ステーションモードへの切り替え（初回のみ）

1. PC を Tello の直 Wi-Fi（`TELLO-XXXXXX`）に接続する。
2. SDK モードに入り、`ap [SSID] [PASSWORD]` コマンドで自宅 AP の認証情報を送る。
3. 機体が再起動し、自宅 LAN に子機として接続される。
4. ルーターで機体 MAC に IP を DHCP 予約し、`.env` の `TELLO_IP` に設定する。
5. 以降は `Tello(host=TELLO_IP)` で接続する。

> 直 Wi-Fi モードに戻したい場合は SDK の該当コマンドを参照（`reference/tello-sdk2.md`）。

## 状態機械

中核となる状態と遷移。**緊急着陸はどの状態からでも `LANDING` に遷移できる**点が最重要。

```
            connect              takeoff            select target
DISCONNECTED ───────▶ CONNECTED ─────────▶ MANUAL ───────────────▶ TARGET_SELECTED
     ▲                   │  ▲                 ▲  ▲                        │
     │ disconnect        │  │                 │  │ stop tracking          │ start tracking
     │ (着地時のみ)       │  │                 │  └────────────────────────┤
     └───────────────────┘  │                 │                           ▼
                            │                 └─── lost target ──────  TRACKING
                            │
   [どの飛行状態からでも]   │  land / emergency / watchdog
   ─────────────────────────┴──────────────▶ LANDING ──(着地)──▶ CONNECTED
```

> **修正メモ (2026-06-18):** `lost target` の遷移先を `MANUAL` から **`TARGET_SELECTED`** に修正。
> spec F-05 / safety S-5 に合わせ、対象ロスト時はホバリングして選択状態を保持する。

遷移ルール:

- 通常の遷移は state_machine が許可した場合のみコマンドを発行する。
- `EMERGENCY`（緊急着陸）と watchdog 起因の安全停止は、状態ガードを無視して常に受理する。
- 飛行中の `disconnect` は禁止。まず着陸させる（F-07）。

## 制御則（追従）

- トラッカー: OpenCV の CSRT（精度重視）。`opencv-contrib-python` が必要（CSRT は contrib 版のみ）。
- 入力: トラッカーが返す対象矩形の中心 `(cx, cy)` と画面中心 `(W/2, H/2)` のズレ。
- 出力: Tello の `rc a b c d`（左右 / 前後 / 上下 / 旋回、各 -100〜100）に写像。

  **初版の制御軸（平面追従）:**
  - 水平ズレ `(cx - W/2)` → **旋回（yaw = rc.d）**（正方向: 右、つまり右ズレ → 時計回り）
  - 矩形サイズの増減（対象との距離の代理指標）→ **前後（pitch = rc.b）**
  - **縦（throttle = rc.c）は初版では制御しない。** `c = 0` 固定。
  - 左右ストラフ（rc.a）も初版では使わない。`a = 0` 固定。
  - 各軸に上限（±30 を暫定値として提案。⚠️ M5 着手前に調整）を設け、急激な速度変化を抑制。

- 矩形座標は**正規化 (0.0〜1.0)** でクライアント → サーバに送り、サーバ側でフレーム解像度へ変換する。
- 対象ロスト時は即座に `rc 0 0 0 0`（ホバリング）にフォールバック（safety S-5）。

## API 仕様（ドラフト）

REST（操作の起点）:

| メソッド | パス | 機能 | 対応 |
| --- | --- | --- | --- |
| POST | `/api/connect` | 接続確立 | F-01 |
| POST | `/api/disconnect` | 切断（着地時のみ） | F-07 |
| POST | `/api/takeoff` | 離陸（人間の明示操作） | F-02 |
| POST | `/api/land` | 通常着陸 | F-02 |
| POST | `/api/move` | 手動移動 `{direction, value}` — **離散cm移動**（20–500cm / 1–360度。`forward/back/left/right/up/down/cw/ccw`）| F-02 |
| POST | `/api/target` | 対象指定 `{x, y, w, h}` | F-04 |
| POST | `/api/target/clear` | 対象解除 | F-04 |
| POST | `/api/track/start` | 追従開始 | F-05 |
| POST | `/api/track/stop` | 追従停止 | F-05 |
| POST | `/api/emergency` | 緊急着陸（最優先・常時受理）— **`land` コマンドを発行。SDK の `emergency`（モーター停止＝落下）ではない** | F-06 |
| GET  | `/api/state` | 現在状態・ステート取得 | F-01/03 |

WebSocket:

- `/ws/video` — 映像フレーム（MJPEG 相当のバイナリ or base64）を push。
- `/ws/state` — 状態・電池残量・追従結果を一定周期で push。
  - クライアントからの heartbeat を受け、途絶を watchdog が検知する（`docs/safety.md`）。

メッセージは JSON（映像バイナリ除く）。スキーマは Pydantic モデルで定義する。
