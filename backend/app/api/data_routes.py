from fastapi import APIRouter, HTTPException, Depends, Request, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
import re
import secrets
import traceback
import pandas as pd
from typing import Optional

from .utils import get_user_id_from_request, engine, SessionLocal
from app.database import get_db, File, FileTable, FileDependency, Project
from app.databasemanager import DatabaseManager
from scripts.filter_db import filter_posts_with_ai, filter_comments_with_ai

router = APIRouter()


@router.get("/file-entries/")
def project_entries(schema: str = Query(..., description="File schema name"), limit: int = 10, offset: int = 0):
    # Allow optional .db suffix (frontend may supply schema.db); validate and strip it.
    import re
    if not schema:
        raise HTTPException(status_code=400, detail="Missing schema name")
    schema = schema.strip()
    if schema.endswith(".db"):
        schema = schema[:-3]

    if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", schema):
        raise HTTPException(status_code=400, detail="Invalid schema name")

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
async def filter_data(request: Request, api_key: str = Form(...), prompt: Optional[str] = Form(None), database: str = Form(None), name: str = Form(...), model: str = Form(""), project_id: str = Form(None), description: Optional[str] = Form(None)):
    """Read a Postgres file schema (provided in `database`), assemble submissions and comments,
    merge into a single string and print it to the server stdout.
    """
    schema = (database or "").strip()

    print(f"[filter-data] incoming: database={schema!r} name={name!r} model={model!r} prompt_len={len((prompt or '').strip())}")

    # Require explicit model selection from the frontend — do not fall back to server defaults
    if not model or not str(model).strip():
        print("[filter-data] no model provided in form; aborting per policy to avoid silent defaults")
        return JSONResponse({"error": "No model specified. Please select a model in the form."}, status_code=400)

    if not schema or not schema.startswith('proj_'):
        print("[filter-data] invalid database parameter; expected proj_<id>")
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

        # Log textual lengths for debugging
        try:
            print(f"[filter-data] submissions_text_len={len(submissions_text)} comments_text_len={len(comments_text)}")
        except Exception:
            print("[filter-data] failed to compute text lengths")

        # Call AI filter functions and print their responses
        posts_filtered = None
        comments_filtered = None
        system_prompt = ""
        user_prompt = ""
        try:
            if submissions_text and submissions_text.strip():
                result = filter_posts_with_ai(prompt or "", submissions_text, api_key, model)
                posts_filtered, system_prompt, user_prompt = result
            else:
                posts_filtered = '[]'

            if comments_text and comments_text.strip():
                comments_filtered = filter_comments_with_ai(prompt or "", comments_text, api_key, model)
            else:
                comments_filtered = '[]'
        except Exception as e:
            traceback.print_exc()
            posts_filtered = f'[{{"error": "Filtering failed: {e}"}}]'
            comments_filtered = f'[{{"error": "Filtering failed: {e}"}}]'

        # Check for AI errors after the try-except
        if isinstance(posts_filtered, list) and len(posts_filtered) == 1 and isinstance(posts_filtered[0], dict) and "error" in posts_filtered[0]:
            raise ValueError(f"Posts filtering failed: {posts_filtered[0]['error']}")
        if isinstance(comments_filtered, list) and len(comments_filtered) == 1 and isinstance(comments_filtered[0], dict) and "error" in comments_filtered[0]:
            raise ValueError(f"Comments filtering failed: {comments_filtered[0]['error']}")

        posts_list = posts_filtered if isinstance(posts_filtered, list) else []
        comments_list = comments_filtered if isinstance(comments_filtered, list) else []
        try:
            print(f"[filter-data] AI results: posts_filtered_type={type(posts_filtered).__name__} comments_filtered_type={type(comments_filtered).__name__}")
            if isinstance(posts_filtered, (list, tuple)):
                print(f"[filter-data] posts_filtered_count={len(posts_filtered)} sample={posts_filtered[:5]}")
            else:
                print(f"[filter-data] posts_filtered_preview={str(posts_filtered)[:200]}")
            if isinstance(comments_filtered, (list, tuple)):
                print(f"[filter-data] comments_filtered_count={len(comments_filtered)} sample={comments_filtered[:5]}")
            else:
                print(f"[filter-data] comments_filtered_preview={str(comments_filtered)[:200]}")
        except Exception:
            print("[filter-data] failed to log AI results")
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
                print(f"[filter-data] selected_posts_count={len(selected_posts)} selected_comments_count={len(selected_comments)}")
            except Exception:
                print("[filter-data] failed to log selected post/comment counts")
        except Exception as e:
            try:
                print(f"[filter-data] creating schema {new_schema}")
            except Exception:
                print("[filter-data] failed to log schema creation")

        # Create a new Postgres schema and store results there; attach to authenticated user if present
        # Resolve authenticated user (optional)
        user_id = get_user_id_from_request(request)

        new_schema = None
        file_rec = None
        try:
            unique_id = secrets.token_hex(6)
            new_schema = f"proj_{unique_id}"
            with engine.begin() as conn:
                pass
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
                # create submissions and comments tables
                conn.execute(text(f"CREATE TABLE IF NOT EXISTS \"{new_schema}\".submissions (id text PRIMARY KEY, title text, selftext text)"))
                conn.execute(text(f"CREATE TABLE IF NOT EXISTS \"{new_schema}\".comments (id text PRIMARY KEY, body text)"))
                pass

                # insert submissions
                inserted_subs = 0
                total_subs = len(posts_list)
                pass
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
                            pass
                            # continue to next item
                    except Exception as ie:
                        pass

                pass

                # insert comments
                inserted_comments = 0
                total_comments = len(comments_list)
                pass
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
                            pass
                            # continue to next item
                    except Exception as ie:
                        pass

                pass

            # create file row and metadata if user authenticated
            if user_id:
                try:
                    with DatabaseManager() as dm:
                        file_rec = File(user_id=user_id, filename=name or new_schema, schemaname=new_schema, file_type='filtered_data', systemprompt=system_prompt, userprompt=user_prompt, description=(description or None))
                        dm.session.add(file_rec)
                        dm.session.flush()
                        # Add dependency for the source database
                        source_file = dm.session.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
                        if source_file:
                            dep = FileDependency(child_file_id=file_rec.id, parent_file_id=source_file.id)
                            dm.session.add(dep)
                            dm.session.flush()
                        try:
                            dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='submissions', row_count=len(posts_list))
                        except Exception:
                            pass
                        try:
                            dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='comments', row_count=len(comments_list))
                        except Exception:
                            pass
                        # Attach to specified project if provided and exists
                        try:
                            if project_id:
                                try:
                                    pid = int(project_id)
                                except Exception:
                                    pid = None
                                if pid is not None:
                                    proj = dm.session.get(Project, pid)
                                    if proj:
                                        file_rec.projects.append(proj)
                                        dm.session.flush()
                        except Exception:
                            pass
                except Exception as e:
                    pass

        except Exception as e:
            traceback.print_exc()

        return JSONResponse({
            "message": "Database filtered and saved",
            "submissions_length": len(submissions_text),
            "comments_length": len(comments_text),
            "posts_filtered_count": len(posts_list),
            "comments_filtered_count": len(comments_list),
            "ai_response": {
                "posts_filtered": posts_filtered,
                "comments_filtered": comments_filtered,
            },
            "file": {"id": str(file_rec.id), "schema_name": new_schema, "filename": file_rec.filename} if file_rec else None,
        })
    except Exception as exc:
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