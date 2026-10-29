import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import admin, auth, me, public
from app.core.config import get_settings
from app.core.security import secret_key
from app.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("scholarscope.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.services.crawl import orchestrator, scheduler

    settings = get_settings()
    secret_key()  # fail fast in production without SECRET_KEY
    with SessionLocal() as db:
        n = orchestrator.recover_interrupted_jobs(db)
        if n:
            log.warning("marked %d interrupted crawl jobs as failed", n)
    if settings.scheduler_enabled:
        scheduler.start()
        log.info("scheduler started (tick %ss)", settings.scheduler_tick_seconds)
    yield
    scheduler.stop()


settings = get_settings()
app = FastAPI(
    title="ScholarScope AI API",
    description="Freshness-aware, evidence-grounded scholarship discovery and explainable recommendation.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
)
app.add_middleware(
    CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = uuid.uuid4().hex[:12]
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Log path and status only: no query strings, bodies or tokens (they may contain personal data).
    log.info("%s %s %s %dms rid=%s", request.method, request.url.path, response.status_code,
             int((time.monotonic() - start) * 1000), rid)
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(public.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"name": "ScholarScope AI API", "docs": "/docs", "health": "/api/health"}
