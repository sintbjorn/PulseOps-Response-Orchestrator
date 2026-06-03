from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api import executions, health, policies, runbooks, webhooks
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal, create_schema
from app.services.bootstrap import seed_demo_data

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.auto_create_schema:
        create_schema()
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Incident response orchestration service for PulseWatch incidents.",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(policies.router)
app.include_router(webhooks.router)
app.include_router(executions.router)
app.include_router(runbooks.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/metrics", tags=["metrics"])
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
