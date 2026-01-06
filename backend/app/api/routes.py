import os
import sqlite3
import json
import tempfile
import traceback
import asyncio
import inspect
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, Form, Query, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

import hashlib
import binascii
import uuid
from datetime import datetime

import pandas as pd
from fastapi.responses import JSONResponse
from fastapi import Request

from app.database import get_db, AuthUser, Project, ProjectTable, engine, SessionLocal
from app.databasemanager import DatabaseManager
from app.auth import create_access_token, decode_access_token
from app.config import settings

from scripts.import_db import stream_zst_to_postgres
from scripts.filter_db import filter_posts_with_ai, filter_comments_with_ai
from scripts.codebook_generator import generate_codebook as generate_codebook_function
from scripts.codebook_apply import classify_posts
from app.services import migrate_sqlite_file

router = APIRouter()


def get_user_id_from_request(request: Request):
    """Extract access token from cookie or Authorization header and decode it.

    Returns the `sub` claim (user id as string) on success, or None on failure.
    """
    token = None
    try:
        token = request.cookies.get("access_token")
    except Exception:
        token = None

    if not token:
        auth = request.headers.get("Authorization") if hasattr(request, "headers") else None
        if auth and isinstance(auth, str) and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]

    if not token:
        return None

    try:
        payload = decode_access_token(token)
    except Exception:
        return None

    return payload.get("sub")

@router.post("/upload-zst/")
async def upload_zst_file(
    request: Request,
    file: UploadFile = File(...), 
    subreddits: str = Form(None),
    data_type: str = Form(...),
    name: str = Form(None)
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

    # Save upload to a temporary .zst file
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix='.zst', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")

    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)

    response_data = {
        "status": "processing",
        "file_name": file.filename,
        "authenticated": bool(user_id),
    }

    # If unauthenticated, reject the request
    if not user_id:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Unauthenticated")

    # Authenticated path: create Postgres schema, tables and stream-insert rows
    base_name = name if name is not None else file.filename.replace('.zst', '')
    unique_id = str(uuid.uuid4()).replace('-', '')[:12]
    schema_name = f"proj_{unique_id}"
    inserted_counts = {"submissions": 0, "comments": 0}

    try:
        with DatabaseManager() as dm:
            project = dm.projects.create(
                user_id=uuid.UUID(user_id),
                display_name=base_name,
                schema_name=schema_name,
                project_type="raw_data",
            )
            # create schema and tables
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

            # add project_tables metadata
            if inserted_counts.get('submissions', 0) > 0:
                dm.project_tables.add_table_metadata(
                    project_id=project.id,
                    table_name='submissions',
                    row_count=inserted_counts.get('submissions', 0)
                )
            if inserted_counts.get('comments', 0) > 0:
                dm.project_tables.add_table_metadata(
                    project_id=project.id,
                    table_name='comments',
                    row_count=inserted_counts.get('comments', 0)
                )

            response_data.update({
                'status': 'completed',
                'display_name': base_name,
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


def get_database_metadata(db_path):
    """Get metadata for a database file."""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM submissions")
        submission_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM comments")
        comment_count = cursor.fetchone()[0]
        
        conn.close()
        
        creation_time = os.path.getctime(str(db_path))
        
        return {
            "total_submissions": submission_count,
            "total_comments": comment_count,
            "date_created": creation_time if creation_time > 0 else None
        }
    except Exception as e:
        print(f"Error getting metadata for {db_path}: {e}")
        return {
            "total_submissions": 0,
            "total_comments": 0,
            "date_created": None
        }


@router.post("/merge-databases/")
async def merge_databases(request: Request, databases: str = Form(...), name: str = Form(...)):
    try:
        db_list = json.loads(databases)
        print(f"Merging databases: {db_list} into {name}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid databases format")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Database name is required")

    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required to merge databases")

    # ensure user doesn't already have a project with same display/schema
    db_check = SessionLocal()
    try:
        existing = db_check.query(Project).filter(
            Project.user_id == user_id,
        ).filter(
            (Project.display_name == name) | (Project.schema_name == name)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"A project with name '{name}' already exists")
    finally:
        try:
            db_check.close()
        except Exception:
            pass

    unique_id = str(uuid.uuid4()).replace('-', '')[:12]
    schema_name = f"proj_{unique_id}"

    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

        total_rows = 0
        tables_written = {}

        database_dir = Path(settings.database_dir)

        for db_name in db_list:
            # Only support Postgres project schema sources (proj_...)
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
                        # Read from Postgres schema.table into dataframe
                        df = pd.read_sql_query(text(f'SELECT * FROM "{schema_src}"."{table_name}"'), con=engine)
                    except Exception as e:
                        print(f"Failed to read table {schema_src}.{table_name} from Postgres: {e}")
                        continue

                    # skip empty dataframes
                    if df is None or df.shape[0] == 0:
                        tables_written[table_name] = 0
                        continue

                    # Check if target table exists
                    try:
                        with engine.connect() as conn:
                            target_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema_name}.{table_name}"}).scalar()
                    except Exception as e:
                        print(f"Error checking target table {schema_name}.{table_name}: {e}")
                        target_exists = None

                    # If target doesn't exist, create it by replacing
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
                        # Target exists: insert only rows not already present using a temporary table + EXCEPT
                        tmp_name = f"tmp_merge_{uuid.uuid4().hex[:8]}"

                        # determine common columns between df and target
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
                            # write source rows to temporary table in target schema
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

        # After writing all tables, compute final per-table row counts from the new schema
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
            # nothing to migrate: drop empty schema and inform client
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            except Exception:
                pass
            return JSONResponse({"message": "No rows found in selected databases; nothing migrated", "database": name, "total_submissions": 0, "total_comments": 0, "project_migrated": False})

        # Create project record and table metadata using the final counts
        with DatabaseManager() as dm:
            proj = dm.projects.create(user_id=uuid.UUID(user_id), display_name=name, schema_name=schema_name, project_type='raw_data')
            for tbl, cnt in final_table_counts.items():
                dm.project_tables.add_table_metadata(project_id=proj.id, table_name=tbl, row_count=cnt)

        return JSONResponse({"message": f"Merged into project schema '{schema_name}'", "project": {"id": str(proj.id), "schema_name": schema_name, "display_name": name}, "project_migrated": True})

    except HTTPException:
        raise
    except Exception as exc:
        # Attempt to drop the schema on failure
        try:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(exc))


class RegisterRequest(BaseModel):
    email: str
    password: str


def _hash_password(password: str) -> str:
    """Hash the password using PBKDF2-HMAC-SHA256. Returns salt$iterations$hashhex"""
    salt = os.urandom(16)
    iterations = 100_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{binascii.hexlify(salt).decode()}${iterations}${binascii.hexlify(dk).decode()}"


def _verify_password(stored: str, provided: str) -> bool:
    """Verify a stored password of format salt$iterations$hashhex against a provided password."""
    try:
        salt_hex, iterations_s, hash_hex = stored.split("$")
        salt = binascii.unhexlify(salt_hex)
        iterations = int(iterations_s)
        dk = binascii.unhexlify(hash_hex)
        test_dk = hashlib.pbkdf2_hmac("sha256", provided.encode("utf-8"), salt, iterations)
        return binascii.hexlify(test_dk) == binascii.hexlify(dk)
    except Exception:
        return False


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login/")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AuthUser).filter(AuthUser.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_password(user.hashed_password, payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    resp = JSONResponse({"id": str(user.id), "email": user.email})
    max_age = int(settings.jwt_access_token_expire_minutes) * 60
    resp.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=max_age)
    return resp


@router.post("/register/")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    # Check if email already exists
    existing = db.query(AuthUser).filter(AuthUser.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_id = uuid.uuid4()
    hashed = _hash_password(payload.password)

    user = AuthUser(id=new_id, email=payload.email, hashed_password=hashed, date_created=datetime.utcnow())
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    token = create_access_token({"sub": str(user.id), "email": user.email})
    resp = JSONResponse({"id": str(user.id), "email": user.email})
    max_age = int(settings.jwt_access_token_expire_minutes) * 60
    resp.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=max_age)
    return resp


@router.get("/me/")
def me(request: Request, db: Session = Depends(get_db)):
    # Use token helper to get the user id; then return user record
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return JSONResponse({"id": str(user.id), "email": user.email})


@router.get("/my-projects/")
def my_projects(request: Request, project_type: str = Query("raw_data"), db: Session = Depends(get_db)):
    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    projects = db.query(Project).filter(Project.user_id == user_id, Project.project_type == project_type).all()
    result = []
    for p in projects:
        tables = []
        try:
            rows = db.query(ProjectTable).filter(ProjectTable.project_id == p.id).all()
            for r in rows:
                tables.append({"table_name": r.table_name, "row_count": r.row_count})
        except Exception:
            tables = []

        result.append({
            "id": str(p.id),
            "display_name": p.display_name,
            "schema_name": p.schema_name,
            "project_type": p.project_type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "tables": tables,
        })

    return JSONResponse({"projects": result})


@router.delete("/delete-database/{db_name}")
async def delete_database(db_name: str, request: Request, db: Session = Depends(get_db)):
    schema = db_name.strip()

    if not schema.startswith('proj_'):
        raise HTTPException(status_code=400, detail="Invalid project schema identifier")

    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    proj = db.query(Project).filter(Project.schema_name == schema, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found or you do not have permission")

    try:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

        db.delete(proj)
        db.commit()
        return JSONResponse({"message": f"Project '{proj.display_name}' and schema '{schema}' deleted"})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete project/schema: {str(e)}")


@router.post("/delete-row/")
async def delete_row(request: Request, schema: str = Form(...), table: str = Form(...), row_id: str = Form(...), db: Session = Depends(get_db)):
    """Delete a single row (by id) from a project's table (submissions or comments).

    Requires authentication and project ownership.
    """
    schema = (schema or "").strip()
    if schema.endswith('.db'):
        schema = schema[:-3]

    if not schema or not schema.startswith('proj_'):
        return JSONResponse({"error": "Invalid project schema"}, status_code=400)

    if table not in ("submissions", "comments"):
        return JSONResponse({"error": "Invalid table"}, status_code=400)

    user_id = get_user_id_from_request(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        proj = db.query(Project).filter(Project.schema_name == schema, Project.user_id == user_id).first()
        if not proj:
            return JSONResponse({"error": "Project not found or not owned by user"}, status_code=403)

        with engine.begin() as conn:
            res = conn.execute(text(f'DELETE FROM "{schema}"."{table}" WHERE id = :id'), {"id": row_id})
            try:
                deleted = int(res.rowcount or 0)
            except Exception:
                deleted = 0

        # Update project_tables metadata: recount rows and persist
        try:
            with engine.connect() as conn:
                cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar() or 0

            # update or insert project_tables row using ORM session `db`
            pt = db.query(ProjectTable).filter(ProjectTable.project_id == proj.id, ProjectTable.table_name == table).first()
            if pt:
                pt.row_count = int(cnt)
            else:
                # create new metadata row
                new_pt = ProjectTable(project_id=proj.id, table_name=table, row_count=int(cnt))
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


@router.post("/rename-project/")
def rename_project(request: Request, schema_name: str = Form(...), display_name: str = Form(...), db: Session = Depends(get_db)):
    """Rename a project's display_name. Requires authentication and ownership."""
    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # normalize schema name
    schema = schema_name.strip()

    proj = db.query(Project).filter(Project.schema_name == schema, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found or you do not have permission")

    proj.display_name = display_name
    try:
        db.commit()
        db.refresh(proj)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to rename project: {exc}")

    return JSONResponse({"message": "Project renamed", "id": str(proj.id), "display_name": proj.display_name})


@router.post("/logout/")
def logout():
    resp = JSONResponse({"message": "Logged out"})
    # clear the HttpOnly cookie by setting an expired cookie
    resp.set_cookie("access_token", "", httponly=True, samesite="lax", max_age=0)
    return resp


@router.get("/codebook")
async def get_codebook(codebook_id: str = Query(None), db: Session = Depends(get_db)):
    """Return a codebook stored in a Postgres project with project_type='codebook'.
    """
    # First try to find a matching project (by schema_name or display_name or id)
    project = None
    if codebook_id:
        # try schema_name match
        project = db.query(Project).filter(Project.project_type == 'codebook', Project.schema_name == codebook_id).first()
        if not project:
            # try display_name match
            project = db.query(Project).filter(Project.project_type == 'codebook', Project.display_name == codebook_id).first()
        if not project:
            # try id match
            try:
                pid = uuid.UUID(codebook_id)
                project = db.query(Project).filter(Project.project_type == 'codebook', Project.id == pid).first()
            except Exception:
                project = None

    else:
        # No id supplied: pick latest codebook project if any
        project = db.query(Project).filter(Project.project_type == 'codebook').order_by(Project.created_at.desc()).first()

    if project:
        schema = project.schema_name
        try:
            with engine.connect() as conn:
                res = conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
                row = res.fetchone()
                if row:
                    return JSONResponse({"codebook": row[0]})
                else:
                    return JSONResponse({"error": "Codebook content not found in project"}, status_code=404)
        except Exception as e:
            print(f"Error reading codebook from schema {schema}: {e}")
            return JSONResponse({"error": f"Error reading codebook: {e}"}, status_code=500)

    return JSONResponse({"error": "No codebook project found"}, status_code=404)


@router.get("/list-codebooks")
async def list_codebooks(db: Session = Depends(get_db)):
    # Only return DB-backed codebook projects
    codebooks = []
    try:
        projects = db.query(Project).filter(Project.project_type == 'codebook').all()
        for p in projects:
            codebooks.append({
                "id": str(p.id),
                "name": p.display_name,
                "metadata": {"schema": p.schema_name, "created_at": p.created_at.isoformat() if p.created_at else None},
                "source": "project",
            })
    except Exception:
        return JSONResponse({"codebooks": []})

    codebooks.sort(key=lambda x: x.get("name") or x.get("id"))
    return JSONResponse({"codebooks": codebooks})


@router.post("/save-project-codebook/")
async def save_project_codebook(request: Request, schema_name: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    """Save codebook content into a Postgres project schema's content_store table.
    Requires authentication and project ownership.
    """
    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    schema = schema_name.strip()

    proj = db.query(Project).filter(Project.schema_name == schema, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found or you do not have permission")

    # Ensure content_store table exists and upsert the single row
    display_name = None
    try:
        # Try to read optional display_name from form data
        form = await request.form()
        if "display_name" in form:
            display_name = str(form.get("display_name"))
    except Exception:
        display_name = None

    # Debug logging to help diagnose save failures
    try:
        print(f"[DEBUG] save_project_codebook called; authenticated={bool(user_id)}, user_id={user_id}, schema={schema}")
        try:
            # show form keys and sizes but not full content for privacy
            form_keys = list((await request.form()).keys())
        except Exception:
            form_keys = []
        print(f"[DEBUG] form_keys: {form_keys}, display_name_provided={bool(display_name)}, content_length={len(content) if content else 0}")
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{schema}".content_store (file_text text)'))
            # Remove existing rows and insert the new content (single-row store)
            conn.execute(text(f'TRUNCATE TABLE "{schema}".content_store'))
            conn.execute(text(f'INSERT INTO "{schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": content})

        # If a display_name was provided, update the projects table
        if display_name:
            proj.display_name = display_name
            try:
                db.commit()
                db.refresh(proj)
            except Exception as exc:
                db.rollback()
                print(f"Failed to update project display_name for {schema}: {exc}")

        return JSONResponse({"message": "Project codebook saved", "id": str(proj.id), "display_name": proj.display_name})
    except Exception as e:
        print(f"Error saving project codebook to schema {schema}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/coded-data") 
async def get_coded_data_query(coded_id: str = Query(None), db: Session = Depends(get_db)):
    """Return coded data stored in a Postgres project with project_type='coding'.
    """
    project = None
    if coded_id:
        # try schema_name match
        project = db.query(Project).filter(Project.project_type == 'coding', Project.schema_name == coded_id).first()
        if not project:
            project = db.query(Project).filter(Project.project_type == 'coding', Project.display_name == coded_id).first()
        if not project:
            try:
                pid = uuid.UUID(coded_id)
                project = db.query(Project).filter(Project.project_type == 'coding', Project.id == pid).first()
            except Exception:
                project = None
    else:
        project = db.query(Project).filter(Project.project_type == 'coding').order_by(Project.created_at.desc()).first()

    if project:
        schema = project.schema_name
        try:
            print(f"[DEBUG] get_coded_data -> selected project id={project.id} schema={schema} user_project_type={project.project_type}")
            with engine.connect() as conn:
                # Check if content_store table exists in the target schema
                tbl_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.content_store"}).scalar()
                if not tbl_exists:
                    print(f"[DEBUG] get_coded_data -> content_store not found in schema {schema}")
                    return JSONResponse({"error": f"content_store table not found in schema {schema}"}, status_code=404)

                # Check for file_text column
                cols = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema = :schema AND table_name = :table"), {"schema": schema, "table": "content_store"}).fetchall()
                col_names = [c[0] for c in cols]
                if 'file_text' not in col_names:
                    print(f"[DEBUG] get_coded_data -> file_text column missing in {schema}.content_store; cols={col_names}")
                    return JSONResponse({"error": f"file_text column missing in {schema}.content_store"}, status_code=404)

                # Fetch the single row
                res = conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
                row = res.fetchone()
                if row:
                    return JSONResponse({"coded_data": row[0]})
                else:
                    print(f"[DEBUG] get_coded_data -> no rows in {schema}.content_store")
                    return JSONResponse({"error": "Coded data content not found in project"}, status_code=404)
        except Exception as e:
            print(f"Error reading coded data from schema {schema}: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse({"error": f"Error reading coded data: {e}"}, status_code=500)

    return JSONResponse({"error": "No coded data project found"}, status_code=404)


@router.post("/save-project-coded-data/")
async def save_project_coded_data(request: Request, schema_name: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    """Save coded content into a Postgres project schema's content_store table for project_type 'coding'.
    Requires authentication and project ownership.
    """
    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    schema = schema_name.strip()

    proj = db.query(Project).filter(Project.schema_name == schema, Project.user_id == user_id, Project.project_type == 'coding').first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found or you do not have permission")

    display_name = None
    try:
        form = await request.form()
        if "display_name" in form:
            display_name = str(form.get("display_name"))
    except Exception:
        display_name = None

    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{schema}".content_store (file_text text)'))
            conn.execute(text(f'TRUNCATE TABLE "{schema}".content_store'))
            conn.execute(text(f'INSERT INTO "{schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": content})

        if display_name:
            proj.display_name = display_name
            try:
                db.commit()
                db.refresh(proj)
            except Exception:
                db.rollback()

        return JSONResponse({"message": "Project coded data saved", "id": str(proj.id), "display_name": proj.display_name})
    except Exception as e:
        print(f"Error saving project coded data to schema {schema}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/project-entries/")
def project_entries(schema: str = Query(..., description="Project schema name"), limit: int = 10):
    # Allow optional .db suffix (frontend may supply schema.db); validate and strip it.
    import re
    if not schema:
        raise HTTPException(status_code=400, detail="Missing schema name")
    schema = schema.strip()
    if schema.endswith(".db"):
        schema = schema[:-3]

    # Validate schema name (allow only letters, numbers, and underscore, must start with letter)
    if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", schema):
        raise HTTPException(status_code=400, detail="Invalid schema name")

    # Build queries for submissions and comments inside the provided schema
    submissions = []
    comments = []
    sub_count = 0
    com_count = 0

    try:
        with engine.connect() as conn:
            # Check if submissions table exists in schema
            q = text("SELECT to_regclass(:tbl)")
            subs_tbl = f"{schema}.submissions"
            comments_tbl = f"{schema}.comments"

            subs_exists = conn.execute(text(f"SELECT to_regclass(:tbl)"), {"tbl": subs_tbl}).scalar()
            comm_exists = conn.execute(text(f"SELECT to_regclass(:tbl)"), {"tbl": comments_tbl}).scalar()

            if subs_exists:
                sub_count = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.submissions")).scalar() or 0
                rows = conn.execute(text(f"SELECT * FROM {schema}.submissions LIMIT :lim"), {"lim": limit}).fetchall()
                # convert rows to dicts
                submissions = [dict(r._mapping) for r in rows]

            if comm_exists:
                com_count = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.comments")).scalar() or 0
                rows = conn.execute(text(f"SELECT * FROM {schema}.comments LIMIT :lim"), {"lim": limit}).fetchall()
                comments = [dict(r._mapping) for r in rows]

    except Exception as exc:
        return JSONResponse({
            "submissions": [],
            "comments": [],
            "total_submissions": 0,
            "total_comments": 0,
            "message": f"Error reading project schema: {exc}"
        }, status_code=500)

    return JSONResponse({
        "submissions": submissions,
        "comments": comments,
        "total_submissions": sub_count,
        "total_comments": com_count,
        "database": schema,
        "date_created": None,
    })


@router.post("/filter-data/")
async def filter_data(request: Request, api_key: str = Form(...), prompt: str = Form(...), database: str = Form(None), name: str = Form(...)):
    """Read a Postgres project schema (provided in `database`), assemble submissions and comments,
    merge into a single string and print it to the server stdout.
    """
    schema = (database or "").strip()

    if not schema or not schema.startswith('proj_'):
        return JSONResponse({"error": "This endpoint expects a proj_<id> schema name in 'database'"}, status_code=400)

    submissions_text = ""
    comments_text = ""
    try:
        with engine.connect() as conn:
            # Submissions: id, title, selftext
            subs_tbl = f"{schema}.submissions"
            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": subs_tbl}).scalar()
            if subs_exists:
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."submissions"')).fetchall()
                for r in rows:
                    try:
                        rid = r._mapping.get('id')
                        title = r._mapping.get('title')
                        selftext = r._mapping.get('selftext')
                    except Exception:
                        rid = r[0] if len(r) > 0 else ""
                        title = r[1] if len(r) > 1 else ""
                        selftext = r[2] if len(r) > 2 else ""
                    submissions_text += f"ID: {rid or ''}\nTitle: {title or ''}\n{selftext or ''}\n\n"

            # Comments: id, body
            comm_tbl = f"{schema}.comments"
            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": comm_tbl}).scalar()
            if comm_exists:
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."comments"')).fetchall()
                for r in rows:
                    try:
                        cid = r._mapping.get('id')
                        body = r._mapping.get('body')
                    except Exception:
                        cid = r[0] if len(r) > 0 else ""
                        body = r[1] if len(r) > 1 else ""
                    comments_text += f"CommentID: {cid or ''}\n{body or ''}\n\n"

        # Print only lengths
        try:
            print(f"[filter-data] submissions length: {len(submissions_text)}")
            print(f"[filter-data] comments length: {len(comments_text)}")
        except Exception as e:
            print(f"[filter-data] Error printing lengths: {e}")

        # Call AI filter functions and print their responses
        posts_filtered = None
        comments_filtered = None
        try:
            if submissions_text and submissions_text.strip():
                posts_filtered = filter_posts_with_ai(prompt or "", submissions_text, api_key)
                print(f"[filter-data] posts_filtered: {posts_filtered}")
            else:
                posts_filtered = '[]'

            if comments_text and comments_text.strip():
                comments_filtered = filter_comments_with_ai(prompt or "", comments_text, api_key)
                print(f"[filter-data] comments_filtered: {comments_filtered}")
            else:
                comments_filtered = '[]'
        except Exception as e:
            print(f"[filter-data] Error calling filter functions: {e}")
            traceback.print_exc()
            posts_filtered = f'[{{"error": "Filtering failed: {e}"}}]'
            comments_filtered = f'[{{"error": "Filtering failed: {e}"}}]'

        posts_list = posts_filtered if isinstance(posts_filtered, list) else []
        comments_list = comments_filtered if isinstance(comments_filtered, list) else []
        print(len(posts_list), len(comments_list))
        try:
            selected_posts = []
            selected_comments = []
            with engine.connect() as conn:
                # posts_list is expected to be a list of id strings; fetch records for each id
                if isinstance(posts_list, list):
                    for item in posts_list:
                        if not item:
                            continue
                        try:
                            row = conn.execute(text(f'SELECT * FROM "{schema}"."submissions" WHERE id = :id'), {"id": item}).fetchone()
                            if row:
                                try:
                                    sid = row._mapping.get('id')
                                    title = row._mapping.get('title')
                                    selftext = row._mapping.get('selftext')
                                except Exception:
                                    sid = row[0] if len(row) > 0 else None
                                    title = row[1] if len(row) > 1 else None
                                    selftext = row[2] if len(row) > 2 else None
                                selected_posts.append({"id": sid, "title": title, "selftext": selftext})
                        except Exception:
                            pass

                # comments_list is expected to be a list of id strings; fetch records for each id
                if isinstance(comments_list, list):
                    for item in comments_list:
                        if not item:
                            continue
                        try:
                            row = conn.execute(text(f'SELECT * FROM "{schema}"."comments" WHERE id = :id'), {"id": item}).fetchone()
                            if row:
                                try:
                                    cid = row._mapping.get('id')
                                    body = row._mapping.get('body')
                                except Exception:
                                    cid = row[0] if len(row) > 0 else None
                                    body = row[1] if len(row) > 1 else None
                                selected_comments.append({"id": cid, "body": body})
                        except Exception:
                            pass

            # Use the fetched records (may be empty lists)
            posts_list = selected_posts
            comments_list = selected_comments

            try:
                print(f"[filter-data] Parsed posts_list length: {len(posts_list)}")
                print(f"[filter-data] Parsed comments_list length: {len(comments_list)}")
            except Exception:
                pass
        except Exception as e:
            print(f"[filter-data] Error normalizing parsed results: {e}")
            try:
                print(f"[filter-data] Raw posts_list type: {type(posts_list)}, comments_list type: {type(comments_list)}")
            except Exception:
                pass

        # Create a new Postgres schema and store results there; attach to authenticated user if present
        # Resolve authenticated user (optional)
        user_id = get_user_id_from_request(request)

        new_schema = None
        proj = None
        try:
            unique_id = str(uuid.uuid4()).replace('-', '')[:12]
            new_schema = f"proj_{unique_id}"
            with engine.begin() as conn:
                print(f"[filter-data] Creating schema {new_schema}")
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
                # create submissions and comments tables
                conn.execute(text(f"CREATE TABLE IF NOT EXISTS \"{new_schema}\".submissions (id text PRIMARY KEY, title text, selftext text)"))
                conn.execute(text(f"CREATE TABLE IF NOT EXISTS \"{new_schema}\".comments (id text PRIMARY KEY, body text)"))
                print(f"[filter-data] Created tables in schema {new_schema}")

                # insert submissions
                inserted_subs = 0
                total_subs = len(posts_list)
                print(f"[filter-data] Inserting {total_subs} submissions into {new_schema}.submissions")
                for item in posts_list:
                    try:
                        if not isinstance(item, dict):
                            continue
                        sid = str(item.get('id')) if item.get('id') is not None else None
                        title = item.get('title')
                        selftext = item.get('selftext')
                        if sid is None:
                            continue
                        conn.execute(text(f'INSERT INTO "{new_schema}".submissions (id, title, selftext) VALUES (:id, :title, :selftext)'), {"id": sid, "title": title, "selftext": selftext})
                        inserted_subs += 1
                    except Exception as ie:
                        print(f"[filter-data] Skipping invalid submission row: {ie}")

                print(f"[filter-data] Inserted {inserted_subs}/{total_subs} submissions")

                # insert comments
                inserted_comments = 0
                total_comments = len(comments_list)
                print(f"[filter-data] Inserting {total_comments} comments into {new_schema}.comments")
                for item in comments_list:
                    try:
                        cid = str(item.get('id')) if item.get('id') is not None else None
                        body = item.get('body')
                        if cid is None:
                            continue
                        conn.execute(text(f'INSERT INTO "{new_schema}".comments (id, body) VALUES (:id, :body)'), {"id": cid, "body": body})
                        inserted_comments += 1
                    except Exception as ie:
                        print(f"[filter-data] Skipping invalid comment row: {ie}")

                print(f"[filter-data] Inserted {inserted_comments}/{total_comments} comments")

            # create project row and metadata if user authenticated
            if user_id:
                try:
                    print(f"[filter-data] Creating project metadata for schema {new_schema} (user={user_id})")
                    with DatabaseManager() as dm:
                        proj = dm.projects.create(user_id=uuid.UUID(user_id), display_name=name or new_schema, schema_name=new_schema, project_type='filtered_data')
                        print(f"[filter-data] Created project id={proj.id} schema={proj.schema_name}")
                        try:
                            dm.project_tables.add_table_metadata(project_id=proj.id, table_name='submissions', row_count=len(posts_list))
                            print(f"[filter-data] Added project_tables entry for submissions (rows={len(posts_list)})")
                        except Exception as e:
                            print(f"[filter-data] Failed to add submissions table metadata: {e}")
                        try:
                            dm.project_tables.add_table_metadata(project_id=proj.id, table_name='comments', row_count=len(comments_list))
                            print(f"[filter-data] Added project_tables entry for comments (rows={len(comments_list)})")
                        except Exception as e:
                            print(f"[filter-data] Failed to add comments table metadata: {e}")
                except Exception as e:
                    print(f"[filter-data] Failed to create project metadata: {e}")

        except Exception as e:
            print(f"[filter-data] Failed to persist filtered results to Postgres: {e}")
            traceback.print_exc()

        return JSONResponse({
            "message": "Printed lengths and filter responses to server logs; persisted to schema",
            "submissions_length": len(submissions_text),
            "comments_length": len(comments_text),
            "posts_filtered_count": len(posts_list),
            "comments_filtered_count": len(comments_list),
            "project": {"id": str(proj.id), "schema_name": new_schema, "display_name": proj.display_name} if proj else None,
        })
    except Exception as exc:
        print(f"[filter-data] Error reading schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/generate-codebook/")
async def generate_codebook(request: Request, database: str = Form("original"), api_key: str = Form(...), prompt: str = Form(""), name: str = Form(...)):
    # Read a Postgres project schema, assemble submissions/comments into text, log it.
    schema = (database or "").strip()

    if not schema.startswith('proj_'):
        return JSONResponse({"error": "This endpoint currently expects a proj_<id> schema name"}, status_code=400)

    try:
        assembled = ""
        with engine.connect() as conn:
            # Check submissions table
            subs_tbl = f"{schema}.submissions"
            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": subs_tbl}).scalar()
            if subs_exists:
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."submissions"')).fetchall()
                for r in rows:
                    try:
                        title = r._mapping.get('title')
                        selftext = r._mapping.get('selftext')
                    except Exception:
                        title = r[0] if len(r) > 0 else ""
                        selftext = r[1] if len(r) > 1 else ""
                    assembled += f"Title: {title or ''}\n{selftext or ''}\n\n"
            else:
                print(f"[DEBUG] generate_codebook: submissions table not found in schema {schema}")

            # Check comments table
            comm_tbl = f"{schema}.comments"
            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": comm_tbl}).scalar()
            if comm_exists:
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."comments"')).fetchall()
                for r in rows:
                    try:
                        body = r._mapping.get('body')
                    except Exception:
                        body = r[0] if len(r) > 0 else ""
                    assembled += f"{body or ''}\n\n"
            else:
                print(f"[DEBUG] generate_codebook: comments table not found in schema {schema}")


        try:
            print("[INFO] generate_codebook: calling generate_codebook function")
            raw_out = generate_codebook_function(assembled, api_key, "", "", prompt)
            # handle coroutine or synchronous return
            if asyncio.iscoroutine(raw_out) or inspect.isawaitable(raw_out):
                codebook_output = await raw_out
            else:
                codebook_output = raw_out
        except Exception as e:
            print(f"Error generating codebook for schema {schema}: {e}")
            traceback.print_exc()
            return JSONResponse({"error": f"Generator failed: {e}"}, status_code=500)

        codebook_text = str(codebook_output or "")

        # Persist into a new Postgres project schema and create metadata
        try:
            # Require authentication to create the codebook project
            user_id = get_user_id_from_request(request)
            if not user_id:
                return JSONResponse({"error": "Authentication required to create project"}, status_code=401)

            # generate a unique schema name
            unique_id = str(uuid.uuid4()).replace('-', '')[:12]
            new_schema = f"proj_{unique_id}"

            with engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
                conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{new_schema}".content_store (file_text text)'))
                conn.execute(text(f'TRUNCATE TABLE "{new_schema}".content_store'))
                conn.execute(text(f'INSERT INTO "{new_schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": codebook_text})

            # create project row and table metadata
            with DatabaseManager() as dm:
                proj = dm.projects.create(user_id=uuid.UUID(user_id), display_name=name, schema_name=new_schema, project_type='codebook')
                dm.project_tables.add_table_metadata(project_id=proj.id, table_name='content_store', row_count=1)

            preview = codebook_text if len(codebook_text) <= 20000 else codebook_text[:20000] + "\n... (truncated)"
            return JSONResponse({"message": "Codebook generated and saved to project", "project": {"id": str(proj.id), "schema_name": new_schema, "display_name": proj.display_name}, "preview": preview})

        except Exception as exc:
            print(f"Error creating project/schema for generated codebook: {exc}")
            traceback.print_exc()
            return JSONResponse({"error": str(exc)}, status_code=500)
    except Exception as exc:
        print(f"Error reading Postgres schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/apply-codebook/")
async def apply_codebook(request: Request, database: str = Form(...), codebook: str = Form(...), methodology: str = Form(""), report_name: str = Form(None), api_key: str = Form(...)):
    """Open the Postgres schema provided by `database`, read `submissions.title`/`selftext`
    and `comments.body`, assemble them into a single string, print it to stdout and
    return a preview in the response.
    """
    schema = (database or "").strip()
    if schema.endswith('.db'):
        schema = schema[:-3]

    if not schema or not schema.startswith('proj_'):
        return JSONResponse({"error": "This endpoint expects a proj_<id> schema name"}, status_code=400)

    assembled = ""
    try:
        with engine.connect() as conn:
            # Submissions
            subs_tbl = f"{schema}.submissions"
            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": subs_tbl}).scalar()
            if subs_exists:
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."submissions"')).fetchall()
                for r in rows:
                    try:
                        title = r._mapping.get('title')
                        selftext = r._mapping.get('selftext')
                    except Exception:
                        title = r[0] if len(r) > 0 else ""
                        selftext = r[1] if len(r) > 1 else ""
                    assembled += f"Title: {title or ''}\n{selftext or ''}\n\n"
            else:
                # submissions table missing — proceed with whatever content was found
                pass

            # Comments
            comm_tbl = f"{schema}.comments"
            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": comm_tbl}).scalar()
            if comm_exists:
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."comments"')).fetchall()
                for r in rows:
                    try:
                        body = r._mapping.get('body')
                    except Exception:
                        body = r[0] if len(r) > 0 else ""
                    assembled += f"{body or ''}\n\n"
            else:
                # comments table missing — proceed
                pass


        cb_schema_raw = (codebook or "").strip()
        codebook_text = ""
        try:
            # provided codebook identifier (no stdout prints)

            resolved_schema = None
            if cb_schema_raw and cb_schema_raw.startswith('proj_'):
                resolved_schema = cb_schema_raw
            else:
                # Try to interpret the provided value as a Project.id (UUID) and resolve schema_name
                try:
                    pid = uuid.UUID(cb_schema_raw)
                    db_sess = SessionLocal()
                    try:
                        proj = db_sess.query(Project).filter(Project.id == pid).first()
                        if proj:
                            resolved_schema = proj.schema_name
                    finally:
                        try:
                            db_sess.close()
                        except Exception:
                            pass
                except Exception:
                    # not a UUID / could not resolve
                    resolved_schema = None

            if resolved_schema:
                with engine.connect() as conn:
                    tbl_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{resolved_schema}.content_store"}).scalar()
                    if tbl_exists:
                        res = conn.execute(text(f'SELECT file_text FROM "{resolved_schema}".content_store LIMIT 1'))
                        row = res.fetchone()
                        codebook_text = row[0] if row else ""
                    else:
                        pass
            else:
                pass
        except Exception:
            pass

        # Attempt classification using the provided codebook and API key
        classification_output = ""
        try:
            if codebook_text and api_key:
                classification_output = classify_posts(codebook_text, assembled, methodology or "", api_key)
            else:
                classification_output = "API request error"
        except Exception:
            classification_output = "API request error"

        # resolve auth (optional)
        user_id = get_user_id_from_request(request)
        if user_id:
            provided_name = (report_name or "").strip()
            display_name = provided_name if provided_name else 'coding'

            unique_id = str(uuid.uuid4()).replace('-', '')[:12]
            new_schema = f"proj_{unique_id}"
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
                    conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{new_schema}".content_store (file_text text)'))
                    conn.execute(text(f'TRUNCATE TABLE "{new_schema}".content_store'))
                    conn.execute(text(f'INSERT INTO "{new_schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": classification_output})

                    # create project row and table metadata
                    with DatabaseManager() as dm:
                        proj = dm.projects.create(user_id=uuid.UUID(user_id), display_name=display_name, schema_name=new_schema, project_type='coding')
                        dm.project_tables.add_table_metadata(project_id=proj.id, table_name='content_store', row_count=1)
            except Exception as e:
                    print(f"Failed to persist classification project/schema: {e}")
        

        return JSONResponse({"classification_output": classification_output})
    except Exception as exc:
        print(f"Error reading schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/comments/{submission_id}") 
async def get_comments_for_submission(submission_id: str, database: str = Query("original")):
    """Fetch all comments for a specific submission from a Postgres project schema.

    The `database` parameter should provide a Postgres project schema name (e.g. proj_xxx).
    A trailing `.db` is tolerated and will be stripped. Returns 404 if the schema or
    comments table is not present.
    """
    schema = (database or "").strip()

    if not schema or not schema.startswith('proj_'):
        return JSONResponse({"error": "This endpoint expects a proj_<id> schema name in 'database'"}, status_code=400)

    try:
        with engine.connect() as conn:
            # Verify comments table exists in the schema
            tbl = f"{schema}.comments"
            tbl_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": tbl}).scalar()
            if not tbl_exists:
                return JSONResponse({"error": f"Comments table not found in schema {schema}"}, status_code=404)

            # Fetch rows where link_id matches submission_id
            q = text(f'SELECT * FROM "{schema}"."comments" WHERE link_id = :link ORDER BY created_utc ASC')
            rows = conn.execute(q, {"link": submission_id}).fetchall()
            comments = [dict(r._mapping) for r in rows]

            return JSONResponse({"comments": comments})

    except Exception as exc:
        print(f"Error reading comments from schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)
