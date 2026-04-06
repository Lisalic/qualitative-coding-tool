import json
import secrets
import traceback
from fastapi import APIRouter, HTTPException, Form, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.utils import get_user_id_from_request
from backend.app.database import get_db, get_async_db, Project, File, FileTable, FileDependency, async_engine
from backend.app.databasemanager import AsyncDatabaseManager

router = APIRouter()


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
        async with AsyncDatabaseManager() as dm:
            file_rec = File(user_id=user_id, filename=base_name, schemaname=schema_name, file_type=(file_type or "comparison"), description=(description or None))
            dm.session.add(file_rec)
            try:
                await dm.session.flush()
            except Exception:
                await dm.session.rollback()
                raise

            if parent_file_ids:
                try:
                    parent_ids = json.loads(parent_file_ids) if isinstance(parent_file_ids, str) else parent_file_ids
                    for pid in parent_ids:
                        dep = FileDependency(child_file_id=file_rec.id, parent_file_id=int(pid))
                        dm.session.add(dep)
                    await dm.session.flush()
                except Exception:
                    await dm.session.rollback()

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

            async with async_engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
                await conn.execute(text(f'''
                    CREATE TABLE IF NOT EXISTS "{schema_name}"."content_store" (
                        id SERIAL PRIMARY KEY,
                        file_text TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
                    )
                '''))
                await conn.execute(text(f'INSERT INTO "{schema_name}"."content_store" (file_text) VALUES (:file_text)'), {"file_text": content})

            return JSONResponse({"message": "Saved", "file_id": file_rec.id, "schema_name": schema_name})
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/save-summary/")
async def save_summary(request: Request, content: str = Form(...), name: str = Form(...), description: str = Form(None), project_id: int = Form(None), db: Session = Depends(get_db)):
    """Save a generated summary into a new Postgres schema and create a File record of type 'summary'.
    Associates the file with a project when `project_id` is provided and belongs to the authenticated user.
    """
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not content:
        raise HTTPException(status_code=400, detail="content is required")

    try:
        unique_id = secrets.token_hex(6)
        new_schema = f"sum_{unique_id}"

        async with async_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{new_schema}"'))
            await conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{new_schema}".content_store (file_text text)'))
            await conn.execute(text(f'TRUNCATE TABLE "{new_schema}".content_store'))
            await conn.execute(text(f'INSERT INTO "{new_schema}".content_store (file_text) VALUES (:file_text)'), {"file_text": content})

        final_description = (description or "").strip() if description is not None else None
        if final_description == "":
            final_description = None

        async with AsyncDatabaseManager() as dm:
            file_rec = File(user_id=user_id, filename=name, schemaname=new_schema, file_type='summary', description=final_description)
            dm.session.add(file_rec)
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

        return JSONResponse({"message": "Summary saved", "file": {"id": str(file_rec.id), "schema_name": new_schema, "filename": file_rec.filename}})
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary/{summary_id}")
async def get_summary_file(summary_id: str = None, db: AsyncSession = Depends(get_async_db)):
    """Return summary content stored in a File record with file_type='summary'.
    Matches by schemaname, filename, or numeric id. If no id provided, returns latest.
    """
    file_rec = None
    if summary_id:
        r = await db.execute(
            select(File).where(File.file_type == "summary", File.schemaname == summary_id)
        )
        file_rec = r.scalar_one_or_none()
        if not file_rec:
            r = await db.execute(
                select(File).where(File.file_type == "summary", File.filename == summary_id)
            )
            file_rec = r.scalar_one_or_none()
        if not file_rec:
            try:
                fid = int(summary_id)
                r = await db.execute(
                    select(File).where(File.file_type == "summary", File.id == fid)
                )
                file_rec = r.scalar_one_or_none()
            except Exception:
                file_rec = None
    else:
        r = await db.execute(
            select(File)
            .where(File.file_type == "summary")
            .order_by(File.created_at.desc())
            .limit(1)
        )
        file_rec = r.scalars().first()

    if file_rec:
        schema = file_rec.schemaname
        try:
            async with async_engine.connect() as conn:
                tbl_exists = (
                    await conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.content_store"})
                ).scalar()
                if not tbl_exists:
                    return JSONResponse({"error": f"content_store table not found in schema {schema}"}, status_code=404)
                res = await conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
                row = res.fetchone()
                if row:
                    return JSONResponse({
                        "summary": {
                            "content": row[0],
                            "display_name": file_rec.filename,
                            "description": file_rec.description,
                        }
                    })
                return JSONResponse({"error": "Summary content not found in file"}, status_code=404)
        except Exception as e:
            print(f"Error reading summary from schema {schema}: {e}")
            return JSONResponse({"error": f"Error reading summary: {e}"}, status_code=500)

    return JSONResponse({"error": "No summary file found"}, status_code=404)