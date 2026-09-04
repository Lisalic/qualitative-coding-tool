"""Version/commit policy layer on top of ``repositories/version_repo.py``.

Four commit functions, not one polymorphic ``commit()`` -- the payloads
genuinely differ (a blob string, a list of code rows, or nothing at all
for coding/data) and every call site already knows statically which kind
of artifact it's writing. A single dispatching ``commit()`` would
collapse to a tagged union with an if-chain at every call site anyway;
this is the anti-speculative-abstraction reading of CLAUDE.md, not an
oversight.

**Sealing, in one rule: every commit is sealed the instant it's
created.** There is no unsealed "draft" state -- ``sealed_at`` is
always set in the same insert that creates the version, for a
job-produced artifact and for a human edit alike. Every human-edit call
site (``save_project_codebook``, ``save_coding_revision``) is reached
only from an explicit Save-button click in the UI, and each click
already batches a whole edit -- a codebook's field changes, a page of
coding-row tag/untag/note edits, accepted AI recode proposals -- into
one request. There is nothing left to coalesce: two Save clicks
two minutes apart are two deliberate decisions to persist state, and
each gets its own version. (An earlier revision of this module opened
a mutable draft that coalesced saves within a 15-minute idle window --
removed because every real call site turned out to already be a single
batched click, making the coalescing dead weight that just made
history harder to reason about.) ``pin_parent`` (the read-as-parent
seal, used before a job reads another artifact's content) still exists
and remains safe to call -- sealing an already-sealed version is a
no-op -- but has nothing to do in practice any more, since nothing this
module writes is ever left unsealed for it to find. The former
``POST /api/artifacts/{ref}/checkpoint`` route that let a user trigger
this manually has been removed for the same reason: there was never
anything left for a user-triggered checkpoint to actually do.

Every entry point takes ``now: datetime | None = None`` (defaulting to
``datetime.now(timezone.utc)``) so the commit timestamp is injectable
in tests rather than monkeypatched.

**Concurrency.** The hazard is two concurrent callers both minting
``version_no = N+1`` for the same file. ``UNIQUE(file_id, version_no)``
is the real guarantee (a genuine collision surfaces as an
``IntegrityError`` -> the caller's request fails with a 409, which is
correct); ``_lock_file`` takes a ``SELECT ... FOR UPDATE`` on the
``files`` row first so that collision essentially never happens in
practice. SQLite (the default test suite's engine) ignores ``FOR
UPDATE`` silently -- harmless for a single-threaded test run, not a bug.
No retry-on-``IntegrityError`` here: every service in this codebase owns
its own ``session.commit()``, so catching and retrying inside this
layer would silently roll back and lose whatever else the caller had
already staged on the same session.

**Codebook-snapshot compaction.** See
``versioning_models.ArtifactVersion.codes_materialized``'s docstring for
the full policy (v1 / latest-3 / every-Kth-version stay materialized;
everything else is compacted to a field-level delta via
``core/codebook_delta.py``). ``_demote_if_eligible`` is the only piece of
that policy that lives here rather than on the model: it runs once per
commit (O(1), never a sweep) and is called from both
``commit_codebook_version`` and ``commit_coding_version``, since a commit
from either can advance the head far enough to age an older version out
of the retained window.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.codebook_delta import apply_delta, encode_delta
from backend.app.core.codebook_diff import CodebookDiff, diff_codes
from backend.app.core.codebook_render import CodeRow, render_codes_to_markdown
from backend.app.core.coding_diff import CodingDiff, diff_coding_entries
from backend.app.core.data_diff import DataDiff, diff_row_ids
from backend.app.core.exceptions import NotFoundError
from backend.app.database import File
from backend.app.repositories import coding_repo, file_repo, raw_data_repo, version_repo
from backend.app.versioning_models import (
    RELATION_FORKED_FROM,
    ROLE_FORK_ORIGIN,
    ArtifactVersion,
    CodebookCode,
)

# See ArtifactVersion.codes_materialized's docstring for what these gate.
KEYFRAME_INTERVAL = 10
LATEST_MATERIALIZED_WINDOW = 3


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(timezone.utc)


@dataclass(frozen=True)
class EdgeSpec:
    """One parent link to create alongside a new version. See
    ``versioning_models.py`` for the ``RELATION_*``/``ROLE_*`` constants.
    """

    parent_file_id: int
    relation: str
    role: str
    position: int = 0


def _blob_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def prompt_meta(rendered: str | None, *, batches: int | None = None) -> dict | None:
    """Reduce a rendered LLM prompt to the provenance worth keeping.

    The rendered prompt embeds the whole batch of sampled submission/
    comment text, which the artifact already owns in ``submissions``/
    ``comments`` -- see ``versioning_models.ArtifactVersion`` for what
    storing it cost. Keep a length and a hash so "this version came from
    that input" stays falsifiable, and drop the payload.

    For the filter and apply pipelines the scripts return only the LAST
    batch's prompt, so these numbers describe that batch; ``batches``
    records how many there were.
    """
    if not rendered:
        return None
    meta: dict = {
        "rendered_chars": len(rendered),
        "rendered_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
    }
    if batches is not None:
        meta["batches"] = batches
    return meta


def _codes_hash(codes: Sequence[CodeRow]) -> str:
    """Hash the canonical ROW serialization, never rendered markdown --
    the renderer is allowed to change independently and would otherwise
    spuriously invalidate every existing hash. Order is NOT sorted:
    ``position`` is content (a pure reorder is a real, diffable change),
    so the hash must be sensitive to it.
    """
    payload = json.dumps(
        [
            [
                c["position"], c["code_uid"], c["family_uid"], c["family_name"], c["name"], c["body"],
                c.get("definition"), c.get("inclusion"), c.get("exclusion"), c.get("keywords"), c.get("example"),
            ]
            for c in codes
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _lock_file(session: AsyncSession, file_id: int) -> None:
    """``SELECT ... FOR UPDATE`` on the ``files`` row, serializing
    concurrent version-minting for this file. SQLite ignores ``FOR
    UPDATE`` (no row locking support) -- harmless under the
    single-threaded default test suite, real under Postgres.
    """
    await session.execute(select(File.id).where(File.id == file_id).with_for_update())


async def _next_version(
    session: AsyncSession,
    file_id: int,
    *,
    author_user_id: int | None,
    origin: str,
    job_id: int | None,
    model: str | None,
    system_prompt: str | None,
    user_instructions: str | None,
    prompt_meta: dict | None,
    now: datetime,
) -> ArtifactVersion:
    """Create and immediately seal the next version for ``file_id`` --
    see the module docstring for why there is no unsealed-draft state to
    open or reuse here any more.
    """
    await _lock_file(session, file_id)
    head = await version_repo.head_version(session, file_id)
    next_no = (head.version_no + 1) if head is not None else 1
    return await version_repo.create_version(
        session,
        file_id=file_id,
        version_no=next_no,
        parent_version_id=head.id if head is not None else None,
        author_user_id=author_user_id,
        origin=origin,
        job_id=job_id,
        model=model,
        system_prompt=system_prompt,
        user_instructions=user_instructions,
        prompt_meta=prompt_meta,
        sealed_at=now,
    )


async def _demote_if_eligible(session: AsyncSession, file_id: int, head_version_no: int) -> None:
    """After a commit makes ``head_version_no`` the head, exactly one
    version can have newly aged out of the retained window: the one at
    ``head_version_no - LATEST_MATERIALIZED_WINDOW``. Check only that one
    -- O(1) per commit, never a sweep over history.

    If it's eligible (not v1, not a keyframe, and still materialized --
    a row-only edit that was never materialized has nothing to demote),
    compute its delta directly against its own nearest still-materialized
    ancestor using its own current rows (read before they're deleted),
    store that as ``codes_delta``, and delete the row set. See
    ``ArtifactVersion.codes_materialized``'s docstring for why this is a
    single direct delta from the anchor rather than a step in a
    consecutive chain.
    """
    candidate_no = head_version_no - LATEST_MATERIALIZED_WINDOW
    if candidate_no <= 1 or candidate_no % KEYFRAME_INTERVAL == 0:
        return

    candidate = await version_repo.get_version_by_no(session, file_id, candidate_no)
    if candidate is None or not candidate.codes_materialized:
        return

    anchor = await version_repo.latest_materialized_version(session, file_id, at_or_before=candidate_no - 1)
    if anchor is None:
        return

    anchor_codes = await version_repo.list_codes(session, anchor.id)
    candidate_codes = await version_repo.list_codes(session, candidate.id)
    candidate.codes_delta = encode_delta(anchor_codes, candidate_codes)
    candidate.codes_materialized = False
    await version_repo.delete_codes(session, candidate.id)


async def link_parents(session: AsyncSession, child_file_id: int, parents: Sequence[EdgeSpec]) -> None:
    """Write one ``artifact_edges`` row per parent spec.

    A parent that no longer exists is **skipped**, not written. Every
    caller here is a long-running job that read its parents minutes
    earlier (an LLM round trip ago), so a parent can be deleted inside
    that window; writing the edge anyway put a ``parent_file_id`` with
    no ``files`` row into the table, which Postgres rejects at COMMIT --
    rolling back the whole finished artifact, LLM output included --
    while SQLite (FKs off in tests) silently stored the dangling edge.
    Lineage is metadata about content, so losing an edge must never
    corrupt or discard the content itself; the artifact is written, one
    edge lighter. Handlers that *copy rows out of* a parent (apply
    codebook, filter) have a stricter requirement and check the parent
    themselves before getting here -- see
    ``file_repo.require_existing_file_ids``.
    """
    if not parents:
        return
    existing = await file_repo.existing_file_ids(session, {s.parent_file_id for s in parents})
    for spec in parents:
        if spec.parent_file_id not in existing:
            continue
        parent_head = await version_repo.head_version(session, spec.parent_file_id)
        await version_repo.add_edge(
            session,
            child_file_id=child_file_id,
            parent_file_id=spec.parent_file_id,
            parent_version_id=parent_head.id if parent_head is not None else None,
            relation=spec.relation,
            role=spec.role,
            position=spec.position,
        )


# ---------------------------------------------------------------------------
# commit_*
# ---------------------------------------------------------------------------


async def commit_blob_version(
    session: AsyncSession,
    *,
    file_id: int,
    author_user_id: int | None,
    origin: str,
    content: str,
    message: str | None = None,
    job_id: int | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    user_instructions: str | None = None,
    prompt_meta: dict | None = None,
    parents: Sequence[EdgeSpec] = (),
    now: datetime | None = None,
) -> ArtifactVersion:
    """Commit for blob-storage artifacts (summary, the comparison
    types). No-op suppression: if the incoming content hashes the same
    as the current head, the existing head is returned untouched (a
    legacy version migrated with ``content_hash=NULL`` never matches, so
    the first save after the version-spine cutover always creates a new
    version -- documented, harmless behavior).
    """
    now = _now(now)
    content_hash = _blob_hash(content)

    head = await version_repo.head_version(session, file_id)
    if head is not None and head.content_hash == content_hash:
        return head

    version = await _next_version(
        session, file_id, author_user_id=author_user_id, origin=origin, job_id=job_id,
        model=model, system_prompt=system_prompt,
        user_instructions=user_instructions, prompt_meta=prompt_meta, now=now,
    )
    version.content = content
    version.content_hash = content_hash
    if message is not None:
        version.message = message
    await session.flush()

    if parents:
        await link_parents(session, file_id, parents)

    return version


async def commit_codebook_version(
    session: AsyncSession,
    *,
    file_id: int,
    author_user_id: int | None,
    origin: str,
    codes: Sequence[CodeRow],
    message: str | None = None,
    job_id: int | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    user_instructions: str | None = None,
    prompt_meta: dict | None = None,
    parents: Sequence[EdgeSpec] = (),
    now: datetime | None = None,
) -> ArtifactVersion:
    """Commit for codebook-shaped artifacts: a real ``codebook`` file, or
    a ``coding`` file's own codebook snapshot. Same no-op suppression as
    ``commit_blob_version``, hashed over the canonical row serialization.

    Always fully materialized (its content is already fully known --
    there's nothing to defer). Also runs the once-per-commit compaction
    check (``_demote_if_eligible``): a real codebook edit can just as
    easily age an older version out of the retained window as a coding
    row-only save can -- see ``ArtifactVersion.codes_materialized``'s
    docstring.
    """
    now = _now(now)
    codes = list(codes)
    content_hash = _codes_hash(codes)

    head = await version_repo.head_version(session, file_id)
    if head is not None and head.content_hash == content_hash:
        return head

    version = await _next_version(
        session, file_id, author_user_id=author_user_id, origin=origin, job_id=job_id,
        model=model, system_prompt=system_prompt,
        user_instructions=user_instructions, prompt_meta=prompt_meta, now=now,
    )
    await version_repo.replace_codes(session, version.id, codes)
    version.content_hash = content_hash
    if message is not None:
        version.message = message
    await session.flush()

    if parents:
        await link_parents(session, file_id, parents)

    await _demote_if_eligible(session, file_id, version.version_no)

    return version


async def commit_coding_version(
    session: AsyncSession,
    *,
    file_id: int,
    author_user_id: int | None,
    origin: str,
    message: str | None = None,
    job_id: int | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    user_instructions: str | None = None,
    prompt_meta: dict | None = None,
    now: datetime | None = None,
) -> ArtifactVersion:
    """Commit for a coding artifact's classification. Takes no
    classification content -- it allocates (or reuses) a version number
    and returns it; the caller then stamps the ``coding_entries`` rows it
    writes with ``valid_from = version.version_no`` (see
    ``coding_repo.py``). This asymmetry with the other two ``commit_*``
    functions is real, not an oversight: coding content is a range
    table, not a per-version snapshot, so there is nothing here to hash
    or store as ``content`` on the version row. ``system_prompt``/
    ``user_instructions``/``prompt_meta`` are still accepted and stored,
    though -- they're provenance metadata about how this version was
    produced, not classification payload.

    A coding file's ``codebook_codes`` and ``coding_entries`` share ONE
    version-number sequence (the SCD-2 ranges are keyed against it), so
    this version must resolve to the SAME codes as whatever preceded it
    -- otherwise a plain row-only edit via ``save_coding_revision`` (a
    save with no codebook change) would leave the coding
    artifact's own codebook snapshot reading as empty from that point
    on. It does NOT do this by copying the rows (that was the earlier
    approach, and it made every single row-only save materialize a
    byte-identical ~44 kB snapshot -- see
    ``versioning_models.ArtifactVersion``'s ``codes_materialized``
    docstring for the numbers). Instead the version is born
    unmaterialized when there's a previous head to inherit from, and
    ``read_codes`` resolves it by looking up the nearest materialized
    ancestor. There is always one: a coding file's v1 is always created
    via ``commit_codebook_version`` (born materialized), never this
    function, so ``previous_head is None`` here in practice never
    happens on a real coding artifact -- the check exists only as a
    defensive fallback, not because it fires.

    The one exception: a row-only edit whose ``version_no`` lands
    exactly on a keyframe boundary (``KEYFRAME_INTERVAL``) is force-
    materialized anyway -- its already-resolved current codes are copied
    in via ``read_codes``/``replace_codes`` -- so the keyframe schedule
    stays unconditional regardless of what kind of edit happens to land
    on it. Also runs the once-per-commit compaction check.
    """
    now = _now(now)
    previous_head = await version_repo.head_version(session, file_id)
    version = await _next_version(
        session, file_id, author_user_id=author_user_id, origin=origin, job_id=job_id,
        model=model, system_prompt=system_prompt,
        user_instructions=user_instructions, prompt_meta=prompt_meta, now=now,
    )
    is_keyframe = version.version_no % KEYFRAME_INTERVAL == 0
    if previous_head is None:
        version.codes_materialized = True
    elif is_keyframe:
        current_codes = await read_codes(session, file_id, version_no=previous_head.version_no)
        rows = [
            {
                "code_uid": c.code_uid, "family_uid": c.family_uid, "family_name": c.family_name,
                "name": c.name, "body": c.body, "definition": c.definition, "inclusion": c.inclusion,
                "exclusion": c.exclusion, "keywords": c.keywords, "example": c.example, "position": c.position,
            }
            for c in current_codes
        ]
        await version_repo.replace_codes(session, version.id, rows)
        version.codes_materialized = True
    else:
        version.codes_materialized = False
    if message is not None:
        version.message = message
    await session.flush()

    await _demote_if_eligible(session, file_id, version.version_no)

    return version


async def commit_data_version(
    session: AsyncSession,
    *,
    file_id: int,
    author_user_id: int | None,
    origin: str,
    message: str | None = None,
    job_id: int | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    user_instructions: str | None = None,
    prompt_meta: dict | None = None,
    parents: Sequence[EdgeSpec] = (),
    now: datetime | None = None,
) -> ArtifactVersion:
    """Commit for a ``raw_data``/``filtered_data`` artifact's rows.
    Shaped like ``commit_coding_version``: it allocates the next version
    number and returns it; the caller stamps the ``submissions``/
    ``comments`` rows it writes with ``valid_from``/``valid_to =
    version.version_no`` (see ``repositories/raw_data_repo.py``). There
    is no ``content``/``codes`` payload here at all -- a data file's rows
    are a range table, not a per-version snapshot, exactly like
    ``coding_entries`` (see that function's docstring for the same
    asymmetry).

    Deliberately no ``content_hash`` and therefore **no no-op
    suppression**: hashing a potentially enormous row set on every
    mutation isn't worth it. Instead every caller is expected to only
    call this when a mutation actually changed something (e.g. a
    delete/move with a non-zero affected-row count) -- an empty-result
    caller should skip the commit entirely rather than relying on this
    function to detect the no-op.
    """
    now = _now(now)
    version = await _next_version(
        session, file_id, author_user_id=author_user_id, origin=origin, job_id=job_id,
        model=model, system_prompt=system_prompt,
        user_instructions=user_instructions, prompt_meta=prompt_meta, now=now,
    )
    if message is not None:
        version.message = message
    await session.flush()

    if parents:
        await link_parents(session, file_id, parents)

    return version


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def read_blob(session: AsyncSession, file_id: int, *, version_no: int | None = None) -> str | None:
    version = (
        await version_repo.get_version_by_no(session, file_id, version_no)
        if version_no is not None
        else await version_repo.head_version(session, file_id)
    )
    return version.content if version is not None else None


async def read_codes(session: AsyncSession, file_id: int, *, version_no: int | None = None) -> list[CodebookCode]:
    """The code rows for one version. If the version itself isn't
    materialized, resolves it against its nearest materialized ancestor
    -- one extra indexed lookup, plus (only for a compacted version that
    actually has a stored ``codes_delta``) one delta application. A
    row-only edit that was never materialized has no delta to apply at
    all (its codes are identical to its ancestor's by construction), so
    that case is a pure lookup, nothing more. See
    ``ArtifactVersion.codes_materialized``'s docstring.
    """
    version = (
        await version_repo.get_version_by_no(session, file_id, version_no)
        if version_no is not None
        else await version_repo.head_version(session, file_id)
    )
    if version is None:
        return []
    if version.codes_materialized:
        return await version_repo.list_codes(session, version.id)

    anchor = await version_repo.latest_materialized_version(session, file_id, at_or_before=version.version_no)
    if anchor is None:
        return []
    anchor_codes = await version_repo.list_codes(session, anchor.id)
    if not version.codes_delta:
        return anchor_codes

    reconstructed = apply_delta(anchor_codes, version.codes_delta)
    # Detached, unflushed CodebookCode instances -- never session.add()ed
    # -- so a reconstruction can never be mistaken for a real row by a
    # later flush. Every caller reads content fields only (code_uid,
    # name, ...), never .version_id, so stamping it with the REQUESTED
    # version's id here (not the anchor's) is for correctness/clarity,
    # not because anything currently depends on it.
    return [CodebookCode(version_id=version.id, **row) for row in reconstructed]


async def read_codebook_markdown(session: AsyncSession, file_id: int, *, version_no: int | None = None) -> str:
    codes = await read_codes(session, file_id, version_no=version_no)
    rows: list[CodeRow] = [
        {
            "code_uid": c.code_uid, "family_uid": c.family_uid, "family_name": c.family_name,
            "name": c.name, "body": c.body, "definition": c.definition, "inclusion": c.inclusion,
            "exclusion": c.exclusion, "keywords": c.keywords, "example": c.example, "position": c.position,
        }
        for c in codes
    ]
    return render_codes_to_markdown(rows)


async def list_history(session: AsyncSession, file_id: int) -> list[ArtifactVersion]:
    return await version_repo.list_versions(session, file_id)


async def pin_parent(session: AsyncSession, parent_file_id: int, *, now: datetime | None = None) -> ArtifactVersion:
    """Seal ``parent_file_id``'s head (if it's an open draft) and return
    it -- the read-as-parent seal trigger. Nothing may pin a mutable
    version: this is the only sanctioned way another artifact's content
    read becomes a ``parent_version_id``.
    """
    now = _now(now)
    head = await version_repo.head_version(session, parent_file_id)
    if head is None:
        raise NotFoundError(f"No version history for file_id={parent_file_id}")
    if head.sealed_at is None:
        await version_repo.seal(session, head, at=now)
    return head


async def diff_codebook(session: AsyncSession, file_id: int, *, from_no: int, to_no: int) -> CodebookDiff:
    from_codes = await read_codes(session, file_id, version_no=from_no)
    to_codes = await read_codes(session, file_id, version_no=to_no)
    return diff_codes(from_codes, to_codes)


async def diff_coding(session: AsyncSession, file_id: int, *, from_no: int, to_no: int) -> CodingDiff:
    """Content diff between two versions of a coding artifact's own
    ``coding_entries`` -- rows recoded, code counts changed -- as
    distinct from ``diff_codebook``'s structural codebook diff. Only
    meaningful for a ``coding`` file; the route only calls this when
    ``file_type == "coding"`` (a codebook or codebook_comparison file has
    no ``coding_entries`` at all, so this would just report an empty
    diff for one, not error).
    """
    from_entries = await coding_repo.entries_as_of(session, file_id, from_no)
    to_entries = await coding_repo.entries_as_of(session, file_id, to_no)
    return diff_coding_entries(from_entries, to_entries)


async def diff_data(session: AsyncSession, file_id: int, *, from_no: int, to_no: int) -> DataDiff:
    """Content diff between two versions of a ``raw_data``/
    ``filtered_data`` artifact's own ``submissions``/``comments`` rows --
    rows added/removed -- as distinct from ``diff_codebook``'s structural
    codebook diff (meaningless for a file with no codebook) and
    ``diff_coding``'s classification diff (meaningless for a file with
    no ``coding_entries``). Only meaningful for ``raw_data``/
    ``filtered_data``; the route only calls this for those two types.
    """
    from_sub_ids = await raw_data_repo.row_ids_as_of(session, file_id, version_no=from_no, table="submissions")
    to_sub_ids = await raw_data_repo.row_ids_as_of(session, file_id, version_no=to_no, table="submissions")
    from_com_ids = await raw_data_repo.row_ids_as_of(session, file_id, version_no=from_no, table="comments")
    to_com_ids = await raw_data_repo.row_ids_as_of(session, file_id, version_no=to_no, table="comments")
    return diff_row_ids(
        from_submission_ids=from_sub_ids, to_submission_ids=to_sub_ids,
        from_comment_ids=from_com_ids, to_comment_ids=to_com_ids,
    )


# ---------------------------------------------------------------------------
# fork_lineage -- replaces coding_service._clone_file_dependencies
# ---------------------------------------------------------------------------


async def fork_lineage(session: AsyncSession, *, source_file_id: int, target_file_id: int, user_id: int) -> None:
    """Copy ``source_file_id``'s parent edges onto ``target_file_id``
    verbatim (relation/role/position/parent_version_id all preserved),
    then add the one true fork edge (``target -> source``) unless a copy
    already produced an edge to the same parent under the same role.

    Two deliberate behavior changes from the ``FileDependency``-era
    ``_clone_file_dependencies``: the per-parent ownership check is one
    ``file_repo.filter_owned_ids`` call instead of an N+1 ``SELECT File``
    per parent, and the dedup key is ``(parent_file_id, role)`` rather
    than bare ``parent_file_id`` -- the old key would collapse two edges
    to the same parent, which under typed edges would silently destroy a
    self-comparison's ``side_a``/``side_b`` pair.
    """
    edges = await version_repo.list_parent_edges(session, source_file_id)
    owned = await file_repo.filter_owned_ids(session, {e.parent_file_id for e in edges}, user_id)

    seen: set[tuple[int, str]] = set()
    for edge in edges:
        key = (edge.parent_file_id, edge.role)
        if edge.parent_file_id not in owned or key in seen:
            continue
        await version_repo.add_edge(
            session,
            child_file_id=target_file_id,
            parent_file_id=edge.parent_file_id,
            parent_version_id=edge.parent_version_id,
            relation=edge.relation,
            role=edge.role,
            position=edge.position,
        )
        seen.add(key)

    if not any(pid == source_file_id for pid, _role in seen):
        head = await version_repo.head_version(session, source_file_id)
        await version_repo.add_edge(
            session,
            child_file_id=target_file_id,
            parent_file_id=source_file_id,
            parent_version_id=head.id if head is not None else None,
            relation=RELATION_FORKED_FROM,
            role=ROLE_FORK_ORIGIN,
            position=0,
        )
