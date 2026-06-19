"""MockTello: 実機なしで動作する TelloController の実装。

TELLO_MODE=mock のときに使用する。映像は動く白い矩形のダミーフレームを生成するか、
MOCK_CAMERA_INDEX で指定した Webカメラデバイスから取得する。
テストは必ずこの実装で完結させ、実機を必要としないこと（CLAUDE.md）。
"""

import logging
import math
import time

import cv2
import numpy as np

from backend.app.drone.base import VALID_DIRECTIONS, DroneStateData, TelloController

logger = logging.getLogger(__name__)

# ダミーフレームのサイズ
_MOCK_FRAME_WIDTH = 640
_MOCK_FRAME_HEIGHT = 480


def _generate_dummy_frame(
    width: int = _MOCK_FRAME_WIDTH, height: int = _MOCK_FRAME_HEIGHT
) -> np.ndarray:
    """テスト用ダミーフレームを生成する（時間で位置が変わる白い矩形）。

    決定論的なパターン（sin/cos で周期運動）なので test_tracker.py でも利用可能。
    """
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    t = time.monotonic()
    # 矩形の中心が画面内を楕円軌道で動く
    cx = int(width / 2 + (width / 4) * math.sin(t * 0.5))
    cy = int(height / 2 + (height / 4) * math.cos(t * 0.35))
    box_w, box_h = 80, 60
    x1 = max(0, cx - box_w // 2)
    y1 = max(0, cy - box_h // 2)
    x2 = min(width - 1, cx + box_w // 2)
    y2 = min(height - 1, cy + box_h // 2)

    # 背景: 暗いグレー
    frame[:] = (30, 30, 30)
    # 対象矩形: 明るいグレー
    frame[y1:y2, x1:x2] = (200, 200, 200)
    # 中心マーク
    cv2.circle(frame, (cx, cy), 4, (255, 255, 255), -1)

    return frame


class MockTello(TelloController):
    """実機なしで動作するモック実装。

    コマンド送信の代わりにログを出力し、ダミーのステートデータを返す。
    連続的な接続・切断テストに対応できるよう、状態はインスタンス変数で管理する。
    """

    def __init__(self, camera_index: int = -1) -> None:
        """
        Args:
            camera_index: Webカメラデバイス番号。-1 はダミー生成フレームを使用。
        """
        self._camera_index = camera_index
        self._cap: cv2.VideoCapture | None = None
        self._connected = False
        self._streaming = False
        self._start_time = time.monotonic()

        logger.info(
            "mock_tello_initialized",
            extra={"camera_index": camera_index},
        )

    # ── ライフサイクル ───────────────────────────────────────────────────────

    def connect(self) -> None:
        """SDK モードを確立する（モック: ログのみ）。"""
        self._connected = True
        self._start_time = time.monotonic()
        logger.info("mock_command_sent", extra={"command": "command", "response": "ok"})

    def disconnect(self) -> None:
        """接続を終了する（モック: ストリームを停止してフラグをリセット）。"""
        if self._streaming:
            self.streamoff()
        self._connected = False
        logger.info("mock_command_sent", extra={"command": "disconnect", "response": "ok"})

    # ── 飛行制御 ────────────────────────────────────────────────────────────

    def takeoff(self) -> None:
        """離陸（モック: ログのみ）。

        ⚠️ 直接呼ばず、必ず /api/takeoff エンドポイント経由で呼ぶこと。
        """
        logger.info("mock_command_sent", extra={"command": "takeoff", "response": "ok"})

    def land(self) -> None:
        """着陸（モック: ログのみ）。緊急着陸・通常着陸の両方でこのメソッドを使う。

        NOTE: SDK の 'emergency'（落下）コマンドは使わない。
        """
        logger.info("mock_command_sent", extra={"command": "land", "response": "ok"})

    def move(self, direction: str, value: int) -> None:
        """離散移動（モック: バリデーション + ログのみ）。

        Raises:
            ValueError: direction が無効、または value が範囲外。
        """
        if direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"無効な方向: '{direction}'. 有効値: {sorted(VALID_DIRECTIONS)}"
            )
        # 旋回は 1–360度、それ以外は 20–500cm
        if direction in {"cw", "ccw"}:
            if not (1 <= value <= 360):
                raise ValueError(f"旋回角度は 1–360 度の範囲で指定してください (got {value})")
        else:
            if not (20 <= value <= 500):
                raise ValueError(f"移動距離は 20–500 cm の範囲で指定してください (got {value})")

        logger.info(
            "mock_command_sent",
            extra={"command": f"{direction} {value}", "response": "ok"},
        )

    def send_rc(self, a: int, b: int, c: int, d: int) -> None:
        """rc コマンド（モック: ログのみ。応答なし fire-and-forget）。"""
        logger.debug(
            "mock_rc_sent",
            extra={"a": a, "b": b, "c": c, "d": d},
        )

    # ── 映像 ────────────────────────────────────────────────────────────────

    def streamon(self) -> None:
        """映像ストリームを開始する（モック: Webカメラ or ダミー生成）。"""
        if self._camera_index >= 0:
            self._cap = cv2.VideoCapture(self._camera_index)
            if not self._cap.isOpened():
                logger.warning(
                    "mock_camera_open_failed",
                    extra={
                        "camera_index": self._camera_index,
                        "fallback": "dummy_frame",
                    },
                )
                self._cap = None
        self._streaming = True
        logger.info(
            "mock_command_sent",
            extra={"command": "streamon", "response": "ok"},
        )

    def streamoff(self) -> None:
        """映像ストリームを停止する（モック: キャプチャデバイスを解放）。"""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._streaming = False
        logger.info(
            "mock_command_sent",
            extra={"command": "streamoff", "response": "ok"},
        )

    def get_frame(self) -> np.ndarray | None:
        """最新フレームを返す（BGR ndarray）。

        Webカメラが設定されている場合はそこから、そうでなければダミーフレームを返す。
        """
        if not self._streaming:
            return None

        if self._cap is not None:
            ret, frame = self._cap.read()
            if ret and frame is not None:
                return frame
            # 読み取り失敗時はダミーにフォールバック
            logger.warning("mock_camera_read_failed", extra={"fallback": "dummy_frame"})

        return _generate_dummy_frame()

    # ── ステート取得 ─────────────────────────────────────────────────────────

    def get_state(self) -> DroneStateData:
        """ダミーのステートデータを返す。

        電池残量は 80% 固定。高度・ヨーは時間経過で緩やかに変化させ、
        実機に近い雰囲気のデータにする。
        """
        elapsed = time.monotonic() - self._start_time
        return DroneStateData(
            battery=80,
            height=int(100 + 10 * math.sin(elapsed * 0.3)),
            temperature_low=25,
            temperature_high=27,
            pitch=int(2 * math.sin(elapsed * 0.2)),
            roll=int(2 * math.cos(elapsed * 0.15)),
            yaw=int(10 * math.sin(elapsed * 0.1)),
            tof=int(100 + 10 * math.cos(elapsed * 0.3)),
            flight_time=int(elapsed),
            speed_x=0,
            speed_y=0,
            speed_z=0,
        )
