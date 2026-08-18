from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api import routes
from backend.app.core.exceptions import AppError
from backend.app.core.logging import configure_logging, get_logger
from backend.app.database import async_engine, Base
from backend.app.jobs.service import reconcile_orphaned_jobs_on_startup
# Imported so their tables register on Base.metadata before create_all runs below.
from backend.app import storage_models  # noqa: F401
from backend.app.jobs import models as job_models  # noqa: F401

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    reconciled = await reconcile_orphaned_jobs_on_startup()
    if reconciled > 0:
        logger.warning("Reconciled %d orphaned jobs on startup", reconciled)
    yield
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
