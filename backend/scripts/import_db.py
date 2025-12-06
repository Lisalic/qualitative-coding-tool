import sqlite3
import json
import zstandard as zstd
import os
import io
from pathlib import Path

def create_database(db_path):
    db_path = Path(db_path)
    print(f"Ensuring reddit_data schema at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # TABLE submissions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    subreddit TEXT,
    title TEXT,
    selftext TEXT,
    author TEXT,
    created_utc INTEGER,
    score INTEGER,
    num_comments INTEGER,
    is_self BOOLEAN,
    retrieved_on INTEGER,
    stickied BOOLEAN,
    over_18 BOOLEAN,
    spoiler BOOLEAN,
    locked BOOLEAN,
    distinguished TEXT,
    permalink TEXT,
    has_image BOOLEAN,
    image_url TEXT
);
    ''')
#TABLE comments
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id TEXT PRIMARY KEY,
        subreddit TEXT,
        body TEXT,
        author TEXT,
        created_utc INTEGER,
        score INTEGER,
        link_id TEXT,
        parent_id TEXT,
        retrieved_on INTEGER,
        stickied BOOLEAN,
        distinguished TEXT,
        controversiality INTEGER,
        FOREIGN KEY (link_id) REFERENCES submissions(id)
    )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_subreddit ON submissions(subreddit)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_author ON submissions(author)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_created ON submissions(created_utc)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_link_id ON comments(link_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_subreddit ON comments(subreddit)')
    
    conn.commit()
    print(f"Database schema ready")
    return conn

def decompress_zst_file(file_path, chunk_size=16384): 
    dctx = zstd.ZstdDecompressor(max_window_size=2**31)
    
    with open(file_path, 'rb') as ifh:
        reader = dctx.stream_reader(ifh, read_size=chunk_size)
        text_buffer = io.TextIOWrapper(reader, encoding='utf-8', errors='ignore')
        
        for line in text_buffer:
            line = line.strip()
            if line:
                yield line

def import_submissions(conn, file_path, batch_size=100000):
    cursor = conn.cursor()
    submissions = []
    count = 0
    errors = 0

    print(f"Importing submissions from {file_path}...")

    try:
        for line in decompress_zst_file(file_path):
            try:
                data = json.loads(line)
                submission_id = data.get("id")

                post_hint = data.get("post_hint")
                domain = str(data.get("domain") or "")
                external_url = data.get("url")

                has_image = False
                image_url = None
                if post_hint == "image" or domain.startswith(("i.redd.it", "i.imgur.com")):
                    has_image = True
                    image_url = external_url or None

                selftext = data.get("selftext")
                if not selftext:
                    if not data.get("is_self") and external_url:
                        selftext = external_url
                    else:
                        selftext = None

                submissions.append((
                    submission_id,
                    data.get('subreddit'),
                    data.get('title'),
                    selftext,          
                    data.get('author'),
                    data.get('created_utc'),
                    data.get('score'),
                    data.get('num_comments'),
                    data.get('is_self'),
                    data.get('retrieved_on'),
                    data.get('stickied'),
                    data.get('over_18'),
                    data.get('spoiler'),
                    data.get('locked'),
                    data.get('distinguished'),
                    data.get('permalink'),
                    has_image,
                    image_url
                ))

                count += 1
                print(f"  Read submission record #{count}")

                if len(submissions) >= batch_size:
                    cursor.executemany('''
                    INSERT OR REPLACE INTO submissions 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', submissions)
                    conn.commit()
                    print(f"  Imported {count} submissions...")
                    submissions = []

            except json.JSONDecodeError as e:
                errors += 1
                if errors < 10:
                    print(f"  JSON error (line {count + errors}): {str(e)[:100]}")
                continue
            except Exception as e:
                errors += 1
                if errors < 10:
                    print(f"  Import error (line {count + errors}): {str(e)[:100]}")
                continue

        if submissions:
            cursor.executemany('''
            INSERT OR REPLACE INTO submissions 
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', submissions)
            conn.commit()

        print(f"Imported {count} submissions ({errors} errors)\n")

    except Exception as e:
        print(f"Fatal error reading file: {e}\n")

def import_comments(conn, file_path, batch_size=100000):
    cursor = conn.cursor()
    comments = []
    count = 0
    errors = 0
    
    print(f"Importing comments from {file_path}...")
    
    try:
        for line in decompress_zst_file(file_path):
            try:
                data = json.loads(line)
                
                link_id = data.get('link_id', '').replace('t3_', '')
                parent_id = data.get('parent_id', '')
                
                comments.append((
                    data['id'],
                    data.get('subreddit'),
                    data.get('body'),
                    data.get('author'),
                    data.get('created_utc'),
                    data.get('score'),
                    link_id,
                    parent_id,
                    data.get('retrieved_on'),
                    data.get('stickied'),
                    data.get('distinguished'),
                    data.get('controversiality')
                ))
                
                count += 1
                print(f"  Read comment record #{count}")
                
                if len(comments) >= batch_size:
                    cursor.executemany('''
                    INSERT OR REPLACE INTO comments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', comments)
                    conn.commit()
                    print(f"  Imported {count} comments...")
                    comments = []
                    
            except json.JSONDecodeError as e:
                errors += 1
                if errors < 10:
                    print(f"  JSON error (line {count + errors}): {str(e)[:100]}")
                continue
            except Exception as e:
                errors += 1
                if errors < 10:
                    print(f"  Import error (line {count + errors}): {str(e)[:100]}")
                continue
        
        if comments:
            cursor.executemany('''
            INSERT OR REPLACE INTO comments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ''', comments)
            conn.commit()
        
        print(f"Imported {count} comments ({errors} errors)\n")
        
    except Exception as e:
        print(f"Fatal error reading file: {e}\n")

def get_file_size_mb(file_path):
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)

def import_from_zst_file(file_path, db_path=None):
    """
    Import data from a single zst file and create/update database.
    Returns a dictionary with import statistics.
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
        'file_path': file_path
    }
    
    if '_submissions' in file_path or 'submission' in file_path.lower():
        import_submissions(conn, file_path)
    elif '_comments' in file_path or 'comment' in file_path.lower():
        import_comments(conn, file_path)
    else:
        print(f"File type unclear, attempting to import as submissions...")
        import_submissions(conn, file_path)
    
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM submissions')
    stats['submissions_imported'] = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM comments')
    stats['comments_imported'] = cursor.fetchone()[0]
    
    conn.close()
    return stats

def main():
    project_root = Path(__file__).resolve().parents[2]
    db_path = project_root / 'reddit_data.db'

    print(f"Opening reddit_data at: {db_path}")
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
    
    print(f"Found {len(submission_files)} submission file(s)")
    for file_path in submission_files:
        size_mb = get_file_size_mb(file_path)
        print(f"File size: {size_mb:.2f} MB")
        import_submissions(conn, file_path)
    
    print(f"Found {len(comment_files)} comment file(s)")
    for file_path in comment_files:
        size_mb = get_file_size_mb(file_path)
        print(f"File size: {size_mb:.2f} MB")
        import_comments(conn, file_path)
    
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM submissions')
    sub_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM comments')
    com_count = cursor.fetchone()[0]
    
    print("IMPORT COMPLETE!")
    print(f"Total submissions: {sub_count:,}")
    print(f"Total comments: {com_count:,}")
    print(f"Database saved to: {db_path}")
    
    conn.close()

if __name__ == '__main__':
    main()