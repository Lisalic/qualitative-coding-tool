import json
import zstandard as zstd
import io
from sqlalchemy import text
try:
    from app.database import engine
except Exception as exc:
    try:
        from backend.app.database import engine
    except Exception:
        print("Failed", exc)
        raise exc

def decompress_zst_file(file_path, chunk_size=16384):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line
        return
    except UnicodeDecodeError:
        try:
            dctx = zstd.ZstdDecompressor(max_window_size=2**31)
            with open(file_path, "rb") as ifh:
                reader = dctx.stream_reader(ifh, read_size=chunk_size)
                text_buffer = io.TextIOWrapper(
                    reader, encoding="utf-8", errors="ignore"
                )
                for line in text_buffer:
                    line = line.strip()
                    if line:
                        yield line
        except Exception as e:
            print(f"Error decompressing {file_path}: {e}")
            return

def stream_zst_to_postgres(file_path: str, schema_name: str, data_type: str, subreddit_filter=None, batch_size: int = 1000) -> dict:
    """Stream a .zst file into a Postgres schema's submissions/comments tables.

    Args:
        file_path: path to the uploaded .zst file
        schema_name: target Postgres schema (e.g., 'proj_abcd')
        data_type: 'submissions' or 'comments'
        subreddit_filter: optional list of subreddit names (lowercase) to keep
        batch_size: number of rows per insert batch

    Returns:
        dict with counts: {'submissions': int, 'comments': int}
    """
    inserted_counts = {"submissions": 0, "comments": 0}

    # Ensure filter list is normalized
    filter_list = None
    if subreddit_filter:
        filter_list = [s.lower() for s in subreddit_filter]

    # Create schema and tables if they don't exist
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        conn.execute(text(f'''
        CREATE TABLE IF NOT EXISTS "{schema_name}"."submissions" (
            id TEXT PRIMARY KEY,
            subreddit TEXT,
            title TEXT,
            selftext TEXT,
            author TEXT,
            created_utc BIGINT,
            score INTEGER,
            num_comments INTEGER,
            word_count INTEGER GENERATED ALWAYS AS (
                CASE WHEN COALESCE(TRIM(title || ' ' || selftext), '') = '' THEN 0
                ELSE array_length(string_to_array(regexp_replace(TRIM(title || ' ' || selftext), '\\s+', ' ', 'g'), ' '), 1)
                END
            ) STORED
        )
        '''))
        conn.execute(text(f'''
        CREATE TABLE IF NOT EXISTS "{schema_name}"."comments" (
            id TEXT PRIMARY KEY,
            subreddit TEXT,
            body TEXT,
            author TEXT,
            created_utc BIGINT,
            score INTEGER,
            link_id TEXT,
            parent_id TEXT,
            word_count INTEGER GENERATED ALWAYS AS (
                CASE WHEN COALESCE(TRIM(body), '') = '' THEN 0
                ELSE array_length(string_to_array(regexp_replace(TRIM(body), '\\s+', ' ', 'g'), ' '), 1)
                END
            ) STORED
        )
        '''))
        # Add indexes on word_count
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_{schema_name}_submissions_word_count ON "{schema_name}"."submissions" (word_count)'))
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_{schema_name}_comments_word_count ON "{schema_name}"."comments" (word_count)'))

    subs_batch = []
    comm_batch = []

    for line in decompress_zst_file(file_path):
        try:
            data = json.loads(line)
        except Exception:
            continue

        if data_type == 'submissions':
            subreddit = data.get('subreddit')
            if filter_list and subreddit and subreddit.lower() not in filter_list:
                continue

            submission_id = data.get('id')
            selftext = data.get('selftext')
        

            # Skip submissions with empty or deleted selftext
            if not selftext or selftext == '[deleted]':
                continue

            subs_batch.append({
                'id': submission_id,
                'subreddit': subreddit,
                'title': data.get('title'),
                'selftext': selftext,
                'author': data.get('author'),
                'created_utc': data.get('created_utc'),
                'score': data.get('score'),
                'num_comments': data.get('num_comments'),
            })

            if len(subs_batch) >= batch_size:
                insert_sql = text(f'''
                    INSERT INTO "{schema_name}"."submissions"
                    (id, subreddit, title, selftext, author, created_utc, score, num_comments)
                    VALUES (:id, :subreddit, :title, :selftext, :author, :created_utc, :score, :num_comments)
                    ON CONFLICT (id) DO UPDATE SET
                        subreddit = EXCLUDED.subreddit,
                        title = EXCLUDED.title,
                        selftext = EXCLUDED.selftext,
                        author = EXCLUDED.author,
                        created_utc = EXCLUDED.created_utc,
                        score = EXCLUDED.score,
                        num_comments = EXCLUDED.num_comments
                ''')
                with engine.begin() as conn:
                    conn.execute(insert_sql, subs_batch)
                inserted_counts['submissions'] += len(subs_batch)
                subs_batch = []

        else:
            subreddit = data.get('subreddit')
            if filter_list and subreddit and subreddit.lower() not in filter_list:
                continue

            link_id = data.get('link_id', '').replace('t3_', '')
            parent_id = data.get('parent_id', '')

            body = data.get('body')
            if not body or body == '[deleted]':
                continue

            comm_batch.append({
                'id': data.get('id'),
                'subreddit': subreddit,
                'body': body,
                'author': data.get('author'),
                'created_utc': data.get('created_utc'),
                'score': data.get('score'),
                'link_id': link_id,
                'parent_id': parent_id,
            })

            if len(comm_batch) >= batch_size:
                insert_sql = text(f'''
                    INSERT INTO "{schema_name}"."comments"
                    (id, subreddit, body, author, created_utc, score, link_id, parent_id)
                    VALUES (:id, :subreddit, :body, :author, :created_utc, :score, :link_id, :parent_id)
                    ON CONFLICT (id) DO UPDATE SET
                        subreddit = EXCLUDED.subreddit,
                        body = EXCLUDED.body,
                        author = EXCLUDED.author,
                        created_utc = EXCLUDED.created_utc,
                        score = EXCLUDED.score,
                        link_id = EXCLUDED.link_id,
                        parent_id = EXCLUDED.parent_id
                ''')
                with engine.begin() as conn:
                    conn.execute(insert_sql, comm_batch)
                inserted_counts['comments'] += len(comm_batch)
                comm_batch = []

    # flush remaining
    if subs_batch:
        insert_sql = text(f'''
            INSERT INTO "{schema_name}"."submissions"
            (id, subreddit, title, selftext, author, created_utc, score, num_comments)
            VALUES (:id, :subreddit, :title, :selftext, :author, :created_utc, :score, :num_comments)
            ON CONFLICT (id) DO UPDATE SET
                subreddit = EXCLUDED.subreddit,
                title = EXCLUDED.title,
                selftext = EXCLUDED.selftext,
                author = EXCLUDED.author,
                created_utc = EXCLUDED.created_utc,
                score = EXCLUDED.score,
                num_comments = EXCLUDED.num_comments
        ''')
        with engine.begin() as conn:
            conn.execute(insert_sql, subs_batch)
        inserted_counts['submissions'] += len(subs_batch)

    if comm_batch:
        insert_sql = text(f'''
            INSERT INTO "{schema_name}"."comments"
            (id, subreddit, body, author, created_utc, score, link_id, parent_id)
            VALUES (:id, :subreddit, :body, :author, :created_utc, :score, :link_id, :parent_id)
            ON CONFLICT (id) DO UPDATE SET
                subreddit = EXCLUDED.subreddit,
                body = EXCLUDED.body,
                author = EXCLUDED.author,
                created_utc = EXCLUDED.created_utc,
                score = EXCLUDED.score,
                link_id = EXCLUDED.link_id,
                parent_id = EXCLUDED.parent_id
        ''')
        with engine.begin() as conn:
            conn.execute(insert_sql, comm_batch)
        inserted_counts['comments'] += len(comm_batch)

    return inserted_counts
