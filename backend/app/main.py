import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app import ai_models
from backend.app.api import routes
from backend.app.core.exceptions import AppError
from backend.app.core.logging import configure_logging, get_logger
from backend.app.database import async_engine, Base
from backend.app.jobs.service import reconcile_orphaned_jobs_on_startup
# Imported so their tables register on Base.metadata before create_all runs below.
from backend.app import storage_models  # noqa: F401
from backend.app.jobs import models as job_models  # noqa: F401

logger = get_logger(__name__)

MODEL_CATALOG_REFRESH_INTERVAL_SECONDS = 24 * 60 * 60


async def _refresh_model_catalog_loop() -> None:
    """Refresh the OpenRouter model catalog immediately, then once a day.

    Runs as a background task rather than blocking startup, so a slow or
    unreachable OpenRouter doesn't delay the app from serving requests --
    on failure it logs and keeps the previously cached catalog.
    """
    while True:
        try:
            await ai_models.refresh_from_openrouter()
            logger.info("Refreshed OpenRouter model catalog (%d models)", len(ai_models.AI_MODELS))
        except Exception:
            logger.exception("Failed to refresh OpenRouter model catalog; keeping existing catalog")
        await asyncio.sleep(MODEL_CATALOG_REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    reconciled = await reconcile_orphaned_jobs_on_startup()
    if reconciled > 0:
        logger.warning("Reconciled %d orphaned jobs on startup", reconciled)
    refresh_task = asyncio.create_task(_refresh_model_catalog_loop())
    yield
    refresh_task.cancel()
    await async_engine.dispose()


app = FastAPI(title="Qualitative Coding API", lifespan=lifespan)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse({"error": exc.message}, status_code=exc.status_code)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://qualitative-coding-tool-lisalics-projects.vercel.app",
        "https://qualitative-coding-tool.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Qualitative Coding API"}
