"""TelloController 抽象インターフェース。

RealTello（djitellopy ラッパー）と MockTello の共通契約を定義する。
実装クラスはこのクラスを継承し、すべての抽象メソッドを実装しなければならない。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class DroneStateData:
    """機体から受信するステートデータ。

    ステート受信ポート (UDP :8890) の情報を構造化したもの。
    djitellopy なら get_battery() 等で取得し、ここに詰める。
    """

    battery: int = 0          # 電池残量 (%)
    height: int = 0           # 高度 (cm)
    temperature_low: int = 0  # 温度下限 (℃)
    temperature_high: int = 0 # 温度上限 (℃)
    pitch: int = 0            # ピッチ角 (度)
    roll: int = 0             # ロール角 (度)
    yaw: int = 0              # ヨー角 (度)
    tof: int = 0              # TOF センサ距離 (cm)
    flight_time: int = 0      # 飛行時間 (s)
    speed_x: int = 0          # X 軸速度 (cm/s)
    speed_y: int = 0          # Y 軸速度 (cm/s)
    speed_z: int = 0          # Z 軸速度 (cm/s)
    extra: dict = field(default_factory=dict)  # その他の生ステート値


# 離散移動コマンドの方向名。reference/tello-sdk2.md 準拠。
VALID_DIRECTIONS: frozenset[str] = frozenset(
    {"forward", "back", "left", "right", "up", "down", "cw", "ccw"}
)


class TelloController(ABC):
    """Tello EDU 制御の抽象インターフェース。

    接続・離着陸・移動・映像取得のシグネチャを定義する。
    状態機械のガードをすり抜けてこのクラスを直接呼ぶことは禁止（唯一の例外は緊急着陸）。
    """

    # ── ライフサイクル ───────────────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """SDK モードを確立する（= 'command' コマンドを送信）。"""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """接続を終了する。映像ストリームは先に停止しておくこと。"""
        ...

    # ── 飛行制御 ────────────────────────────────────────────────────────────

    @abstractmethod
    def takeoff(self) -> None:
        """離陸する。

        ⚠️ 必ず人間の明示操作（API エンドポイント /api/takeoff）を起点として呼ぶこと。
        ソフトウェアが自律的にこのメソッドを呼ぶことは禁止（docs/safety.md 原則 1）。
        """
        ...

    @abstractmethod
    def land(self) -> None:
        """着陸する（通常着陸・緊急着陸の両方で使用）。

        NOTE: SDK の 'emergency' コマンド（モーター即時停止 = 落下）は使わない。
        緊急着陸も 'land' コマンドで安全に降ろす。
        （reference/tello-sdk2.md: "emergency: モーター即時停止。落下する。"）
        """
        ...

    @abstractmethod
    def move(self, direction: str, value: int) -> None:
        """離散移動コマンドを送る（手動操作用）。

        direction: "forward" | "back" | "left" | "right" | "up" | "down" | "cw" | "ccw"
        value:
            移動方向 → 20–500 (cm)  (reference/tello-sdk2.md)
            旋回 (cw/ccw) → 1–360 (度)

        Raises:
            ValueError: direction が無効、または value が範囲外の場合。
        """
        ...

    @abstractmethod
    def send_rc(self, a: int, b: int, c: int, d: int) -> None:
        """rc コマンドを送る（追従制御用、fire-and-forget・応答なし）。

        rc チャンネル（reference/tello-sdk2.md 準拠）:
            a: 左右 roll      (-100〜100, 正=右)
            b: 前後 pitch     (-100〜100, 正=前)
            c: 上下 throttle  (-100〜100, 正=上)
            d: 旋回 yaw       (-100〜100, 正=時計回り)

        初版の追従制御では a=0, c=0 固定（平面追従: ヨー + 前後のみ）。
        各値は呼び出し側で ±MAX_RC_SPEED にクランプしてから渡すこと（safety S-3）。
        """
        ...

    # ── 映像 ────────────────────────────────────────────────────────────────

    @abstractmethod
    def streamon(self) -> None:
        """映像ストリームを開始する。

        NOTE: ステーションモードでの映像可否はファームウェアに依存する場合がある
        （reference/tello-sdk2.md 参照）。
        """
        ...

    @abstractmethod
    def streamoff(self) -> None:
        """映像ストリームを停止する。"""
        ...

    @abstractmethod
    def get_frame(self) -> np.ndarray | None:
        """最新のカメラフレームを返す（BGR ndarray）。

        Returns:
            shape (H, W, 3) の uint8 BGR 配列、取得できない場合は None。
        """
        ...

    # ── ステート取得 ─────────────────────────────────────────────────────────

    @abstractmethod
    def get_state(self) -> DroneStateData:
        """最新のステートデータを返す。"""
        ...
