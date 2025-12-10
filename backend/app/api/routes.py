import os
import sqlite3
import sys
import json
import tempfile
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, Form
from fastapi.responses import JSONResponse

from app.config import settings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts'))
from import_db import import_from_zst_file
from filter_db import main as filter_database_with_ai
from codebook_generator import main as generate_codebook_main
from codebook_apply import main as apply_codebook_main

router = APIRouter()

DB_PATH = Path(settings.reddit_db_path)


@router.post("/upload-zst/")
async def upload_zst_file(
    file: UploadFile = File(...), 
    subreddits: str = Form(None)
):
    print(f"Received upload request for file: {file.filename}")
    
    if not file.filename.endswith('.zst'):
        print("File rejected: not a .zst file")
        raise HTTPException(status_code=400, detail="File must be a .zst file")

    subreddit_list = None
    if subreddits:
        try:
            subreddit_list = json.loads(subreddits)
            print(f"Subreddit filter: {subreddit_list}")
        except json.JSONDecodeError:
            print("Invalid subreddit JSON")
            raise HTTPException(status_code=400, detail="Invalid subreddits format")

    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix='.zst', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        print(f"File temporarily saved to: {tmp_path}, size: {len(content)} bytes")

        stats = import_from_zst_file(tmp_path, str(DB_PATH), subreddit_list)
        print(f"Import completed successfully: {stats}")

        os.unlink(tmp_path)

        response_data = {
            "status": "completed",
            "message": "Import completed successfully",
            "database": str(DB_PATH.relative_to(DB_PATH.parent.parent)),
            "file_name": file.filename,
            "stats": stats
        }
        print(f"Sending response: {response_data}")
        return JSONResponse(response_data)
        
    except Exception as exc:
        print(f"Error during upload/import: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error uploading/importing file: {exc}")


@router.get("/codebook")
async def get_codebook():
    codebook_path = Path(__file__).parent.parent.parent.parent / "data" / "codebook.txt"
    if codebook_path.exists():
        with open(codebook_path, 'r') as f:
            codebook_content = f.read()
        return JSONResponse({"codebook": codebook_content})
    else:
        return JSONResponse({"status": "processing", "message": "Codebook generation in progress. Please try again later."})


@router.get("/classification-report")
async def get_classification_report():
    report_path = Path(__file__).parent.parent.parent.parent / "data" / "classification_report.txt"
    if report_path.exists():
        with open(report_path, 'r') as f:
            report_content = f.read()
        return JSONResponse({"classification_report": report_content})
    else:
        return JSONResponse({"error": "Classification report not found. Please apply a codebook first."}, status_code=404)


@router.get("/database-entries/")
async def get_database_entries(limit: int = 10, database: str = "original"):
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
async def generate_codebook(database: str = Form("original"), api_key: str = Form(...)):
    db_path = Path(settings.reddit_db_path)
    if database == "filtered":
        db_path = db_path.parent / "filtereddata.db"
    
    if not db_path.exists():
        db_name = "Reddit Data" if database == "original" else "Filtered Data"
        return JSONResponse({"error": f"{db_name} database not found. Please import and filter data first."}, status_code=404)
    
    try:
        generate_codebook_main(str(db_path), api_key)
        # Read the generated codebook.txt
        import os
        print(f"Current working directory: {os.getcwd()}")
        codebook_path = Path(__file__).parent.parent.parent.parent / "data" / "codebook.txt"
        print(f"Looking for codebook at: {codebook_path}")
        if codebook_path.exists():
            with open(codebook_path, 'r') as f:
                codebook_content = f.read()
            return JSONResponse({"codebook": codebook_content})
        else:
            print(f"Codebook file not found at: {codebook_path}")
            return JSONResponse({"error": "Codebook file not found"})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/apply-codebook/")
async def apply_codebook(
    database: str = Form("original"), 
    api_key: str = Form(...), 
    methodology: str = Form("")
):
    db_path = Path(settings.reddit_db_path)
    if database == "filtered":
        db_path = db_path.parent / "filtereddata.db"
    
    if not db_path.exists():
        db_name = "Reddit Data" if database == "original" else "Filtered Data"
        return JSONResponse({"error": f"{db_name} database not found. Please import and filter data first."}, status_code=404)
    
    try:
        apply_codebook_main(str(db_path), api_key, methodology)
        # Read the generated classification report
        report_path = Path(__file__).parent.parent.parent.parent / "data" / "classification_report.txt"
        if report_path.exists():
            with open(report_path, 'r') as f:
                report_content = f.read()
            return JSONResponse({"classification_report": report_content})
        else:
            return JSONResponse({"error": "Classification report not found"})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
