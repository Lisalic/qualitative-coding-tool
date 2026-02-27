from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

from .utils import get_user_id_from_request, engine
from app.database import get_db, File, FileDependency, Project, SessionLocal
from app.databasemanager import DatabaseManager

router = APIRouter()


@router.get("/coded-data")
async def get_coded_data_query(coded_id: str = None, db: Session = Depends(get_db)):
    """Return coded data stored in a File record with file_type='coding' or 'coding_comparison'.
    """
    file_rec = None
    if coded_id:
        file_rec = db.query(File).filter(File.file_type.in_(['coding', 'coding_comparison']), File.schemaname == coded_id).first()
        if not file_rec:
            file_rec = db.query(File).filter(File.file_type.in_(['coding', 'coding_comparison']), File.filename == coded_id).first()
        if not file_rec:
            try:
                fid = int(coded_id)
                file_rec = db.query(File).filter(File.file_type.in_(['coding', 'coding_comparison']), File.id == fid).first()
            except Exception:
                file_rec = None
    else:
        file_rec = db.query(File).filter(File.file_type.in_(['coding', 'coding_comparison'])).order_by(File.created_at.desc()).first()

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
                    return JSONResponse({
                        "coded_data": row[0],
                        "systemprompt": file_rec.systemprompt,
                        "userprompt": file_rec.userprompt
                    })
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
    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == user_id, File.file_type == 'coding').first()
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


@router.post("/apply-codebook/")
async def apply_codebook(request: Request, database: str = Form(...), codebook: str = Form(...), methodology: str = Form(""), report_name: str = Form(None), api_key: str = Form(...), model: str = Form("")):
    """Open the Postgres schema provided by `database`, read `submissions.title`/`selftext`
    and `comments.body`, assemble them into a single string, print it to stdout and
    return a preview in the response.
    """
    from .utils import classify_posts
    import secrets

    print(f"DEBUG: apply_codebook called with codebook='{codebook}', database='{database}'")

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
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."submissions" LIMIT 100')).fetchall()  # Limit to 100 posts for AI processing
                for r in rows:
                    try:
                        post_id = r._mapping.get('id')
                        title = r._mapping.get('title')
                        selftext = r._mapping.get('selftext')
                    except Exception:
                        post_id = r[0] if len(r) > 0 else ""
                        title = r[1] if len(r) > 1 else ""
                        selftext = r[2] if len(r) > 2 else ""
                    assembled += f"POST_ID: {post_id}\nTitle: {title or ''}\n{selftext or ''}\n\n"
            else:
                # submissions table missing — proceed with whatever content was found
                pass

            # Comments
            comm_tbl = f"{schema}.comments"
            comm_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": comm_tbl}).scalar()
            if comm_exists:
                rows = conn.execute(text(f'SELECT * FROM "{schema}"."comments" LIMIT 50')).fetchall()  # Limit comments too
                for r in rows:
                    try:
                        comment_id = r._mapping.get('id')
                        body = r._mapping.get('body')
                    except Exception:
                        comment_id = r[0] if len(r) > 0 else ""
                        body = r[1] if len(r) > 1 else ""
                    assembled += f"POST_ID: {comment_id}\n{body or ''}\n\n"
            else:
                # comments table missing — proceed
                pass


        cb_schema_raw = (codebook or "").strip()
        codebook_text = ""
        try:
            # provided codebook identifier (no stdout prints)
            print(f"DEBUG: Resolving codebook from input: '{cb_schema_raw}'")

            resolved_schema = None
            if cb_schema_raw and cb_schema_raw.startswith('proj_'):
                resolved_schema = cb_schema_raw
                print(f"DEBUG: Codebook starts with 'proj_', using as schema: {resolved_schema}")
            else:
                # Try to interpret the provided value as a File.id (integer) and resolve schemaname
                try:
                    fid = int(cb_schema_raw)
                    print(f"DEBUG: Treating '{cb_schema_raw}' as File ID: {fid}")
                    
                    # First, let's see what codebook files exist
                    db_sess = SessionLocal()
                    try:
                        all_codebooks = db_sess.query(File).filter(File.file_type.in_(['codebook', 'codebook_comparison'])).all()
                        print(f"DEBUG: Available codebook IDs: {[f'{cb.id}: {cb.filename} ({cb.file_type})' for cb in all_codebooks]}")
                        
                        f = db_sess.query(File).filter(File.id == fid, File.file_type.in_(['codebook', 'codebook_comparison'])).first()
                        if f:
                            resolved_schema = f.schemaname
                            print(f"DEBUG: Found codebook file with ID {fid}, schema: {resolved_schema}, type: {f.file_type}")
                        else:
                            print(f"DEBUG: No codebook file found with ID {fid} (checked {len(all_codebooks)} codebooks)")
                            # Try without file_type filter to see if it exists as a different type
                            any_file = db_sess.query(File).filter(File.id == fid).first()
                            if any_file:
                                print(f"DEBUG: File {fid} exists but has type: {any_file.file_type}")
                            else:
                                print(f"DEBUG: File {fid} does not exist at all")
                    finally:
                        try:
                            db_sess.close()
                        except Exception:
                            pass
                except Exception as e:
                    print(f"DEBUG: Could not parse '{cb_schema_raw}' as integer: {e}")
                    resolved_schema = None

            if resolved_schema:
                print(f"DEBUG: Querying codebook content from schema: {resolved_schema}")
                with engine.connect() as conn:
                    tbl_exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{resolved_schema}.content_store"}).scalar()
                    if tbl_exists:
                        res = conn.execute(text(f'SELECT file_text FROM "{resolved_schema}".content_store LIMIT 1'))
                        row = res.fetchone()
                        codebook_text = row[0] if row else ""
                        print(f"DEBUG: Retrieved codebook text, length: {len(codebook_text)}")
                    else:
                        print(f"DEBUG: content_store table not found in schema {resolved_schema}")
            else:
                print("DEBUG: Could not resolve codebook schema")
        except Exception as e:
            print(f"DEBUG: Exception during codebook resolution: {e}")
            import traceback
            traceback.print_exc()

        # Attempt classification using the provided codebook and API key
        classification_output = ""
        system_prompt = ""
        user_prompt = ""
        try:
            print(f"DEBUG: codebook_text length: {len(codebook_text)}, api_key provided: {bool(api_key)}")
            if codebook_text and api_key:
                print("DEBUG: Calling classify_posts...")
                result = classify_posts(codebook_text, assembled, methodology or "", api_key, model)
                classification_output, system_prompt, user_prompt = result
                print(f"DEBUG: classify_posts returned successfully, output length: {len(classification_output)}")
            else:
                error_msg = []
                if not codebook_text:
                    error_msg.append("codebook not found or empty")
                if not api_key:
                    error_msg.append("api_key not provided")
                classification_output = f"Cannot apply codebook: {', '.join(error_msg)}"
                print(f"DEBUG: Skipping classification: {classification_output}")
        except Exception as e:
            print(f"DEBUG: Exception during classification: {e}")
            import traceback
            traceback.print_exc()
            classification_output = f"API request error: {str(e)}"

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
                        file_rec = File(user_id=user_id, filename=display_name, schemaname=new_schema, file_type='coding', systemprompt=system_prompt, userprompt=user_prompt)
                        dm.session.add(file_rec)
                        dm.session.flush()
                        # Add dependencies for database and codebook
                        db_file = dm.session.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
                        if db_file:
                            dep = FileDependency(child_file_id=file_rec.id, parent_file_id=db_file.id)
                            dm.session.add(dep)
                        cb_file = dm.session.query(File).filter((File.schemaname == codebook) | (File.filename == codebook), File.user_id == user_id).first()
                        if cb_file:
                            dep = FileDependency(child_file_id=file_rec.id, parent_file_id=cb_file.id)
                            dm.session.add(dep)
                        dm.session.flush()
                        # Link the coding file to the same projects as the raw data
                        raw_file = dm.session.query(File).filter(File.schemaname == schema, File.file_type == "raw_data").first()
                        if raw_file:
                            for proj in raw_file.projects:
                                if proj not in file_rec.projects:
                                    file_rec.projects.append(proj)
                            dm.session.flush()
                        dm.file_tables.add_table_metadata(file_id=file_rec.id, table_name='content_store', row_count=1)
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
            "Return the full comparison in a markdown format."
        )

        user_prompt = f"Coding A: {text_a} Coding B: {text_b} Please compare them in detail. Additional instructions: {prompt}"

        chosen_model = model or MODEL_3

        resp = codebook_get_client(system_prompt, user_prompt, api_key, chosen_model)
        return JSONResponse({"comparison": resp})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/summarize-coding/")
async def summarize_coding(request: Request, coding: str = Form(...), api_key: str = Form(...), model: str = Form(None), prompt: str = Form("")):
    """Summarize a coding output stored in Postgres schema by calling the LLM and return the summary."""
    from scripts.summarize_coding import summarize_coding as summarize_coding_function

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
        with engine.connect() as conn:
            row = conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1')).fetchone()

        coding_data = (row[0] if row else "") or ""
        print(f"[summarize-coding] Retrieved coding data length: {len(coding_data)}")

        if not coding_data:
            print("[summarize-coding] No content found in coding data")
            return JSONResponse({"error": "No content found in coding"}, status_code=400)

        print("[summarize-coding] Calling summarize_coding function")
        summary = summarize_coding_function(coding_data, prompt, api_key, model)
        print(f"[summarize-coding] Summary generated, length: {len(summary)}")
        return JSONResponse({"summary": summary})
    except Exception as exc:
        print(f"[summarize-coding] Error: {exc}")
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)