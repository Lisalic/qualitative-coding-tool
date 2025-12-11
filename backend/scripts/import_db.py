import sqlite3
import json
import zstandard as zstd
import os
import io
from pathlib import Path

def create_database(db_path):
    db_path = Path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS submissions (
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
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comments (
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
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_subreddit ON submissions(subreddit)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_author ON submissions(author)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_created ON submissions(created_utc)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_link_id ON comments(link_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_subreddit ON comments(subreddit)')
    
    conn.commit()
    return conn

def decompress_zst_file(file_path, chunk_size=16384): 
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line
        return
    except UnicodeDecodeError:
        pass  
    
    try:
        dctx = zstd.ZstdDecompressor(max_window_size=2**31)
        
        with open(file_path, 'rb') as ifh:
            reader = dctx.stream_reader(ifh, read_size=chunk_size)
            text_buffer = io.TextIOWrapper(reader, encoding='utf-8', errors='ignore')
            
            for line in text_buffer:
                line = line.strip()
                if line:
                    yield line
    except Exception as e:
        print(f"Error decompressing {file_path}: {e}")
        return

def import_submissions(conn, file_path, batch_size=100000, subreddit_filter=None):
    cursor = conn.cursor()
    submissions = []
    count = 0
    errors = 0
    processed_lines = 0

    print(f"Starting submission import from {file_path}")
    
    try:
        for line in decompress_zst_file(file_path):
            processed_lines += 1
            
            if processed_lines % 10000 == 0:
                print(f"Processed {processed_lines} lines, imported {count} submissions")
                
            try:
                data = json.loads(line)
                subreddit = data.get('subreddit')
                
                if subreddit_filter and subreddit and subreddit.lower() not in subreddit_filter:
                    continue
                
                submission_id = data.get("id")
                external_url = data.get("url")


                selftext = data.get("selftext")
                if not selftext:
                    if not data.get("is_self") and external_url:
                        selftext = external_url
                    else:
                        selftext = None

                submissions.append((
                    submission_id,
                    subreddit,
                    data.get('title'),
                    selftext,          
                    data.get('author'),
                    data.get('created_utc'),
                    data.get('score'),
                    data.get('num_comments'),
                ))

                count += 1

                if len(submissions) >= batch_size:
                    cursor.executemany('''
                    INSERT OR REPLACE INTO submissions 
                    VALUES (?,?,?,?,?,?,?,?)
                    ''', submissions)
                    conn.commit()
                    print(f"Committed batch of {len(submissions)} submissions")
                    submissions = []

            except json.JSONDecodeError as e:
                errors += 1
                continue
            except Exception as e:
                errors += 1
                continue

        if submissions:
            cursor.executemany('''
            INSERT OR REPLACE INTO submissions 
            VALUES (?,?,?,?,?,?,?,?)
            ''', submissions)
            conn.commit()
            print(f"Committed final batch of {len(submissions)} submissions")

        print(f"Submission import complete: {count} imported, {errors} errors, {processed_lines} lines processed")

    except Exception as e:
        print(f"Error in import_submissions: {e}")

def import_comments(conn, file_path, batch_size=100000, subreddit_filter=None):
    cursor = conn.cursor()
    comments = []
    count = 0
    errors = 0
    
    try:
        for line in decompress_zst_file(file_path):
            try:
                data = json.loads(line)
                subreddit = data.get('subreddit')
                
                if subreddit_filter and subreddit and subreddit.lower() not in subreddit_filter:
                    continue
                
                link_id = data.get('link_id', '').replace('t3_', '')
                parent_id = data.get('parent_id', '')
                
                comments.append((
                    data['id'],
                    subreddit,
                    data.get('body'),
                    data.get('author'),
                    data.get('created_utc'),
                    data.get('score'),
                    link_id,
                    parent_id,
                ))
                
                count += 1
                
                if len(comments) >= batch_size:
                    cursor.executemany('''
                    INSERT OR REPLACE INTO comments VALUES (?,?,?,?,?,?,?,?)
                    ''', comments)
                    conn.commit()
                    comments = []
                    
            except json.JSONDecodeError as e:
                errors += 1
                continue
            except Exception as e:
                errors += 1
                continue
        
        if comments:
            cursor.executemany('''
            INSERT OR REPLACE INTO comments VALUES (?,?,?,?,?,?,?,?)
            ''', comments)
            conn.commit()
        
    except Exception as e:
        print(f"Error in import_comments: {e}")

def get_file_size_mb(file_path):
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)

def import_from_zst_file(file_path, db_path=None, subreddit_filter=None):
    """
    Import data from a single zst file and create/update database.
    Returns a dictionary with import statistics.
    
    Args:
        file_path: Path to the .zst file
        db_path: Path to the database (optional)
        subreddit_filter: List of subreddit names to import (optional, None imports all)
    """
    file_path = str(file_path)

    if db_path is None:
        project_root = Path(__file__).resolve().parents[2]
        db_path = project_root / 'reddit_data.db'

    db_path = Path(db_path)
    conn = create_database(db_path)
    
    stats = {
        'submissions_imported': 0,
        'comments_imported': 0,
        'errors': 0,
        'db_path': str(db_path),
        'file_path': file_path,
        'subreddit_filter': subreddit_filter
    }
    
    filter_list = None
    if subreddit_filter:
        filter_list = [s.lower() for s in subreddit_filter]
    
    try:
        if '_submissions' in file_path or 'submission' in file_path.lower():
            import_submissions(conn, file_path, subreddit_filter=filter_list)
        elif '_comments' in file_path or 'comment' in file_path.lower():
            import_comments(conn, file_path, subreddit_filter=filter_list)
        else:
            import_submissions(conn, file_path, subreddit_filter=filter_list)
    except Exception as e:
        print(f"Error importing {file_path}: {e}")
        stats['errors'] += 1
    
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM submissions')
    stats['submissions_imported'] = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM comments')
    stats['comments_imported'] = cursor.fetchone()[0]
    
    print(f"Final stats: {stats}")
    conn.close()
    return stats

def main():
    project_root = Path(__file__).resolve().parents[2]
    db_path = project_root / 'data' / 'reddit_data.db'

    conn = create_database(db_path)
    
    submission_files = []
    comment_files = []
    
    for root, dirs, files in os.walk('zst_files'):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith('_submissions.zst'):
                submission_files.append(file_path)
            elif file.endswith('_comments.zst'):
                comment_files.append(file_path)
    
    for file_path in submission_files:
        import_submissions(conn, file_path)
    
    for file_path in comment_files:
        import_comments(conn, file_path)
    
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM submissions')
    cursor.execute('SELECT COUNT(*) FROM comments')
    
    conn.close()

if __name__ == '__main__':
    main()