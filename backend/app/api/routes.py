import os
import sqlite3
import json
import tempfile
import traceback
import asyncio
import inspect
from pathlib import Path
from fastapi import APIRouter, File as FastAPIFile, HTTPException, UploadFile, Form, Query, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

import hashlib
import binascii
import secrets
from datetime import datetime

import pandas as pd
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi import Request

try:
    from app.database import get_db, User, Prompt, Project, File, FileTable, engine, SessionLocal
    from app.databasemanager import DatabaseManager
    from app.auth import create_access_token, decode_access_token
    from app.config import settings

    from scripts.import_db import stream_zst_to_postgres
    from scripts.filter_db import filter_posts_with_ai, filter_comments_with_ai
    from scripts.codebook_generator import (
        generate_codebook as generate_codebook_function,
        compare_agreement as compare_agreement_function,
        get_client as codebook_get_client,
        MODEL_1,
        MODEL_2,
        MODEL_3,
    )
    from scripts.codebook_apply import classify_posts
    from scripts.display_codebook import parse_codebook_to_json
    from app.services import migrate_sqlite_file
except:
    try:
        from backend.app.database import get_db, User, Prompt, Project, File, FileTable, engine, SessionLocal
        from backend.app.databasemanager import DatabaseManager
        from backend.app.auth import create_access_token, decode_access_token
        from backend.app.config import settings

        from backend.scripts.import_db import stream_zst_to_postgres
        from backend.scripts.filter_db import filter_posts_with_ai, filter_comments_with_ai
        from backend.scripts.codebook_generator import (
            generate_codebook as generate_codebook_function,
            compare_agreement as compare_agreement_function,
            get_client as codebook_get_client,
            MODEL_1,
            MODEL_2,
            MODEL_3,
        )
        from backend.scripts.codebook_apply import classify_posts
        from backend.scripts.display_codebook import parse_codebook_to_json
        from backend.app.services import migrate_sqlite_file
    except Exception as exc:
        print("Failed", exc)
        raise exc

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
    unique_id = secrets.token_hex(6)
    schema_name = f"proj_{unique_id}"
    inserted_counts = {"submissions": 0, "comments": 0}

    try:
        with DatabaseManager() as dm:
            # Create a File record instead of a Project; files back a Postgres schema
            file_rec = File(user_id=int(user_id), filename=base_name, schemaname=schema_name, file_type="raw_data", description=(description or None))
            dm.session.add(file_rec)
            try:
                dm.session.flush()
            except Exception:
                dm.session.rollback()
                raise
            # If a project_id was provided, ensure ownership and link the file to the project
            if project_id is not None:
                try:
                    proj = dm.session.query(Project).filter(Project.id == int(project_id)).first()
                    if proj is None:
                        raise HTTPException(status_code=404, detail="Project not found")
                    # ensure the project belongs to the authenticated user
                    try:
                        uid = int(user_id)
                    except Exception:
                        uid = None
                    if proj.user_id != uid:
                        raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")
                    # create association
                    file_rec.projects.append(proj)
                    dm.session.flush()
                except HTTPException:
                    raise
                except Exception:
                    # If anything goes wrong with linking, roll back and continue without linking
                    dm.session.rollback()
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

            # add file_tables metadata
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
async def merge_databases(request: Request):
    # Accept either form-data (`databases` as JSON string) or application/json
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

        # Normalize databases into a list
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

    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required to merge databases")

    # ensure user doesn't already have a file with same filename/schemaname
    db_check = SessionLocal()
    try:
        existing = db_check.query(File).filter(
            File.user_id == int(user_id),
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
            # Only support Postgres file schema sources (proj_...)
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
                        tmp_name = f"tmp_merge_{secrets.token_hex(4)}"

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
            return JSONResponse({"message": "No rows found in selected databases; nothing migrated", "database": name, "total_submissions": 0, "total_comments": 0, "file_migrated": False})

        # Create file record and file_tables metadata using the final counts
        with DatabaseManager() as dm:
            file_rec = File(user_id=int(user_id), filename=name, schemaname=schema_name, file_type='raw_data', description=(description or None))
            dm.session.add(file_rec)
            try:
                dm.session.flush()
            except Exception:
                dm.session.rollback()
                raise
            for tbl, cnt in final_table_counts.items():
                dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name=tbl, row_count=cnt)
            # If a project_id was provided, attempt to link the created file to the project
            if project_id is not None:
                try:
                    # project_id may be a string when coming from form-data
                    pid = int(project_id)
                    proj = dm.session.query(Project).filter(Project.id == pid).first()
                    if proj is None:
                        raise HTTPException(status_code=404, detail="Project not found")
                    try:
                        uid = int(user_id)
                    except Exception:
                        uid = None
                    if proj.user_id != uid:
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
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_password(user.hashed_password, payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    resp = JSONResponse({"id": str(user.id), "email": user.email, "access_token": token})
    max_age = int(settings.jwt_access_token_expire_minutes) * 60
    resp.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=max_age)
    return resp


@router.post("/register/")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    # Check if email already exists
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = _hash_password(payload.password)

    # let DB assign integer primary key
    user = User(email=payload.email, hashed_password=hashed)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    token = create_access_token({"sub": str(user.id), "email": user.email})
    resp = JSONResponse({"id": str(user.id), "email": user.email, "access_token": token})
    max_age = int(settings.jwt_access_token_expire_minutes) * 60
    resp.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=max_age)
    return resp


@router.get("/me/")
def me(request: Request, db: Session = Depends(get_db)):
    # Use token helper to get the user id; then return user record
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return JSONResponse({"id": str(user.id), "email": user.email})


@router.get("/my-files/")
def my_projects(request: Request, file_type: str = Query("raw_data"), db: Session = Depends(get_db)):
    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Use File table instead of Project; `file_type` query param maps to `file_type` on File
    files = db.query(File).filter(File.user_id == int(user_id), File.file_type == file_type).all()
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

        result.append({
            "id": str(p.id),
            "display_name": p.filename,
            "description": p.description,
            "schema_name": p.schemaname,
            "file_type": p.file_type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "tables": tables,
        })

    # Return under the legacy "projects" key so frontend code expecting
    # `data.projects` continues to work.
    return JSONResponse({"projects": result})


@router.post("/create-project/")
def create_project(request: Request, name: str = Form(...), description: str = Form(None), db: Session = Depends(get_db)):
    """Create a new Project owned by the authenticated user.

    Returns the created project object.
    """
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    # create project record (no schema_name column in DB)
    proj = Project(user_id=uid, projectname=name.strip(), description=(description or None))
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
    """Update an existing project owned by the authenticated user."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    # load project
    proj = db.query(Project).filter(Project.id == int(project_id)).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.user_id != uid:
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
    """List projects owned by the authenticated user."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    with DatabaseManager() as dm:
        rows = dm.projects.get_all_for_user(uid)
        result = []
        for r in rows:
            # Include associated files (databases) for each project
            files = []
            try:
                for f in getattr(r, "files", []) or []:
                    files.append({
                        "id": str(f.id),
                        "display_name": f.filename,
                        "schema_name": f.schemaname,
                        "file_type": f.file_type,
                        "description": f.description,
                        "created_at": f.created_at.isoformat() if f.created_at else None,
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


@router.get("/prompts/")
def list_prompts(request: Request, prompt_type: str = Query(None), db: Session = Depends(get_db)):
    """List prompts belonging to the authenticated user. Optional `prompt_type` filters by `type`."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        try:
            uid = int(user_id)
        except Exception:
            uid = None
        q = db.query(Prompt).filter(Prompt.user_id == uid)
    except Exception:
        try:
            uid = int(user_id)
        except Exception:
            uid = None
        q = db.query(Prompt).filter(Prompt.user_id == uid)

    if prompt_type:
        q = q.filter(Prompt.type == prompt_type)

    rows = q.all()
    result = []
    for r in rows:
        result.append({
            "id": int(r.id),
            "user_id": int(r.user_id) if r.user_id is not None else None,
            "promptname": r.promptname,
            "prompt": r.prompt,
            "type": r.type,
        })

    return JSONResponse({"prompts": result})


@router.post("/prompts/")
async def create_prompt(request: Request, db: Session = Depends(get_db)):
    """Create a new prompt for the authenticated user.

    This endpoint accepts either multipart/form-data or application/json. It
    validates required fields and returns clear 400 responses instead of the
    default 422 when the client sends an unexpected payload shape.
    """
    # Read raw body for debugging and parse payload (form or json)
    try:
        raw_body = await request.body()
    except Exception:
        raw_body = b""

    content_type = (request.headers.get("content-type") or "").lower()
    data = {}
    try:
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            # convert FormData to a simple dict
            data = {k: form.get(k) for k in form.keys()}
    except Exception:
        data = {}

    display_name = data.get("display_name") or data.get("promptname")
    prompt_val = data.get("prompt")
    ptype = data.get("type")
    user_id = data.get("user_id")

    # Validate required fields and provide a helpful error message
    missing = [k for k, v in [("display_name", display_name), ("prompt", prompt_val), ("type", ptype)] if not (v or (isinstance(v, str) and v == "")) and v is None]
    if not display_name or not prompt_val or not ptype:
        # Log helpful debug info to server stdout for diagnosis
        try:
            _ct = request.headers.get("content-type")
            _auth = request.headers.get("authorization")
            _cookie = request.headers.get("cookie")
            print("[create_prompt] Missing fields. content-type:", _ct)
            print("[create_prompt] Parsed data:", data)
            snippet = raw_body[:4000]
            try:
                print("[create_prompt] Raw body snippet:", snippet.decode(errors="replace"))
            except Exception:
                print("[create_prompt] Raw body (bytes):", repr(snippet))
            print("[create_prompt] Authorization present:", bool(_auth), " Cookie present:", bool(_cookie))
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Missing required fields: display_name, prompt, type")

    # If `user_id` was not provided, resolve via the authenticated token
    if not user_id:
        try:
            user_resp = me(request, db)
        except HTTPException as he:
            raise he
        except Exception:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            import json as _json

            if isinstance(user_resp, JSONResponse):
                payload = _json.loads(user_resp.body)
            else:
                payload = dict(user_resp)
            user_id = payload.get("id") or payload.get("sub")
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to resolve user identity")

    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    new = Prompt(user_id=uid, promptname=display_name, prompt=prompt_val, type=ptype)
    db.add(new)
    try:
        db.commit()
        db.refresh(new)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"id": int(new.id), "user_id": int(new.user_id), "promptname": new.promptname, "prompt": new.prompt, "type": new.type})


@router.post("/prompts/{prompt_id}/update")
def update_prompt(prompt_id: int, request: Request, display_name: str = Form(None), promptname: str = Form(None), prompt: str = Form(None), type: str = Form(None), db: Session = Depends(get_db)):
    """Update a prompt owned by the authenticated user."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    p = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # ensure ownership
    try:
        owner_id = int(p.user_id)
    except Exception:
        owner_id = p.user_id
    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    if owner_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")

    # accept either `display_name` (legacy) or `promptname` (canonical)
    new_name = promptname if (promptname is not None) else display_name
    if new_name is not None:
        p.promptname = new_name
    if prompt is not None:
        p.prompt = prompt
    if type is not None:
        p.type = type

    try:
        db.commit()
        db.refresh(p)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"id": int(p.id), "user_id": int(p.user_id), "promptname": p.promptname, "prompt": p.prompt, "type": p.type})


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a prompt owned by the authenticated user."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    p = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prompt not found")
    # ensure ownership: Prompt.user_id should be integer referencing User.id
    try:
        owner_id = int(p.user_id) if p.user_id is not None else None
    except Exception:
        owner_id = p.user_id
    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    if owner_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        db.delete(p)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"deleted": True, "id": int(p.id)})


@router.delete("/delete-database/{db_name}")
async def delete_database(db_name: str, request: Request, db: Session = Depends(get_db)):
    schema = db_name.strip()

    if not schema.startswith('proj_'):
        raise HTTPException(status_code=400, detail="Invalid file schema identifier")

    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == int(user_id)).first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File not found or you do not have permission")

    try:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

        db.delete(file_rec)
        db.commit()
        return JSONResponse({"message": f"File '{file_rec.filename}' and schema '{schema}' deleted"})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete file/schema: {str(e)}")


@router.post("/delete-row/")
async def delete_row(request: Request, schema: str = Form(...), table: str = Form(...), row_id: str = Form(...), db: Session = Depends(get_db)):
    """Delete a single row (by id) from a file's table (submissions or comments).

    Requires authentication and file ownership.
    """
    schema = (schema or "").strip()
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
        file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == int(user_id)).first()
        if not file_rec:
            return JSONResponse({"error": "File not found or not owned by user"}, status_code=403)

        with engine.begin() as conn:
            res = conn.execute(text(f'DELETE FROM "{schema}"."{table}" WHERE id = :id'), {"id": row_id})
            try:
                deleted = int(res.rowcount or 0)
            except Exception:
                deleted = 0

        # Update file_tables metadata: recount rows and persist
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
    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # normalize schema name
    schema = schema_name.strip()

    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == int(user_id)).first()
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
    """Move rows from one file schema to another. Expects JSON body:
    {"source_schema": "proj_x", "target_schema": "proj_y", "table": "submissions", "row_ids": [..]}
    Requires authentication and ownership of both files.
    """
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
        file_src = db.query(File).filter(File.schemaname == source, File.user_id == int(user_id)).first()
        file_tgt = db.query(File).filter(File.schemaname == target, File.user_id == int(user_id)).first()
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


@router.post("/logout/")
def logout():
    resp = JSONResponse({"message": "Logged out"})
    # clear the HttpOnly cookie by setting an expired cookie
    resp.set_cookie("access_token", "", httponly=True, samesite="lax", max_age=0)
    return resp


@router.get("/codebook")
async def get_codebook(codebook_id: str = Query(None), db: Session = Depends(get_db)):
    """Return a codebook stored in a File record with file_type='codebook'.
    """
    # First try to find a matching file (by schemaname or filename or id)
    file_rec = None
    if codebook_id:
        # try schemaname match
        file_rec = db.query(File).filter(File.file_type == 'codebook', File.schemaname == codebook_id).first()
        if not file_rec:
            # try filename match
            file_rec = db.query(File).filter(File.file_type == 'codebook', File.filename == codebook_id).first()
        if not file_rec:
            # try id match (integer)
            try:
                fid = int(codebook_id)
                file_rec = db.query(File).filter(File.file_type == 'codebook', File.id == fid).first()
            except Exception:
                file_rec = None
    else:
        # No id supplied: pick latest codebook file if any
        file_rec = db.query(File).filter(File.file_type == 'codebook').order_by(File.created_at.desc()).first()

    if file_rec:
        schema = file_rec.schemaname
        try:
            with engine.connect() as conn:
                res = conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
                row = res.fetchone()
                if row:
                    return JSONResponse({"codebook": row[0]})
                else:
                    return JSONResponse({"error": "Codebook content not found in file"}, status_code=404)
        except Exception as e:
            print(f"Error reading codebook from schema {schema}: {e}")
            return JSONResponse({"error": f"Error reading codebook: {e}"}, status_code=500)

    return JSONResponse({"error": "No codebook file found"}, status_code=404)


@router.get("/parse-codebook")
async def parse_codebook(codebook_id: str = Query(None), db: Session = Depends(get_db)):
    """Return a parsed JSON structure for a codebook file using the display_codebook helper.
    The response will be { "parsed": [ ... ] } where parsed is an array of families with codes.
    """
    file_rec = None
    if codebook_id:
        file_rec = db.query(File).filter(File.file_type == 'codebook', File.schemaname == codebook_id).first()
        if not file_rec:
            file_rec = db.query(File).filter(File.file_type == 'codebook', File.filename == codebook_id).first()
        if not file_rec:
            try:
                fid = int(codebook_id)
                file_rec = db.query(File).filter(File.file_type == 'codebook', File.id == fid).first()
            except Exception:
                file_rec = None
    else:
        file_rec = db.query(File).filter(File.file_type == 'codebook').order_by(File.created_at.desc()).first()

    if not file_rec:
        return JSONResponse({"error": "No codebook file found"}, status_code=404)

    schema = file_rec.schemaname
    try:
        with engine.connect() as conn:
            res = conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
            row = res.fetchone()
            if not row:
                return JSONResponse({"error": "Codebook content not found in file"}, status_code=404)
            raw = row[0] or ""
            try:
                parsed_text = parse_codebook_to_json(raw)
                parsed_obj = json.loads(parsed_text)
                return JSONResponse({"parsed": parsed_obj})
            except Exception as e:
                return JSONResponse({"error": f"Failed to parse codebook: {e}", "raw": raw}, status_code=500)
    except Exception as e:
        print(f"Error reading codebook from schema {schema}: {e}")
        return JSONResponse({"error": f"Error reading codebook: {e}"}, status_code=500)


@router.get("/list-codebooks")
async def list_codebooks(db: Session = Depends(get_db)):
    # Only return DB-backed codebook files
    codebooks = []
    try:
        files = db.query(File).filter(File.file_type == 'codebook').all()
        for p in files:
            codebooks.append({
                "id": str(p.id),
                "name": p.filename,
                "metadata": {"schema": p.schemaname, "created_at": p.created_at.isoformat() if p.created_at else None},
                "description": p.description,
                "source": "file",
            })
    except Exception:
        return JSONResponse({"codebooks": []})

    codebooks.sort(key=lambda x: x.get("name") or x.get("id"))
    return JSONResponse({"codebooks": codebooks})


@router.post("/save-file-codebook/")
async def save_project_codebook(request: Request, schema_name: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    """Save codebook content into a Postgres file schema's content_store table.
    Requires authentication and file ownership.
    """
    # Resolve authenticated user from token
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    schema = schema_name.strip()

    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == int(user_id)).first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File/project not found or you do not have permission")

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
            # Ensure the project's Postgres schema exists before creating tables
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{schema}".content_store (file_text text)'))
            # Remove existing rows and insert the new content (single-row store)
            conn.execute(text(f'TRUNCATE TABLE "{schema}".content_store'))
            conn.execute(text(f'INSERT INTO "{schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": content})

        # If a display_name was provided, update the file record
        if display_name:
            file_rec.filename = display_name
            try:
                db.commit()
                db.refresh(file_rec)
            except Exception as exc:
                db.rollback()
                print(f"Failed to update file filename for {schema}: {exc}")

        return JSONResponse({"message": "File codebook saved", "id": str(file_rec.id), "display_name": file_rec.filename})
    except Exception as e:
        print(f"Error saving file codebook to schema {schema}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/coded-data")
async def get_coded_data_query(coded_id: str = Query(None), db: Session = Depends(get_db)):
    """Return coded data stored in a File record with file_type='coding'.
    """
    file_rec = None
    if coded_id:
        file_rec = db.query(File).filter(File.file_type == 'coding', File.schemaname == coded_id).first()
        if not file_rec:
            file_rec = db.query(File).filter(File.file_type == 'coding', File.filename == coded_id).first()
        if not file_rec:
            try:
                fid = int(coded_id)
                file_rec = db.query(File).filter(File.file_type == 'coding', File.id == fid).first()
            except Exception:
                file_rec = None
    else:
        file_rec = db.query(File).filter(File.file_type == 'coding').order_by(File.created_at.desc()).first()

    if file_rec:
        schema = file_rec.schemaname
        try:
            with engine.connect() as conn:
                tbl_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.content_store"}).scalar()
                if not tbl_exists:
                    return JSONResponse({"error": f"content_store table not found in schema {schema}"}, status_code=404)
                res = conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
                row = res.fetchone()
                if row:
                    return JSONResponse({"coded_data": row[0]})
                else:
                    return JSONResponse({"error": "Coded data content not found in file"}, status_code=404)
        except Exception as e:
            print(f"Error reading coded data from schema {schema}: {e}")
            return JSONResponse({"error": f"Error reading coded data: {e}"}, status_code=500)

    return JSONResponse({"error": "No coded data file found"}, status_code=404)


@router.post("/save-file-coded-data/")
async def save_project_coded_data(request: Request, schema_name: str = Form(None), content: str = Form(None), db: Session = Depends(get_db)):
    """Save coded content into a Postgres file-backed schema's content_store table for file_type 'coding'.
    Requires authentication and ownership.
    Accepts JSON or form-data with `schema_name` and `content`.
    """
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Support JSON body as well as form-data
    try:
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            body = await request.json()
            schema_name = body.get("schema_name")
            content = body.get("content")
            display_name = body.get("display_name")
        else:
            form = await request.form()
            if schema_name is None:
                schema_name = form.get("schema_name")
            if content is None:
                content = form.get("content")
            display_name = form.get("display_name") if "display_name" in form else None
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not schema_name or not content:
        raise HTTPException(status_code=400, detail="schema_name and content are required")

    schema = schema_name.strip()
    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == int(user_id), File.file_type == 'coding').first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File/project not found or you do not have permission")

    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{schema}".content_store (file_text text)'))
            conn.execute(text(f'TRUNCATE TABLE "{schema}".content_store'))
            conn.execute(text(f'INSERT INTO "{schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": content})

        if display_name:
            file_rec.filename = display_name
            try:
                db.commit()
                db.refresh(file_rec)
            except Exception:
                db.rollback()

        return JSONResponse({"message": "File coded data saved", "id": str(file_rec.id), "filename": file_rec.filename})
    except Exception as e:
        print(f"Error saving file coded data to schema {schema}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/file-entries/")
def project_entries(schema: str = Query(..., description="File schema name"), limit: int = 10, offset: int = 0):
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
                rows = conn.execute(text(f"SELECT * FROM {schema}.submissions ORDER BY id LIMIT :lim OFFSET :off"), {"lim": limit, "off": max(0, offset)}).fetchall()
                submissions = [dict(r._mapping) for r in rows]

            if comm_exists:
                com_count = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.comments")).scalar() or 0
                rows = conn.execute(text(f"SELECT * FROM {schema}.comments ORDER BY id LIMIT :lim OFFSET :off"), {"lim": limit, "off": max(0, offset)}).fetchall()
                comments = [dict(r._mapping) for r in rows]

    except Exception as exc:
        return JSONResponse({
            "submissions": [],
            "comments": [],
            "total_submissions": 0,
            "total_comments": 0,
            "message": f"Error reading file schema: {exc}"
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
    """Read a Postgres file schema (provided in `database`), assemble submissions and comments,
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
        file_rec = None
        try:
            unique_id = secrets.token_hex(6)
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
                        try:
                            # Use a nested transaction (savepoint) so a single bad row
                            # does not abort the outer transaction.
                            with conn.begin_nested():
                                conn.execute(
                                    text(f'INSERT INTO "{new_schema}".submissions (id, title, selftext) VALUES (:id, :title, :selftext)'),
                                    {"id": sid, "title": title, "selftext": selftext},
                                )
                            inserted_subs += 1
                        except Exception as ie:
                            print(f"[filter-data] Skipping invalid submission row (savepoint rollback): {ie}")
                            # continue to next item
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
                        try:
                            with conn.begin_nested():
                                conn.execute(
                                    text(f'INSERT INTO "{new_schema}".comments (id, body) VALUES (:id, :body)'),
                                    {"id": cid, "body": body},
                                )
                            inserted_comments += 1
                        except Exception as ie:
                            print(f"[filter-data] Skipping invalid comment row (savepoint rollback): {ie}")
                            # continue to next item
                    except Exception as ie:
                        print(f"[filter-data] Skipping invalid comment row: {ie}")

                print(f"[filter-data] Inserted {inserted_comments}/{total_comments} comments")

            # create file row and metadata if user authenticated
            if user_id:
                try:
                    print(f"[filter-data] Creating file metadata for schema {new_schema} (user={user_id})")
                    with DatabaseManager() as dm:
                        file_rec = File(user_id=int(user_id), filename=name or new_schema, schemaname=new_schema, file_type='filtered_data')
                        dm.session.add(file_rec)
                        dm.session.flush()
                        try:
                            dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='submissions', row_count=len(posts_list))
                            print(f"[filter-data] Added file_tables entry for submissions (rows={len(posts_list)})")
                        except Exception as e:
                            print(f"[filter-data] Failed to add submissions table metadata: {e}")
                        try:
                            dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='comments', row_count=len(comments_list))
                            print(f"[filter-data] Added file_tables entry for comments (rows={len(comments_list)})")
                        except Exception as e:
                            print(f"[filter-data] Failed to add comments table metadata: {e}")
                except Exception as e:
                    print(f"[filter-data] Failed to create file metadata: {e}")

        except Exception as e:
            print(f"[filter-data] Failed to persist filtered results to Postgres: {e}")
            traceback.print_exc()

        return JSONResponse({
            "message": "Database filtered and saved",
            "submissions_length": len(submissions_text),
            "comments_length": len(comments_text),
            "posts_filtered_count": len(posts_list),
            "comments_filtered_count": len(comments_list),
            "file": {"id": str(file_rec.id), "schema_name": new_schema, "filename": file_rec.filename} if file_rec else None,
        })
    except Exception as exc:
        print(f"[filter-data] Error reading schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/generate-codebook/")
async def generate_codebook(request: Request, database: str = Form("original"), api_key: str = Form(...), prompt: str = Form(""), name: str = Form(...), description: str = Form(None), project_id: int = Form(None)):
    # Read a Postgres file schema, assemble submissions/comments into text, log it.
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
            print("[INFO] generate_codebook: calling generate_codebook function for MODEL_1")
            raw_out = generate_codebook_function(assembled, api_key, "", "", prompt, MODEL=MODEL_1)
            codebook_text = await raw_out if asyncio.iscoroutine(raw_out) or inspect.isawaitable(raw_out) else raw_out
        except Exception as e:
            print(f"Error generating codebook for schema {schema}: {e}")
            traceback.print_exc()
            return JSONResponse({"error": f"Generator failed: {e}"}, status_code=500)

        codebook_text = str(codebook_text or "")

        # Persist into a new Postgres file schema and create metadata
        try:
            # Require authentication to create the codebook file
            user_id = get_user_id_from_request(request)
            if not user_id:
                return JSONResponse({"error": "Authentication required to create file"}, status_code=401)

            # generate a unique schema name
            unique_id = secrets.token_hex(6)
            new_schema = f"proj_{unique_id}"

            with engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
                conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{new_schema}".content_store (file_text text)'))
                conn.execute(text(f'TRUNCATE TABLE "{new_schema}".content_store'))
                conn.execute(text(f'INSERT INTO "{new_schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": codebook_text})

            # Persist provided description (do not append agreement percent)
            final_description = (description or "").strip() if description is not None else None
            if final_description == "":
                final_description = None

            # create file record and file_tables metadata
            with DatabaseManager() as dm:
                file_rec = File(user_id=int(user_id), filename=name, schemaname=new_schema, file_type='codebook', description=final_description)
                dm.session.add(file_rec)
                dm.session.flush()
                dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='content_store', row_count=1)

                # If a project_id was provided, ensure ownership and link the file to the project
                if project_id is not None:
                    try:
                        proj = dm.session.query(Project).filter(Project.id == int(project_id)).first()
                        if proj is None:
                            raise HTTPException(status_code=404, detail="Project not found")
                        # ensure the project belongs to the authenticated user
                        try:
                            uid = int(user_id)
                        except Exception:
                            uid = None
                        if proj.user_id != uid:
                            raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")
                        # create association
                        file_rec.projects.append(proj)
                        dm.session.flush()
                    except HTTPException:
                        raise
                    except Exception:
                        # If anything goes wrong with linking, roll back and continue without linking
                        dm.session.rollback()

            resp_payload = {
                "codebook": codebook_text,
                "file": {"id": str(file_rec.id), "schema_name": new_schema, "filename": file_rec.filename, "description": file_rec.description},
            }
            return JSONResponse(resp_payload)

        except Exception as exc:
            print(f"Error creating file/schema for generated codebook: {exc}")
            traceback.print_exc()
            return JSONResponse({"error": str(exc)}, status_code=500)
    except Exception as exc:
        print(f"Error reading Postgres schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)



@router.post("/compare-codebooks/")
async def compare_codebooks(request: Request, codebook_a: str = Form(...), codebook_b: str = Form(...), api_key: str = Form(...), model: str = Form(None)):
    """Compare two codebooks stored in Postgres schemas by calling the LLM and return the full message."""
    schema_a = (codebook_a or "").strip()
    schema_b = (codebook_b or "").strip()

    if not schema_a.startswith("proj_") or not schema_b.startswith("proj_"):
        return JSONResponse({"error": "schema names must be proj_<id>"}, status_code=400)

    if not api_key:
        return JSONResponse({"error": "api_key is required"}, status_code=400)

    try:
        with engine.connect() as conn:
            a_row = conn.execute(text(f'SELECT file_text FROM "{schema_a}".content_store LIMIT 1')).fetchone()
            b_row = conn.execute(text(f'SELECT file_text FROM "{schema_b}".content_store LIMIT 1')).fetchone()

        text_a = (a_row[0] if a_row else "") or ""
        text_b = (b_row[0] if b_row else "") or ""

        if not text_a and not text_b:
            return JSONResponse({"error": "No content found in either codebook"}, status_code=400)

        # Compose prompts
        system_prompt = (
            "You are an expert qualitative researcher. Compare the two provided codebooks.\n"
            "Provide a clear, structured comparison including:\n"
            "- Major similarities and differences\n"
            "- Conflicting or duplicate codes\n"
            "- Suggestions for merging or refining codes\n"
            "- An overall recommendation and confidence level.\n"
            "Return the full comparison as text (no extra JSON or metadata)."
        )

        user_prompt = f"Codebook A:\n{text_a}\n\n---\n\nCodebook B:\n{text_b}\n\nPlease compare them in detail."

        # choose model if provided, otherwise use MODEL_3 if available
        chosen_model = model or MODEL_3

        resp = codebook_get_client(system_prompt, user_prompt, api_key, chosen_model)
        return JSONResponse({"comparison": resp})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)



@router.post("/compare-codings/")
async def compare_codings(request: Request, coding_a: str = Form(...), coding_b: str = Form(...), api_key: str = Form(...), model: str = Form(None)):
    """Compare two coding outputs stored in Postgres schemas by calling the LLM and return the full message."""
    schema_a = (coding_a or "").strip()
    schema_b = (coding_b or "").strip()

    if not schema_a.startswith("proj_") or not schema_b.startswith("proj_"):
        return JSONResponse({"error": "schema names must be proj_<id>"}, status_code=400)

    if not api_key:
        return JSONResponse({"error": "api_key is required"}, status_code=400)

    try:
        with engine.connect() as conn:
            a_row = conn.execute(text(f'SELECT file_text FROM "{schema_a}".content_store LIMIT 1')).fetchone()
            b_row = conn.execute(text(f'SELECT file_text FROM "{schema_b}".content_store LIMIT 1')).fetchone()

        text_a = (a_row[0] if a_row else "") or ""
        text_b = (b_row[0] if b_row else "") or ""

        if not text_a and not text_b:
            return JSONResponse({"error": "No content found in either coding"}, status_code=400)

        system_prompt = (
            "You are an expert qualitative researcher. Compare the two provided coded datasets.\n"
            "Provide a clear, structured comparison including:\n"
            "- Major overlaps and divergences in coding decisions\n"
            "- Instances where codes appear inconsistent or misapplied\n"
            "- Suggestions for reconciliation or re-labeling\n"
            "- An overall recommendation and confidence level.\n"
            "Return the full comparison as text (no extra JSON or metadata)."
        )

        user_prompt = f"Coding A:\n{text_a}\n\n---\n\nCoding B:\n{text_b}\n\nPlease compare them in detail."

        chosen_model = model or MODEL_3

        resp = codebook_get_client(system_prompt, user_prompt, api_key, chosen_model)
        return JSONResponse({"comparison": resp})
    except Exception as exc:
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
                # Try to interpret the provided value as a File.id (integer) and resolve schemaname
                try:
                    fid = int(cb_schema_raw)
                    db_sess = SessionLocal()
                    try:
                        f = db_sess.query(File).filter(File.id == fid).first()
                        if f:
                            resolved_schema = f.schemaname
                    finally:
                        try:
                            db_sess.close()
                        except Exception:
                            pass
                except Exception:
                    # not an integer / could not resolve
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

            unique_id = secrets.token_hex(6)
            new_schema = f"proj_{unique_id}"
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
                    conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{new_schema}".content_store (file_text text)'))
                    conn.execute(text(f'TRUNCATE TABLE "{new_schema}".content_store'))
                    conn.execute(text(f'INSERT INTO "{new_schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": classification_output})

                    # create file row and table metadata
                    with DatabaseManager() as dm:
                        file_rec = File(user_id=int(user_id), filename=display_name, schemaname=new_schema, file_type='coding')
                        dm.session.add(file_rec)
                        dm.session.flush()
                        dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='content_store', row_count=1)
            except Exception as e:
                    print(f"Failed to persist classification project/schema: {e}")
        

        return JSONResponse({"classification_output": classification_output})
    except Exception as exc:
        print(f"Error reading schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/comments/{submission_id}") 
async def get_comments_for_submission(submission_id: str, database: str = Query("original")):
    """Fetch all comments for a specific submission from a Postgres file schema.

    The `database` parameter should provide a Postgres file schema name (e.g. proj_xxx).
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
