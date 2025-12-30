import uuid
import sqlite3
import pandas as pd
from sqlalchemy import text
from backend.app.database import engine
from backend.app.databasemanager import DatabaseManager

def migrate_sqlite_file(user_id: uuid.UUID, file_path: str, display_name: str, project_type: str = "raw_data"):
    unique_id = str(uuid.uuid4()).replace("-", "")[:12]
    schema_name = f"proj_{unique_id}"

    print(f"--> Starting migration for '{display_name}' into schema '{schema_name}'...")

    with DatabaseManager() as db:
        # create project record first (project_type may be specified)
        project = db.projects.create(
            user_id=user_id,
            display_name=display_name,
            schema_name=schema_name,
            project_type=project_type,
        )

        # Use a transactional begin() to ensure CREATE SCHEMA is committed
        # and avoid calling commit() on a plain Connection.
        with engine.begin() as conn:
            # quote the identifier to be safe and use IF NOT EXISTS
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

        sqlite_conn = sqlite3.connect(file_path)
        cursor = sqlite_conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        for table_name in tables:
            print(f"    Moving table: {table_name}")
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", sqlite_conn)
            except Exception as e:
                print(f"      Failed to read table {table_name} from sqlite: {e}")
                df = pd.DataFrame()

            try:
                # Write to Postgres in the target schema
                df.to_sql(
                    name=table_name,
                    con=engine,
                    schema=schema_name,
                    if_exists="replace",
                    index=False,
                    method="multi",
                )
            except Exception as e:
                # Log error but continue with next table
                print(f"      Error writing table {table_name} to Postgres schema {schema_name}: {e}")

            # Verify inserted row count directly from Postgres and record metadata
            try:
                with engine.connect() as conn:
                    res = conn.execute(text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"'))
                    pg_count = int(res.scalar() or 0)
            except Exception as e:
                print(f"      Could not verify row count for {schema_name}.{table_name}: {e}")
                pg_count = len(df)

            db.project_tables.add_table_metadata(
                project_id=project.id, table_name=table_name, row_count=pg_count
            )

        sqlite_conn.close()
        print(f"--> Successfully migrated '{display_name}'!")