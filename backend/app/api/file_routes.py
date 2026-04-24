import os
import asyncio
import tempfile
import traceback
import json
import secrets
from pathlib import Path
from fastapi import APIRouter, File as FastAPIFile, HTTPException, UploadFile, Form, Query, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, select, or_
import pandas as pd

from backend.app.api.utils import get_user_id_from_request, get_database_metadata
from backend.app.database import (
    get_db,
    User,
    Prompt,
    Project,
    File,
    FileTable,
    FileDependency,
    engine,
    AsyncSessionLocal,
    async_engine,
    async_link_file_to_project,
)
from backend.app.databasemanager import AsyncDatabaseManager
from backend.scripts.import_db import stream_zst_to_postgres

router = APIRouter()


@router.post("/upload-zst/")
async def upload_zst_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    subreddits: str = Form(None),
    data_type: str = Form(...),
    name: str = Form(None),
    description: str = Form(None),
    project_id: int = Form(None),
):

    if not file.filename.endswith('.zst'):
        raise HTTPException(status_code=400, detail="File must be a .zst file")

    subreddit_list = None
    if subreddits:
        try:
            subreddit_list = json.loads(subreddits)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid subreddits format")

    allowed = ("comments", "posts")
    if data_type not in allowed:
        raise HTTPException(status_code=400, detail="data_type must be 'posts' or 'comments'")
    import_data_type = "submissions" if data_type == "posts" else data_type

    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix='.zst', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")

    user_id = get_user_id_from_request(request)

    response_data = {
        "status": "processing",
        "file_name": file.filename,
        "authenticated": bool(user_id),
    }

    if not user_id:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Unauthenticated")

    base_name = name if name is not None else file.filename.replace('.zst', '')
    unique_id = secrets.token_hex(6)
    schema_name = f"proj_{unique_id}"
    inserted_counts = {"submissions": 0, "comments": 0}

    try:
        async with AsyncDatabaseManager() as dm:
            file_rec = File(user_id=user_id, filename=base_name, schemaname=schema_name, file_type="raw_data", description=(description or None))
            dm.session.add(file_rec)
            try:
                await dm.session.flush()
            except Exception:
                await dm.session.rollback()
                raise
            if project_id is not None:
                try:
                    pr = await dm.session.execute(select(Project).where(Project.id == project_id))
                    proj = pr.scalar_one_or_none()
                    if proj is None:
                        raise HTTPException(status_code=404, detail="Project not found")
                    if proj.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")
                    await async_link_file_to_project(dm.session, file_rec.id, proj.id)
                    await dm.session.flush()
                except HTTPException:
                    raise
                except Exception:
                    await dm.session.rollback()
                    raise
            await dm.session.commit()
            async with async_engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
                await conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS "{schema_name}"."submissions" (
                    id TEXT PRIMARY KEY,
                    subreddit TEXT,
                    title TEXT,
                    selftext TEXT,
                    author TEXT,
                    created_utc BIGINT,
                    score INTEGER,
                    num_comments INTEGER,
                    word_count INTEGER GENERATED ALWAYS AS (
                        CASE WHEN COALESCE(TRIM(title || ' ' || selftext), '') = '' THEN 0
                        ELSE array_length(string_to_array(regexp_replace(TRIM(title || ' ' || selftext), '\\s+', ' ', 'g'), ' '), 1)
                        END
                    ) STORED
                )
                '''))
                await conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS "{schema_name}"."comments" (
                    id TEXT PRIMARY KEY,
                    subreddit TEXT,
                    body TEXT,
                    author TEXT,
                    created_utc BIGINT,
                    score INTEGER,
                    link_id TEXT,
                    parent_id TEXT,
                    word_count INTEGER GENERATED ALWAYS AS (
                        CASE WHEN COALESCE(TRIM(body), '') = '' THEN 0
                        ELSE array_length(string_to_array(regexp_replace(TRIM(body), '\\s+', ' ', 'g'), ' '), 1)
                        END
                    ) STORED
                )
                '''))
                await conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_{schema_name}_submissions_word_count ON "{schema_name}"."submissions" (word_count)'))
                await conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_{schema_name}_comments_word_count ON "{schema_name}"."comments" (word_count)'))

            inserted_counts = await asyncio.to_thread(
                stream_zst_to_postgres,
                tmp_path,
                schema_name,
                import_data_type,
                subreddit_list,
                1000,
            )

            if inserted_counts.get('submissions', 0) > 0:
                await dm.file_tables.add_table_metadata(
                    file_id=file_rec.id,
                    table_name='submissions',
                    row_count=inserted_counts.get('submissions', 0)
                )
            if inserted_counts.get('comments', 0) > 0:
                await dm.file_tables.add_table_metadata(
                    file_id=file_rec.id,
                    table_name='comments',
                    row_count=inserted_counts.get('comments', 0)
                )

            response_data.update({
                'status': 'completed',
                'display_name': base_name,
                'description': (description or None),
                'schema_name': schema_name,
                'inserted_counts': inserted_counts,
            })
            return JSONResponse(response_data)

    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/merge-databases/")
async def merge_databases(request: Request):
    try:
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            body = await request.json()
            databases = body.get("databases")
            name = body.get("name")
            description = body.get("description")
            project_id = body.get("project_id")
        else:
            form = await request.form()
            databases = form.get("databases")
            name = form.get("name")
            description = form.get("description")
            project_id = form.get("project_id")

        if isinstance(databases, str):
            db_list = json.loads(databases)
        elif isinstance(databases, list):
            db_list = databases
        else:
            raise HTTPException(status_code=400, detail="Invalid databases format")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid databases format") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {exc}") from exc

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Database name is required")

    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required to merge databases")

    async with AsyncSessionLocal() as db_check:
        chk = await db_check.execute(
            select(File).where(
                File.user_id == user_id,
                or_(File.filename == name, File.schemaname == name),
            )
        )
        existing = chk.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail=f"A file with name '{name}' already exists")

    unique_id = secrets.token_hex(6)
    schema_name = f"proj_{unique_id}"

    try:
        async with async_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

        total_rows = 0
        tables_written = {}

        database_dir = Path(settings.database_dir)

        for db_name in db_list:
            if isinstance(db_name, str) and db_name.startswith("proj_"):
                schema_src = db_name
                try:
                    with engine.connect() as conn:
                        tbls = conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = :schema"), {"schema": schema_src}).fetchall()
                        src_tables = [r[0] for r in tbls]
                except Exception:
                    continue

                for table_name in src_tables:
                    try:
                        df = pd.read_sql_query(text(f'SELECT * FROM "{schema_src}"."{table_name}"'), con=engine)
                    except Exception:
                        continue




                    if df is None or df.shape[0] == 0:
                        tables_written[table_name] = 0
                        continue

                    try:
                        with engine.connect() as conn:
                            target_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema_name}.{table_name}"}).scalar()
                    except Exception:
                        target_exists = None

                    if not target_exists:
                        try:
                            df.to_sql(name=table_name, con=engine, schema=schema_name, if_exists='replace', index=False, method='multi')
                            with engine.connect() as conn:
                                res = conn.execute(text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"'))
                                pg_count = int(res.scalar() or 0)
                        except Exception:
                            continue
                    else:
                        tmp_name = f"tmp_merge_{secrets.token_hex(4)}"

                        try:
                            with engine.connect() as conn:
                                cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema=:schema AND table_name=:table"), {"schema": schema_name, "table": table_name}).fetchall()]
                        except Exception:
                            cols = list(df.columns)

                        common_cols = [c for c in df.columns if c in cols]
                        if not common_cols:
                            print(f"No common columns for {schema_src}.{table_name} -> {schema_name}.{table_name}, skipping")
                            tables_written[table_name] = 0
                            continue

                        cols_quoted = ",".join([f'"{c}"' for c in common_cols])

                        try:
                            df[common_cols].to_sql(name=tmp_name, con=engine, schema=schema_name, if_exists='replace', index=False, method='multi')
                        except Exception:
                            try:
                                with engine.begin() as conn:
                                    conn.execute(text(f'DROP TABLE IF EXISTS "{schema_name}"."{tmp_name}"'))
                            except Exception:
                                pass
                            tables_written[table_name] = 0
                            continue

                        try:
                            with engine.begin() as conn:
                                before = conn.execute(text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"')).scalar() or 0
                                insert_sql = text(f'INSERT INTO "{schema_name}"."{table_name}" ({cols_quoted}) SELECT {cols_quoted} FROM "{schema_name}"."{tmp_name}" EXCEPT SELECT {cols_quoted} FROM "{schema_name}"."{table_name}"')
                                conn.execute(insert_sql)
                                after = conn.execute(text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"')).scalar() or 0
                                pg_count = int(after - before)
                        except Exception:
                            pg_count = 0
                        finally:
                            try:
                                with engine.begin() as conn:
                                    conn.execute(text(f'DROP TABLE IF EXISTS "{schema_name}"."{tmp_name}"'))
                            except Exception:
                                pass

                    total_rows += pg_count
                    tables_written[table_name] = pg_count

                continue

            # Non-Postgres sources are not supported in this Postgres-only flow
            continue

        final_table_counts = {}
        try:
            with engine.connect() as conn:
                tbls = conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = :schema"), {"schema": schema_name}).fetchall()
                schema_tables = [r[0] for r in tbls]
                for table_name in schema_tables:
                    try:
                        res = conn.execute(text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"'))
                        final_table_counts[table_name] = int(res.scalar() or 0)
                    except Exception as e:
                        print(f"Warning: could not count rows for {schema_name}.{table_name}: {e}")
                        final_table_counts[table_name] = 0
        except Exception as e:
            print(f"Warning: could not list tables for schema {schema_name}: {e}")

        total_rows = sum(final_table_counts.values())

        if total_rows == 0:
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            except Exception:
                pass
            return JSONResponse({"message": "No rows found in selected databases; nothing migrated", "database": name, "total_submissions": 0, "total_comments": 0, "file_migrated": False})

        async with AsyncDatabaseManager() as dm:
            file_rec = File(user_id=user_id, filename=name, schemaname=schema_name, file_type='raw_data', description=(description or None))
            dm.session.add(file_rec)
            try:
                await dm.session.flush()
            except Exception:
                await dm.session.rollback()
                raise
            for schema in db_list:
                pf = await dm.session.execute(
                    select(File).where(File.schemaname == schema, File.user_id == user_id)
                )
                parent_file = pf.scalar_one_or_none()
                if parent_file:
                    dep = FileDependency(child_file_id=file_rec.id, parent_file_id=parent_file.id)
                    dm.session.add(dep)
            try:
                await dm.session.flush()
            except Exception:
                await dm.session.rollback()
            for tbl, cnt in final_table_counts.items():
                await dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name=tbl, row_count=cnt)
            if project_id is not None:
                try:
                    pr = await dm.session.execute(select(Project).where(Project.id == project_id))
                    proj = pr.scalar_one_or_none()
                    if proj is None:
                        raise HTTPException(status_code=404, detail="Project not found")
                    if proj.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")
                    await async_link_file_to_project(dm.session, file_rec.id, proj.id)
                    await dm.session.flush()
                except HTTPException:
                    raise
                except Exception:
                    await dm.session.rollback()

        return JSONResponse({
                "message": f"Merged into file schema '{schema_name}'",
                "file": {"id": str(file_rec.id), "schema_name": schema_name, "display_name": name, "description": (description or None)},
                "file_migrated": True,
        })

    except HTTPException:
        raise
    except Exception as exc:
        try:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/delete-database/{db_name}")
async def delete_database(db_name: str, request: Request, db: Session = Depends(get_db)):
    schema = db_name.strip()

    # Allow project-backed schemas (proj_), comparison schemas (cmp_), and summaries (sum_)
    if not (schema.startswith('proj_') or schema.startswith('cmp_') or schema.startswith('sum_')):
        raise HTTPException(status_code=400, detail="Invalid file schema identifier")

    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File not found or you do not have permission")

    try:
        # First, clean up file dependencies to avoid foreign key issues
        db.query(FileDependency).filter(
            (FileDependency.child_file_id == file_rec.id)
            | (FileDependency.parent_file_id == file_rec.id)
        ).delete()

        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

        db.delete(file_rec)
        db.commit()
        return JSONResponse({"message": f"File '{file_rec.filename}' and schema '{schema}' deleted"})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete file/schema: {str(e)}")


@router.post("/delete-row/")
async def delete_row(request: Request, schemaname: str = Form(...), table: str = Form(...), row_id: str = Form(...), db: Session = Depends(get_db)):
    """Delete a row from submissions or comments table."""
    schema = (schemaname or "").strip()
    if schema.endswith('.db'):
        schema = schema[:-3]

    if not schema or not schema.startswith('proj_'):
        return JSONResponse({"error": "Invalid file schema"}, status_code=400)

    if table not in ("submissions", "comments"):
        return JSONResponse({"error": "Invalid table"}, status_code=400)

    user_id = get_user_id_from_request(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
        if not file_rec:
            return JSONResponse({"error": "File not found or not owned by user"}, status_code=403)

        with engine.begin() as conn:
            res = conn.execute(text(f'DELETE FROM "{schema}"."{table}" WHERE id = :id'), {"id": row_id})
            try:
                deleted = int(res.rowcount or 0)
            except Exception:
                deleted = 0

        try:
            with engine.connect() as conn:
                cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar() or 0

            # update or insert file_tables row using ORM session `db`
            pt = db.query(FileTable).filter(FileTable.file_id == file_rec.id, FileTable.tablename == table).first()
            if pt:
                pt.row_count = int(cnt)
            else:
                # create new metadata row for file
                new_pt = FileTable(file_id=file_rec.id, tablename=table, row_count=int(cnt))
                db.add(new_pt)
            try:
                db.commit()
            except Exception:
                db.rollback()

        except Exception:
            # non-fatal: continue even if metadata update fails
            pass

        return JSONResponse({"deleted": deleted})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/move-rows/")
async def move_rows(request: Request, db: Session = Depends(get_db)):
    """Move rows between file schemas."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    source = (body.get("source_schema") or "").strip()
    target = (body.get("target_schema") or "").strip()
    table = body.get("table")
    row_ids = body.get("row_ids") or []

    if source.endswith('.db'):
        source = source[:-3]
    if target.endswith('.db'):
        target = target[:-3]

    if not source or not source.startswith('proj_') or not target or not target.startswith('proj_'):
        return JSONResponse({"error": "Invalid file schema"}, status_code=400)
    if table not in ("submissions", "comments"):
        return JSONResponse({"error": "Invalid table"}, status_code=400)
    if not isinstance(row_ids, list) or len(row_ids) == 0:
        return JSONResponse({"error": "row_ids must be a non-empty list"}, status_code=400)

    user_id = get_user_id_from_request(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        file_src = db.query(File).filter(File.schemaname == source, File.user_id == user_id).first()
        file_tgt = db.query(File).filter(File.schemaname == target, File.user_id == user_id).first()
        if not file_src or not file_tgt:
            return JSONResponse({"error": "Source or target file not found or not owned by user"}, status_code=403)

        moved = 0
        with engine.begin() as conn:
            # Fetch rows from source
            rows = conn.execute(text(f'SELECT * FROM "{source}"."{table}" WHERE id = ANY(:ids)'), {"ids": row_ids}).fetchall()
            if not rows:
                return JSONResponse({"moved": 0, "message": "No matching rows found"})

            cols = list(rows[0]._mapping.keys())
            col_list = ", ".join([f'"{c}"' for c in cols])

            # Insert each row into target
            for r in rows:
                mapping = dict(r._mapping)
                # build paramized insert
                params = {f"p_{i}": mapping[c] for i, c in enumerate(cols)}
                placeholders = ", ".join([f":p_{i}" for i in range(len(cols))])
                conn.execute(text(f'INSERT INTO "{target}"."{table}" ({col_list}) VALUES ({placeholders})'), params)
                moved += 1

            # Delete from source
            conn.execute(text(f'DELETE FROM "{source}"."{table}" WHERE id = ANY(:ids)'), {"ids": row_ids})

        # Update metadata counts for both projects (best-effort)
        try:
            with engine.connect() as conn:
                src_cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{source}"."{table}"')).scalar() or 0
                tgt_cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{target}"."{table}"')).scalar() or 0

            # update file_tables rows
            pt_src = db.query(FileTable).filter(FileTable.file_id == file_src.id, FileTable.tablename == table).first()
            if pt_src:
                pt_src.row_count = int(src_cnt)
            else:
                db.add(FileTable(file_id=file_src.id, tablename=table, row_count=int(src_cnt)))

            pt_tgt = db.query(FileTable).filter(FileTable.file_id == file_tgt.id, FileTable.tablename == table).first()
            if pt_tgt:
                pt_tgt.row_count = int(tgt_cnt)
            else:
                db.add(FileTable(file_id=file_tgt.id, tablename=table, row_count=int(tgt_cnt)))
            try:
                db.commit()
            except Exception:
                db.rollback()
        except Exception:
            pass

        return JSONResponse({"moved": moved})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

