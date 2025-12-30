import uuid
import sqlite3
import pandas as pd
from sqlalchemy import text
from backend.app.database import engine
from backend.app.databasemanager import DatabaseManager

def migrate_sqlite_file(user_id: uuid.UUID, file_path: str, display_name: str):
    unique_id = str(uuid.uuid4()).replace("-", "")[:12]
    schema_name = f"proj_{unique_id}"

    print(f"--> Starting migration for '{display_name}' into schema '{schema_name}'...")

    with DatabaseManager() as db:
        project = db.projects.create(
            user_id=user_id,
            display_name=display_name,
            schema_name=schema_name,
        )

        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema_name}"))
            conn.commit()

        sqlite_conn = sqlite3.connect(file_path)
        cursor = sqlite_conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        for table_name in tables:
            print(f"    Moving table: {table_name}")
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", sqlite_conn)
            df.to_sql(
                name=table_name,
                con=engine,
                schema=schema_name,
                if_exists="replace",
                index=False,
            )
            db.project_tables.add_table_metadata(
                project_id=project.id, table_name=table_name, row_count=len(df)
            )

        sqlite_conn.close()
        print(f"--> Successfully migrated '{display_name}'!")