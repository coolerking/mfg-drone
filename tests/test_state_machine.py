"""state_machine.py の単体テスト。

検証項目:
  - 通常遷移の許可 / 拒否
  - 緊急着陸がどの状態からでも受理される（safety S-1）
  - takeoff は CONNECTED 状態でのみ受理（ガード確認）
  - lost_target は TARGET_SELECTED に戻る（spec F-05 / safety S-5）
  - LANDING 後は CONNECTED に戻る
  - is_flying プロパティの正確性
  - スレッドセーフな連続遷移（基本確認）
"""

import threading

import pytest

from backend.app.state_machine import (
    DroneState,
    InvalidTransitionError,
    StateMachine,
)

# ── フィクスチャ ──────────────────────────────────────────────────────────────

@pytest.fixture
def sm() -> StateMachine:
    """各テストに新しい StateMachine インスタンスを渡す。"""
    return StateMachine()


@pytest.fixture
def sm_flying(sm: StateMachine) -> StateMachine:
    """MANUAL 状態（飛行中）まで進めた StateMachine。"""
    sm.transition("connect")
    sm.transition("takeoff")
    assert sm.state == DroneState.MANUAL
    return sm


@pytest.fixture
def sm_tracking(sm_flying: StateMachine) -> StateMachine:
    """TRACKING 状態まで進めた StateMachine。"""
    sm_flying.transition("select_target")
    sm_flying.transition("start_tracking")
    assert sm_flying.state == DroneState.TRACKING
    return sm_flying


# ── 初期状態 ─────────────────────────────────────────────────────────────────

def test_initial_state(sm: StateMachine) -> None:
    assert sm.state == DroneState.DISCONNECTED


def test_initial_is_not_flying(sm: StateMachine) -> None:
    assert sm.is_flying is False


def test_initial_is_not_connected(sm: StateMachine) -> None:
    assert sm.is_connected is False


# ── 通常の遷移 ────────────────────────────────────────────────────────────────

def test_connect(sm: StateMachine) -> None:
    sm.transition("connect")
    assert sm.state == DroneState.CONNECTED
    assert sm.is_connected is True
    assert sm.is_flying is False


def test_takeoff_from_connected(sm: StateMachine) -> None:
    sm.transition("connect")
    sm.transition("takeoff")
    assert sm.state == DroneState.MANUAL
    assert sm.is_flying is True


def test_land_from_manual(sm_flying: StateMachine) -> None:
    sm_flying.transition("land")
    assert sm_flying.state == DroneState.LANDING


def test_landed_from_landing(sm_flying: StateMachine) -> None:
    sm_flying.transition("land")
    sm_flying.transition("landed")
    assert sm_flying.state == DroneState.CONNECTED
    assert sm_flying.is_flying is False


def test_select_target(sm_flying: StateMachine) -> None:
    sm_flying.transition("select_target")
    assert sm_flying.state == DroneState.TARGET_SELECTED


def test_start_tracking(sm_flying: StateMachine) -> None:
    sm_flying.transition("select_target")
    sm_flying.transition("start_tracking")
    assert sm_flying.state == DroneState.TRACKING


def test_stop_tracking_returns_to_manual(sm_tracking: StateMachine) -> None:
    sm_tracking.transition("stop_tracking")
    assert sm_tracking.state == DroneState.MANUAL


def test_clear_target_returns_to_manual(sm_flying: StateMachine) -> None:
    sm_flying.transition("select_target")
    sm_flying.transition("clear_target")
    assert sm_flying.state == DroneState.MANUAL


def test_disconnect_from_connected(sm: StateMachine) -> None:
    sm.transition("connect")
    sm.transition("disconnect")
    assert sm.state == DroneState.DISCONNECTED


# ── spec F-05 / safety S-5: ロスト時は TARGET_SELECTED に戻る ──────────────────

def test_lost_target_returns_to_target_selected(sm_tracking: StateMachine) -> None:
    """対象ロスト時の遷移先は TARGET_SELECTED であること（MANUAL ではない）。

    docs/architecture.md の状態図に記載されていた MANUAL への誤りを修正済み。
    spec F-05 および safety S-5 の定義が正しい。
    """
    sm_tracking.transition("lost_target")
    assert sm_tracking.state == DroneState.TARGET_SELECTED, (
        "lost_target の遷移先は TARGET_SELECTED であること（spec F-05 / safety S-5）"
    )


def test_lost_target_not_manual(sm_tracking: StateMachine) -> None:
    """念押し: lost_target で MANUAL に遷移しないことを確認。"""
    sm_tracking.transition("lost_target")
    assert sm_tracking.state != DroneState.MANUAL


# ── safety S-1: 緊急着陸はどの状態からでも受理 ──────────────────────────────────

@pytest.mark.parametrize("setup_events, start_state", [
    ([], DroneState.DISCONNECTED),
    (["connect"], DroneState.CONNECTED),
    (["connect", "takeoff"], DroneState.MANUAL),
    (["connect", "takeoff", "select_target"], DroneState.TARGET_SELECTED),
    (["connect", "takeoff", "select_target", "start_tracking"], DroneState.TRACKING),
])
def test_emergency_land_from_any_state(
    sm: StateMachine,
    setup_events: list[str],
    start_state: DroneState,
) -> None:
    """緊急着陸は全状態から LANDING に遷移する（safety S-1）。"""
    for event in setup_events:
        sm.transition(event)
    assert sm.state == start_state

    result = sm.emergency_land()

    assert result == DroneState.LANDING
    assert sm.state == DroneState.LANDING


def test_emergency_land_while_landing_is_idempotent(sm_flying: StateMachine) -> None:
    """LANDING 中に再度緊急着陸を呼んでも LANDING のまま（冪等）。"""
    sm_flying.transition("land")
    assert sm_flying.state == DroneState.LANDING
    sm_flying.emergency_land()
    assert sm_flying.state == DroneState.LANDING


# ── safety S-8: 許可されていない遷移はエラー ────────────────────────────────────

def test_takeoff_from_disconnected_is_rejected(sm: StateMachine) -> None:
    """DISCONNECTED から takeoff は拒否される。"""
    with pytest.raises(InvalidTransitionError) as exc_info:
        sm.transition("takeoff")
    assert exc_info.value.state == DroneState.DISCONNECTED
    assert exc_info.value.event == "takeoff"


def test_takeoff_requires_connected(sm: StateMachine) -> None:
    """CONNECTED 状態でないと takeoff できない（MANUAL から再離陸など）。"""
    sm.transition("connect")
    sm.transition("takeoff")
    # MANUAL 状態から再度 takeoff
    with pytest.raises(InvalidTransitionError):
        sm.transition("takeoff")


def test_connect_from_connected_is_rejected(sm: StateMachine) -> None:
    """接続済みから再度 connect は拒否される。"""
    sm.transition("connect")
    with pytest.raises(InvalidTransitionError):
        sm.transition("connect")


def test_disconnect_while_flying_is_rejected(sm_flying: StateMachine) -> None:
    """飛行中の disconnect は拒否される（safety S-7）。

    実際の切断は MANUAL から land → LANDING → landed → CONNECTED の経路を経てから。
    """
    with pytest.raises(InvalidTransitionError):
        sm_flying.transition("disconnect")


def test_start_tracking_without_target(sm_flying: StateMachine) -> None:
    """TARGET_SELECTED に遷移せずに start_tracking は拒否される。"""
    with pytest.raises(InvalidTransitionError):
        sm_flying.transition("start_tracking")


def test_unknown_event_is_rejected(sm: StateMachine) -> None:
    """存在しないイベント名は拒否される。"""
    with pytest.raises(InvalidTransitionError):
        sm.transition("fly_to_moon")


# ── is_flying プロパティ ─────────────────────────────────────────────────────

@pytest.mark.parametrize("state, expected", [
    (DroneState.DISCONNECTED,    False),
    (DroneState.CONNECTED,       False),
    (DroneState.MANUAL,          True),
    (DroneState.TARGET_SELECTED, True),
    (DroneState.TRACKING,        True),
    (DroneState.LANDING,         True),
])
def test_is_flying(state: DroneState, expected: bool) -> None:
    sm = StateMachine()
    # 内部ステートを直接設定してプロパティをテスト
    sm._state = state  # noqa: SLF001
    assert sm.is_flying == expected


# ── スレッドセーフ確認（基本） ─────────────────────────────────────────────────

def test_concurrent_emergency_land_is_safe(sm_tracking: StateMachine) -> None:
    """複数スレッドから emergency_land を呼んでも最終状態は LANDING。"""
    errors: list[Exception] = []

    def call_emergency() -> None:
        try:
            sm_tracking.emergency_land()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=call_emergency) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"スレッド実行中に例外: {errors}"
    assert sm_tracking.state == DroneState.LANDING
