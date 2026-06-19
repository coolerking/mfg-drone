"""構造化ログの基盤。

使い方:
    from backend.app.logging_config import setup_logging
    setup_logging(level="INFO")

各モジュールでは標準の logging を使い、extra= でフィールドを追加する:
    logger = logging.getLogger(__name__)
    logger.info("command_sent", extra={"command": "takeoff"})
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# logging.LogRecord の組み込み属性（extra に混入させない）
_BUILTIN_ATTRS: frozenset[str] = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno",
        "pathname", "filename", "module", "exc_info", "exc_text",
        "stack_info", "lineno", "funcName", "created", "msecs",
        "relativeCreated", "thread", "threadName", "processName",
        "process", "message", "taskName",
    }
)


class StructuredFormatter(logging.Formatter):
    """JSON 形式の構造化ログフォーマッタ。

    logger.info("msg", extra={"key": "value"}) で渡した extra フィールドを
    JSON ルートに展開して出力する。
    機体へ送ったコマンドと受信ステートは必ずこのロガーで記録すること（CLAUDE.md）。
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # extra フィールドをマージ
        for key, value in record.__dict__.items():
            if key not in _BUILTIN_ATTRS:
                log_data[key] = value

        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """アプリ起動時に一度だけ呼ぶ。ルートロガーを構造化 JSON 形式に設定する。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
