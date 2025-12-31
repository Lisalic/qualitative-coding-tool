import os
import sqlite3
import sys
import json
import tempfile
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, Form, Query, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

import hashlib
import os
import binascii
import uuid
from datetime import datetime

from backend.app.database import get_db, AuthUser, Project, engine, SessionLocal
from backend.app.databasemanager import DatabaseManager
import pandas as pd
from fastapi.responses import JSONResponse
from fastapi import Request
from backend.app.auth import create_access_token, decode_access_token

from backend.app.config import settings

from backend.scripts.import_db import import_from_zst_file
from backend.scripts.filter_db import main as filter_database_with_ai
from backend.scripts.codebook_generator import main as generate_codebook_main
from backend.scripts.codebook_apply import main as apply_codebook_main
from backend.app.services import migrate_sqlite_file

router = APIRouter()

# Legacy reddit DB path used by older scripts. Resolve from project root instead
project_root = Path(__file__).resolve().parent.parent


@router.post("/upload-zst/")
async def upload_zst_file(
    request: Request,
    file: UploadFile = File(...), 
    subreddits: str = Form(None),
    data_type: str = Form(...),
    name: str = Form(None)
):
    print(f"Received upload request for file: {file.filename}")
    
    if not file.filename.endswith('.zst'):
        print("File rejected: not a .zst file")
        raise HTTPException(status_code=400, detail="File must be a .zst file")

    subreddit_list = None
    if subreddits:
        try:
            subreddit_list = json.loads(subreddits)
            print(f"Subreddit filter: {subreddit_list}")
        except json.JSONDecodeError:
            print("Invalid subreddit JSON")
            raise HTTPException(status_code=400, detail="Invalid subreddits format")

    allowed = ("comments", "posts")
    if data_type not in allowed:
        raise HTTPException(status_code=400, detail="data_type must be 'posts' or 'comments'")
    import_data_type = "submissions" if data_type == "posts" else data_type
    print(f"Data type: {import_data_type}")

    # Generate unique database name
    database_dir = Path(settings.database_dir)
    database_dir.mkdir(parents=True, exist_ok=True)
    base_name = name.strip() if name else file.filename.replace('.zst', '')
    counter = 1
    db_name = f"{base_name}{counter}.db"
    db_path = database_dir / db_name
    while db_path.exists():
        counter += 1
        db_name = f"{base_name}{counter}.db"
        db_path = database_dir / db_name

    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix='.zst', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        print(f"File temporarily saved to: {tmp_path}, size: {len(content)} bytes")

        stats = import_from_zst_file(tmp_path, str(db_path), subreddit_list, import_data_type)
        print(f"Import completed successfully: {stats}")

        os.unlink(tmp_path)

        count = stats['comments_imported'] if import_data_type == 'comments' else stats['submissions_imported']
        # If the request is authenticated, migrate the new DB into a per-user project
        user_id = None
        try:
            token = request.cookies.get("access_token")
            if not token:
                auth = request.headers.get("Authorization")
                if auth and auth.lower().startswith("bearer "):
                    token = auth.split(None, 1)[1]
            if token:
                payload = decode_access_token(token)
                user_id = payload.get("sub")
        except Exception:
            user_id = None

        response_data = {
            "status": "completed",
            "message": f"Created {db_name} with {count} {import_data_type}",
            "database": db_name,
            "file_name": file.filename,
            "stats": stats,
        }

        # Indicate whether the request was authenticated (helps debug client behavior)
        response_data["authenticated"] = bool(user_id)

        # If authenticated, attempt to create a project and migrate the sqlite DB into a schema
        if user_id:
            try:
                # use base_name as display name
                migrate_sqlite_file(uuid.UUID(user_id), str(db_path), base_name)
                response_data["project_migrated"] = True
            except Exception as exc:
                response_data["project_migrated"] = False
                response_data["migration_error"] = str(exc)
        else:
            # explicitly mark that no migration was attempted due to missing auth
            response_data["project_migrated"] = False

        print(f"Sending response: {response_data}")
        return JSONResponse(response_data)
        
    except Exception as exc:
        print(f"Error during upload/import: {exc}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/list-databases/")
async def list_databases(request: Request, db: Session = Depends(get_db)):
    """List filesystem databases and, if authenticated, include user's Postgres projects.
    This helps the client determine whether a desired merge name conflicts with an existing
    project/schema owned by the user.
    """
    database_dir = Path(settings.database_dir)
    if not database_dir.exists():
        files = []
    else:
        files = []
        for f in database_dir.iterdir():
            if f.is_file() and f.name.endswith('.db'):
                metadata = get_database_metadata(f)
                files.append({
                    "name": f.name,
                    "metadata": metadata,
                })

    projects_list = []
    # Attempt to authenticate and include projects owned by the user
    token = None
    try:
        token = request.cookies.get("access_token")
        if not token:
            auth = request.headers.get("Authorization")
            if auth and auth.lower().startswith("bearer "):
                token = auth.split(None, 1)[1]
    except Exception:
        token = None

    if token:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id:
                projects = db.query(Project).filter(Project.user_id == user_id).all()
                for p in projects:
                    projects_list.append({
                        "id": str(p.id),
                        "display_name": p.display_name,
                        "schema_name": p.schema_name,
                        "project_type": p.project_type,
                    })
        except Exception:
            return JSONResponse({"databases": files, "projects": None})

    return JSONResponse({"databases": files, "projects": projects_list})


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


@router.get("/list-filtered-databases/")
async def list_filtered_databases():
    filtered_database_dir = Path(settings.filtered_database_dir)
    # Debug logging to help identify why files might not be listed
    try:
        print(f"[DEBUG] list_filtered_databases -> resolved: {filtered_database_dir}")
        print(f"[DEBUG] exists: {filtered_database_dir.exists()}")
        if filtered_database_dir.exists():
            print(f"[DEBUG] contents: {[p.name for p in filtered_database_dir.iterdir()]}")
    except Exception as e:
        print(f"[DEBUG] error inspecting filtered_database_dir: {e}")

    if not filtered_database_dir.exists():
        return JSONResponse({"databases": []})

    databases = [f.name for f in filtered_database_dir.iterdir() if f.is_file() and f.name.endswith('.db')]
    return JSONResponse({"databases": databases})


@router.post("/merge-databases/")
async def merge_databases(request: Request, databases: str = Form(...), name: str = Form(...)):
    try:
        db_list = json.loads(databases)
        print(f"Merging databases: {db_list} into {name}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid databases format")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Database name is required")

    token = None
    try:
        token = request.cookies.get("access_token")
        if not token:
            auth = request.headers.get("Authorization")
            if auth and auth.lower().startswith("bearer "):
                token = auth.split(None, 1)[1]
    except Exception:
        token = None

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required to merge databases")

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

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

        if total_rows == 0:
            # nothing to migrate: drop empty schema and inform client
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            except Exception:
                pass
            return JSONResponse({"message": "No rows found in selected databases; nothing migrated", "database": name, "total_submissions": 0, "total_comments": 0, "project_migrated": False})

        # Create project record and table metadata
        with DatabaseManager() as dm:
            proj = dm.projects.create(user_id=uuid.UUID(user_id), display_name=name, schema_name=schema_name, project_type='raw_data')
            for tbl, cnt in tables_written.items():
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
    # Try cookie first then Authorization header
    token = None
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return JSONResponse({"id": str(user.id), "email": user.email})


@router.get("/my-projects/")
def my_projects(request: Request, project_type: str = Query("raw_data"), db: Session = Depends(get_db)):
    # Authenticate same as /me/
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    projects = db.query(Project).filter(Project.user_id == user_id, Project.project_type == project_type).all()
    result = [
        {
            "id": str(p.id),
            "display_name": p.display_name,
            "schema_name": p.schema_name,
            "project_type": p.project_type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in projects
    ]

    return JSONResponse({"projects": result})


@router.delete("/delete-database/{db_name}")
async def delete_database(db_name: str, request: Request, db: Session = Depends(get_db)):
    """
    Delete a filesystem .db file or a project schema.
    - If `db_name` ends with `.db` or corresponds to a file, delete the file.
    - If `db_name` looks like a project schema (e.g. starts with `proj_`) and belongs
      to the authenticated user, drop the schema and delete the `projects` row.
    """
    database_dir = Path(settings.database_dir)

    # Normalize potential .db suffix
    name = db_name.strip()
    # If it's a file path request (endswith .db) try filesystem delete first
    if name.endswith('.db'):
        db_path = database_dir / name
        if not db_path.exists():
            raise HTTPException(status_code=404, detail="Database not found")
        try:
            db_path.unlink()
            return JSONResponse({"message": f"Database '{name}' deleted successfully"})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete database: {str(e)}")

    # Otherwise treat as possible project schema name. Require auth.
    schema = name
    # strip accidental .db suffix if provided
    if schema.endswith('.db'):
        schema = schema[:-3]

    # Only allow project schema deletions for safe names starting with proj_
    if not schema.startswith('proj_'):
        # Not a project schema and not a .db file -> invalid request
        raise HTTPException(status_code=400, detail="Invalid database identifier")

    # Authenticate: cookie first then Authorization header
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Find project owned by user with this schema
    proj = db.query(Project).filter(Project.schema_name == schema, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found or you do not have permission")

    # Drop schema in Postgres and delete project row
    try:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

        db.delete(proj)
        db.commit()
        return JSONResponse({"message": f"Project '{proj.display_name}' and schema '{schema}' deleted"})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete project/schema: {str(e)}")


@router.post("/rename-database/")
async def rename_database(old_name: str = Form(...), new_name: str = Form(...)):
    database_dir = Path(settings.database_dir)
    
    if not old_name.endswith('.db'):
        old_name += '.db'
    if not new_name.endswith('.db'):
        new_name += '.db'
    
    old_path = database_dir / old_name
    new_path = database_dir / new_name
    
    if old_path == new_path:
        return JSONResponse({"message": "Database name unchanged"})
    
    if not old_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")
    
    if new_path.exists():
        raise HTTPException(status_code=400, detail="Database with new name already exists")
    
    try:
        old_path.rename(new_path)
        return JSONResponse({"message": f"Database renamed from '{old_name}' to '{new_name}' successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename database: {str(e)}")


@router.post("/rename-project/")
def rename_project(request: Request, schema_name: str = Form(...), display_name: str = Form(...), db: Session = Depends(get_db)):
    """Rename a project's display_name. Requires authentication and ownership."""
    # auth: cookie or Authorization header
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # normalize schema name
    schema = schema_name.strip()
    if schema.endswith('.db'):
        schema = schema[:-3]

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
    """Return a codebook. Prefer a Postgres project with project_type='codebook'.
    Falls back to filesystem codebooks in backend/data/codebooks if no project found.
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


@router.post("/rename-codebook/")
async def rename_codebook(old_id: str = Form(...), new_id: str = Form(...)):
    codebooks_dir = Path(__file__).parent.parent.parent / "data" / "codebooks"
    if not codebooks_dir.exists():
        return JSONResponse({"error": "Codebooks directory not found"}, status_code=404)
    
    old_file = codebooks_dir / f"{old_id}.txt"
    new_file = codebooks_dir / f"{new_id}.txt"
    
    if not old_file.exists():
        return JSONResponse({"error": f"Codebook {old_id} not found"}, status_code=404)
    
    if new_file.exists():
        return JSONResponse({"error": f"Codebook {new_id} already exists"}, status_code=400)
    
    try:
        old_file.rename(new_file)
        return JSONResponse({"message": f"Codebook {old_id} renamed to {new_id}"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/save-codebook/")
async def save_codebook(codebook_id: str = Form(...), content: str = Form(...)):
    codebooks_dir = Path(__file__).parent.parent.parent / "data" / "codebooks"
    codebooks_dir.mkdir(parents=True, exist_ok=True)
    
    codebook_file = codebooks_dir / f"{codebook_id}.txt"
    
    try:
        with open(codebook_file, 'w') as f:
            f.write(content)
        return JSONResponse({"message": f"Codebook {codebook_id} saved successfully"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/save-project-codebook/")
async def save_project_codebook(request: Request, schema_name: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    """Save codebook content into a Postgres project schema's content_store table.
    Requires authentication and project ownership.
    """
    # auth: cookie or Authorization header
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    schema = schema_name.strip()
    if schema.endswith('.db'):
        schema = schema[:-3]

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
        print(f"[DEBUG] save_project_codebook called; token_present={bool(token)}, user_id={user_id}, schema={schema}")
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


@router.get("/list-coded-data")
async def list_coded_data():
    coded_data_dir = Path(__file__).parent.parent.parent / "data" / "coded_data"
    if coded_data_dir.exists():
        coded_files = list(coded_data_dir.glob("*.txt"))
        coded_data = []
        for cf in coded_files:
            coded_id = cf.stem  # filename without .txt
            coded_data.append({"id": coded_id, "name": coded_id})
        coded_data.sort(key=lambda x: x["id"], reverse=True)  # Most recent first
        return JSONResponse({"coded_data": coded_data})


@router.get("/coded-data")
async def get_coded_data_query(coded_id: str = Query(None), db: Session = Depends(get_db)):
    """Return coded data. Prefer a Postgres project with project_type='coding'.
    Falls back to filesystem coded_data in backend/data/coded_data if no project found.
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


@router.get("/coded-data/{coded_id}")
async def get_coded_data(coded_id: str):
    coded_data_dir = Path(__file__).parent.parent.parent / "data" / "coded_data"
    coded_file = coded_data_dir / f"{coded_id}.txt"
    if coded_file.exists():
        with open(coded_file, 'r') as f:
            coded_content = f.read()
        return JSONResponse({"coded_data": coded_content})
    else:
        return JSONResponse({"error": f"Coded data {coded_id} not found"}, status_code=404)


@router.post("/save-coded-data/")
async def save_coded_data(coded_id: str = Form(...), content: str = Form(...)):
    coded_data_dir = Path(__file__).parent.parent.parent / "data" / "coded_data"
    coded_data_dir.mkdir(parents=True, exist_ok=True)

    coded_file = coded_data_dir / f"{coded_id}.txt"
    try:
        with open(coded_file, 'w') as f:
            f.write(content)
        return JSONResponse({"message": f"Coded data {coded_id} saved successfully"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/save-project-coded-data/")
async def save_project_coded_data(request: Request, schema_name: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    """Save coded content into a Postgres project schema's content_store table for project_type 'coding'.
    Requires authentication and project ownership.
    """
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    schema = schema_name.strip()
    if schema.endswith('.db'):
        schema = schema[:-3]

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


@router.get("/classification-report") #look to remove
async def get_classification_report():
    report_path = Path(__file__).parent.parent.parent / "data" / "classification_report.txt"
    if report_path.exists():
        with open(report_path, 'r') as f:
            report_content = f.read()
        return JSONResponse({"classification_report": report_content})
    else:
        return JSONResponse({"error": "Classification report not found. Please apply a codebook first."}, status_code=404)


@router.get("/database-entries/")
async def get_database_entries(limit: int = 10, database: str = Query(..., description="Database name")):
    if not database:
        raise HTTPException(status_code=400, detail="Database name is required")
        
    if database.endswith('.db'):
        # Check if it's in the filtered directory first
        filtered_db_path = Path(settings.filtered_database_dir) / database
        if filtered_db_path.exists():
            db_path = filtered_db_path
        else:
            db_path = Path(settings.database_dir) / database
    elif database == "filtered_data":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "filtered":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "codebook":
        db_path = project_root / "data" / "codebook.db"
    elif database == "coding":
        db_path = project_root / "data" / "codeddata.db"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown database type: {database}")

    if not db_path.exists():
        return JSONResponse({
            "submissions": [],
            "comments": [],
            "total_submissions": 0,
            "total_comments": 0,
            "message": f"Database not found. Please upload a file first.",
        })

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if database == "codebook":
            cursor.execute('SELECT COUNT(*) as count FROM codebooks')
            sub_count = cursor.fetchone()['count']
            cursor.execute('SELECT * FROM codebooks LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            comments = []
            com_count = 0
        elif database == "coding":
            cursor.execute('SELECT COUNT(*) as count FROM codings')
            sub_count = cursor.fetchone()['count']
            cursor.execute('SELECT * FROM codings LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            comments = []
            com_count = 0
        elif database == "filtered" or (database.endswith('.db') and str(db_path).startswith(str(settings.filtered_database_dir))):
            # Filtered databases only have submissions table
            cursor.execute('SELECT COUNT(*) as count FROM submissions')
            sub_count = cursor.fetchone()['count']
            com_count = 0
            cursor.execute('SELECT * FROM submissions LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            comments = []
        else:
            cursor.execute('SELECT COUNT(*) as count FROM submissions')
            sub_count = cursor.fetchone()['count']
            cursor.execute('SELECT COUNT(*) as count FROM comments')
            com_count = cursor.fetchone()['count']

            cursor.execute('SELECT * FROM submissions LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            cursor.execute('SELECT * FROM comments LIMIT ?', (limit,))
            comments = [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as exc:
        if conn:
            conn.close()
        return JSONResponse({
            "submissions": [],
            "comments": [],
            "total_submissions": 0,
            "total_comments": 0,
            "message": f"Database schema missing or invalid: {exc}"
        }, status_code=500)
    finally:
        if conn:
            conn.close()

    return JSONResponse({
        "submissions": submissions,
        "comments": comments,
        "total_submissions": sub_count,
        "total_comments": com_count,
        "database": database,
        "date_created": os.path.getctime(str(db_path)) if db_path.exists() and os.path.getctime(str(db_path)) > 0 else None
    })


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
async def filter_data(api_key: str = Form(...), prompt: str = Form(...), database: str = Form(None), name: str = Form(...)):
    # Resolve database path similar to other endpoints; database must be provided or exist in uploads
    if database and database.endswith('.db'):
        filtered_db_path = Path(settings.filtered_database_dir) / database
        if filtered_db_path.exists():
            db_path = filtered_db_path
        else:
            db_path = Path(settings.database_dir) / database
    elif database in ("filtered_data", "filtered"):
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    else:
        return JSONResponse({"error": "No database specified. Please provide a database name."}, status_code=400)

    if not db_path.exists():
        return JSONResponse({"error": f"Database not found: {db_path}. Please upload data first."}, status_code=404)

    # Validate output name for filtered DB (required)
    filtered_dir = Path(settings.filtered_database_dir)
    filtered_dir.mkdir(parents=True, exist_ok=True)

    if not name or not name.strip():
        return JSONResponse({"error": "A name for the filtered database is required"}, status_code=400)

    # Basic sanitization: no path separators, no parent traversal
    if any(sep in name for sep in ("/", "\\")) or ".." in name:
        return JSONResponse({"error": "Invalid name provided"}, status_code=400)
    if not name.endswith('.db'):
        name = f"{name}.db"
    candidate = filtered_dir / name
    if candidate.exists():
        return JSONResponse({"error": f"Filtered database '{name}' already exists"}, status_code=400)

    output_db_path = str(candidate)

    try:
        # Pass the resolved db path and the desired output path to the filter script
        filter_database_with_ai(api_key, prompt, str(db_path), output_db_path)

        response_payload = {"message": "Data filtered successfully", "output": Path(output_db_path).name}

        # If the request is authenticated, migrate the filtered sqlite DB into a Postgres schema
        # and mark the project_type as 'filtered_data'. This creates a project owned by the user.
        token = None
        try:
            token = request.cookies.get("access_token")
            if not token:
                auth = request.headers.get("Authorization")
                if auth and auth.lower().startswith("bearer "):
                    token = auth.split(None, 1)[1]
        except Exception:
            token = None

        if token:
            try:
                payload = decode_access_token(token)
                user_id = payload.get("sub")
                if user_id:
                    # migrate and tag as filtered_data
                    migrate_sqlite_file(uuid.UUID(user_id), output_db_path, name, project_type="filtered_data")
                    response_payload["project_migrated"] = True
                else:
                    response_payload["project_migrated"] = False
            except Exception as exc:
                response_payload["project_migrated"] = False
                response_payload["migration_error"] = str(exc)

        return JSONResponse(response_payload)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/generate-codebook/")
async def generate_codebook(database: str = Form("original"), api_key: str = Form(...), prompt: str = Form(""), name: str = Form(...)):
    # Resolve database path using same logic as database-entries endpoint
    if database.endswith('.db'):
        # Check if it's in the filtered directory first
        filtered_db_path = Path(settings.filtered_database_dir) / database
        if filtered_db_path.exists():
            db_path = filtered_db_path
        else:
            db_path = Path(settings.database_dir) / database
    elif database == "filtered_data":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "filtered":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "codebook":
        db_path = project_root / "data" / "codebook.db"
    elif database == "coding":
        db_path = project_root / "data" / "codeddata.db"
    else:
        return JSONResponse({"error": "No database specified. Please provide a database name."}, status_code=400)
    
    if not db_path.exists():
        return JSONResponse({"error": f"Database not found. Please import data first."}, status_code=404)
    
    # Validate name
    codebooks_dir = Path(__file__).parent.parent.parent / "data" / "codebooks"
    codebooks_dir.mkdir(parents=True, exist_ok=True)

    if not name or not name.strip():
        return JSONResponse({"error": "A name for the codebook is required"}, status_code=400)
    # Basic sanitization
    if any(sep in name for sep in ("/", "\\")) or ".." in name:
        return JSONResponse({"error": "Invalid name provided"}, status_code=400)
    if not name.endswith('.txt'):
        name = f"{name}.txt"
    candidate = codebooks_dir / name
    if candidate.exists():
        return JSONResponse({"error": f"Codebook '{name}' already exists"}, status_code=400)

    try:
        # Pass desired output name to generator
        generate_codebook_main(str(db_path), api_key, prompt, output_name=name)
        if candidate.exists():
            with open(candidate, 'r') as f:
                codebook_content = f.read()
            return JSONResponse({"codebook": codebook_content})
        return JSONResponse({"error": "Codebook file not found after generation"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/apply-codebook/")
async def apply_codebook(
    database: str = Form("original"), 
    api_key: str = Form(...), 
    methodology: str = Form(""),
    codebook: str = Form(...)
):
    # Resolve database path using same logic as database-entries endpoint
    if database.endswith('.db'):
        # Check if it's in the filtered directory first
        filtered_db_path = Path(settings.filtered_database_dir) / database
        if filtered_db_path.exists():
            db_path = filtered_db_path
        else:
            db_path = Path(settings.database_dir) / database
    elif database == "filtered_data":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "filtered":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "codebook":
        db_path = project_root / "data" / "codebook.db"
    elif database == "coding":
        db_path = project_root / "data" / "codeddata.db"
    else:
        return JSONResponse({"error": "No database specified. Please provide a database name."}, status_code=400)
    
    if not db_path.exists():
        db_name = "Database"
        return JSONResponse({"error": f"{db_name} not found. Please import data first."}, status_code=404)
    
    try:
        report_path = apply_codebook_main(str(db_path), api_key, methodology, codebook)
        if report_path and Path(report_path).exists():
            with open(report_path, 'r') as f:
                report_content = f.read()
            return JSONResponse({"classification_report": report_content})
        else:
            return JSONResponse({"error": "Classification report not found"})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/comments/{submission_id}")
async def get_comments_for_submission(submission_id: str, database: str = Query("original")):
    """Fetch all comments for a specific submission"""
    if database.endswith('.db'):
        db_path = Path(settings.database_dir) / database
    elif database == "filtered":
        db_path = project_root / "data" / "filtered_data.db"
    elif database == "codebook":
        db_path = project_root / "data" / "codebook.db"
    elif database == "coding":
        db_path = project_root / "data" / "codeddata.db"
    else:
        return JSONResponse({"error": "No database specified. Please provide a database name."}, status_code=400)

    if not db_path.exists():
        return JSONResponse({"error": f"Database not found: {database}"}, status_code=404)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch comments where link_id matches the submission_id
        cursor.execute('SELECT * FROM comments WHERE link_id = ? ORDER BY created_utc ASC', (submission_id,))
        comments = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return JSONResponse({"comments": comments})

    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
