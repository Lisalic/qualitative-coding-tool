import asyncio
from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import text, select
import json
import traceback
import secrets
import math

from backend.app.api.utils import get_user_id_from_request
from backend.app.database import get_db, File, FileDependency, engine, async_engine
from backend.scripts.display_codebook import parse_codebook_to_json
from backend.app.databasemanager import AsyncDatabaseManager

router = APIRouter()


def _resolve_coding_file_record(db: Session, coded_id: str | None) -> File | None:
    if not coded_id:
        return (
            db.query(File)
            .filter(File.file_type.in_(["coding", "coding_comparison"]))
            .order_by(File.created_at.desc())
            .first()
        )

    file_rec = (
        db.query(File)
        .filter(
            File.file_type.in_(["coding", "coding_comparison"]),
            File.schemaname == coded_id,
        )
        .first()
    )
    if file_rec:
        return file_rec

    file_rec = (
        db.query(File)
        .filter(
            File.file_type.in_(["coding", "coding_comparison"]),
            File.filename == coded_id,
        )
        .first()
    )
    if file_rec:
        return file_rec

    try:
        fid = int(coded_id)
    except Exception:
        return None

    return (
        db.query(File)
        .filter(File.file_type.in_(["coding", "coding_comparison"]), File.id == fid)
        .first()
    )


def _assemble_posts_content(schema: str, sample_percentage: float = 100.0) -> str:
    assembled_rows: list[str] = []
    sample_percentage = max(1.0, min(100.0, float(sample_percentage)))

    with engine.connect() as conn:
        submissions_table = f"{schema}.submissions"
        submissions_exists = conn.execute(
            text("SELECT to_regclass(:tbl)"),
            {"tbl": submissions_table},
        ).scalar()
        if submissions_exists:
            submissions_total = int(
                conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}"."submissions"')
                ).scalar()
                or 0
            )
            submissions_limit = math.ceil(
                (submissions_total * sample_percentage) / 100.0
            )
            rows = []
            if submissions_limit > 0:
                rows = conn.execute(
                    text(
                        f'SELECT id, title, selftext FROM "{schema}"."submissions" ORDER BY RANDOM() LIMIT :sample_limit'
                    ),
                    {"sample_limit": submissions_limit},
                ).fetchall()
            for row in rows:
                data = row._mapping
                assembled_rows.append(
                    f"POST_ID: {data.get('id', '')}  "
                    f"Title: {(data.get('title') or '')}  "
                    f"{(data.get('selftext') or '')}"
                )

        comments_table = f"{schema}.comments"
        comments_exists = conn.execute(
            text("SELECT to_regclass(:tbl)"),
            {"tbl": comments_table},
        ).scalar()
        if comments_exists:
            comments_total = int(
                conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}"."comments"')
                ).scalar()
                or 0
            )
            comments_limit = math.ceil((comments_total * sample_percentage) / 100.0)
            rows = []
            if comments_limit > 0:
                rows = conn.execute(
                    text(
                        f'SELECT id, body FROM "{schema}"."comments" ORDER BY RANDOM() LIMIT :sample_limit'
                    ),
                    {"sample_limit": comments_limit},
                ).fetchall()
            for row in rows:
                data = row._mapping
                assembled_rows.append(
                    f"POST_ID: {data.get('id', '')}  "
                    f"{(data.get('body') or '')}"
                )

    return "\n\n".join(assembled_rows).strip()


def _resolve_codebook_schema(db: Session, codebook_value: str) -> str | None:
    raw_value = (codebook_value or "").strip()
    if not raw_value:
        return None

    if raw_value.startswith("proj_"):
        return raw_value

    try:
        file_id = int(raw_value)
    except Exception:
        return None

    file_rec = (
        db.query(File)
        .filter(
            File.id == file_id,
            File.file_type.in_(["codebook", "codebook_comparison"]),
        )
        .first()
    )
    return file_rec.schemaname if file_rec else None


def _load_content_store_text(schema: str | None) -> str:
    if not schema:
        return ""

    with engine.connect() as conn:
        table_exists = conn.execute(
            text("SELECT to_regclass(:tbl)"),
            {"tbl": f"{schema}.content_store"},
        ).scalar()
        if not table_exists:
            return ""

        row = conn.execute(
            text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1')
        ).fetchone()
        return (row[0] if row else "") or ""


def _load_codebook_snapshot(schema: str | None) -> tuple[bool, str]:
    if not schema:
        return False, ""

    with engine.connect() as conn:
        table_exists = conn.execute(
            text("SELECT to_regclass(:tbl)"),
            {"tbl": f"{schema}.codebook"},
        ).scalar()
        if not table_exists:
            return False, ""

        row = conn.execute(
            text(f'SELECT codebook_text FROM "{schema}".codebook LIMIT 1')
        ).fetchone()
        return True, (row[0] if row else "") or ""


def _generate_unique_schema_name(prefix: str = "proj") -> str:
    for _ in range(12):
        candidate = f"{prefix}_{secrets.token_hex(6)}"
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT to_regnamespace(:schema_name)"),
                {"schema_name": candidate},
            ).scalar()
        if not exists:
            return candidate
    raise RuntimeError("Failed to allocate unique schema name")


@router.get("/coded-data")
async def get_coded_data_query(coded_id: str = None, db: Session = Depends(get_db)):
    """Return coded data stored in a File record with file_type='coding' or 'coding_comparison'.
    Also includes codebook content/tree from the coding schema's `codebook` table when present.
    """
    file_rec = _resolve_coding_file_record(db, coded_id)

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
                    codebook_text = ""
                    codebook_tree = []
                    codebook_tbl_exists = conn.execute(
                        text("SELECT to_regclass(:tbl)"),
                        {"tbl": f"{schema}.codebook"},
                    ).scalar()
                    if codebook_tbl_exists:
                        cb_res = conn.execute(
                            text(f'SELECT codebook_text FROM "{schema}".codebook LIMIT 1')
                        )
                        cb_row = cb_res.fetchone()
                        codebook_text = (cb_row[0] if cb_row else "") or ""
                        if codebook_text:
                            try:
                                parsed_text = parse_codebook_to_json(codebook_text)
                                parsed_obj = json.loads(parsed_text)
                                if isinstance(parsed_obj, list):
                                    codebook_tree = parsed_obj
                            except Exception:
                                codebook_tree = []

                    return JSONResponse({
                        "coded_data": row[0],
                        "codebook_text": codebook_text,
                        "codebook_tree": codebook_tree,
                        "systemprompt": file_rec.systemprompt,
                        "userprompt": file_rec.userprompt
                    })
                else:
                    return JSONResponse({"error": "Coded data content not found in file"}, status_code=404)
        except Exception as e:
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
    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == user_id, File.file_type == 'coding').first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File/project not found or you do not have permission")

    try:
        async with async_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            await conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{schema}".content_store (file_text text)'))
            await conn.execute(text(f'TRUNCATE TABLE "{schema}".content_store'))
            await conn.execute(text(f'INSERT INTO "{schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": content})

        if display_name:
            file_rec.filename = display_name
            try:
                db.commit()
                db.refresh(file_rec)
            except Exception:
                db.rollback()

        return JSONResponse({"message": "File coded data saved", "id": str(file_rec.id), "filename": file_rec.filename})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/save-file-coded-data-duplicate/")
async def save_project_coded_data_duplicate(
    request: Request,
    source_schema_name: str = Form(None),
    content: str = Form(None),
    display_name: str = Form(None),
    db: Session = Depends(get_db),
):
    """Duplicate coding data into a new schema and file record.
    Accepts JSON or form-data with source_schema_name, content, and display_name.
    """
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            body = await request.json()
            source_schema_name = body.get("source_schema_name")
            content = body.get("content")
            display_name = body.get("display_name")
        else:
            form = await request.form()
            if source_schema_name is None:
                source_schema_name = form.get("source_schema_name")
            if content is None:
                content = form.get("content")
            if display_name is None:
                display_name = form.get("display_name")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not source_schema_name or not content or not display_name:
        raise HTTPException(
            status_code=400,
            detail="source_schema_name, content, and display_name are required",
        )

    source_schema = source_schema_name.strip()
    target_display_name = display_name.strip()
    if not source_schema or not target_display_name:
        raise HTTPException(
            status_code=400,
            detail="source_schema_name and display_name cannot be empty",
        )

    source_file = (
        db.query(File)
        .filter(
            File.schemaname == source_schema,
            File.user_id == user_id,
            File.file_type.in_(["coding", "coding_comparison"]),
        )
        .first()
    )
    if not source_file:
        raise HTTPException(
            status_code=404,
            detail="Source coding file not found or you do not have permission",
        )

    try:
        source_codebook_exists, copied_codebook_text = _load_codebook_snapshot(
            source_schema
        )
        new_schema = _generate_unique_schema_name("proj")
        source_file_type = source_file.file_type or "coding"
        source_system_prompt = source_file.systemprompt
        source_user_prompt = source_file.userprompt
        source_file_id = source_file.id

        async with async_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
            await conn.execute(
                text(
                    f'CREATE TABLE IF NOT EXISTS "{new_schema}".content_store (file_text text)'
                )
            )
            await conn.execute(text(f'TRUNCATE TABLE "{new_schema}".content_store'))
            await conn.execute(
                text(
                    f'INSERT INTO "{new_schema}".content_store (file_text) VALUES (:file_text)'
                ),
                {"file_text": content},
            )

            if source_codebook_exists:
                await conn.execute(
                    text(
                        f'CREATE TABLE IF NOT EXISTS "{new_schema}".codebook (codebook_text text)'
                    )
                )
                await conn.execute(text(f'TRUNCATE TABLE "{new_schema}".codebook'))
                await conn.execute(
                    text(
                        f'INSERT INTO "{new_schema}".codebook (codebook_text) VALUES (:codebook_text)'
                    ),
                    {"codebook_text": copied_codebook_text},
                )

        async with AsyncDatabaseManager() as dm:
            file_rec = File(
                user_id=user_id,
                filename=target_display_name,
                schemaname=new_schema,
                file_type=source_file_type,
                systemprompt=source_system_prompt,
                userprompt=source_user_prompt,
            )
            dm.session.add(file_rec)
            await dm.session.flush()

            sfdm = await dm.session.execute(
                select(File)
                .where(File.id == source_file_id, File.user_id == user_id)
                .options(selectinload(File.projects))
            )
            source_file_in_dm = sfdm.scalar_one_or_none()

            for project in (source_file_in_dm.projects if source_file_in_dm else []):
                if project not in file_rec.projects:
                    file_rec.projects.append(project)

            copied_parent_ids: set[int] = set()
            spd = await dm.session.execute(
                select(FileDependency).where(FileDependency.child_file_id == source_file_id)
            )
            source_parent_dependencies = spd.scalars().all()

            for parent_dependency in source_parent_dependencies:
                pf = await dm.session.execute(
                    select(File).where(
                        File.id == parent_dependency.parent_file_id,
                        File.user_id == user_id,
                    )
                )
                parent_file = pf.scalar_one_or_none()
                if not parent_file:
                    continue

                parent_file_id = parent_file.id
                if parent_file_id in copied_parent_ids:
                    continue

                dm.session.add(
                    FileDependency(
                        child_file_id=file_rec.id,
                        parent_file_id=parent_file_id,
                    )
                )
                copied_parent_ids.add(parent_file_id)

            if source_file_id not in copied_parent_ids:
                dm.session.add(
                    FileDependency(
                        child_file_id=file_rec.id,
                        parent_file_id=source_file_id,
                    )
                )

            await dm.session.flush()

            await dm.file_tables.add_table_metadata(
                file_id=file_rec.id,
                table_name="content_store",
                row_count=1,
            )
            if source_codebook_exists:
                await dm.file_tables.add_table_metadata(
                    file_id=file_rec.id,
                    table_name="codebook",
                    row_count=1,
                )

            new_file_id = file_rec.id

        return JSONResponse(
            {
                "message": "File coded data duplicated",
                "id": str(new_file_id),
                "schema_name": new_schema,
                "filename": target_display_name,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/apply-codebook/")
async def apply_codebook(
    request: Request,
    database: str = Form(...),
    codebook: str = Form(...),
    methodology: str = Form(""),
    report_name: str = Form(None),
    api_key: str = Form(...),
    model: str = Form(""),
    sample_percentage: float = Form(100.0),
    db: Session = Depends(get_db),
):
    """Open the Postgres schema provided by `database`, read `submissions.title`/`selftext`
    and `comments.body`, assemble them into a single string, print it to stdout and
    return a preview in the response.
    """
    from .utils import classify_posts
    import secrets

    # apply-codebook endpoint invoked

    schema = (database or "").strip()
    if schema.endswith('.db'):
        schema = schema[:-3]

    if not schema or not schema.startswith('proj_'):
        return JSONResponse({"error": "This endpoint expects a proj_<id> schema name"}, status_code=400)

    try:
        assembled = await asyncio.to_thread(_assemble_posts_content, schema, sample_percentage)

        resolved_codebook_schema = _resolve_codebook_schema(db, codebook)
        codebook_text = _load_content_store_text(resolved_codebook_schema)

        if not codebook_text:
            return JSONResponse(
                {"error": "Cannot apply codebook: codebook not found or empty"},
                status_code=400,
            )
        if not api_key:
            return JSONResponse(
                {"error": "Cannot apply codebook: api_key not provided"},
                status_code=400,
            )

        # Attempt classification using the provided codebook and API key
        classification_output = ""
        system_prompt = ""
        user_prompt = ""
        try:
            result = await asyncio.to_thread(
                classify_posts,
                codebook_text,
                assembled,
                methodology or "",
                api_key,
                model,
            )
            classification_output, system_prompt, user_prompt = result
        except Exception as e:
            print(f"Exception during classification: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse(
                {"error": f"API request error: {str(e)}"},
                status_code=502,
            )

        # resolve auth (optional)
        user_id = get_user_id_from_request(request)
        if user_id:
            provided_name = (report_name or "").strip()
            display_name = provided_name if provided_name else 'coding'

            unique_id = secrets.token_hex(6)
            new_schema = f"proj_{unique_id}"
            try:
                async with async_engine.begin() as conn:
                    await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
                    await conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{new_schema}".content_store (file_text text)'))
                    await conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{new_schema}".codebook (codebook_text text)'))
                    await conn.execute(text(f'TRUNCATE TABLE "{new_schema}".content_store'))
                    await conn.execute(text(f'TRUNCATE TABLE "{new_schema}".codebook'))
                    await conn.execute(text(f'INSERT INTO "{new_schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": classification_output})
                    await conn.execute(text(f'INSERT INTO "{new_schema}".codebook (codebook_text) VALUES (:codebook_text)'), {"codebook_text": codebook_text})

                async with AsyncDatabaseManager() as dm:
                    file_rec = File(user_id=user_id, filename=display_name, schemaname=new_schema, file_type='coding', systemprompt=system_prompt, userprompt=user_prompt)
                    dm.session.add(file_rec)
                    await dm.session.flush()
                    db_fr = await dm.session.execute(
                        select(File).where(File.schemaname == schema, File.user_id == user_id)
                    )
                    db_file = db_fr.scalar_one_or_none()
                    if db_file:
                        dep = FileDependency(child_file_id=file_rec.id, parent_file_id=db_file.id)
                        dm.session.add(dep)
                    cb_file = None
                    if resolved_codebook_schema:
                        cb_fr = await dm.session.execute(
                            select(File).where(
                                File.schemaname == resolved_codebook_schema,
                                File.user_id == user_id,
                            )
                        )
                        cb_file = cb_fr.scalar_one_or_none()
                    if not cb_file and codebook:
                        cb_fr2 = await dm.session.execute(
                            select(File).where(File.filename == codebook, File.user_id == user_id)
                        )
                        cb_file = cb_fr2.scalar_one_or_none()
                    if cb_file:
                        dep = FileDependency(child_file_id=file_rec.id, parent_file_id=cb_file.id)
                        dm.session.add(dep)
                    await dm.session.flush()
                    raw_fr = await dm.session.execute(
                        select(File)
                        .where(File.schemaname == schema, File.file_type == "raw_data")
                        .options(selectinload(File.projects))
                    )
                    raw_file = raw_fr.scalar_one_or_none()
                    if raw_file:
                        for proj in raw_file.projects:
                            if proj not in file_rec.projects:
                                file_rec.projects.append(proj)
                        await dm.session.flush()
                    await dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='content_store', row_count=1)
                    await dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='codebook', row_count=1)
            except Exception as e:
                print(f"Failed to persist classification project/schema: {e}")
        

        return JSONResponse({"classification_output": classification_output})
    except Exception as exc:
        print(f"Error reading schema {schema}: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/compare-codings/")
async def compare_codings(request: Request, coding_a: str = Form(...), coding_b: str = Form(...), api_key: str = Form(...), model: str = Form(None), prompt: str = Form("")):
    """Compare two coding outputs stored in Postgres schemas by calling the LLM and return the full message."""
    from .utils import codebook_get_client, MODEL_3

    schema_a = (coding_a or "").strip()
    schema_b = (coding_b or "").strip()

    if not schema_a.startswith("proj_") or not schema_b.startswith("proj_"):
        return JSONResponse({"error": "schema names must be proj_<id>"}, status_code=400)

    if not api_key:
        return JSONResponse({"error": "api_key is required"}, status_code=400)

    try:
        async with async_engine.connect() as conn:
            ar = await conn.execute(text(f'SELECT file_text FROM "{schema_a}".content_store LIMIT 1'))
            br = await conn.execute(text(f'SELECT file_text FROM "{schema_b}".content_store LIMIT 1'))
            a_row = ar.fetchone()
            b_row = br.fetchone()

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
            "Return the full comparison in a markdown format."
        )

        user_prompt = f"Coding A: {text_a} Coding B: {text_b} Please compare them in detail. Additional instructions: {prompt}"

        chosen_model = model or MODEL_3

        resp = await asyncio.to_thread(
            codebook_get_client, system_prompt, user_prompt, api_key, chosen_model
        )
        return JSONResponse({"comparison": resp})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/summarize-coding/")
async def summarize_coding(request: Request, coding: str = Form(...), api_key: str = Form(...), model: str = Form(None), prompt: str = Form("")):
    """Summarize a coding output stored in Postgres schema by calling the LLM and return the summary."""
    from backend.scripts.summarize_coding import summarize_coding as summarize_coding_function

    print("[summarize-coding] Endpoint called")
    schema = (coding or "").strip()

    if not schema.startswith("proj_"):
        print(f"[summarize-coding] Invalid schema name: {schema}")
        return JSONResponse({"error": "schema name must be proj_<id>"}, status_code=400)

    if not api_key:
        print("[summarize-coding] No API key provided")
        return JSONResponse({"error": "api_key is required"}, status_code=400)

    try:
        print(f"[summarize-coding] Retrieving data from schema: {schema}")
        async with async_engine.connect() as conn:
            rr = await conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
            row = rr.fetchone()

        coding_data = (row[0] if row else "") or ""
        print(f"[summarize-coding] Retrieved coding data length: {len(coding_data)}")

        if not coding_data:
            print("[summarize-coding] No content found in coding data")
            return JSONResponse({"error": "No content found in coding"}, status_code=400)

        print("[summarize-coding] Calling summarize_coding function")
        summary = await asyncio.to_thread(
            summarize_coding_function, coding_data, prompt, api_key, model
        )
        print(f"[summarize-coding] Summary generated, length: {len(summary)}")
        return JSONResponse({"summary": summary})
    except Exception as exc:
        print(f"[summarize-coding] Error: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)