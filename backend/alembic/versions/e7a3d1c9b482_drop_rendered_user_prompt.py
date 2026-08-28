"""drop the rendered user_prompt; keep instructions + prompt metadata

Revision ID: e7a3d1c9b482
Revises: d4f97a2c6e1b
Create Date: 2026-08-27 00:00:00.000001

``artifact_versions.user_prompt`` stored the *fully rendered* LLM input
-- which embeds the entire batch of sampled submission/comment text that
the same artifact already owns in ``submissions``/``comments``. Measured
on a real database before this change: 61 rows, **119 MB on disk**, of
which ``user_prompt`` was 213 MB logical (99.94%); ``system_prompt`` was
32 kB and ``content`` 68 kB. Per file_type the average rendered prompt
was 4.5-7.2 MB, worst case 13 MB.

It was also worse than a storage problem. 107 MB of it (every
``filtered_data`` version) is write-only -- no route and no frontend file
has ever serialized a filtered_data version's prompts. The rest was
being shipped in the JSON body of *every* ``GET /api/coding/{ref}`` and
``GET /api/codebook`` response, on every ViewCoding/ViewCodebook mount,
to populate a 160px-tall scroll box.

What replaces it:

- ``user_instructions`` -- only the human-authored fragment (the generate
  prompt, the apply methodology, the filter criteria). Tens to hundreds
  of bytes, and the only part anyone would want to read back.
- ``prompt_meta`` (JSON) -- ``{"rendered_chars", "rendered_sha256",
  "batches"}``, so "this version came from that input" stays falsifiable
  without keeping the payload. For the filter and apply pipelines the
  scripts only ever returned the LAST batch's prompt, so those two
  numbers describe that batch; ``batches`` says how many there were.
  (The old column had exactly the same limitation, silently.)

Full generation parameters -- source file, sample percentage, content
scope, model, the user's prompt -- are already persisted secret-free in
``jobs.payload``, reachable from ``artifact_versions.job_id``. No new
columns are needed for those.

Existing rows are **not** backfilled: the user-authored fragment is not
separably recoverable from a concatenated multi-megabyte string, and
CLAUDE.md rules out migration scripts for existing rows. They end with
``user_instructions = NULL``, which is already exactly what the codebook
*edit* path produces today (``codebook_service.save_codebook`` passes no
prompts at all), so the UI already handles that state.

**Operator note -- reclaiming the disk.** ``DROP COLUMN`` in Postgres is
metadata-only; it does not free the TOAST chunks. The ``UPDATE ... SET
NULL`` below detoasts them first so ordinary autovacuum can reclaim the
space within minutes. To get it back immediately, run this once *after*
the upgrade -- it cannot live inside the migration, because Alembic runs
in a transaction and ``VACUUM`` cannot::

    psql "$DATABASE_URL" -c 'VACUUM (FULL, ANALYZE) artifact_versions;'

The heap is only ~48 kB, so that rewrite is effectively instantaneous.

Downgrade recreates ``user_prompt`` structurally (empty). The rendered
prompt is not reconstructible -- it was a function of the sampled rows,
the model, and the batch boundaries at generation time -- and that is the
whole point of dropping it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7a3d1c9b482"
down_revision: Union[str, Sequence[str], None] = "d4f97a2c6e1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("artifact_versions", sa.Column("user_instructions", sa.Text(), nullable=True))
    op.add_column("artifact_versions", sa.Column("prompt_meta", sa.JSON(), nullable=True))
    # Detoast before dropping so the space becomes reclaimable by
    # autovacuum -- see the operator note above.
    op.execute("UPDATE artifact_versions SET user_prompt = NULL")
    op.drop_column("artifact_versions", "user_prompt")


def downgrade() -> None:
    op.add_column("artifact_versions", sa.Column("user_prompt", sa.Text(), nullable=True))
    op.drop_column("artifact_versions", "prompt_meta")
    op.drop_column("artifact_versions", "user_instructions")
