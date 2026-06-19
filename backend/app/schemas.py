"""API の入出力スキーマ（Pydantic モデル）。

REST レスポンスと WebSocket メッセージの両方でこのモデルを使い、
型の一貫性を保つ。
"""

from pydantic import BaseModel

from backend.app.state_machine import DroneState


class StatePayload(BaseModel):
    """GET /api/state および /ws/state の push メッセージ。

    機体ステートと DroneState を一体で返す。
    フロントエンドはこの型のオブジェクトを受け取って applyState() に渡す。
    """

    state: DroneState
    battery: int = 0
    height: int = 0
    flight_time: int = 0
    pitch: int = 0
    roll: int = 0
    yaw: int = 0
    tof: int = 0


class MoveRequest(BaseModel):
    """POST /api/move のリクエストボディ（M2 で使用）。

    direction: "forward" | "back" | "left" | "right" | "up" | "down" | "cw" | "ccw"
    value: 移動 20–500 cm / 旋回 1–360 度
    """

    direction: str
    value: int


class TargetRequest(BaseModel):
    """POST /api/target のリクエストボディ（M4 で使用）。

    座標・サイズは映像フレームに対する正規化値 (0.0〜1.0)。
    サーバ側でフレーム解像度に変換してトラッカーを初期化する。
    """

    x: float  # 左上 X (normalized)
    y: float  # 左上 Y (normalized)
    w: float  # 幅 (normalized)
    h: float  # 高さ (normalized)
