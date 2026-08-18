from fastapi import APIRouter, HTTPException, Depends, Request, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, select as sa_select
import json
import math
import re
import secrets
import traceback
import pandas as pd
from typing import Optional

from backend.app.api.utils import (
    get_user_id_from_request,
    normalize_schema,
    is_proj_schema,
)
from backend.app.api.schemas import (
    FilterDataRequest,
    FilterDataResponse,
    FilterDataFileInfo,
    FilterDataTagInfo,
    as_form,
)

from backend.app.database import (
    get_db,
    File,
    FileTable,
    FileDependency,
    Project,
    async_engine,
    engine,
    async_link_file_to_project,
)
from backend.app.databasemanager import AsyncDatabaseManager
from backend.scripts import filter_db as filter_db_module
from backend.scripts.filter_db import AIFilterError
from backend.scripts.openrouter_http import OPENROUTER_CLIENT_ERROR_CODES
from backend.scripts import tag_expansion as tag_expansion_module
from backend.scripts.tag_expansion import (
    TagExpansionError,
    comment_body_tag_predicate_sql,
    parse_filter_tags_input,
    submission_text_tag_predicate_sql,
)

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
            subs_exists = conn.execute(
                text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.submissions"}
            ).scalar()
            comm_exists = conn.execute(
                text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.comments"}
            ).scalar()

            has_word_count_subs = False
            has_word_count_comm = False
            if subs_exists:
                has_word_count_subs = conn.execute(
                    text(
                        """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = :schema AND table_name = 'submissions' AND column_name = 'word_count'
                    )
                    """
                    ),
                    {"schema": schema},
                ).scalar()
            if comm_exists:
                has_word_count_comm = conn.execute(
                    text(
                        """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = :schema AND table_name = 'comments' AND column_name = 'word_count'
                    )
                    """
                    ),
                    {"schema": schema},
                ).scalar()

            if subs_exists:
                if has_word_count_subs:
                    result = conn.execute(
                        text(
                            f"""
                        SELECT
                            LEAST((floor(word_count / 10) * 10)::int, 1000) as min_words,
                            COUNT(*) as count
                        FROM "{schema}"."submissions"
                        WHERE word_count BETWEEN 0 AND 1000
                        GROUP BY LEAST((floor(word_count / 10) * 10)::int, 1000)
                        ORDER BY min_words
                        """
                        )
                    )
                else:
                    wc_expr = _word_count_expr(["title", "selftext"])
                    result = conn.execute(
                        text(
                            f"""
                        SELECT
                            LEAST((floor(({wc_expr}) / 10) * 10)::int, 1000) as min_words,
                            COUNT(*) as count
                        FROM "{schema}"."submissions"
                        WHERE {wc_expr} BETWEEN 0 AND 1000
                        GROUP BY LEAST((floor(({wc_expr}) / 10) * 10)::int, 1000)
                        ORDER BY min_words
                        """
                        )
                    )
                submissions_ranges = [
                    {"min_words": row[0], "count": row[1]} for row in result
                ]

            if comm_exists:
                if has_word_count_comm:
                    result = conn.execute(
                        text(
                            f"""
                        SELECT
                            LEAST((floor(word_count / 10) * 10)::int, 1000) as min_words,
                            COUNT(*) as count
                        FROM "{schema}"."comments"
                        WHERE word_count BETWEEN 0 AND 1000
                        GROUP BY LEAST((floor(word_count / 10) * 10)::int, 1000)
                        ORDER BY min_words
                        """
                        )
                    )
                else:
                    wc_expr = _word_count_expr(["body"])
                    result = conn.execute(
                        text(
                            f"""
                        SELECT
                            LEAST((floor(({wc_expr}) / 10) * 10)::int, 1000) as min_words,
                            COUNT(*) as count
                        FROM "{schema}"."comments"
                        WHERE {wc_expr} BETWEEN 0 AND 1000
                        GROUP BY LEAST((floor(({wc_expr}) / 10) * 10)::int, 1000)
                        ORDER BY min_words
                        """
                        )
                    )
                comments_ranges = [
                    {"min_words": row[0], "count": row[1]} for row in result
                ]
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"submissions": submissions_ranges, "comments": comments_ranges})


@router.get("/file-entries/")
def project_entries(schema: str = Query(..., description="File schema name"), limit: int = 10, offset: int = 0):
    # Allow optional .db suffix (frontend may supply schema.db); validate and strip it.
    import re
    import datetime
    
    def _log_entries(msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] FILE_ENTRIES | {msg}")
    
    if not schema:
        raise HTTPException(status_code=400, detail="Missing schema name")
    schema = schema.strip()
    if schema.endswith(".db"):
        schema = schema[:-3]

    if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", schema):
        raise HTTPException(status_code=400, detail="Invalid schema name")

    _log_entries(f"Fetching entries from schema={schema} limit={limit} offset={offset}")
    
    submissions = []
    comments = []
    sub_count = 0
    com_count = 0

    try:
        with engine.connect() as conn:
            # Check if submissions table exists in schema
            subs_tbl = f"{schema}.submissions"
            comments_tbl = f"{schema}.comments"

            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": subs_tbl}).scalar()
            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": comments_tbl}).scalar()
            
            _log_entries(f"Tables exist: submissions={bool(subs_exists)} comments={bool(comm_exists)}")

            if subs_exists:
                sub_count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."submissions"')).scalar() or 0
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."submissions" ORDER BY id LIMIT :lim OFFSET :off'), {"lim": limit, "off": max(0, offset)}).fetchall()
                submissions = [dict(r._mapping) for r in rows]
                _log_entries(f"Submissions: total={sub_count} returned={len(submissions)}")

            if comm_exists:
                com_count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."comments"')).scalar() or 0
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."comments" ORDER BY id LIMIT :lim OFFSET :off'), {"lim": limit, "off": max(0, offset)}).fetchall()
                comments = [dict(r._mapping) for r in rows]
                _log_entries(f"Comments: total={com_count} returned={len(comments)}")

    except Exception as exc:
        _log_entries(f"ERROR: {exc}")
        import traceback
        traceback.print_exc()
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


def _log(stage: str, message: str, data: dict = None):
    """Human-readable debug logging for filter-data route."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    prefix = f"[{timestamp}] FILTER | {stage}"
    if data:
        details = " | ".join(f"{k}={v}" for k, v in data.items())
        print(f"{prefix} | {message} | {details}")
    else:
        print(f"{prefix} | {message}")


def _build_content_for_ai(rows: list, content_type: str) -> str:
    """
    Build a compact string representation of posts/comments for AI processing.
    Optimized for large datasets by using minimal formatting.
    """
    parts = []
    for r in rows:
        mapping = r._mapping
        if content_type == "submission":
            rid = mapping.get('id', '')
            title = mapping.get('title', '') or ''
            selftext = mapping.get('selftext', '') or ''
            # Compact format: less overhead per entry
            parts.append(f"[{rid}] {title}\n{selftext}")
        else:  # comment
            cid = mapping.get('id', '')
            body = mapping.get('body', '') or ''
            parts.append(f"[{cid}] {body}")
    return "\n---\n".join(parts)


def _create_submissions_table_for_filter(
    conn,
    new_schema: str,
    source_schema: str,
    source_has_submissions: bool,
) -> None:
    """Match source column layout (including extra columns from merges); fallback to builtin Reddit-style DDL."""
    if source_has_submissions:
        try:
            conn.execute(
                text(
                    f'CREATE TABLE "{new_schema}"."submissions" ('
                    f'LIKE "{source_schema}"."submissions" '
                    "INCLUDING DEFAULTS INCLUDING GENERATED INCLUDING CONSTRAINTS INCLUDING INDEXES"
                    f")"
                )
            )
            return
        except Exception as e:
            _log("SCHEMA", f'submissions LIKE "{source_schema}" failed, using default DDL: {e}')
    conn.execute(
        text(
            f'''
                CREATE TABLE "{new_schema}"."submissions" (
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
            '''
        )
    )


def _create_comments_table_for_filter(
    conn,
    new_schema: str,
    source_schema: str,
    source_has_comments: bool,
) -> None:
    if source_has_comments:
        try:
            conn.execute(
                text(
                    f'CREATE TABLE "{new_schema}"."comments" ('
                    f'LIKE "{source_schema}"."comments" '
                    "INCLUDING DEFAULTS INCLUDING GENERATED INCLUDING CONSTRAINTS INCLUDING INDEXES"
                    f")"
                )
            )
            return
        except Exception as e:
            _log("SCHEMA", f'comments LIKE "{source_schema}" failed, using default DDL: {e}')
    conn.execute(
        text(
            f'''
                CREATE TABLE "{new_schema}"."comments" (
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
            '''
        )
    )


@router.post("/filter-data/", response_model=FilterDataResponse)
async def filter_data(
    request: Request,
    payload: FilterDataRequest = Depends(as_form(FilterDataRequest)),
):
    """Filter posts/comments using AI and save results to a new Postgres schema.

    Flow:
    1. Optionally expand ``filter_tags`` via OpenRouter, then restrict rows by
       keyword match against submission/comment text.
    2. Fetch submissions/comments from the source schema (filtered by
       ``min_words``, then random-sampled per table using
       ``sample_percentage``).
    3. Send content to the AI for filtering based on ``prompt`` (skipped when
       prompt is empty but tags were used).
    4. Create a new ``proj_<hex>`` schema with the filtered results.
    5. Register file metadata + parent dependency for the authenticated user.
    """
    api_key = payload.api_key
    schema = payload.database
    model = payload.model
    name = payload.name
    filter_prompt = (payload.prompt or "").strip()
    pct = payload.sample_percentage
    min_words = payload.min_words
    user_tags_list = parse_filter_tags_input(payload.filter_tags)
    expanded_terms_sql: list[str] = []
    original_tags_meta: list[str] = []
    if user_tags_list:
        try:
            original_tags_meta, expanded_terms_sql = (
                tag_expansion_module.expand_tags_via_openrouter(
                    user_tags_list, api_key, model
                )
            )
        except TagExpansionError as e:
            code = e.code if e.code in OPENROUTER_CLIENT_ERROR_CODES else 502
            _log("TAG_ERROR", f"Tag expansion failed (HTTP {code}): {e}")
            return JSONResponse({"error": str(e)}, status_code=code)
    has_tags = bool(user_tags_list)
    use_ai_posts = (not has_tags) or bool(filter_prompt)
    use_ai_comments = (not has_tags) or bool(filter_prompt)
    sub_tag_sql, sub_tag_bind = submission_text_tag_predicate_sql(expanded_terms_sql)
    com_tag_sql, com_tag_bind = comment_body_tag_predicate_sql(expanded_terms_sql)

    _log("START", "Filter request received", {
        "schema": schema,
        "name": name,
        "model": model,
        "prompt_chars": len(filter_prompt),
        "min_words": min_words,
        "sample_percentage": pct,
        "has_tags": has_tags,
        "expanded_term_count": len(expanded_terms_sql),
    })

    try:
        # ===== STEP 1: Fetch source data (optional tag match, min_words, then random sample per table) =====
        submissions_text = ""
        comments_text = ""
        submission_count = 0
        comment_count = 0
        subs_eligible = 0
        comm_eligible = 0
        sub_rows = []
        comm_rows = []

        with engine.connect() as conn:
            # Check table existence
            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.submissions"}).scalar()
            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.comments"}).scalar()

            # Fetch submissions
            if subs_exists:
                wc_expr = _word_count_expr(["title", "selftext"])
                subs_count_params = {"mw": min_words, **sub_tag_bind}
                subs_eligible = int(
                    conn.execute(
                        text(
                            f'SELECT COUNT(*) FROM "{schema}"."submissions" '
                            f"WHERE {wc_expr} >= :mw{sub_tag_sql}"
                        ),
                        subs_count_params,
                    ).scalar()
                    or 0
                )
                subs_limit = math.ceil((subs_eligible * pct) / 100.0)
                if subs_limit > 0:
                    subs_cols = "id, title, selftext" if use_ai_posts else "id"
                    sub_rows = conn.execute(
                        text(
                            f'SELECT {subs_cols} FROM "{schema}"."submissions" '
                            f"WHERE {wc_expr} >= :mw{sub_tag_sql} ORDER BY RANDOM() LIMIT :lim"
                        ),
                        {**subs_count_params, "lim": subs_limit},
                    ).fetchall()
                submission_count = len(sub_rows)
                submissions_text = (
                    _build_content_for_ai(sub_rows, "submission") if use_ai_posts else ""
                )

            # Fetch comments
            if comm_exists:
                wc_expr = _word_count_expr(["body"])
                comm_count_params = {"mw": min_words, **com_tag_bind}
                comm_eligible = int(
                    conn.execute(
                        text(
                            f'SELECT COUNT(*) FROM "{schema}"."comments" '
                            f"WHERE {wc_expr} >= :mw{com_tag_sql}"
                        ),
                        comm_count_params,
                    ).scalar()
                    or 0
                )
                comm_limit = math.ceil((comm_eligible * pct) / 100.0)
                if comm_limit > 0:
                    comm_cols = "id, body" if use_ai_comments else "id"
                    comm_rows = conn.execute(
                        text(
                            f'SELECT {comm_cols} FROM "{schema}"."comments" '
                            f"WHERE {wc_expr} >= :mw{com_tag_sql} ORDER BY RANDOM() LIMIT :lim"
                        ),
                        {**comm_count_params, "lim": comm_limit},
                    ).fetchall()
                comment_count = len(comm_rows)
                comments_text = (
                    _build_content_for_ai(comm_rows, "comment") if use_ai_comments else ""
                )

        _log("DATA", "Source data fetched", {
            "submissions_sampled": submission_count,
            "comments_sampled": comment_count,
            "submissions_eligible": subs_eligible,
            "comments_eligible": comm_eligible,
            "subs_chars": len(submissions_text),
            "comm_chars": len(comments_text),
        })

        # ===== STEP 2: AI Filtering (skipped when tags-only: keep all sampled rows) =====
        post_ids = []
        comment_ids = []
        system_prompt = ""
        user_prompt = ""

        if not use_ai_posts and sub_rows:
            post_ids = [str(r._mapping["id"]) for r in sub_rows if r._mapping.get("id")]
            _log("TAG_ONLY", "Skipping post AI filter; using tag-matched sample IDs", {"ids": len(post_ids)})

        if not use_ai_comments and comm_rows:
            comment_ids = [str(r._mapping["id"]) for r in comm_rows if r._mapping.get("id")]
            _log("TAG_ONLY", "Skipping comment AI filter; using tag-matched sample IDs", {"ids": len(comment_ids)})

        # Filter submissions
        if use_ai_posts and submissions_text:
            _log("AI", f"Sending {len(submissions_text):,} chars to AI for post filtering...")
            try:
                result = filter_db_module.filter_posts_with_ai(
                    filter_prompt, submissions_text, api_key, model
                )
                post_ids, system_prompt, user_prompt = result
                _log("AI", "Posts filtered", {"matched_ids": len(post_ids)})
            except AIFilterError as e:
                code = e.code if e.code in OPENROUTER_CLIENT_ERROR_CODES else 502
                _log("AI_ERROR", f"Post filtering failed (HTTP {code}): {e}")
                return JSONResponse({"error": str(e)}, status_code=code)
            except Exception as e:
                _log("AI_ERROR", f"Post filtering failed: {e}")
                traceback.print_exc()
                return JSONResponse({"error": f"AI filtering failed for posts: {e}"}, status_code=502)

        # Filter comments
        if use_ai_comments and comments_text:
            _log("AI", f"Sending {len(comments_text):,} chars to AI for comment filtering...")
            try:
                result = filter_db_module.filter_comments_with_ai(
                    filter_prompt, comments_text, api_key, model
                )
                comment_ids, _, _ = result
                _log("AI", "Comments filtered", {"matched_ids": len(comment_ids)})
            except AIFilterError as e:
                code = e.code if e.code in OPENROUTER_CLIENT_ERROR_CODES else 502
                _log("AI_ERROR", f"Comment filtering failed (HTTP {code}): {e}")
                return JSONResponse({"error": str(e)}, status_code=code)
            except Exception as e:
                _log("AI_ERROR", f"Comment filtering failed: {e}")
                traceback.print_exc()
                return JSONResponse({"error": f"AI filtering failed for comments: {e}"}, status_code=502)

        if has_tags and not filter_prompt:
            tag_ctx = json.dumps(
                {"original_tags": original_tags_meta, "expanded_terms": expanded_terms_sql},
                ensure_ascii=False,
            )
            system_prompt = "Tag-based pre-filter only (no AI content criteria)."
            user_prompt = tag_ctx[:8000] if len(tag_ctx) > 8000 else tag_ctx
        
        # Validate AI returned IDs
        if not isinstance(post_ids, list):
            _log("WARN", f"post_ids is {type(post_ids).__name__}, expected list")
            post_ids = []
        if not isinstance(comment_ids, list):
            _log("WARN", f"comment_ids is {type(comment_ids).__name__}, expected list")
            comment_ids = []

        _log("AI_RESULT", "AI filtering complete", {
            "post_ids": len(post_ids),
            "comment_ids": len(comment_ids)
        })

        # ===== STEP 3: Create new schema and insert filtered data =====
        unique_id = secrets.token_hex(6)
        new_schema = f"proj_{unique_id}"
        inserted_subs = 0
        inserted_comments = 0
        
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
            _create_submissions_table_for_filter(
                conn, new_schema, schema, bool(subs_exists)
            )
            _create_comments_table_for_filter(
                conn, new_schema, schema, bool(comm_exists)
            )
            conn.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS idx_{new_schema}_subs_wc ON "{new_schema}"."submissions" (word_count)'
                )
            )
            conn.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS idx_{new_schema}_comm_wc ON "{new_schema}"."comments" (word_count)'
                )
            )
            
            _log("DB", "Schema created", {"schema": new_schema})
            
            # Insert submissions by ID
            not_found_count = 0
            if post_ids:
                _log("INSERT", f"Looking up {len(post_ids)} post IDs in source schema {schema}")
                # Log sample of IDs we're looking for
                sample_ids = post_ids[:5]
                _log("INSERT", f"Sample IDs to find: {sample_ids}")
                
                for post_id in post_ids:
                    if not post_id:
                        continue
                    try:
                        orig_row = conn.execute(
                            text(f'SELECT * FROM "{schema}"."submissions" WHERE id = :id'),
                            {"id": str(post_id)}
                        ).fetchone()
                        if orig_row:
                            orig_dict = dict(orig_row._mapping)
                            # Remove word_count if present (it's generated)
                            orig_dict.pop('word_count', None)
                            columns = list(orig_dict.keys())
                            placeholders = ", ".join(f":{c}" for c in columns)
                            columns_str = ", ".join(f'"{c}"' for c in columns)
                            with conn.begin_nested():
                                conn.execute(
                                    text(f'INSERT INTO "{new_schema}"."submissions" ({columns_str}) VALUES ({placeholders})'),
                                    orig_dict
                                )
                            inserted_subs += 1
                        else:
                            not_found_count += 1
                            if not_found_count <= 5:
                                _log("INSERT_WARN", f"ID not found in source: {post_id}")
                    except Exception as e:
                        _log("INSERT_ERR", f"Failed to insert submission {post_id}: {e}")
                
                if not_found_count > 0:
                    _log("INSERT", f"IDs not found in source: {not_found_count}/{len(post_ids)}")
            
            # Insert comments by ID
            if comment_ids:
                for comment_id in comment_ids:
                    if not comment_id:
                        continue
                    try:
                        orig_row = conn.execute(
                            text(f'SELECT * FROM "{schema}"."comments" WHERE id = :id'),
                            {"id": str(comment_id)}
                        ).fetchone()
                        if orig_row:
                            orig_dict = dict(orig_row._mapping)
                            orig_dict.pop('word_count', None)
                            columns = list(orig_dict.keys())
                            placeholders = ", ".join(f":{c}" for c in columns)
                            columns_str = ", ".join(f'"{c}"' for c in columns)
                            with conn.begin_nested():
                                conn.execute(
                                    text(f'INSERT INTO "{new_schema}"."comments" ({columns_str}) VALUES ({placeholders})'),
                                    orig_dict
                                )
                            inserted_comments += 1
                    except Exception as e:
                        _log("INSERT_ERR", f"Failed to insert comment {comment_id}: {e}")
        
        _log("DB", "Data inserted", {
            "submissions": inserted_subs,
            "comments": inserted_comments
        })
        
        # Verify data was actually inserted
        with engine.connect() as verify_conn:
            actual_subs = verify_conn.execute(text(f'SELECT COUNT(*) FROM "{new_schema}"."submissions"')).scalar() or 0
            actual_comms = verify_conn.execute(text(f'SELECT COUNT(*) FROM "{new_schema}"."comments"')).scalar() or 0
            _log("VERIFY", f"Actual counts in new schema: submissions={actual_subs} comments={actual_comms}")
            
            if actual_subs != inserted_subs or actual_comms != inserted_comments:
                _log("VERIFY_WARN", f"Count mismatch! Expected subs={inserted_subs} comms={inserted_comments}")

        # ===== STEP 4: Register file metadata =====
        user_id = get_user_id_from_request(request)
        file_rec = None
        
        if user_id:
            try:
                async with AsyncDatabaseManager() as dm:
                    file_rec = File(
                        user_id=user_id,
                        filename=name or new_schema,
                        schemaname=new_schema,
                        file_type='filtered_data',
                        systemprompt=system_prompt,
                        userprompt=user_prompt,
                        description=payload.description or None
                    )
                    dm.session.add(file_rec)
                    await dm.session.flush()

                    sf = await dm.session.execute(
                        sa_select(File).where(
                            File.schemaname == schema,
                            File.user_id == user_id,
                        )
                    )
                    source_file = sf.scalar_one_or_none()
                    if source_file:
                        dep = FileDependency(child_file_id=file_rec.id, parent_file_id=source_file.id)
                        dm.session.add(dep)

                    await dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='submissions', row_count=inserted_subs)
                    await dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='comments', row_count=inserted_comments)

                    if payload.project_id is not None:
                        proj = await dm.session.get(Project, payload.project_id)
                        if proj is None:
                            raise HTTPException(status_code=404, detail="Project not found")
                        if proj.user_id != user_id:
                            raise HTTPException(
                                status_code=403,
                                detail="Forbidden: project does not belong to user",
                            )
                        await async_link_file_to_project(
                            dm.session, file_rec.id, proj.id
                        )

                    await dm.session.flush()
                    _log("META", "File metadata saved", {"file_id": file_rec.id})
            except HTTPException:
                raise
            except Exception as e:
                _log("META_ERROR", f"Failed to save metadata: {e}")
                traceback.print_exc()

        _log("DONE", "Filter complete", {
            "new_schema": new_schema,
            "posts": inserted_subs,
            "comments": inserted_comments
        })

        resp_body = {
            "message": "Database filtered and saved",
            "submissions_length": len(submissions_text),
            "comments_length": len(comments_text),
            "posts_filtered_count": inserted_subs,
            "comments_filtered_count": inserted_comments,
            "file": {
                "id": str(file_rec.id),
                "schema_name": new_schema,
                "filename": file_rec.filename
            } if file_rec else None,
        }
        if has_tags:
            resp_body["tag_filter"] = {
                "original_tags": original_tags_meta,
                "expanded_terms": expanded_terms_sql,
            }
        return JSONResponse(resp_body)

    except HTTPException:
        raise
    except Exception as exc:
        _log("FATAL", f"Unhandled error: {exc}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


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
        async with async_engine.connect() as conn:
            tbl = f"{schema}.comments"
            tbl_exists = (
                await conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": tbl})
            ).scalar()
            if not tbl_exists:
                return JSONResponse({"error": f"Comments table not found in schema {schema}"}, status_code=404)

            q = text(f'SELECT * FROM "{schema}"."comments" WHERE link_id = :link ORDER BY created_utc ASC')
            result = await conn.execute(q, {"link": submission_id})
            rows = result.fetchall()
            comments = [dict(r._mapping) for r in rows]

            return JSONResponse({"comments": comments})

    except Exception as exc:
        print(f"Error reading comments from schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)

@router.post("/post-contents/")
async def get_post_contents(request: Request):
    try:
        data = await request.json()
        schema_name = normalize_schema(data.get("schema"))
        post_ids = data.get("post_ids", [])

        if not schema_name or not post_ids:
            raise HTTPException(status_code=400, detail="schema and post_ids are required")
        if not is_proj_schema(schema_name):
            raise HTTPException(status_code=400, detail="Invalid schema name")

        async with async_engine.connect() as conn:
            placeholders = ", ".join([f":id_{i}" for i in range(len(post_ids))])
            params = {f"id_{i}": pid for i, pid in enumerate(post_ids)}

            query = f"""
            SELECT id, title, selftext
            FROM "{schema_name}".submissions
            WHERE id IN ({placeholders})
            """

            result = await conn.execute(text(query), params)
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
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

