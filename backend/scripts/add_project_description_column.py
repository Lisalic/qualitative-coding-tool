from sqlalchemy import text

# Import the engine from the application's database module
try:
    from backend.app.database import engine
except Exception:
    from app.database import engine

SQL = """
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS description VARCHAR;
"""

if __name__ == '__main__':
    try:
        with engine.begin() as conn:
            conn.execute(text(SQL))
        print('Column "description" added (or already exists).')
    except Exception as e:
        print('Failed to add column:', e)
        raise
