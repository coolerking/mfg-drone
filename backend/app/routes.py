"""REST API ルート（prefix /api）と WebSocket ルート（prefix /ws）。

main.py での登録:
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

エンドポイント一覧（M1 実装済み）:
    POST /api/connect       接続確立 (F-01)
    POST /api/disconnect    切断 (F-07) — 飛行中は自動着陸後切断 (S-7)
    GET  /api/state         現在状態をポーリング取得
    WS   /ws/state          状態を 1 秒ごとに push

後続マイルストーンで追加するルートは末尾に TODO コメントで記載。
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from backend.app.drone.base import TelloController
from backend.app.schemas import StatePayload
from backend.app.state_machine import DroneState, InvalidTransitionError, StateMachine

logger = logging.getLogger(__name__)

api_router = APIRouter()
ws_router = APIRouter()

# ── 共通ヘルパー ──────────────────────────────────────────────────────────────


def _sm(request: Request) -> StateMachine:
    return request.app.state.sm


def _ctrl(request: Request) -> TelloController:
    return request.app.state.controller


def _build_payload(sm: StateMachine, controller: TelloController) -> StatePayload:
    """StateMachine と TelloController から StatePayload を組み立てる。"""
    d = controller.get_state()
    return StatePayload(
        state=sm.state,
        battery=d.battery,
        height=d.height,
        flight_time=d.flight_time,
        pitch=d.pitch,
        roll=d.roll,
        yaw=d.yaw,
        tof=d.tof,
    )


def _do_land(sm: StateMachine, controller: TelloController) -> None:
    """飛行中の切断に先立ち、着陸→着地確認を行う（モックでは即時）。

    NOTE: 実機では着地確認まで待つ必要がある（M2 以降で対応）。
    """
    state = sm.state
    if state in (DroneState.MANUAL, DroneState.TARGET_SELECTED, DroneState.TRACKING):
        sm.transition("land")
    # LANDING のケースはそのまま landed に進む
    controller.land()  # モック: ログのみ。実機: "land" コマンド送信
    sm.transition("landed")  # → CONNECTED


# ── M1: 接続 / 切断 / 状態取得 ───────────────────────────────────────────────


@api_router.post("/connect", response_model=StatePayload)
async def connect(request: Request) -> StatePayload:
    """SDK モードを確立し、CONNECTED 状態に遷移する (F-01)。

    Raises:
        409: すでに接続済みの場合。
        500: コントローラの接続に失敗した場合。
    """
    sm = _sm(request)
    controller = _ctrl(request)
    try:
        controller.connect()
        sm.transition("connect")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        logger.exception("connect_failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    logger.info("api_connect_ok", extra={"state": sm.state})
    return _build_payload(sm, controller)


@api_router.post("/disconnect", response_model=StatePayload)
async def disconnect(request: Request) -> StatePayload:
    """接続を切断する (F-07 / safety S-7)。

    飛行中の場合は自動着陸してから切断する（設計決定: 自動着陸後切断）。
    DISCONNECTED 状態からの呼び出しは 409 を返す。
    """
    sm = _sm(request)
    controller = _ctrl(request)

    if sm.state == DroneState.DISCONNECTED:
        raise HTTPException(status_code=409, detail="既に切断済みです")

    # 飛行中は着陸してから切断（safety S-7）
    if sm.is_flying:
        logger.info("auto_land_before_disconnect", extra={"state": sm.state})
        _do_land(sm, controller)
        # sm.state は CONNECTED になっている

    sm.transition("disconnect")
    controller.disconnect()
    logger.info("api_disconnect_ok", extra={"state": sm.state})
    return _build_payload(sm, controller)


@api_router.get("/state", response_model=StatePayload)
async def get_state(request: Request) -> StatePayload:
    """現在の状態・ステートを返す (F-01/03)。

    WebSocket が使えない環境や初回取得でポーリングに使う。
    """
    return _build_payload(_sm(request), _ctrl(request))


# ── M1: WebSocket 状態 push ──────────────────────────────────────────────────


@ws_router.websocket("/ws/state")
async def ws_state(websocket: WebSocket) -> None:
    """/ws/state — 状態・ステートを 1 秒ごとに push する (F-01/03)。

    クライアントからの heartbeat メッセージを受け付ける（M3 ウォッチドッグで活用）。
    接続断は WebSocketDisconnect で検知し、静かに終了する。
    """
    await websocket.accept()
    sm: StateMachine = websocket.app.state.sm
    controller: TelloController = websocket.app.state.controller
    logger.info("ws_state_connected", extra={"client": str(websocket.client)})

    try:
        while True:
            payload = _build_payload(sm, controller)
            await websocket.send_json(payload.model_dump(mode="json"))

            # 1 秒スリープしつつ、クライアントから来た heartbeat を読み捨てる
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except TimeoutError:
                pass  # heartbeat なし — 正常
    except WebSocketDisconnect:
        logger.info("ws_state_disconnected", extra={"client": str(websocket.client)})
    except Exception:
        logger.exception("ws_state_error")


# ── 後続マイルストーンで追加するルート（スタブ） ─────────────────────────────

# M2: POST /api/takeoff, /api/land, /api/move
# M3: POST /api/emergency
# M4: POST /api/target, /api/target/clear
# M5: POST /api/track/start, /api/track/stop
# M2: WS  /ws/video
