import os
import sqlite3
import sys
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts'))
from import_db import import_from_zst_file

router = APIRouter()

UPLOADS_DIR = Path(__file__).resolve().parent.parent / 'uploads'
DB_PATH = Path(settings.reddit_db_path)
os.makedirs(UPLOADS_DIR, exist_ok=True)


@router.post("/upload-zst/")
async def upload_zst_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.zst'):
        raise HTTPException(status_code=400, detail="File must be a .zst file")

    file_path = UPLOADS_DIR / file.filename
    try:
        content = await file.read()
        with open(file_path, 'wb') as fh:
            fh.write(content)

        stats = import_from_zst_file(str(file_path), str(DB_PATH))

        return JSONResponse({
            "status": "success",
            "message": "File imported successfully",
            "database": "reddit_data.db",
            "file_path": str(file_path),
            "stats": stats,
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error importing file: {exc}")


@router.get("/database-entries/")
async def get_database_entries(limit: int = 5):
    if not DB_PATH.exists():
        return JSONResponse({
            "submissions": [],
            "comments": [],
            "total_submissions": 0,
            "total_comments": 0,
            "message": "Database not found. Please upload a file first.",
        })

    conn = None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

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
    })
