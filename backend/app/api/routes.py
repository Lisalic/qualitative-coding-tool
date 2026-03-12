from fastapi import APIRouter

from .auth_routes import router as auth_router
from .file_routes import router as file_router
from .prompt_routes import router as prompt_router
from .codebook_routes import router as codebook_router
from .coding_routes import router as coding_router
from .data_routes import router as data_router
from .project_routes import router as project_router
from .content_routes import router as content_router

router = APIRouter()

router.include_router(auth_router, tags=["authentication"])
router.include_router(file_router, tags=["files"])
router.include_router(prompt_router, tags=["prompts"])
router.include_router(codebook_router, tags=["codebooks"])
router.include_router(coding_router, tags=["coding"])
router.include_router(data_router, tags=["data"])
router.include_router(project_router, tags=["projects"])
router.include_router(content_router, tags=["content"])

