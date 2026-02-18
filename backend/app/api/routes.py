from fastapi import APIRouter

from .auth_routes import router as auth_router
from .file_routes import router as file_router
from .prompt_routes import router as prompt_router
from .codebook_routes import router as codebook_router
from .coding_routes import router as coding_router
from .data_routes import router as data_router

router = APIRouter()

# Include sub-routers
router.include_router(auth_router, tags=["authentication"])
router.include_router(file_router, tags=["files"])
router.include_router(prompt_router, tags=["prompts"])
router.include_router(codebook_router, tags=["codebooks"])
router.include_router(coding_router, tags=["coding"])
router.include_router(data_router, tags=["data"])

# Defensive route re-registration:
# If, for any reason, some route decorators did not register onto `router`,
# scan this source file for `@router.<method>("/path")` patterns and add
# any missing routes programmatically. This helps recover from prior
# import-time manipulations during the migration.
try:
    import re
    from pathlib import Path as _Path

    _existing_paths = {getattr(r, "path", None) for r in router.routes}
    _src = _Path(__file__).read_text()
    _pat = re.compile(r"@router\.(get|post|put|delete)\(\s*(['\"])\\s*(/[^'\"]*?)\\s*\2\s*\)")
    for _m in _pat.finditer(_src):
        _method = _m.group(1).upper()
        _path = _m.group(3)
        if _path in _existing_paths:
            continue

        # find the following function name
        _after = _src[_m.end():]
        _fn = None
        _fn_m = re.search(r"def\s+([A-Za-z0-9_]+)\s*\(", _after)
        if _fn_m:
            _fn = _fn_m.group(1)
        if not _fn:
            continue

        _callable = globals().get(_fn)
        if not callable(_callable):
            continue

        try:
            router.add_api_route(_path, _callable, methods=[_method])
            _existing_paths.add(_path)
        except Exception:
            # best-effort only
            pass
except Exception:
    pass
