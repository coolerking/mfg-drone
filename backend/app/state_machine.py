"""ドローンの状態機械。

すべての状態遷移はこのモジュールを通す（safety S-8）。
状態を無視した直接コマンド送信は禁止。唯一の例外は緊急着陸（emergency_land）。

状態一覧:
    DISCONNECTED     機体と未接続
    CONNECTED        接続済み・地上待機
    MANUAL           飛行中・手動操作
    TARGET_SELECTED  飛行中・追従対象を選択済み
    TRACKING         飛行中・自動追従中
    LANDING          着陸処理中（通常着陸・緊急着陸ともに経由する）

遷移ルール（通常遷移）:
    DISCONNECTED  --connect-->        CONNECTED
    CONNECTED     --disconnect-->     DISCONNECTED
    CONNECTED     --takeoff-->        MANUAL        ※必ず人間の明示操作から
    MANUAL        --land-->           LANDING
    MANUAL        --select_target-->  TARGET_SELECTED
    TARGET_SELECTED --clear_target--> MANUAL
    TARGET_SELECTED --start_tracking--> TRACKING
    TRACKING      --stop_tracking-->  MANUAL
    TRACKING      --lost_target-->    TARGET_SELECTED  ※spec F-05 / safety S-5
    LANDING       --landed-->         CONNECTED

緊急着陸（emergency_land）: どの状態からでも LANDING に遷移（safety S-1）。
"""

import logging
import threading
from enum import StrEnum

logger = logging.getLogger(__name__)


class DroneState(StrEnum):
    """ドローンの運用状態。str を継承するので JSON シリアライズ可能。"""

    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    MANUAL = "MANUAL"
    TARGET_SELECTED = "TARGET_SELECTED"
    TRACKING = "TRACKING"
    LANDING = "LANDING"


# 飛行中の状態セット（切断禁止ガード S-7 や is_flying プロパティで参照）
FLYING_STATES: frozenset[DroneState] = frozenset(
    {DroneState.MANUAL, DroneState.TARGET_SELECTED, DroneState.TRACKING, DroneState.LANDING}
)

# 通常遷移テーブル: {現在状態: {イベント名: 遷移先状態}}
_TRANSITIONS: dict[DroneState, dict[str, DroneState]] = {
    DroneState.DISCONNECTED: {
        "connect": DroneState.CONNECTED,
    },
    DroneState.CONNECTED: {
        "disconnect": DroneState.DISCONNECTED,
        "takeoff": DroneState.MANUAL,
    },
    DroneState.MANUAL: {
        "land": DroneState.LANDING,
        "select_target": DroneState.TARGET_SELECTED,
    },
    DroneState.TARGET_SELECTED: {
        "land": DroneState.LANDING,
        "clear_target": DroneState.MANUAL,
        "start_tracking": DroneState.TRACKING,
    },
    DroneState.TRACKING: {
        "land": DroneState.LANDING,
        "stop_tracking": DroneState.MANUAL,
        "lost_target": DroneState.TARGET_SELECTED,  # spec F-05 / safety S-5
    },
    DroneState.LANDING: {
        "landed": DroneState.CONNECTED,
    },
}


class InvalidTransitionError(ValueError):
    """許可されていない状態遷移を要求したときに送出する例外。"""

    def __init__(self, state: DroneState, event: str) -> None:
        allowed = sorted(_TRANSITIONS.get(state, {}).keys())
        super().__init__(
            f"状態 '{state}' からイベント '{event}' は受理できません。"
            f"この状態で有効なイベント: {allowed}"
        )
        self.state = state
        self.event = event


class StateMachine:
    """ドローン状態機械。

    スレッドセーフ（内部ロックで保護）。
    緊急着陸（emergency_land）はロックを取得した上で状態ガードをスキップして常に受理する。
    """

    def __init__(self) -> None:
        self._state = DroneState.DISCONNECTED
        self._lock = threading.Lock()
        logger.info("state_machine_initialized", extra={"initial_state": self._state})

    # ── プロパティ ───────────────────────────────────────────────────────────

    @property
    def state(self) -> DroneState:
        """現在の状態を返す（スレッドセーフ）。"""
        with self._lock:
            return self._state

    @property
    def is_flying(self) -> bool:
        """機体が飛行中（地面にいない）のとき True を返す。"""
        return self.state in FLYING_STATES

    @property
    def is_connected(self) -> bool:
        """接続済み（飛行中を含む）のとき True を返す。"""
        return self.state != DroneState.DISCONNECTED

    # ── 遷移 ────────────────────────────────────────────────────────────────

    def transition(self, event: str) -> DroneState:
        """通常の状態遷移を実行する。

        Args:
            event: 遷移イベント名（"connect", "takeoff", "land" 等）。

        Returns:
            遷移後の DroneState。

        Raises:
            InvalidTransitionError: 現在の状態からそのイベントが許可されていない場合。
        """
        with self._lock:
            allowed = _TRANSITIONS.get(self._state, {})
            if event not in allowed:
                raise InvalidTransitionError(self._state, event)

            new_state = allowed[event]
            old_state = self._state
            self._state = new_state

        # ロック外でログ（ロック保持中の I/O を最小化）
        logger.info(
            "state_transition",
            extra={"from_state": old_state, "event": event, "to_state": new_state},
        )
        return new_state

    def emergency_land(self) -> DroneState:
        """緊急着陸: どの状態からでも LANDING に遷移する（safety S-1）。

        通常の状態ガードを無視して常に受理する。
        DISCONNECTED から呼んだ場合も LANDING に遷移するが、
        実際のコマンド送信は呼び出し側（routes.py）が is_flying を確認して判断する。

        Returns:
            DroneState.LANDING（常に）。
        """
        with self._lock:
            old_state = self._state
            self._state = DroneState.LANDING

        logger.warning(
            "emergency_land_triggered",
            extra={"from_state": old_state, "to_state": DroneState.LANDING},
        )
        return DroneState.LANDING
