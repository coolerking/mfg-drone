"""アプリケーション設定。.env ファイルから読み込む。"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数 / .env で上書き可能な設定値。

    ⚠️ 安全パラメータ（MOVE_DISTANCE_CM 以降）は M2/M3 着手前に機体オーナーが確認・調整すること。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 基本設定 ──────────────────────────────────────────────────────────────
    tello_mode: str = Field(default="mock", description="'mock' or 'real'")
    tello_ip: str = Field(default="192.168.11.31", description="機体 IP（real モード時）")
    host: str = Field(default="0.0.0.0", description="サーバがバインドするアドレス")
    port: int = Field(default=8000, description="サーバポート")
    log_level: str = Field(default="INFO", description="ログレベル")

    # モック映像
    mock_camera_index: int = Field(
        default=-1, description="Webカメラデバイス番号（-1 でダミー生成フレーム）"
    )

    # ── 安全パラメータ（⚠️ 要確認） ──────────────────────────────────────────
    # S-3: 速度・移動量の上限
    move_distance_cm: int = Field(default=30, description="手動 1 ステップの移動距離 (cm)")
    rotate_degrees: int = Field(default=20, description="手動 1 ステップの旋回角度 (度)")
    max_rc_speed: int = Field(default=30, description="追従 rc 各軸の出力上限 (絶対値 0–100)")

    # S-2: コマンドレート制限
    max_command_rate_hz: int = Field(default=10, description="rc 送信レート上限 (Hz)")

    # S-4: ウォッチドッグ
    watchdog_timeout_sec: float = Field(
        default=2.0, description="heartbeat 途絶 → ホバリングまでの猶予 (秒)"
    )
    autoland_timeout_sec: float = Field(
        default=5.0, description="ホバリング後 → 自動着陸までの猶予 (秒)"
    )

    # S-6: 電池残量による保護
    battery_warn_pct: int = Field(default=30, description="電池警告表示閾値 (%)")
    min_battery_to_takeoff: int = Field(default=15, description="離陸禁止・着陸推奨閾値 (%)")

    @property
    def is_mock(self) -> bool:
        """モックモードのとき True を返す。"""
        return self.tello_mode.lower() == "mock"


# モジュールレベルのシングルトン。アプリ全体で `from backend.app.config import settings` して使う。
settings = Settings()
