from fastapi import APIRouter, HTTPException, Depends, Request, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

from .utils import get_user_id_from_request
from app.database import get_db, Project, File, FileTable, FileDependency
from app.databasemanager import DatabaseManager

router = APIRouter()


@router.get("/my-files/")
def my_projects(request: Request, file_type: str = Query("raw_data"), db: Session = Depends(get_db)):
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Use File table instead of Project; `file_type` query param maps to `file_type` on File
    # Allow callers requesting 'codebook' or 'coding' to also receive saved comparison files
    if file_type == 'codebook':
        files = db.query(File).filter(File.user_id == user_id, File.file_type.in_(['codebook', 'codebook_comparison'])).all()
    elif file_type == 'coding':
        files = db.query(File).filter(File.user_id == user_id, File.file_type.in_(['coding', 'coding_comparison'])).all()
    else:
        files = db.query(File).filter(File.user_id == user_id, File.file_type == file_type).all()
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

        # Query parent file IDs
        parent_files = []
        try:
            deps = db.query(FileDependency).filter(FileDependency.child_file_id == p.id).all()
            for d in deps:
                parent_file = db.query(File).filter(File.id == d.parent_file_id).first()
                if parent_file:
                    parent_files.append({
                        "id": str(parent_file.id),
                        "name": parent_file.filename,
                        "schema_name": parent_file.schemaname,
                        "type": parent_file.file_type
                    })
        except Exception:
            parent_files = []

        result.append({
            "id": str(p.id),
            "display_name": p.filename,
            "description": p.description,
            "schema_name": p.schemaname,
            "file_type": p.file_type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "tables": tables,
            "parent_files": parent_files,
        })

    # Return under the legacy "projects" key so frontend code expecting
    # `data.projects` continues to work.
    return JSONResponse({"projects": result})


@router.post("/create-project/")
def create_project(request: Request, name: str = Form(...), description: str = Form(None), db: Session = Depends(get_db)):
    """Create a new project."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    # create project record (no schema_name column in DB)
    proj = Project(user_id=user_id, projectname=name.strip(), description=(description or None))
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
    """Update a project."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.user_id != user_id:
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
    """List user's projects."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    with DatabaseManager() as dm:
        rows = dm.projects.get_all_for_user(user_id)
        result = []
        for r in rows:
            # Include associated files (databases) for each project
            files = []
            try:
                for f in getattr(r, "files", []) or []:
                    # Query parent files
                    parent_files = []
                    try:
                        deps = dm.session.query(FileDependency).filter(FileDependency.child_file_id == f.id).all()
                        for d in deps:
                            parent_file = dm.session.query(File).filter(File.id == d.parent_file_id).first()
                            if parent_file:
                                parent_files.append({
                                    "id": str(parent_file.id),
                                    "name": parent_file.filename,
                                    "type": parent_file.file_type
                                })
                    except Exception:
                        parent_files = []
                    files.append({
                        "id": str(f.id),
                        "display_name": f.filename,
                        "schema_name": f.schemaname,
                        "file_type": f.file_type,
                        "description": f.description,
                        "created_at": f.created_at.isoformat() if f.created_at else None,
                        "parent_files": parent_files,
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


@router.post("/rename-file/")
def rename_project(request: Request, schema_name: str = Form(...), display_name: str = Form(...), description: str = Form(None), db: Session = Depends(get_db)):
    """Rename a file's display_name. Requires authentication and ownership."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    schema = schema_name.strip()

    file_rec = db.query(File).filter(File.schemaname == schema, File.user_id == user_id).first()
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