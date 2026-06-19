"""M1 REST / WebSocket エンドポイントのテスト。

TestClient の lifespan コンテキストマネージャを使い、
各テスト関数ごとに新しい StateMachine + MockTello を起動する。
実機を必要とせず、TELLO_MODE=mock（デフォルト）で完結する。
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.state_machine import DroneState

# ── フィクスチャ ──────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """lifespan 付き TestClient（各テストで新しい SM / Controller を起動）。"""
    with TestClient(app) as c:
        yield c


# ── /health ───────────────────────────────────────────────────────────────────


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["mode"] == "mock"


# ── GET /api/state ────────────────────────────────────────────────────────────


def test_get_state_initial(client):
    """起動直後は DISCONNECTED 状態を返す。"""
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == DroneState.DISCONNECTED
    assert "battery" in data


# ── POST /api/connect ─────────────────────────────────────────────────────────


def test_connect_ok(client):
    """正常な接続で CONNECTED を返す。"""
    resp = client.post("/api/connect")
    assert resp.status_code == 200
    assert resp.json()["state"] == DroneState.CONNECTED


def test_connect_twice_returns_409(client):
    """接続済みにもう一度 connect すると 409。"""
    client.post("/api/connect")
    resp = client.post("/api/connect")
    assert resp.status_code == 409


def test_state_after_connect(client):
    """connect 後に GET /api/state が CONNECTED を返す。"""
    client.post("/api/connect")
    resp = client.get("/api/state")
    assert resp.json()["state"] == DroneState.CONNECTED


# ── POST /api/disconnect ──────────────────────────────────────────────────────


def test_disconnect_ok(client):
    """接続→切断が正常に動く。"""
    client.post("/api/connect")
    resp = client.post("/api/disconnect")
    assert resp.status_code == 200
    assert resp.json()["state"] == DroneState.DISCONNECTED


def test_disconnect_when_disconnected_returns_409(client):
    """未接続状態で disconnect すると 409。"""
    resp = client.post("/api/disconnect")
    assert resp.status_code == 409


def test_state_after_disconnect(client):
    """切断後に GET /api/state が DISCONNECTED を返す。"""
    client.post("/api/connect")
    client.post("/api/disconnect")
    resp = client.get("/api/state")
    assert resp.json()["state"] == DroneState.DISCONNECTED


# ── safety S-7: 飛行中の切断は自動着陸後切断 ────────────────────────────────


def test_disconnect_while_flying_auto_lands(client):
    """飛行中に disconnect を呼ぶと自動着陸してから DISCONNECTED になる。

    M1 では takeoff エンドポイントがないため、SM の内部状態を直接 MANUAL に設定して
    飛行中を再現する。
    """
    client.post("/api/connect")
    # SM 内部を直接 MANUAL に設定して飛行中を模擬
    app.state.sm._state = DroneState.MANUAL  # noqa: SLF001

    resp = client.post("/api/disconnect")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == DroneState.DISCONNECTED


@pytest.mark.parametrize("flying_state", [
    DroneState.MANUAL,
    DroneState.TARGET_SELECTED,
    DroneState.TRACKING,
])
def test_disconnect_while_flying_covers_all_flying_states(client, flying_state):
    """MANUAL / TARGET_SELECTED / TRACKING のどの飛行状態からでも切断が成功する。"""
    client.post("/api/connect")
    app.state.sm._state = flying_state  # noqa: SLF001
    resp = client.post("/api/disconnect")
    assert resp.status_code == 200
    assert resp.json()["state"] == DroneState.DISCONNECTED


# ── WebSocket /ws/state ───────────────────────────────────────────────────────


def test_ws_state_pushes_initial_state(client):
    """/ws/state に接続すると即座に状態 JSON が来る。"""
    with client.websocket_connect("/ws/state") as ws:
        data = ws.receive_json()
    assert "state" in data
    assert "battery" in data
    assert "height" in data
    assert data["state"] == DroneState.DISCONNECTED


def test_ws_state_reflects_connect(client):
    """connect 後に /ws/state が CONNECTED 状態を push する。"""
    client.post("/api/connect")
    with client.websocket_connect("/ws/state") as ws:
        data = ws.receive_json()
    assert data["state"] == DroneState.CONNECTED


def test_ws_state_reflects_disconnect(client):
    """connect → disconnect 後に /ws/state が DISCONNECTED を push する。"""
    client.post("/api/connect")
    client.post("/api/disconnect")
    with client.websocket_connect("/ws/state") as ws:
        data = ws.receive_json()
    assert data["state"] == DroneState.DISCONNECTED
