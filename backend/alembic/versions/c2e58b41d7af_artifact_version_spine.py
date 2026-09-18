"""artifact version spine (additive half)

Revision ID: c2e58b41d7af
Revises: 9a1c3e7f5b2d
Create Date: 2026-08-26 00:00:00.000000

First of two revisions that replace ``file_dependencies`` (a single
untyped edge table conflating "artifact B was derived from artifact A"
with "artifact A's content changed", unable to say which parent played
which role, in what order, or from which revision -- see
``coding_service.py::_clone_file_dependencies``'s grandparent-copying
hack) and the one-row-per-file ``artifact_content`` blob (every save was
a destructive overwrite) with a git-shaped model: ``artifact_versions``
(commits), ``artifact_edges`` (typed, ordered, version-pinned derivation),
and ``codebook_codes`` (one row per code, materialized per codebook
version, keyed by a stable ``code_uid`` so a rename is recorded rather
than inferred from a name-similarity heuristic). See
``backend/app/versioning_models.py`` for the full model docstrings.

**Why this is split into two revisions with a script in between, rather
than the single revision most of this project's other migrations use.**
Turning existing local codebooks into ``codebook_codes`` rows means
parsing their ``artifact_content`` blobs and minting fresh ``code_uid``
values; turning existing ``coding_entries.code`` name strings into stable
``code_uid`` references means matching them against those freshly-minted
codes. That parsing/matching is real, non-trivial application logic
(``display_codebook.py::parse_codebook_to_json`` plus name-matching), and
running it as one-off Python is a far better fit for a standalone,
re-runnable, ``--dry-run``-capable script than for DDL frozen into a
migration file forever (the classic "don't pin a revision to today's
parser" anti-pattern) -- hence
``backend/scripts/backfill_codebook_codes.py``. But that script needs
somewhere to WRITE its output, and it needs to still be able to READ the
old ``artifact_content``/``coding_entries.code`` data it's migrating
FROM. A single revision that both creates the new tables AND drops the
old ones would destroy the second requirement before the script ever
runs. So:

  1. THIS revision (``c2e58b41d7af``) only adds -- new tables, new
     nullable ``coding_entries`` columns -- and does the parts of the
     migration that are pure structural transformation with no identity
     to invent: existing ``file_dependencies`` rows become
     ``artifact_edges`` (role inferred from the parent's ``file_type``,
     which is exact, not heuristic, for every case -- see below);
     existing ``summary``/``comparison``/``codebook_comparison``/
     ``coding_comparison`` blobs move verbatim into
     ``artifact_versions.content`` (same bytes, new home, no parsing
     involved); every ``raw_data``/``filtered_data`` file gets an empty
     v1 version (closes the gap where the app's single most common edge,
     ``filtered_data -> raw_data``, would otherwise have no
     ``parent_version_id`` to pin).
  2. The operator runs ``backend/scripts/backfill_codebook_codes.py``
     (dry-run first), which parses ``codebook``/``coding`` artifact
     content into ``codebook_codes`` rows and backfills
     ``coding_entries.code_uid`` by name-match, reporting (never
     silently dropping) anything it can't resolve.
  3. ``d4f97a2c6e1b`` (the next revision) finalizes the cutover: makes
     ``coding_entries.code_uid``/``valid_from`` ``NOT NULL``, and drops
     ``file_dependencies``, ``artifact_content``, and
     ``files.systemprompt``/``userprompt``.

A database with no real codebook/coding content to preserve (a fresh
install, most CI runs) can skip step 2 entirely -- step 3's ``NOT NULL``
will simply apply to zero rows.

**Role inference for the ``file_dependencies -> artifact_edges`` DML is
exact, not a heuristic**, because of how ``_clone_file_dependencies``
(the only place a ``coding -> coding`` edge was ever written) actually
worked: it never linked a fork to another CODING file except the fork's
own source, and always copied the source's OWN data/codebook parents
(never another coding file) alongside that one link. So:

  - parent.file_type IN ('raw_data','filtered_data') -> ``derived_from``/``source_data``
  - parent.file_type IN ('codebook','codebook_comparison') AND child.file_type = 'coding' -> ``derived_from``/``codebook``
  - parent.file_type = 'coding' AND child.file_type = 'coding' -> ``forked_from``/``fork_origin`` (the ONLY way this combination was ever produced)
  - child.file_type IN ('codebook_comparison','coding_comparison') -> ``compared``, ``position`` = row order by the old dependency's own ``id`` (insertion order was always A-then-B)
  - child.file_type = 'summary' -> ``derived_from``/``source_data``
  - child.file_type = 'raw_data' with >1 parent (a merge) -> ``merged_from``/``merge_input``, ``position`` = row order by ``id``
  - a plain client-supplied comparison/summary (``content_service.save_comparison``/``save_summary``, ``file_type`` possibly ``'comparison'`` or NULL) -> ``compared`` if it has >1 parent, else ``derived_from``/``source_data``

``parent_version_id`` on these migrated edges is populated when the
parent already has a v1 by this point (raw_data/filtered_data/blob
types); it's left NULL for codebook/coding parents, since those don't
get a version until step 2 -- the backfill script fills those in.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2e58b41d7af'
down_revision: Union[str, Sequence[str], None] = '9a1c3e7f5b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'artifact_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('parent_version_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('author_user_id', sa.Integer(), nullable=True),
        sa.Column('origin', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('sealed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('user_prompt', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_version_id'], ['artifact_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_id', 'version_no', name='uq_artifact_versions_file_id_version_no'),
    )
    op.create_index('idx_artifact_versions_file_id_version_no', 'artifact_versions', ['file_id', 'version_no'])

    op.create_table(
        'artifact_edges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('child_file_id', sa.Integer(), nullable=False),
        sa.Column('parent_file_id', sa.Integer(), nullable=False),
        sa.Column('parent_version_id', sa.Integer(), nullable=True),
        sa.Column('relation', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['child_file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_version_id'], ['artifact_versions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_artifact_edges_child', 'artifact_edges', ['child_file_id'])
    op.create_index('idx_artifact_edges_parent', 'artifact_edges', ['parent_file_id'])

    op.create_table(
        'codebook_codes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False),
        sa.Column('code_uid', sa.String(), nullable=False),
        sa.Column('family_uid', sa.String(), nullable=False),
        sa.Column('family_name', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('definition', sa.Text(), nullable=True),
        sa.Column('inclusion', sa.Text(), nullable=True),
        sa.Column('exclusion', sa.Text(), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('example', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['version_id'], ['artifact_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_id', 'code_uid', name='uq_codebook_codes_version_id_code_uid'),
    )
    op.create_index('idx_codebook_codes_version_position', 'codebook_codes', ['version_id', 'position'])

    # Nullable for now -- step 3 (d4f97a2c6e1b) makes these NOT NULL once
    # the backfill script (or the fact that there was nothing to backfill)
    # has settled every existing row.
    op.add_column('coding_entries', sa.Column('code_uid', sa.String(), nullable=True))
    op.add_column('coding_entries', sa.Column('valid_from', sa.Integer(), nullable=True, server_default='1'))
    op.add_column('coding_entries', sa.Column('valid_to', sa.Integer(), nullable=True))
    op.create_index('idx_coding_entries_file_id_code_uid', 'coding_entries', ['file_id', 'code_uid'])
    op.create_index('idx_coding_entries_live', 'coding_entries', ['file_id', 'valid_to'])
    # Every pre-existing row is, by construction, still "live" (nothing
    # could have superseded it before this column existed).
    op.execute(sa.text("UPDATE coding_entries SET valid_from = 1 WHERE valid_from IS NULL"))

    conn = op.get_bind()

    # -- v1 versions for raw_data/filtered_data files (never had content,
    #    but need a version row so downstream edges can pin parent_version_id) --
    conn.execute(sa.text(
        """
        INSERT INTO artifact_versions
            (file_id, version_no, origin, sealed_at, author_user_id, model,
             system_prompt, user_prompt, created_at)
        SELECT f.id, 1, 'imported', f.created_at, f.user_id, NULL,
               f.systemprompt, f.userprompt, f.created_at
        FROM files f
        WHERE f.file_type IN ('raw_data', 'filtered_data')
        """
    ))

    # -- v1 versions for blob-storage artifact types: same bytes, new home --
    conn.execute(sa.text(
        """
        INSERT INTO artifact_versions
            (file_id, version_no, origin, sealed_at, author_user_id,
             content, content_hash, created_at)
        SELECT f.id, 1, 'imported', ac.created_at, f.user_id,
               ac.content, md5(ac.content), ac.created_at
        FROM artifact_content ac
        JOIN files f ON f.id = ac.file_id
        WHERE f.file_type IN ('summary', 'comparison', 'codebook_comparison', 'coding_comparison')
        """
    ))

    # -- file_dependencies -> artifact_edges, role inferred from the
    #    parent's (and for the fork case, the child's) file_type. See the
    #    module docstring for why this inference is exact rather than a
    #    heuristic. --
    conn.execute(sa.text(
        """
        WITH ranked AS (
            SELECT
                fd.id,
                fd.child_file_id,
                fd.parent_file_id,
                pf.file_type AS parent_type,
                cf.file_type AS child_type,
                ROW_NUMBER() OVER (PARTITION BY fd.child_file_id ORDER BY fd.id) - 1 AS ord,
                COUNT(*) OVER (PARTITION BY fd.child_file_id) AS sibling_count
            FROM file_dependencies fd
            JOIN files pf ON pf.id = fd.parent_file_id
            JOIN files cf ON cf.id = fd.child_file_id
        )
        INSERT INTO artifact_edges
            (child_file_id, parent_file_id, parent_version_id, relation, role, position)
        SELECT
            r.child_file_id,
            r.parent_file_id,
            av.id,
            CASE
                WHEN r.parent_type = 'coding' AND r.child_type = 'coding' THEN 'forked_from'
                WHEN r.child_type IN ('codebook_comparison', 'coding_comparison') THEN 'compared'
                WHEN r.child_type = 'raw_data' AND r.sibling_count > 1 THEN 'merged_from'
                WHEN r.child_type NOT IN ('codebook', 'coding', 'raw_data', 'filtered_data')
                     AND r.sibling_count > 1 THEN 'compared'
                ELSE 'derived_from'
            END AS relation,
            CASE
                WHEN r.parent_type = 'coding' AND r.child_type = 'coding' THEN 'fork_origin'
                WHEN r.child_type IN ('codebook_comparison', 'coding_comparison') THEN
                    CASE WHEN r.ord = 0 THEN 'side_a' ELSE 'side_b' END
                WHEN r.child_type = 'raw_data' AND r.sibling_count > 1 THEN 'merge_input'
                WHEN r.child_type NOT IN ('codebook', 'coding', 'raw_data', 'filtered_data')
                     AND r.sibling_count > 1 THEN
                    CASE WHEN r.ord = 0 THEN 'side_a' ELSE 'side_b' END
                WHEN r.parent_type IN ('codebook', 'codebook_comparison') AND r.child_type = 'coding' THEN 'codebook'
                ELSE 'source_data'
            END AS role,
            r.ord AS position
        FROM ranked r
        LEFT JOIN artifact_versions av ON av.file_id = r.parent_file_id AND av.version_no = 1
        """
    ))


def downgrade() -> None:
    op.drop_index('idx_coding_entries_live', table_name='coding_entries')
    op.drop_index('idx_coding_entries_file_id_code_uid', table_name='coding_entries')
    op.drop_column('coding_entries', 'valid_to')
    op.drop_column('coding_entries', 'valid_from')
    op.drop_column('coding_entries', 'code_uid')

    op.drop_index('idx_codebook_codes_version_position', table_name='codebook_codes')
    op.drop_table('codebook_codes')

    op.drop_index('idx_artifact_edges_parent', table_name='artifact_edges')
    op.drop_index('idx_artifact_edges_child', table_name='artifact_edges')
    op.drop_table('artifact_edges')

    op.drop_index('idx_artifact_versions_file_id_version_no', table_name='artifact_versions')
    op.drop_table('artifact_versions')
