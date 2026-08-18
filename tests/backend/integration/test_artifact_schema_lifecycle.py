"""Integration coverage for the raw-SQL, per-artifact-schema pattern used
throughout codebook_routes.py / coding_routes.py / content_routes.py:
`CREATE SCHEMA IF NOT EXISTS "<schema>"` + a `content_store` table +
insert/read. This is exactly what the SQLite-backed unit tests can't
exercise, since `CREATE SCHEMA` and Postgres's catalog functions
(`to_regclass`) have no SQLite equivalent.
"""

import pytest
from sqlalchemy import text


async def test_create_schema_and_content_store_round_trip(integration_async_engine):
    schema = "proj_integration_test1"
    async with integration_async_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(
            text(f'CREATE TABLE IF NOT EXISTS "{schema}".content_store (file_text text)')
        )
        await conn.execute(
            text(f'INSERT INTO "{schema}".content_store (file_text) VALUES (:t)'),
            {"t": "hello from integration test"},
        )

    async with integration_async_engine.connect() as conn:
        row = (
            await conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
        ).fetchone()
        assert row[0] == "hello from integration test"

        exists = (
            await conn.execute(
                text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.content_store"}
            )
        ).scalar()
        assert exists is not None

    # Cleanup
    async with integration_async_engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


async def test_truncate_and_replace_single_row_pattern(integration_async_engine):
    # save_summary / generate_codebook / apply_codebook all use this exact
    # create-if-missing -> truncate -> insert-one-row pattern to replace a
    # single-row content_store table's content.
    schema = "proj_integration_test2"
    async with integration_async_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(
            text(f'CREATE TABLE IF NOT EXISTS "{schema}".content_store (file_text text)')
        )
        await conn.execute(
            text(f'INSERT INTO "{schema}".content_store (file_text) VALUES (:t)'), {"t": "v1"}
        )

    async with integration_async_engine.begin() as conn:
        await conn.execute(text(f'TRUNCATE TABLE "{schema}".content_store'))
        await conn.execute(
            text(f'INSERT INTO "{schema}".content_store (file_text) VALUES (:t)'), {"t": "v2"}
        )

    async with integration_async_engine.connect() as conn:
        rows = (
            await conn.execute(text(f'SELECT file_text FROM "{schema}".content_store'))
        ).fetchall()
        assert [r[0] for r in rows] == ["v2"]

    async with integration_async_engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
