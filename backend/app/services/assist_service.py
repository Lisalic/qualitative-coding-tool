"""Record and read AI-assist provenance (``artifact_assists``) -- the C2
avenue in
``documentation/research/qualitative-coding-landscape-and-expansion.md``,
closing GAP-4.

**Trust boundary.** A caller (the filter/codebook/coding editors) tells
this module only what it decided: which ``job_id`` an assistant run came
from, and how many proposals it accepted/dismissed. Every provenance
fact that matters for an audit -- the model, the rendered system prompt,
the human-authored instructions, ``prompt_meta`` -- is read from the
referenced ``jobs`` row itself (``payload``/``result``, populated by the
``filter_preview``/``codebook_preview``/``recode_items``/
``integrate_codebook_preview`` handlers), never from the client. This
is the same reasoning
``coding_service.start_recode_items_job`` already applies to a job's
API key: the thing worth trusting is what the server actually ran, not
what a request claims it ran.

A run is rejected outright (``ValidationAppError``) rather than silently
downgraded if it doesn't check out -- fail loudly, per CLAUDE.md -- so a
malformed or mismatched ``job_id`` never gets recorded as if it were
real assist provenance.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationAppError
from backend.app.jobs import service as jobs_service
from backend.app.repositories import assist_repo
from backend.app.versioning_models import (
    ASSIST_STAGE_CODEBOOK,
    ASSIST_STAGE_CODING,
    ASSIST_STAGE_FILTER,
    ASSIST_STAGE_INTEGRATE,
    ArtifactAssist,
)

# Which job_type a run must reference for each stage, and how to find the
# artifact it was run against inside that job's own payload.
_JOB_TYPE_BY_STAGE = {
    ASSIST_STAGE_FILTER: "filter_preview",
    ASSIST_STAGE_CODEBOOK: "codebook_preview",
    ASSIST_STAGE_CODING: "recode_items",
    ASSIST_STAGE_INTEGRATE: "integrate_codebook_preview",
}


async def _validated_job(
    session: AsyncSession,
    *,
    user_id: int,
    stage: str,
    job_id: int,
    source_file_id: int | None,
    source_file_ids: Sequence[int] | None,
    file_id: int,
):
    expected_type = _JOB_TYPE_BY_STAGE.get(stage)
    if expected_type is None:
        raise ValidationAppError(f"Unknown assist stage: {stage!r}")

    # get_job raises NotFoundError/ForbiddenError -- a job that doesn't
    # exist, or exists but belongs to someone else, is exactly as invalid
    # as one that ran against the wrong artifact.
    job = await jobs_service.get_job(session, job_id, user_id)

    if job.job_type != expected_type:
        raise ValidationAppError(
            f"Job {job_id} is a {job.job_type!r} job, not {expected_type!r} -- cannot record it as a {stage} assist"
        )
    if job.status != "succeeded":
        raise ValidationAppError(f"Job {job_id} has not succeeded (status={job.status!r})")

    payload = job.payload or {}
    if stage == ASSIST_STAGE_CODING:
        if payload.get("coding_file_id") != file_id:
            raise ValidationAppError(f"Job {job_id} was not run against this coding artifact")
    elif stage == ASSIST_STAGE_INTEGRATE:
        # Set equality, not containment: a submit must not be able to
        # claim a run that covered a DIFFERENT, larger set of source
        # codebooks than the ones actually being integrated here --
        # that would be exactly the false-provenance claim this module
        # exists to refuse. Sets (not ordered lists) because merge
        # inputs are unordered by construction, unlike compare's
        # load-bearing side_a/side_b; artifact_edges.position is a
        # display ordering only.
        if not source_file_ids or set(payload.get("source_file_ids") or []) != set(source_file_ids):
            raise ValidationAppError(f"Job {job_id} was not run against these source codebooks")
    else:
        if source_file_id is None or payload.get("source_file_id") != source_file_id:
            raise ValidationAppError(f"Job {job_id} was not run against this artifact's source data")

    return job


async def record_assist_runs(
    session: AsyncSession,
    *,
    user_id: int,
    file_id: int,
    version_id: int,
    stage: str,
    source_file_id: int | None = None,
    source_file_ids: Sequence[int] | None = None,
    runs: list[dict[str, Any]],
) -> list[ArtifactAssist]:
    """Persist one ``ArtifactAssist`` row per entry in ``runs``.

    Each ``run`` dict is ``{"job_id", "proposed_count"?, "accepted_count"?,
    "dismissed_count"?, "accepted_refs"?}`` -- the editor's own
    accept/dismiss bookkeeping (``filterEditorState.js``'s ``aiDecided``,
    ``codebookEditorState.js``'s ``aiAccepted``/``dismissed``,
    ``useViewCodingPage.js``'s ``aiProposedItemIds``). ``model``/
    ``system_prompt``/``user_instructions``/``prompt_meta`` are never
    read from ``run`` -- see the module docstring.

    Does not commit; the caller's existing ``session.commit()`` (already
    reached from ``create_manual_filtered_data``/``create_manual_codebook``/
    ``create_integrated_codebook``/``save_coding_revision``) covers this too.
    """
    if not runs:
        return []

    created: list[ArtifactAssist] = []
    for run in runs:
        job_id = run.get("job_id")
        if not job_id:
            raise ValidationAppError("An assist run is missing job_id")
        job = await _validated_job(
            session,
            user_id=user_id,
            stage=stage,
            job_id=job_id,
            source_file_id=source_file_id,
            source_file_ids=source_file_ids,
            file_id=file_id,
        )
        result = job.result or {}
        payload = job.payload or {}
        assist = await assist_repo.insert_assist(
            session,
            file_id=file_id,
            version_id=version_id,
            stage=stage,
            job_id=job.id,
            model=payload.get("model"),
            system_prompt=result.get("system_prompt"),
            user_instructions=result.get("user_instructions"),
            prompt_meta=result.get("prompt_meta"),
            proposed_count=int(run.get("proposed_count") or 0),
            accepted_count=int(run.get("accepted_count") or 0),
            dismissed_count=int(run.get("dismissed_count") or 0),
            accepted_refs=run.get("accepted_refs") or None,
        )
        created.append(assist)
    return created


async def resolve_ai_coder_model(session: AsyncSession, *, user_id: int, file_id: int, job_id: int | None) -> str | None:
    """Validate that ``job_id`` is a ``recode_items`` job that ran
    against coding artifact ``file_id``, and return the model it used --
    B1's per-entry counterpart to :func:`record_assist_runs`, called once
    per distinct ``assist_job_id`` a save's row entries claim
    ``coder="ai"`` under (see ``coding_service.save_coding_revision``).

    Raises ``ValidationAppError`` if ``job_id`` is missing or doesn't
    check out -- an entry cannot claim AI authorship without a real job
    to back it.
    """
    if not job_id:
        raise ValidationAppError("coder='ai' entry is missing assist_job_id")
    job = await _validated_job(
        session,
        user_id=user_id,
        stage=ASSIST_STAGE_CODING,
        job_id=job_id,
        source_file_id=None,
        source_file_ids=None,
        file_id=file_id,
    )
    payload = job.payload or {}
    return payload.get("model")


def _assist_out(assist: ArtifactAssist, version_no: int) -> dict:
    return {
        "version_no": version_no,
        "stage": assist.stage,
        "job_id": assist.job_id,
        "model": assist.model,
        "system_prompt": assist.system_prompt,
        "user_instructions": assist.user_instructions,
        "prompt_meta": assist.prompt_meta,
        "proposed_count": assist.proposed_count,
        "accepted_count": assist.accepted_count,
        "dismissed_count": assist.dismissed_count,
        "accepted_refs": assist.accepted_refs,
        "created_at": assist.created_at.isoformat() if assist.created_at else None,
    }


async def list_assists(session: AsyncSession, file_id: int, *, version_no: int | None = None) -> list[dict]:
    """Every assist run recorded against ``file_id``, oldest first --
    the read side of C3's methods appendix and C4's TROUT-AI disclosure.
    """
    rows = await assist_repo.list_for_file(session, file_id, version_no=version_no)
    return [_assist_out(assist, v_no) for assist, v_no in rows]
