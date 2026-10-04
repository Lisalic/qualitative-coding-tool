"""Generic version-history routes -- work for any artifact type, since
``artifact_versions``/``artifact_edges``/``codebook_codes`` are the same
shape underneath every ``File``. Backs the version rail/diff UI in
``ViewCodebook``/``ViewCoding``.

There is no revert/rewind route. Recovering an old state is "duplicate
from that version" (``POST /api/coding/{ref}/duplicate`` /
``POST /api/codebook/{ref}/duplicate`` with ``from_version_no``) --
non-destructive and needs no truncation guard against other artifacts'
``parent_version_id`` pins, since nothing is ever deleted.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from backend.app.core.auth_dependency import require_user_id
from backend.app.core.exceptions import NotFoundError
from backend.app.database import File, get_async_db
from backend.app.repositories import file_repo, version_repo
from backend.app.services import assist_service, version_service
from backend.app.versioning_models import ArtifactVersion

router = APIRouter()


def _version_out(version) -> dict:
    return {
        "version_no": version.version_no,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "author_user_id": version.author_user_id,
        "origin": version.origin,
        "message": version.message,
        "sealed": version.sealed_at is not None,
        "model": version.model,
    }


@router.get("/artifacts/{ref}/versions")
async def list_versions(
    ref: str,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Every version of an artifact owned by the authenticated user,
    newest first.
    """
    file_id = await file_repo.resolve_file_id(db, ref, user_id)
    versions = await version_service.list_history(db, file_id)
    return JSONResponse({"versions": [_version_out(v) for v in versions]})


@router.get("/artifacts/{ref}/diff")
async def diff_artifact(
    ref: str,
    from_no: int,
    to_no: int,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Diff between two versions of the same artifact: always a
    structural codebook diff (added/removed/renamed/redefined/moved/
    reordered, keyed on stable ``code_uid`` -- see
    ``core/codebook_diff.py``), plus one type-specific content diff:
    for a ``coding`` file, its own ``coding_entries`` (rows recoded,
    code counts changed -- see ``core/coding_diff.py``) under
    ``coding``; for a ``raw_data``/``filtered_data`` file, its own
    ``submissions``/``comments`` rows (added/removed -- see
    ``core/data_diff.py``) under ``data``. A file type outside the
    matching branch gets ``null`` for that key -- a codebook has no
    coding_entries or data rows of its own, and vice versa.
    """
    file_rec = await file_repo.get_owned_file(db, ref, user_id)
    # A missing version would otherwise diff as empty: everything "added"
    # or "removed", which reads as a real (and alarming) change.
    for version_no in (from_no, to_no):
        if await version_repo.get_version_by_no(db, file_rec.id, version_no) is None:
            raise NotFoundError(f"Version {version_no} not found")
    codebook_diff = await version_service.diff_codebook(db, file_rec.id, from_no=from_no, to_no=to_no)

    def _code_ref(code: dict) -> dict:
        return {"code_uid": code["code_uid"], "family_name": code["family_name"], "name": code["name"]}

    def _change_ref(entry: dict) -> dict:
        return {
            "code_uid": entry["code_uid"],
            "from": _code_ref(entry["from"]),
            "to": _code_ref(entry["to"]),
        }

    coding_out = None
    if file_rec.file_type == "coding":
        coding_diff = await version_service.diff_coding(db, file_rec.id, from_no=from_no, to_no=to_no)
        coding_out = {
            "from_total_entries": coding_diff.from_total_entries,
            "to_total_entries": coding_diff.to_total_entries,
            "from_coded_rows": coding_diff.from_coded_rows,
            "to_coded_rows": coding_diff.to_coded_rows,
            "rows_recoded": coding_diff.rows_recoded,
            "rows_newly_coded": coding_diff.rows_newly_coded,
            "rows_newly_uncoded": coding_diff.rows_newly_uncoded,
            "code_counts": [
                {
                    "code_uid": c.code_uid,
                    "name": c.name,
                    "from_count": c.from_count,
                    "to_count": c.to_count,
                    "delta": c.delta,
                }
                for c in coding_diff.code_counts
            ],
            "applied": [
                {
                    "row_type": entry.row_type,
                    "post_id": entry.post_id,
                    "code_uid": entry.code_uid,
                    "code": entry.code,
                    "text": entry.quote,
                }
                for entry in coding_diff.applied
            ],
            "removed": [
                {
                    "row_type": entry.row_type,
                    "post_id": entry.post_id,
                    "code_uid": entry.code_uid,
                    "code": entry.code,
                    "text": entry.quote,
                }
                for entry in coding_diff.removed
            ],
        }

    data_out = None
    if file_rec.file_type in ("raw_data", "filtered_data"):
        data_diff = await version_service.diff_data(db, file_rec.id, from_no=from_no, to_no=to_no)
        data_out = {
            "from_submissions": data_diff.from_submissions,
            "to_submissions": data_diff.to_submissions,
            "from_comments": data_diff.from_comments,
            "to_comments": data_diff.to_comments,
            "submissions_added": data_diff.submissions_added,
            "submissions_removed": data_diff.submissions_removed,
            "comments_added": data_diff.comments_added,
            "comments_removed": data_diff.comments_removed,
            "sample_submissions_added": data_diff.sample_submissions_added,
            "sample_submissions_removed": data_diff.sample_submissions_removed,
            "sample_comments_added": data_diff.sample_comments_added,
            "sample_comments_removed": data_diff.sample_comments_removed,
        }

    return JSONResponse(
        {
            "codebook": {
                "added": [_code_ref(c) for c in codebook_diff.added],
                "removed": [_code_ref(c) for c in codebook_diff.removed],
                "renamed": [_change_ref(e) for e in codebook_diff.renamed],
                "redefined": [_change_ref(e) for e in codebook_diff.redefined],
                "moved": [_change_ref(e) for e in codebook_diff.moved],
                "reordered": [_change_ref(e) for e in codebook_diff.reordered],
            },
            "coding": coding_out,
            "data": data_out,
        }
    )


def _neighbor_out(file_rec: File, edge) -> dict:
    return {
        "id": str(file_rec.id),
        "schema_name": file_rec.schemaname,
        "filename": file_rec.filename,
        "file_type": file_rec.file_type,
        "relation": edge.relation,
        "role": edge.role,
        "position": edge.position,
        "parent_version_no": None,
        "models": [],
        "prompts": [],
    }


async def _parent_provenance(db: AsyncSession, neighbor_id: int, version: ArtifactVersion | None) -> tuple[list[str], list[dict]]:
    """Models and prompts behind one pinned parent revision: the
    version's own provenance (set only for a one-shot ``origin=generated``
    artifact -- compare/summarize) plus every AI-assist run recorded
    against that version (set for an AI-assisted edit -- filter/codebook/
    coding, see the ``artifact_assists`` channel in CLAUDE.md's Storage
    model section). A revision can carry both, e.g. a coding artifact
    recoded once via AI-assist and then hand-edited.
    """
    if version is None:
        return [], []

    models: list[str] = []
    prompts: list[dict] = []

    if version.model:
        models.append(version.model)
        prompts.append(
            {
                "stage": "generated",
                "model": version.model,
                "system_prompt": version.system_prompt,
                "user_instructions": version.user_instructions,
                "prompt_meta": version.prompt_meta,
            }
        )

    assists = await assist_service.list_assists(db, neighbor_id, version_no=version.version_no)
    for assist in assists:
        if assist["model"] and assist["model"] not in models:
            models.append(assist["model"])
        prompts.append(
            {
                "stage": assist["stage"],
                "model": assist["model"],
                "system_prompt": assist["system_prompt"],
                "user_instructions": assist["user_instructions"],
                "prompt_meta": assist["prompt_meta"],
            }
        )

    return models, prompts


@router.get("/artifacts/{ref}/lineage")
async def lineage(
    ref: str,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """The typed derivation graph immediately around one artifact: its
    parents (what it was derived from, each edge's role/relation, and
    which revision was pinned) and its children (what has since been
    derived from it) -- roadmap item C6, a read path over
    ``artifact_edges`` that cost nothing extra once the edges were typed
    and version-pinned (see ``versioning_models.py::ArtifactEdge``).
    One level each direction, not the full transitive closure.
    """
    file_id = await file_repo.resolve_file_id(db, ref, user_id)
    file_rec = await db.get(File, file_id)

    parent_edges = await version_repo.list_parent_edges(db, file_id)
    child_edges = await version_repo.list_child_edges(db, file_id)

    neighbor_ids = {e.parent_file_id for e in parent_edges} | {e.child_file_id for e in child_edges}
    neighbors: dict[int, File] = {}
    if neighbor_ids:
        result = await db.execute(select(File).where(File.id.in_(neighbor_ids)))
        neighbors = {f.id: f for f in result.scalars().all()}

    parent_version_by_edge: dict[int, ArtifactVersion | None] = {}
    for edge in parent_edges:
        if edge.parent_version_id is not None:
            parent_version_by_edge[edge.id] = await version_repo.get_version(db, edge.parent_version_id)

    parents = []
    for edge in sorted(parent_edges, key=lambda e: e.position):
        neighbor = neighbors.get(edge.parent_file_id)
        if neighbor is None:
            continue
        version = parent_version_by_edge.get(edge.id)
        entry = _neighbor_out(neighbor, edge)
        entry["parent_version_no"] = version.version_no if version else None
        entry["models"], entry["prompts"] = await _parent_provenance(db, neighbor.id, version)
        parents.append(entry)

    children = []
    for edge in sorted(child_edges, key=lambda e: e.position):
        neighbor = neighbors.get(edge.child_file_id)
        if neighbor is None:
            continue
        children.append(_neighbor_out(neighbor, edge))

    return JSONResponse(
        {
            "file": {
                "id": str(file_rec.id),
                "schema_name": file_rec.schemaname,
                "filename": file_rec.filename,
                "file_type": file_rec.file_type,
            },
            "parents": parents,
            "children": children,
        }
    )


@router.get("/artifacts/{ref}/assists")
async def list_artifact_assists(
    ref: str,
    version_no: int | None = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Every AI-assist run recorded against an artifact, oldest first --
    the C2 provenance channel (``versioning_models.ArtifactAssist``) that
    closes GAP-4. ``version_no`` narrows to assists recorded on that one
    version; omitted, returns the whole history. Read side for C3's
    methods appendix and C4's TROUT-AI disclosure.
    """
    file_id = await file_repo.resolve_file_id(db, ref, user_id)
    assists = await assist_service.list_assists(db, file_id, version_no=version_no)
    return JSONResponse({"assists": assists})
