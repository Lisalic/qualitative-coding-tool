from fastapi import APIRouter

from backend.app.api.auth_routes import router as auth_router
from backend.app.api.file_routes import router as file_router
from backend.app.api.prompt_routes import router as prompt_router
from backend.app.api.codebook_routes import router as codebook_router
from backend.app.api.coding_routes import router as coding_router
from backend.app.api.data_routes import router as data_router
from backend.app.api.project_routes import router as project_router
from backend.app.api.content_routes import router as content_router
from backend.app.api.models_routes import router as models_router
from backend.app.jobs.routes import router as jobs_router

router = APIRouter()

router.include_router(auth_router, tags=["authentication"])
router.include_router(file_router, tags=["files"])
router.include_router(prompt_router, tags=["prompts"])
router.include_router(codebook_router, tags=["codebooks"])
router.include_router(coding_router, tags=["coding"])
router.include_router(data_router, tags=["data"])
router.include_router(project_router, tags=["projects"])
router.include_router(content_router, tags=["content"])
router.include_router(models_router, tags=["models"])
router.include_router(jobs_router, tags=["jobs"])

