from __future__ import annotations

from fastapi import FastAPI

from app.webhook.router import router as lead_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(lead_router)
    return app


app = create_app()
