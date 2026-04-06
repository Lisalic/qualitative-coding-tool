from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, select
import json
import secrets
import traceback

from backend.app.api.utils import get_user_id_from_request
from backend.app.database import get_db, File, FileDependency, Project, async_engine, engine
from backend.app.databasemanager import AsyncDatabaseManager
from backend.scripts.display_codebook import parse_codebook_to_json

router = APIRouter()


@router.get("/codebook")
async def get_codebook(codebook_id: str = None, db: Session = Depends(get_db)):
    """Get a codebook file."""
    file_rec = None
    if codebook_id:
        # try schemaname match (include comparisons)
        file_rec = db.query(File).filter(File.file_type.in_(['codebook', 'codebook_comparison']), File.schemaname == codebook_id).first()
        if not file_rec:
            # try filename match
            file_rec = db.query(File).filter(File.file_type.in_(['codebook', 'codebook_comparison']), File.filename == codebook_id).first()
        if not file_rec:
            # try id match (integer)
            try:
                fid = int(codebook_id)
            except Exception:
                file_rec = None
            else:
                file_rec = db.query(File).filter(File.file_type.in_(['codebook', 'codebook_comparison']), File.id == fid).first()
    else:
        # No id supplied: pick latest codebook or codebook_comparison file if any
        file_rec = db.query(File).filter(File.file_type.in_(['codebook', 'codebook_comparison'])).order_by(File.created_at.desc()).first()

    if file_rec:
        schema = file_rec.schemaname
        try:
            with engine.connect() as conn:
                res = conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
                row = res.fetchone()
                if row:
                    return JSONResponse({
                        "codebook": row[0],
                        "systemprompt": file_rec.systemprompt,
                        "userprompt": file_rec.userprompt
                    })
                else:
                    return JSONResponse({"error": "Codebook content not found in file"}, status_code=404)
        except Exception as e:
            return JSONResponse({"error": f"Error reading codebook: {e}"}, status_code=500)

    return JSONResponse({"error": "No codebook file found"}, status_code=404)


@router.get("/parse-codebook")
async def parse_codebook(codebook_id: str = None, db: Session = Depends(get_db)):
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
            except Exception:
                file_rec = None
            else:
                file_rec = db.query(File).filter(File.file_type == 'codebook', File.id == fid).first()
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
        return JSONResponse({"error": f"Error reading codebook: {e}"}, status_code=500)


@router.get("/list-codebooks")
async def list_codebooks(db: Session = Depends(get_db)):
    codebooks = []
    try:
        files = db.query(File).filter(File.file_type.in_(['codebook', 'codebook_comparison'])).all()
        for p in files:
            codebooks.append({
                "id": str(p.id),
                "name": p.filename,
                "metadata": {"schema": p.schemaname, "created_at": p.created_at.isoformat() if p.created_at else None, "file_type": p.file_type},
                "description": p.description,
                "source": "file",
            })
    except Exception:
        return JSONResponse({"codebooks": []})

    codebooks.sort(key=lambda x: x.get("name") or x.get("id"))
    return JSONResponse({"codebooks": codebooks})


@router.post("/save-file-codebook/")
async def save_project_codebook(request: Request, schema_name: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    """Save codebook content to file schema."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    schema = schema_name.strip()

    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File/project not found or you do not have permission")

    display_name = None
    try:
        # Try to read optional display_name from form data
        form = await request.form()
        if "display_name" in form:
            display_name = str(form.get("display_name"))
    except Exception:
        display_name = None

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


@router.post("/generate-codebook/")
async def generate_codebook(request: Request, database: str = Form("original"), api_key: str = Form(...), prompt: str = Form(""), name: str = Form(...), description: str = Form(None), project_id: int = Form(None), model: str = Form(""), sample_percentage: float = Form(100.0)):
    from .utils import engine, MODEL_1
    from backend.scripts.codebook_generator import generate_codebook
    import asyncio
    import inspect
    import math

    schema = (database or "").strip()

    if not schema.startswith('proj_'):
        return JSONResponse({"error": "This endpoint currently expects a proj_<id> schema name"}, status_code=400)

    try:
        sample_percentage = max(0.0, min(100.0, float(sample_percentage)))
        assembled = ""
        with engine.connect() as conn:
            # Check submissions table
            subs_tbl = f"{schema}.submissions"
            subs_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": subs_tbl}).scalar()
            if subs_exists:
                subs_total = int(conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."submissions"')).scalar() or 0)
                subs_limit = math.ceil((subs_total * sample_percentage) / 100.0)
                rows = []
                if subs_limit > 0:
                    rows = conn.execute(
                        text(
                            f'SELECT title, selftext FROM "{schema}"."submissions" ORDER BY RANDOM() LIMIT :sample_limit'
                        ),
                        {"sample_limit": subs_limit},
                    ).fetchall()
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
                comm_total = int(conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."comments"')).scalar() or 0)
                comm_limit = math.ceil((comm_total * sample_percentage) / 100.0)
                rows = []
                if comm_limit > 0:
                    rows = conn.execute(
                        text(
                            f'SELECT body FROM "{schema}"."comments" ORDER BY RANDOM() LIMIT :sample_limit'
                        ),
                        {"sample_limit": comm_limit},
                    ).fetchall()
                for r in rows:
                    try:
                        body = r._mapping.get('body')
                    except Exception:
                        body = r[0] if len(r) > 0 else ""
                    assembled += f"{body or ''}\n\n"
            else:
                print(f"[DEBUG] generate_codebook: comments table not found in schema {schema}")


        if not assembled.strip():
            return JSONResponse(
                {
                    "error": "No records were sampled from the selected database. Increase sample size above 0%."
                },
                status_code=400,
            )

        try:
            print("[INFO] generate_codebook: calling generate_codebook function")
            chosen_model = model or MODEL_1
            result = generate_codebook(assembled, api_key, prompt, MODEL=chosen_model)
            if asyncio.iscoroutine(result) or inspect.isawaitable(result):
                result = await result
            codebook_text, system_prompt, user_prompt = result
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

            async with async_engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
                await conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{new_schema}".content_store (file_text text)'))
                await conn.execute(text(f'TRUNCATE TABLE "{new_schema}".content_store'))
                await conn.execute(text(f'INSERT INTO "{new_schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": codebook_text})

            # Persist provided description (do not append agreement percent)
            final_description = (description or "").strip() if description is not None else None
            if final_description == "":
                final_description = None

            async with AsyncDatabaseManager() as dm:
                file_rec = File(user_id=user_id, filename=name, schemaname=new_schema, file_type='codebook', description=final_description, systemprompt=system_prompt, userprompt=user_prompt)
                dm.session.add(file_rec)
                await dm.session.flush()
                pf = await dm.session.execute(
                    select(File).where(File.schemaname == schema, File.user_id == user_id)
                )
                parent_file = pf.scalar_one_or_none()
                if parent_file:
                    dep = FileDependency(child_file_id=file_rec.id, parent_file_id=parent_file.id)
                    dm.session.add(dep)
                    await dm.session.flush()
                await dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='content_store', row_count=1)

                if project_id is not None:
                    try:
                        pr = await dm.session.execute(select(Project).where(Project.id == project_id))
                        proj = pr.scalar_one_or_none()
                        if proj is None:
                            raise HTTPException(status_code=404, detail="Project not found")
                        if proj.user_id != user_id:
                            raise HTTPException(status_code=403, detail="Forbidden: project does not belong to user")
                        file_rec.projects.append(proj)
                        await dm.session.flush()
                    except HTTPException:
                        raise
                    except Exception:
                        await dm.session.rollback()

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
async def compare_codebooks(request: Request, codebook_a: str = Form(...), codebook_b: str = Form(...), api_key: str = Form(...), model: str = Form(None), prompt: str = Form("")):
    """Compare two codebooks stored in Postgres schemas by calling the LLM and return the full message."""
    from .utils import engine, MODEL_3, codebook_get_client

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

        user_prompt = f"Codebook A: {text_a} Codebook B: {text_b} Please compare them in detail. Additional instructions: {prompt}"

        # choose model if provided, otherwise use MODEL_3 if available
        chosen_model = model or MODEL_3

        resp = codebook_get_client(system_prompt, user_prompt, api_key, chosen_model)
        return JSONResponse({"comparison": resp})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)