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


def _word_count_expr(columns):
    """Build a SQL expression that returns the exact word count for one or more text columns concatenated."""
    if len(columns) == 1:
        col = columns[0]
        combined = f"COALESCE({col}, '')"
    else:
        parts = " || ' ' || ".join(f"COALESCE({c}, '')" for c in columns)
        combined = parts
    # Optimized: normalize multiple whitespace to single spaces, then split
    normalized = f"regexp_replace(TRIM({combined}), '\\s+', ' ', 'g')"
    return (
        f"CASE WHEN COALESCE(TRIM({combined}), '') = '' THEN 0 "
        f"ELSE array_length(string_to_array({normalized}, ' '), 1) END"
    )


@router.get("/record-counts-by-words/")
def record_counts_by_words(schema: str = Query(...), min_words: int = Query(0)):
    """Return the number of submissions and comments whose word count >= min_words."""
    schema = (schema or "").strip()
    if schema.endswith(".db"):
        schema = schema[:-3]
    if not schema or not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", schema):
        raise HTTPException(status_code=400, detail="Invalid schema name")

    sub_count = 0
    com_count = 0
    try:
        with engine.connect() as conn:
            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.submissions"}).scalar()
            if subs_exists:
                # Check if word_count column exists (for optimized databases)
                has_word_count = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_schema = '{schema}' AND table_name = 'submissions' AND column_name = 'word_count'
                    )
                """)).scalar()
                
                if has_word_count:
                    sub_count = conn.execute(
                        text(f'SELECT COUNT(*) FROM "{schema}"."submissions" WHERE word_count >= :mw'),
                        {"mw": min_words}
                    ).scalar() or 0
                else:
                    wc = _word_count_expr(["title", "selftext"])
                    sub_count = conn.execute(
                        text(f'SELECT COUNT(*) FROM "{schema}"."submissions" WHERE {wc} >= :mw'),
                        {"mw": min_words}
                    ).scalar() or 0

            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.comments"}).scalar()
            if comm_exists:
                # Check if word_count column exists (for optimized databases)
                has_word_count = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_schema = '{schema}' AND table_name = 'comments' AND column_name = 'word_count'
                    )
                """)).scalar()
                
                if has_word_count:
                    com_count = conn.execute(
                        text(f'SELECT COUNT(*) FROM "{schema}"."comments" WHERE word_count >= :mw'),
                        {"mw": min_words}
                    ).scalar() or 0
                else:
                    wc = _word_count_expr(["body"])
                    com_count = conn.execute(
                        text(f'SELECT COUNT(*) FROM "{schema}"."comments" WHERE {wc} >= :mw'),
                        {"mw": min_words}
                    ).scalar() or 0
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"submissions": sub_count, "comments": com_count, "min_words": min_words})


@router.get("/word-count-ranges/")
def word_count_ranges(schema: str = Query(...)):
    """Return word count ranges (0-1000 in steps of 10) for submissions and comments using efficient SQL binning."""
    schema = (schema or "").strip()
    if schema.endswith(".db"):
        schema = schema[:-3]
    if not schema or not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", schema):
        raise HTTPException(status_code=400, detail="Invalid schema name")

    submissions_ranges = []
    comments_ranges = []

    try:
        with engine.connect() as conn:
            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.submissions"}).scalar()
            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.comments"}).scalar()

            # Check if word_count columns exist
            has_word_count_subs = False
            has_word_count_comm = False
            if subs_exists:
                has_word_count_subs = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = '{schema}' AND table_name = 'submissions' AND column_name = 'word_count'
                    )
                """)).scalar()
            if comm_exists:
                has_word_count_comm = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = '{schema}' AND table_name = 'comments' AND column_name = 'word_count'
                    )
                """)).scalar()

            # Get submissions ranges using efficient SQL binning
            if subs_exists and has_word_count_subs:
                result = conn.execute(text(f"""
                    SELECT
                        (floor(word_count / 10) * 10)::int as min_words,
                        COUNT(*) as count
                    FROM "{schema}"."submissions"
                    WHERE word_count >= 0
                    GROUP BY floor(word_count / 10) * 10
                    ORDER BY min_words
                """))
                submissions_ranges = [{"min_words": row[0], "count": row[1]} for row in result]
            elif subs_exists:
                # Fallback to computed word counts if no word_count column
                result = conn.execute(text(f"""
                    SELECT
                        (floor(({_word_count_expr(["title", "selftext"])}) / 10) * 10)::int as min_words,
                        COUNT(*) as count
                    FROM "{schema}"."submissions"
                    WHERE {_word_count_expr(["title", "selftext"])} >= 0
                    GROUP BY floor(({_word_count_expr(["title", "selftext"])}) / 10) * 10
                    ORDER BY min_words
                """))
                submissions_ranges = [{"min_words": row[0], "count": row[1]} for row in result]

            # Get comments ranges using efficient SQL binning
            if comm_exists and has_word_count_comm:
                result = conn.execute(text(f"""
                    SELECT
                        (floor(word_count / 10) * 10)::int as min_words,
                        COUNT(*) as count
                    FROM "{schema}"."comments"
                    WHERE word_count >= 0
                    GROUP BY floor(word_count / 10) * 10
                    ORDER BY min_words
                """))
                comments_ranges = [{"min_words": row[0], "count": row[1]} for row in result]
            elif comm_exists:
                # Fallback to computed word counts if no word_count column
                result = conn.execute(text(f"""
                    SELECT
                        (floor(({_word_count_expr(["body"])}) / 10) * 10)::int as min_words,
                        COUNT(*) as count
                    FROM "{schema}"."comments"
                    WHERE {_word_count_expr(["body"])} >= 0
                    GROUP BY floor(({_word_count_expr(["body"])}) / 10) * 10
                    ORDER BY min_words
                """))
                comments_ranges = [{"min_words": row[0], "count": row[1]} for row in result]

    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"submissions": submissions_ranges, "comments": comments_ranges})


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
async def filter_data(request: Request, api_key: str = Form(...), prompt: Optional[str] = Form(None), database: str = Form(None), name: str = Form(...), model: str = Form(""), project_id: str = Form(None), description: Optional[str] = Form(None), min_words: int = Form(0)):
    """Read a Postgres file schema, assemble submissions and comments,
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
            # Submissions: id, title, selftext (filtered by min_words)
            subs_tbl = f"{schema}.submissions"
            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": subs_tbl}).scalar()
            if subs_exists:
                wc = _word_count_expr(["title", "selftext"])
                rows = conn.execute(
                    text(f'SELECT id, title, selftext FROM "{schema}"."submissions" WHERE {wc} >= :mw'),
                    {"mw": min_words}
                ).fetchall()
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

            # Comments: id, body (filtered by min_words)
            comm_tbl = f"{schema}.comments"
            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": comm_tbl}).scalar()
            if comm_exists:
                wc = _word_count_expr(["body"])
                rows = conn.execute(
                    text(f'SELECT id, body FROM "{schema}"."comments" WHERE {wc} >= :mw'),
                    {"mw": min_words}
                ).fetchall()
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
                # posts_list is expected to be a list of id strings; fetch complete records for each id
                if isinstance(posts_list, list):
                    for item in posts_list:
                        if not item:
                            continue
                        try:
                            row = conn.execute(text(f'SELECT * FROM "{schema}"."submissions" WHERE id = :id'), {"id": item}).fetchone()
                            if row:
                                # Include all fields from the original record
                                selected_posts.append(dict(row._mapping))
                        except Exception:
                            pass

                # comments_list is expected to be a list of id strings; fetch complete records for each id
                if isinstance(comments_list, list):
                    for item in comments_list:
                        if not item:
                            continue
                        try:
                            row = conn.execute(text(f'SELECT * FROM "{schema}"."comments" WHERE id = :id'), {"id": item}).fetchone()
                            if row:
                                # Include all fields from the original record
                                selected_comments.append(dict(row._mapping))
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
                # create submissions and comments tables with all original fields
                conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS "{new_schema}"."submissions" (
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
                conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS "{new_schema}"."comments" (
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
                # Add indexes on word_count
                conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_{new_schema}_submissions_word_count ON "{new_schema}"."submissions" (word_count)'))
                conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_{new_schema}_comments_word_count ON "{new_schema}"."comments" (word_count)'))
                pass

                # insert submissions - fetch complete records from original database
                inserted_subs = 0
                total_subs = len(posts_list)
                pass
                for item in posts_list:
                    try:
                        if not isinstance(item, dict):
                            continue
                        sid = str(item.get('id')) if item.get('id') is not None else None
                        if sid is None:
                            continue
                        try:
                            # Fetch the complete record from original database
                            orig_row = conn.execute(text(f'SELECT * FROM "{schema}"."submissions" WHERE id = :id'), {"id": sid}).fetchone()
                            if not orig_row:
                                continue
                            
                            # Use a nested transaction (savepoint) so a single bad row
                            # does not abort the outer transaction.
                            with conn.begin_nested():
                                # Insert all fields from the original record
                                orig_dict = dict(orig_row._mapping)
                                columns = list(orig_dict.keys())
                                placeholders = ", ".join([f":{col}" for col in columns])
                                columns_str = ", ".join([f'"{col}"' for col in columns])
                                conn.execute(
                                    text(f'INSERT INTO "{new_schema}".submissions ({columns_str}) VALUES ({placeholders})'),
                                    orig_dict,
                                )
                            inserted_subs += 1
                        except Exception as ie:
                            pass
                            # continue to next item
                    except Exception as ie:
                        pass

                pass

                # insert comments - fetch complete records from original database
                inserted_comments = 0
                total_comments = len(comments_list)
                pass
                for item in comments_list:
                    try:
                        cid = str(item.get('id')) if item.get('id') is not None else None
                        if cid is None:
                            continue
                        try:
                            # Fetch the complete record from original database
                            orig_row = conn.execute(text(f'SELECT * FROM "{schema}"."comments" WHERE id = :id'), {"id": cid}).fetchone()
                            if not orig_row:
                                continue
                            
                            with conn.begin_nested():
                                # Insert all fields from the original record
                                orig_dict = dict(orig_row._mapping)
                                columns = list(orig_dict.keys())
                                placeholders = ", ".join([f":{col}" for col in columns])
                                columns_str = ", ".join([f'"{col}"' for col in columns])
                                conn.execute(
                                    text(f'INSERT INTO "{new_schema}".comments ({columns_str}) VALUES ({placeholders})'),
                                    orig_dict,
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

