"""Aggregate every domain router in ``api/routes/``; ``main.py`` mounts it under ``/api``."""

from fastapi import APIRouter

from backend.app.api.routes import (
    ai_models,
    auth,
    codebook,
    coding,
    content,
    coverage,
    data,
    export,
    files,
    jobs,
    memos,
    projects,
    prompts,
    versions,
)

router = APIRouter()

router.include_router(auth.router, tags=["authentication"])
router.include_router(files.router, tags=["files"])
router.include_router(prompts.router, tags=["prompts"])
router.include_router(codebook.router, tags=["codebooks"])
router.include_router(coding.router, tags=["coding"])
router.include_router(data.router, tags=["data"])
router.include_router(memos.router, tags=["memos"])
router.include_router(projects.router, tags=["projects"])
router.include_router(content.router, tags=["content"])
router.include_router(ai_models.router, tags=["models"])
router.include_router(versions.router, tags=["versions"])
router.include_router(jobs.router, tags=["jobs"])
router.include_router(export.router, tags=["export"])
router.include_router(coverage.router, tags=["coverage"])
