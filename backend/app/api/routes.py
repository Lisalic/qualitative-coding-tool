import os
import sqlite3
import sys
import json
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, Form
from fastapi.responses import JSONResponse

from app.config import settings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts'))
from import_db import import_from_zst_file
from filter_db import main as filter_database_with_ai

router = APIRouter()

UPLOADS_DIR = Path(__file__).resolve().parent.parent / 'uploads'
DB_PATH = Path(settings.reddit_db_path)
os.makedirs(UPLOADS_DIR, exist_ok=True)


@router.post("/upload-zst/")
async def upload_zst_file(
    file: UploadFile = File(...), 
    subreddits: str = Form(None)
):
    print(f"Received upload request for file: {file.filename}")
    
    if not file.filename.endswith('.zst'):
        print("File rejected: not a .zst file")
        raise HTTPException(status_code=400, detail="File must be a .zst file")

    # Parse subreddits if provided
    subreddit_list = None
    if subreddits:
        try:
            subreddit_list = json.loads(subreddits)
            print(f"Subreddit filter: {subreddit_list}")
        except json.JSONDecodeError:
            print("Invalid subreddit JSON")
            raise HTTPException(status_code=400, detail="Invalid subreddits format")

    file_path = UPLOADS_DIR / file.filename
    print(f"Saving file to: {file_path}")
    
    try:
        content = await file.read()
        with open(file_path, 'wb') as fh:
            fh.write(content)
        print(f"File saved successfully, size: {len(content)} bytes")

        # Perform import synchronously
        print("Starting synchronous import...")
        # Always import to the main DB, never to filtered DB
        stats = import_from_zst_file(str(file_path), str(DB_PATH), subreddit_list)
        print(f"Import completed successfully: {stats}")

        # Return response with import statistics
        response_data = {
            "status": "completed",
            "message": "Import completed successfully",
            "database": "reddit_data.db",
            "file_path": str(file_path),
            "stats": stats
        }
        print(f"Sending response: {response_data}")
        return JSONResponse(response_data)
        
    except Exception as exc:
        print(f"Error during upload/import: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error uploading/importing file: {exc}")


@router.get("/database-entries/")
async def get_database_entries(limit: int = 5, database: str = "original"):
    db_path = DB_PATH
    if database == "filtered":
        db_path = DB_PATH.parent / "filtereddata.db"
    elif database == "codebook":
        db_path = DB_PATH.parent / "codebook.db"
    elif database == "coding":
        db_path = DB_PATH.parent / "codeddata.db"

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
            # For codebook database, assume different schema
            cursor.execute('SELECT COUNT(*) as count FROM codebooks')
            sub_count = cursor.fetchone()['count']
            cursor.execute('SELECT * FROM codebooks LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            comments = []  # No comments in codebook
            com_count = 0
        elif database == "coding":
            # For coding database, assume different schema
            cursor.execute('SELECT COUNT(*) as count FROM codings')
            sub_count = cursor.fetchone()['count']
            cursor.execute('SELECT * FROM codings LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            comments = []  # No comments in coding
            com_count = 0
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
        "database": database
    })


@router.post("/filter-data/")
async def filter_database(api_key: str = Form(...), prompt: str = Form("")):
    if not api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required")

    try:
        result = filter_database_with_ai(api_key=api_key, prompt=prompt or None)
        return JSONResponse(result)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
