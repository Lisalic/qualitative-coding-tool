import os
import sqlite3
import sys
import json
import tempfile
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, Form, Query
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
    subreddits: str = Form(None),
    data_type: str = Form(...),
    name: str = Form(None)
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

    # Process data type
    if data_type not in ["submissions", "comments"]:
        raise HTTPException(status_code=400, detail="data_type must be 'submissions' or 'comments'")
    import_data_type = data_type
    print(f"Data type: {import_data_type}")

    # Generate unique database name
    database_dir = Path(settings.database_dir)
    database_dir.mkdir(parents=True, exist_ok=True)
    base_name = name.strip() if name else file.filename.replace('.zst', '')
    counter = 1
    db_name = f"{base_name}{counter}.db"
    db_path = database_dir / db_name
    while db_path.exists():
        counter += 1
        db_name = f"{base_name}{counter}.db"
        db_path = database_dir / db_name

    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix='.zst', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        print(f"File temporarily saved to: {tmp_path}, size: {len(content)} bytes")

        stats = import_from_zst_file(tmp_path, str(db_path), subreddit_list, import_data_type)
        print(f"Import completed successfully: {stats}")

        os.unlink(tmp_path)

        count = stats['comments_imported'] if import_data_type == 'comments' else stats['submissions_imported']
        
        response_data = {
            "status": "completed",
            "message": f"Created {db_name} with {count} {import_data_type}",
            "database": db_name,
            "file_name": file.filename,
            "stats": stats
        }
        print(f"Sending response: {response_data}")
        return JSONResponse(response_data)
        
    except Exception as exc:
        print(f"Error during upload/import: {exc}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/list-databases/")
async def list_databases():
    database_dir = Path(settings.database_dir)
    if not database_dir.exists():
        return JSONResponse({"databases": []})
    
    databases = []
    for f in database_dir.iterdir():
        if f.is_file() and f.name.endswith('.db'):
            metadata = get_database_metadata(f)
            databases.append({
                "name": f.name,
                "metadata": metadata
            })
    
    return JSONResponse({"databases": databases})


def get_database_metadata(db_path):
    """Get metadata for a database file."""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get submission count
        cursor.execute("SELECT COUNT(*) FROM submissions")
        submission_count = cursor.fetchone()[0]
        
        # Get comment count
        cursor.execute("SELECT COUNT(*) FROM comments")
        comment_count = cursor.fetchone()[0]
        
        conn.close()
        
        # Get file creation date
        import os
        creation_time = os.path.getctime(str(db_path))
        
        return {
            "total_submissions": submission_count,
            "total_comments": comment_count,
            "date_created": creation_time if creation_time > 0 else None
        }
    except Exception as e:
        print(f"Error getting metadata for {db_path}: {e}")
        return {
            "total_submissions": 0,
            "total_comments": 0,
            "date_created": None
        }


@router.get("/list-filtered-databases/")
async def list_filtered_databases():
    filtered_database_dir = Path(settings.filtered_database_dir)
    # Debug logging to help identify why files might not be listed
    try:
        print(f"[DEBUG] list_filtered_databases -> resolved: {filtered_database_dir}")
        print(f"[DEBUG] exists: {filtered_database_dir.exists()}")
        if filtered_database_dir.exists():
            print(f"[DEBUG] contents: {[p.name for p in filtered_database_dir.iterdir()]}")
    except Exception as e:
        print(f"[DEBUG] error inspecting filtered_database_dir: {e}")

    if not filtered_database_dir.exists():
        return JSONResponse({"databases": []})

    databases = [f.name for f in filtered_database_dir.iterdir() if f.is_file() and f.name.endswith('.db')]
    return JSONResponse({"databases": databases})


@router.post("/merge-databases/")
async def merge_databases(databases: str = Form(...), name: str = Form(...)):
    try:
        db_list = json.loads(databases)
        print(f"Merging databases: {db_list} into {name}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid databases format")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Database name is required")

    database_dir = Path(settings.database_dir)
    print(f"Database directory: {database_dir}")
    
    # Ensure name has .db extension
    if not name.endswith('.db'):
        name = f"{name}.db"
    
    merged_path = database_dir / name
    print(f"Merged database path: {merged_path}")
    
    # Check if database with this name already exists
    if merged_path.exists():
        raise HTTPException(status_code=400, detail=f"Database '{name}' already exists")

    # Create new merged DB
    try:
        merged_conn = sqlite3.connect(str(merged_path))
        print("Created merged database connection")
    except Exception as e:
        print(f"Error creating merged database: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create database: {str(e)}")
    merged_conn.execute('''
        CREATE TABLE submissions (
        id TEXT PRIMARY KEY,
        subreddit TEXT,
        title TEXT,
        selftext TEXT,
        author TEXT,
        created_utc INTEGER,
        score INTEGER,
        num_comments INTEGER
        )
    ''')
    merged_conn.execute('''
        CREATE TABLE comments (
            id TEXT PRIMARY KEY,
            subreddit TEXT,
            body TEXT,
            author TEXT,
            created_utc INTEGER,
            score INTEGER,
            link_id TEXT,
            parent_id TEXT
        )
    ''')
    merged_conn.commit()

    for db_name in db_list:
        db_path = database_dir / db_name
        print(f"Processing database: {db_name}, path: {db_path}, exists: {db_path.exists()}")
        if not db_path.exists():
            print(f"Database {db_name} does not exist, skipping")
            continue
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            print(f"Connected to {db_name}")
            
            # Check if submissions table exists and copy data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='submissions'")
            if cursor.fetchone():
                cursor.execute('SELECT COUNT(*) FROM submissions')
                sub_count = cursor.fetchone()[0]
                print(f"Found {sub_count} submissions in {db_name}")
                cursor.execute('SELECT * FROM submissions')
                submissions = cursor.fetchall()
                print(f"Retrieved {len(submissions)} submissions from {db_name}")
                try:
                    merged_conn.executemany('INSERT OR IGNORE INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?)', submissions)
                    print(f"Inserted submissions from {db_name}")
                except Exception as e:
                    print(f"Error inserting submissions from {db_name}: {e}")
            else:
                print(f"No submissions table in {db_name}")
            
            # Check if comments table exists and copy data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comments'")
            if cursor.fetchone():
                cursor.execute('SELECT COUNT(*) FROM comments')
                comment_count = cursor.fetchone()[0]
                print(f"Found {comment_count} comments in {db_name}")
                cursor.execute('SELECT * FROM comments')
                comments = cursor.fetchall()
                print(f"Retrieved {len(comments)} comments from {db_name}")
                try:
                    merged_conn.executemany('INSERT OR IGNORE INTO comments VALUES (?, ?, ?, ?, ?, ?, ?, ?)', comments)
                    print(f"Inserted comments from {db_name}")
                except Exception as e:
                    print(f"Error inserting comments from {db_name}: {e}")
            else:
                print(f"No comments table in {db_name}")
            
            conn.close()
            print(f"Successfully processed {db_name}")
        except Exception as e:
            print(f"Error merging {db_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    try:
        merged_conn.commit()
        print("Committed merged database")
    except Exception as e:
        print(f"Error committing merged database: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to commit merged database: {str(e)}")
    
    try:
        merged_conn.close()
        print("Closed merged database connection")
    except Exception as e:
        print(f"Error closing merged database: {e}")
    
    return JSONResponse({"message": f"Databases merged into '{name}' successfully"})


@router.delete("/delete-database/{db_name}")
async def delete_database(db_name: str):
    database_dir = Path(settings.database_dir)
    db_path = database_dir / db_name
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")
    
    if not db_name.endswith('.db'):
        raise HTTPException(status_code=400, detail="Invalid database name")
    
    try:
        db_path.unlink()
        return JSONResponse({"message": f"Database '{db_name}' deleted successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete database: {str(e)}")


@router.post("/rename-database/")
async def rename_database(old_name: str = Form(...), new_name: str = Form(...)):
    database_dir = Path(settings.database_dir)
    
    if not old_name.endswith('.db'):
        old_name += '.db'
    if not new_name.endswith('.db'):
        new_name += '.db'
    
    old_path = database_dir / old_name
    new_path = database_dir / new_name
    
    if old_path == new_path:
        return JSONResponse({"message": "Database name unchanged"})
    
    if not old_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")
    
    if new_path.exists():
        raise HTTPException(status_code=400, detail="Database with new name already exists")
    
    try:
        old_path.rename(new_path)
        return JSONResponse({"message": f"Database renamed from '{old_name}' to '{new_name}' successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename database: {str(e)}")


@router.get("/codebook")
async def get_codebook(codebook_id: str = Query(None)):
    codebooks_dir = Path(__file__).parent.parent.parent / "data" / "codebooks"
    if codebooks_dir.exists():
        if codebook_id:
            target_file = codebooks_dir / f"{codebook_id}.txt"
            if target_file.exists():
                with open(target_file, 'r') as f:
                    codebook_content = f.read()
                return JSONResponse({"codebook": codebook_content})
            else:
                return JSONResponse({"error": f"Codebook {codebook_id} not found"}, status_code=404)
        else:
            codebook_files = list(codebooks_dir.glob("*.txt"))
            if codebook_files:
                latest_codebook = sorted(codebook_files, key=lambda x: x.name)[0]
                with open(latest_codebook, 'r') as f:
                    codebook_content = f.read()
                return JSONResponse({"codebook": codebook_content})
    return JSONResponse({"status": "processing", "message": "No codebooks found."})


@router.get("/list-codebooks")
async def list_codebooks():
    codebooks_dir = Path(__file__).parent.parent.parent / "data" / "codebooks"
    if codebooks_dir.exists():
        codebook_files = list(codebooks_dir.glob("*.txt"))
        codebooks = []
        for cb in codebook_files:
            codebook_id = cb.stem  # filename without .txt
            # collect metadata: character count and modification time
            try:
                with open(cb, 'r') as f:
                    content = f.read()
                stat = cb.stat()
                metadata = {
                    "characters": len(content),
                    "date_created": int(stat.st_mtime)
                }
            except Exception:
                metadata = {}
            codebooks.append({"id": codebook_id, "name": codebook_id, "metadata": metadata})
        codebooks.sort(key=lambda x: x["id"])
        return JSONResponse({"codebooks": codebooks})
    return JSONResponse({"codebooks": []})


@router.post("/rename-codebook/")
async def rename_codebook(old_id: str = Form(...), new_id: str = Form(...)):
    codebooks_dir = Path(__file__).parent.parent.parent / "data" / "codebooks"
    if not codebooks_dir.exists():
        return JSONResponse({"error": "Codebooks directory not found"}, status_code=404)
    
    old_file = codebooks_dir / f"{old_id}.txt"
    new_file = codebooks_dir / f"{new_id}.txt"
    
    if not old_file.exists():
        return JSONResponse({"error": f"Codebook {old_id} not found"}, status_code=404)
    
    if new_file.exists():
        return JSONResponse({"error": f"Codebook {new_id} already exists"}, status_code=400)
    
    try:
        old_file.rename(new_file)
        return JSONResponse({"message": f"Codebook {old_id} renamed to {new_id}"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/save-codebook/")
async def save_codebook(codebook_id: str = Form(...), content: str = Form(...)):
    codebooks_dir = Path(__file__).parent.parent.parent / "data" / "codebooks"
    codebooks_dir.mkdir(parents=True, exist_ok=True)
    
    codebook_file = codebooks_dir / f"{codebook_id}.txt"
    
    try:
        with open(codebook_file, 'w') as f:
            f.write(content)
        return JSONResponse({"message": f"Codebook {codebook_id} saved successfully"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/list-coded-data")
async def list_coded_data():
    coded_data_dir = Path(__file__).parent.parent.parent / "data" / "coded_data"
    if coded_data_dir.exists():
        coded_files = list(coded_data_dir.glob("*.txt"))
        coded_data = []
        for cf in coded_files:
            coded_id = cf.stem  # filename without .txt
            coded_data.append({"id": coded_id, "name": coded_id})
        coded_data.sort(key=lambda x: x["id"], reverse=True)  # Most recent first
        return JSONResponse({"coded_data": coded_data})
    return JSONResponse({"coded_data": []})


@router.get("/coded-data/{coded_id}")
async def get_coded_data(coded_id: str):
    coded_data_dir = Path(__file__).parent.parent.parent / "data" / "coded_data"
    coded_file = coded_data_dir / f"{coded_id}.txt"
    if coded_file.exists():
        with open(coded_file, 'r') as f:
            coded_content = f.read()
        return JSONResponse({"coded_data": coded_content})
    else:
        return JSONResponse({"error": f"Coded data {coded_id} not found"}, status_code=404)


@router.post("/save-coded-data/")
async def save_coded_data(coded_id: str = Form(...), content: str = Form(...)):
    coded_data_dir = Path(__file__).parent.parent.parent / "data" / "coded_data"
    coded_data_dir.mkdir(parents=True, exist_ok=True)

    coded_file = coded_data_dir / f"{coded_id}.txt"
    try:
        with open(coded_file, 'w') as f:
            f.write(content)
        return JSONResponse({"message": f"Coded data {coded_id} saved successfully"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/classification-report")
async def get_classification_report():
    report_path = Path(__file__).parent.parent.parent / "data" / "classification_report.txt"
    if report_path.exists():
        with open(report_path, 'r') as f:
            report_content = f.read()
        return JSONResponse({"classification_report": report_content})
    else:
        return JSONResponse({"error": "Classification report not found. Please apply a codebook first."}, status_code=404)


@router.get("/database-entries/")
async def get_database_entries(limit: int = 10, database: str = Query(..., description="Database name")):
    if not database:
        raise HTTPException(status_code=400, detail="Database name is required")
        
    if database.endswith('.db'):
        # Check if it's in the filtered directory first
        filtered_db_path = Path(settings.filtered_database_dir) / database
        if filtered_db_path.exists():
            db_path = filtered_db_path
        else:
            db_path = Path(settings.database_dir) / database
    elif database == "filtered_data":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "filtered":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "codebook":
        db_path = DB_PATH.parent / "codebook.db"
    elif database == "coding":
        db_path = DB_PATH.parent / "codeddata.db"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown database type: {database}")

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
            cursor.execute('SELECT COUNT(*) as count FROM codebooks')
            sub_count = cursor.fetchone()['count']
            cursor.execute('SELECT * FROM codebooks LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            comments = []
            com_count = 0
        elif database == "coding":
            cursor.execute('SELECT COUNT(*) as count FROM codings')
            sub_count = cursor.fetchone()['count']
            cursor.execute('SELECT * FROM codings LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            comments = []
            com_count = 0
        elif database == "filtered" or (database.endswith('.db') and str(db_path).startswith(str(settings.filtered_database_dir))):
            # Filtered databases only have submissions table
            cursor.execute('SELECT COUNT(*) as count FROM submissions')
            sub_count = cursor.fetchone()['count']
            com_count = 0
            cursor.execute('SELECT * FROM submissions LIMIT ?', (limit,))
            submissions = [dict(row) for row in cursor.fetchall()]
            comments = []
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
        "database": database,
        "date_created": os.path.getctime(str(db_path)) if db_path.exists() and os.path.getctime(str(db_path)) > 0 else None
    })


@router.post("/filter-data/")
async def filter_data(api_key: str = Form(...), prompt: str = Form(...), database: str = Form(None), name: str = Form(...)):
    # Resolve database path similar to other endpoints; if not provided, use settings.reddit_db_path
    if database and database.endswith('.db'):
        filtered_db_path = Path(settings.filtered_database_dir) / database
        if filtered_db_path.exists():
            db_path = filtered_db_path
        else:
            db_path = Path(settings.database_dir) / database
    elif database in ("filtered_data", "filtered"):
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    else:
        db_path = Path(settings.reddit_db_path)

    if not db_path.exists():
        return JSONResponse({"error": f"Database not found: {db_path}. Please upload data first."}, status_code=404)

    # Validate output name for filtered DB (required)
    filtered_dir = Path(settings.filtered_database_dir)
    filtered_dir.mkdir(parents=True, exist_ok=True)

    if not name or not name.strip():
        return JSONResponse({"error": "A name for the filtered database is required"}, status_code=400)

    # Basic sanitization: no path separators, no parent traversal
    if any(sep in name for sep in ("/", "\\")) or ".." in name:
        return JSONResponse({"error": "Invalid name provided"}, status_code=400)
    if not name.endswith('.db'):
        name = f"{name}.db"
    candidate = filtered_dir / name
    if candidate.exists():
        return JSONResponse({"error": f"Filtered database '{name}' already exists"}, status_code=400)

    output_db_path = str(candidate)

    try:
        # Pass the resolved db path and the desired output path to the filter script
        filter_database_with_ai(api_key, prompt, str(db_path), output_db_path)
        return JSONResponse({"message": "Data filtered successfully", "output": Path(output_db_path).name})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/generate-codebook/")
async def generate_codebook(database: str = Form("original"), api_key: str = Form(...), prompt: str = Form(""), name: str = Form(...)):
    # Resolve database path using same logic as database-entries endpoint
    if database.endswith('.db'):
        # Check if it's in the filtered directory first
        filtered_db_path = Path(settings.filtered_database_dir) / database
        if filtered_db_path.exists():
            db_path = filtered_db_path
        else:
            db_path = Path(settings.database_dir) / database
    elif database == "filtered_data":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "filtered":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "codebook":
        db_path = DB_PATH.parent / "codebook.db"
    elif database == "coding":
        db_path = DB_PATH.parent / "codeddata.db"
    else:  # "original"
        db_path = DB_PATH
    
    if not db_path.exists():
        return JSONResponse({"error": f"Database not found. Please import data first."}, status_code=404)
    
    # Validate name
    codebooks_dir = Path(__file__).parent.parent.parent / "data" / "codebooks"
    codebooks_dir.mkdir(parents=True, exist_ok=True)

    if not name or not name.strip():
        return JSONResponse({"error": "A name for the codebook is required"}, status_code=400)
    # Basic sanitization
    if any(sep in name for sep in ("/", "\\")) or ".." in name:
        return JSONResponse({"error": "Invalid name provided"}, status_code=400)
    if not name.endswith('.txt'):
        name = f"{name}.txt"
    candidate = codebooks_dir / name
    if candidate.exists():
        return JSONResponse({"error": f"Codebook '{name}' already exists"}, status_code=400)

    try:
        # Pass desired output name to generator
        generate_codebook_main(str(db_path), api_key, prompt, output_name=name)
        if candidate.exists():
            with open(candidate, 'r') as f:
                codebook_content = f.read()
            return JSONResponse({"codebook": codebook_content})
        return JSONResponse({"error": "Codebook file not found after generation"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/apply-codebook/")
async def apply_codebook(
    database: str = Form("original"), 
    api_key: str = Form(...), 
    methodology: str = Form(""),
    codebook: str = Form(...)
):
    # Resolve database path using same logic as database-entries endpoint
    if database.endswith('.db'):
        # Check if it's in the filtered directory first
        filtered_db_path = Path(settings.filtered_database_dir) / database
        if filtered_db_path.exists():
            db_path = filtered_db_path
        else:
            db_path = Path(settings.database_dir) / database
    elif database == "filtered_data":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "filtered":
        db_path = Path(settings.filtered_database_dir) / "filtered_data.db"
    elif database == "codebook":
        db_path = DB_PATH.parent / "codebook.db"
    elif database == "coding":
        db_path = DB_PATH.parent / "codeddata.db"
    else:  # "original"
        db_path = DB_PATH
    
    if not db_path.exists():
        db_name = "Database"
        return JSONResponse({"error": f"{db_name} not found. Please import data first."}, status_code=404)
    
    try:
        report_path = apply_codebook_main(str(db_path), api_key, methodology, codebook)
        if report_path and Path(report_path).exists():
            with open(report_path, 'r') as f:
                report_content = f.read()
            return JSONResponse({"classification_report": report_content})
        else:
            return JSONResponse({"error": "Classification report not found"})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/comments/{submission_id}")
async def get_comments_for_submission(submission_id: str, database: str = Query("original")):
    """Fetch all comments for a specific submission"""
    if database.endswith('.db'):
        db_path = Path(settings.database_dir) / database
    elif database == "filtered":
        db_path = DB_PATH.parent / "filtered_data.db"
    elif database == "codebook":
        db_path = DB_PATH.parent / "codebook.db"
    elif database == "coding":
        db_path = DB_PATH.parent / "codeddata.db"
    else:  # "original"
        db_path = DB_PATH

    if not db_path.exists():
        return JSONResponse({"error": f"Database not found: {database}"}, status_code=404)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch comments where link_id matches the submission_id
        cursor.execute('SELECT * FROM comments WHERE link_id = ? ORDER BY created_utc ASC', (submission_id,))
        comments = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return JSONResponse({"comments": comments})

    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
