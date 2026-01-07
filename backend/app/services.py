import uuid
import sqlite3
import pandas as pd
from sqlalchemy import text
try:
    from app.database import engine
    from app.databasemanager import DatabaseManager
except Exception as exc:
    try:
        from backend.app.database import engine
        from backend.app.databasemanager import DatabaseManager
    except Exception:
        print("Failed", exc)
        raise exc


def migrate_sqlite_file(user_id: uuid.UUID, file_path: str, display_name: str, project_type: str = "raw_data"):
    unique_id = str(uuid.uuid4()).replace("-", "")[:12]
    schema_name = f"proj_{unique_id}"

    print(f"--> Starting migration for '{display_name}' into schema '{schema_name}'...")

    with DatabaseManager() as db:
        project = db.projects.create(
            user_id=user_id,
            display_name=display_name,
            schema_name=schema_name,
            project_type=project_type,
        )

        with engine.begin() as conn:
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
                print(f"      Error writing table {table_name} to Postgres schema {schema_name}: {e}")

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

def migrate_text_file(user_id: uuid.UUID, file_path: str, display_name: str, project_type: str):
    """
    Migrates a .txt file into a Postgres Schema.
    Structure: 1 Schema -> 1 Table ('content_store') -> 1 Column ('file_text')
    """
    
    valid_types = ['codebook', 'coding', 'raw_data','filtered_data'] 
    if project_type not in valid_types:
        raise ValueError(f"Invalid Type. Must be one of: {valid_types}")

    unique_id = str(uuid.uuid4()).replace("-", "")[:12]
    schema_name = f"proj_{unique_id}"
    
    print(f"--> Importing text '{display_name}' as type '{project_type}'...")

    with DatabaseManager() as db:
        project = db.projects.create(
            user_id=user_id,
            display_name=display_name,
            schema_name=schema_name,
            project_type=project_type # 'codebook' or 'coding'
        )
        
        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema_name}"))
            conn.commit()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                raw_text = f.read()

        df = pd.DataFrame([{"file_text": raw_text}])

        df.to_sql(
            name="content_store", 
            con=engine,
            schema=schema_name,
            if_exists='replace',
            index=False          
        )

        db.project_tables.add_table_metadata(
            project_id=project.id,
            table_name="content_store",
            row_count=1
        )
        
        print(f"--> Success! Text saved to {schema_name}.content_store")