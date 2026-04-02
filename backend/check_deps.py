from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Get dependencies for file 47
    result = conn.execute(text('SELECT parent_file_id FROM file_dependencies WHERE child_file_id = 47'))
    parents = [row[0] for row in result]
    print('Parent IDs for file 47:', parents)
    
    for pid in parents:
        result2 = conn.execute(text('SELECT id, filename, file_type, schemaname FROM files WHERE id = :pid'), {'pid': pid})
        parent = result2.fetchone()
        print(f'Parent {pid}: {parent}')