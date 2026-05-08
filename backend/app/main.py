from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routes.auth import router as auth_router
from .routes.profiles import router as profiles_router
from .routes.runs import router as runs_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Preflight AI", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    init_db()
    app.include_router(auth_router)
    app.include_router(profiles_router)
    app.include_router(runs_router)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    return app


app = create_app()
