import os
import tempfile
import traceback
import json
import secrets
from pathlib import Path
from fastapi import APIRouter, File as FastAPIFile, HTTPException, UploadFile, Form, Query, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd

from .utils import get_user_id_from_request, get_database_metadata
from app.database import get_db, User, Prompt, Project, File, FileTable, FileDependency, engine, SessionLocal
from app.databasemanager import DatabaseManager
from scripts.import_db import stream_zst_to_postgres

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
        with DatabaseManager() as dm:
            file_rec = File(user_id=user_id, filename=base_name, schemaname=schema_name, file_type="raw_data", description=(description or None))
            dm.session.add(file_rec)
            try:
                dm.session.flush()
            except Exception:
                dm.session.rollback()
                raise
            if project_id is not None:
                try:
                    proj = dm.session.query(Project).filter(Project.id == project_id).first()
                    if proj is None:
                        raise HTTPException(status_code=404, detail="Project not found")
                    if proj.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")
                    file_rec.projects.append(proj)
                    dm.session.flush()
                except HTTPException:
                    raise
                except Exception:
                    dm.session.rollback()
            with engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
                conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS "{schema_name}"."submissions" (
                    id TEXT PRIMARY KEY,
                    subreddit TEXT,
                    title TEXT,
                    selftext TEXT,
                    author TEXT,
                    created_utc BIGINT,
                    score INTEGER,
                    num_comments INTEGER
                )
                '''))
                conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS "{schema_name}"."comments" (
                    id TEXT PRIMARY KEY,
                    subreddit TEXT,
                    body TEXT,
                    author TEXT,
                    created_utc BIGINT,
                    score INTEGER,
                    link_id TEXT,
                    parent_id TEXT
                )
                '''))

            inserted_counts = stream_zst_to_postgres(tmp_path, schema_name, import_data_type, subreddit_filter=subreddit_list, batch_size=1000)

            if inserted_counts.get('submissions', 0) > 0:
                dm.file_tables.add_table_metadata(
                    file_id=file_rec.id,
                    table_name='submissions',
                    row_count=inserted_counts.get('submissions', 0)
                )
            if inserted_counts.get('comments', 0) > 0:
                dm.file_tables.add_table_metadata(
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
        print(f"Merging databases: {db_list} into {name}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid databases format")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {exc}")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Database name is required")

    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required to merge databases")

    db_check = SessionLocal()
    try:
        existing = db_check.query(File).filter(
            File.user_id == user_id,
        ).filter(
            (File.filename == name) | (File.schemaname == name)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"A file with name '{name}' already exists")
    finally:
        try:
            db_check.close()
        except Exception:
            pass

    unique_id = secrets.token_hex(6)
    schema_name = f"proj_{unique_id}"

    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

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
                except Exception as e:
                    print(f"Error listing tables for Postgres schema {schema_src}: {e}")
                    continue

                for table_name in src_tables:
                    try:
                        df = pd.read_sql_query(text(f'SELECT * FROM "{schema_src}"."{table_name}"'), con=engine)
                    except Exception as e:
                        print(f"Failed to read table {schema_src}.{table_name} from Postgres: {e}")
                        continue




                    if df is None or df.shape[0] == 0:
                        tables_written[table_name] = 0
                        continue

                    try:
                        with engine.connect() as conn:
                            target_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema_name}.{table_name}"}).scalar()
                    except Exception as e:
                        print(f"Error checking target table {schema_name}.{table_name}: {e}")
                        target_exists = None

                    if not target_exists:
                        try:
                            df.to_sql(name=table_name, con=engine, schema=schema_name, if_exists='replace', index=False, method='multi')
                            with engine.connect() as conn:
                                res = conn.execute(text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"'))
                                pg_count = int(res.scalar() or 0)
                        except Exception as e:
                            print(f"Error creating table {schema_name}.{table_name}: {e}")
                            continue
                    else:
                        tmp_name = f"tmp_merge_{secrets.token_hex(4)}"

                        try:
                            with engine.connect() as conn:
                                cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema=:schema AND table_name=:table"), {"schema": schema_name, "table": table_name}).fetchall()]
                        except Exception as e:
                            print(f"Error fetching columns for target {schema_name}.{table_name}: {e}")
                            cols = list(df.columns)

                        common_cols = [c for c in df.columns if c in cols]
                        if not common_cols:
                            print(f"No common columns for {schema_src}.{table_name} -> {schema_name}.{table_name}, skipping")
                            tables_written[table_name] = 0
                            continue

                        cols_quoted = ",".join([f'"{c}"' for c in common_cols])

                        try:
                            df[common_cols].to_sql(name=tmp_name, con=engine, schema=schema_name, if_exists='replace', index=False, method='multi')
                        except Exception as e:
                            print(f"Error creating temporary table {schema_name}.{tmp_name}: {e}")
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
                        except Exception as e:
                            print(f"Error inserting deduplicated rows into {schema_name}.{table_name}: {e}")
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
            print(f"Skipping non-Postgres source {db_name}; only proj_... schema names are supported")
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

        with DatabaseManager() as dm:
            file_rec = File(user_id=user_id, filename=name, schemaname=schema_name, file_type='raw_data', description=(description or None))
            dm.session.add(file_rec)
            try:
                dm.session.flush()
            except Exception:
                dm.session.rollback()
                raise
            # Add dependencies for merged databases
            for schema in db_list:
                parent_file = dm.session.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
                if parent_file:
                    dep = FileDependency(child_file_id=file_rec.id, parent_file_id=parent_file.id)
                    dm.session.add(dep)
            try:
                dm.session.flush()
            except Exception:
                dm.session.rollback()
            for tbl, cnt in final_table_counts.items():
                dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name=tbl, row_count=cnt)
            if project_id is not None:
                try:
                    proj = dm.session.query(Project).filter(Project.id == project_id).first()
                    if proj is None:
                        raise HTTPException(status_code=404, detail="Project not found")
                    if proj.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")
                    file_rec.projects.append(proj)
                    dm.session.flush()
                except HTTPException:
                    raise
                except Exception:
                    dm.session.rollback()

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


@router.post("/save-comparison/")
async def save_comparison(
    request: Request,
    content: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    file_type: str = Form(None),
    project_id: int = Form(None),
    parent_file_ids: str = Form(None),
):
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required to save comparison")

    base_name = title if title and title.strip() else "comparison"
    unique_id = secrets.token_hex(6)
    schema_name = f"cmp_{unique_id}"

    try:
        with DatabaseManager() as dm:
            file_rec = File(user_id=user_id, filename=base_name, schemaname=schema_name, file_type=(file_type or "comparison"), description=(description or None))
            dm.session.add(file_rec)
            try:
                dm.session.flush()
            except Exception:
                dm.session.rollback()
                raise

            # Add dependencies if parent_file_ids provided
            if parent_file_ids:
                try:
                    parent_ids = json.loads(parent_file_ids) if isinstance(parent_file_ids, str) else parent_file_ids
                    for pid in parent_ids:
                        dep = FileDependency(child_file_id=file_rec.id, parent_file_id=int(pid))
                        dm.session.add(dep)
                    dm.session.flush()
                except Exception:
                    dm.session.rollback()

            # If project_id provided, verify ownership and link
            if project_id is not None:
                try:
                    proj = dm.session.query(Project).filter(Project.id == project_id).first()
                    if proj is None:
                        raise HTTPException(status_code=404, detail="Project not found")
                    if proj.user_id != user_id:
                        raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")
                    file_rec.projects.append(proj)
                    dm.session.flush()
                except HTTPException:
                    raise
                except Exception:
                    dm.session.rollback()

            with engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
                conn.execute(text(f'''
                    CREATE TABLE IF NOT EXISTS "{schema_name}"."content_store" (
                        id SERIAL PRIMARY KEY,
                        file_text TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
                    )
                '''))
                conn.execute(text(f'INSERT INTO "{schema_name}"."content_store" (file_text) VALUES (:file_text)'), {"file_text": content})

            return JSONResponse({"message": "Saved", "file_id": file_rec.id, "schema_name": schema_name})
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/my-files/")
def my_projects(request: Request, file_type: str = Query("raw_data"), db: Session = Depends(get_db)):
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Use File table instead of Project; `file_type` query param maps to `file_type` on File
    # Allow callers requesting 'codebook' or 'coding' to also receive saved comparison files
    if file_type == 'codebook':
        files = db.query(File).filter(File.user_id == user_id, File.file_type.in_(['codebook', 'codebook_comparison'])).all()
    elif file_type == 'coding':
        files = db.query(File).filter(File.user_id == user_id, File.file_type.in_(['coding', 'coding_comparison'])).all()
    else:
        files = db.query(File).filter(File.user_id == user_id, File.file_type == file_type).all()
    result = []
    for p in files:
        tables = []
        try:
            # Query file-backed table metadata
            rows = db.query(FileTable).filter(FileTable.file_id == p.id).all()
            for r in rows:
                tables.append({"table_name": r.tablename, "row_count": r.row_count})
        except Exception:
            tables = []

        # Query parent file IDs
        parent_files = []
        try:
            deps = db.query(FileDependency).filter(FileDependency.child_file_id == p.id).all()
            for d in deps:
                parent_file = db.query(File).filter(File.id == d.parent_file_id).first()
                if parent_file:
                    parent_files.append({
                        "id": str(parent_file.id),
                        "name": parent_file.filename,
                        "schema_name": parent_file.schemaname,
                        "type": parent_file.file_type
                    })
        except Exception:
            parent_files = []

        result.append({
            "id": str(p.id),
            "display_name": p.filename,
            "description": p.description,
            "schema_name": p.schemaname,
            "file_type": p.file_type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "tables": tables,
            "parent_files": parent_files,
        })

    # Return under the legacy "projects" key so frontend code expecting
    # `data.projects` continues to work.
    return JSONResponse({"projects": result})


@router.post("/create-project/")
def create_project(request: Request, name: str = Form(...), description: str = Form(None), db: Session = Depends(get_db)):
    """Create a new project."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    # create project record (no schema_name column in DB)
    proj = Project(user_id=user_id, projectname=name.strip(), description=(description or None))
    db.add(proj)
    try:
        db.commit()
        db.refresh(proj)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"project": {"id": str(proj.id), "projectname": proj.projectname, "description": proj.description, "created_at": proj.created_at.isoformat() if proj.created_at else None}})


@router.post("/update-project/")
def update_project(request: Request, project_id: int = Form(...), name: str = Form(...), description: str = Form(None), db: Session = Depends(get_db)):
    """Update a project."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    proj.projectname = name.strip()
    proj.description = description or None
    try:
        db.add(proj)
        db.commit()
        db.refresh(proj)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"project": {"id": str(proj.id), "projectname": proj.projectname, "description": proj.description, "created_at": proj.created_at.isoformat() if proj.created_at else None}})


@router.get("/projects/")
def list_projects(request: Request):
    """List user's projects."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    with DatabaseManager() as dm:
        rows = dm.projects.get_all_for_user(user_id)
        result = []
        for r in rows:
            # Include associated files (databases) for each project
            files = []
            try:
                for f in getattr(r, "files", []) or []:
                    # Query parent files
                    parent_files = []
                    try:
                        deps = dm.session.query(FileDependency).filter(FileDependency.child_file_id == f.id).all()
                        for d in deps:
                            parent_file = dm.session.query(File).filter(File.id == d.parent_file_id).first()
                            if parent_file:
                                parent_files.append({
                                    "id": str(parent_file.id),
                                    "name": parent_file.filename,
                                    "type": parent_file.file_type
                                })
                    except Exception:
                        parent_files = []
                    files.append({
                        "id": str(f.id),
                        "display_name": f.filename,
                        "schema_name": f.schemaname,
                        "file_type": f.file_type,
                        "description": f.description,
                        "created_at": f.created_at.isoformat() if f.created_at else None,
                        "parent_files": parent_files,
                    })
            except Exception:
                files = []

            result.append({
                "id": str(r.id),
                "projectname": r.projectname,
                "description": r.description,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "files": files,
            })

    return JSONResponse({"projects": result})


@router.delete("/delete-database/{db_name}")
async def delete_database(db_name: str, request: Request, db: Session = Depends(get_db)):
    schema = db_name.strip()

    # Allow project-backed schemas (proj_) and comparison schemas (cmp_)
    if not (schema.startswith('proj_') or schema.startswith('cmp_')):
        raise HTTPException(status_code=400, detail="Invalid file schema identifier")

    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File not found or you do not have permission")

    try:
        # First, clean up file dependencies to avoid foreign key issues
        deps_deleted = db.query(FileDependency).filter(
            (FileDependency.child_file_id == file_rec.id) | 
            (FileDependency.parent_file_id == file_rec.id)
        ).delete()
        print(f"[DEBUG] Deleted {deps_deleted} file dependency records for file {file_rec.id}")
        
        with engine.begin() as conn:
            print(f"[DEBUG] Dropping schema {schema}")
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            print(f"[DEBUG] Schema {schema} dropped successfully")

        db.delete(file_rec)
        db.commit()
        print(f"[DEBUG] File record {file_rec.id} deleted successfully")
        return JSONResponse({"message": f"File '{file_rec.filename}' and schema '{schema}' deleted"})
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to delete file/schema {schema}: {str(e)}")
        import traceback
        traceback.print_exc()
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


@router.post("/rename-file/")
def rename_project(request: Request, schema_name: str = Form(...), display_name: str = Form(...), description: str = Form(None), db: Session = Depends(get_db)):
    """Rename a file's display_name. Requires authentication and ownership."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    schema = schema_name.strip()

    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File not found or you do not have permission")

    file_rec.filename = display_name
    if description is not None:
        file_rec.description = description
    try:
        db.commit()
        db.refresh(file_rec)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to rename file: {exc}")

    return JSONResponse({"message": "File renamed", "id": str(file_rec.id), "display_name": file_rec.filename, "description": file_rec.description})


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


@router.post("/post-contents/")
async def get_post_contents(
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        data = await request.json()
        schema_name = data.get("schema")
        post_ids = data.get("post_ids", [])

        if not schema_name or not post_ids:
            raise HTTPException(status_code=400, detail="schema and post_ids are required")

        # Query the database for the posts
        with engine.connect() as conn:
            # Build the query
            placeholders = ", ".join([f":id_{i}" for i in range(len(post_ids))])
            params = {f"id_{i}": pid for i, pid in enumerate(post_ids)}
            
            query = f"""
            SELECT id, title, selftext
            FROM "{schema_name}".submissions
            WHERE id IN ({placeholders})
            """
            
            result = conn.execute(text(query), params)
            posts = {}
            for row in result:
                post_id = str(row[0])
                title = row[1] or ""
                selftext = row[2] or ""
                posts[post_id] = {
                    "title": title,
                    "content": selftext
                }

        return JSONResponse({"contents": posts})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)