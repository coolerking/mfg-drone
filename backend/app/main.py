"""FastAPI アプリケーションのエントリポイント。

起動:
    uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

ブラウザで http://<サーバIP>:8000 を開くと frontend/index.html が配信される。
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.logging_config import setup_logging

# ── ロギング初期化（アプリ全体で最初に行う） ──────────────────────────────────
setup_logging(level=settings.log_level)
logger = logging.getLogger(__name__)

# フロントエンドのディレクトリ
# parents[0]=backend/app, parents[1]=backend, parents[2]=mfg-drone(repo root)
_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """アプリ起動・終了時のフック。

    StateMachine と TelloController をここで初期化し app.state に格納する。
    routes.py のハンドラはすべて app.state 経由でこれらにアクセスする。
    """
    from backend.app.state_machine import StateMachine

    app.state.sm = StateMachine()

    if settings.is_mock:
        from backend.app.drone.mock import MockTello

        app.state.controller = MockTello(camera_index=settings.mock_camera_index)
    else:
        # real モードは M2 以降で実装する
        raise NotImplementedError(
            "TELLO_MODE=real はまだ実装されていません。"
            ".env で TELLO_MODE=mock を設定してください。"
        )

    logger.info(
        "app_startup",
        extra={
            "mode": settings.tello_mode,
            "host": settings.host,
            "port": settings.port,
        },
    )
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title="mfg-drone",
    description="Tello EDU を Web から手動操作・自動追従する学習用アプリ",
    version="0.1.0",
    lifespan=lifespan,
)

# ── ルーター登録 ──────────────────────────────────────────────────────────────
from backend.app.routes import api_router, ws_router  # noqa: E402

app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

# ── 静的ファイル配信 ──────────────────────────────────────────────────────────
if _FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")
else:
    logger.warning("frontend_dir_not_found", extra={"path": str(_FRONTEND_DIR)})


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """ルートアクセスで index.html を返す。"""
    return FileResponse(str(_FRONTEND_DIR / "index.html"))


@app.get("/health")
async def health() -> dict[str, str]:
    """サーバが起動していることを確認するためのエンドポイント。"""
    return {"status": "ok", "mode": settings.tello_mode}
