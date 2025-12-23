from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # Project root
REDDIT_DATABASE_PATH = PROJECT_ROOT / "data" / "reddit_data.db"
DATABASE_DIR = PROJECT_ROOT / "data" / "databases"
FILTERED_DATABASE_DIR = PROJECT_ROOT / "data" / "filtered_data"


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{REDDIT_DATABASE_PATH}"
    reddit_db_path: str = str(REDDIT_DATABASE_PATH)
    database_dir: str = str(DATABASE_DIR)
    filtered_database_dir: str = str(FILTERED_DATABASE_DIR)
    secret_key: str = "your-secret-key-here"

    class Config:
        env_file = ".env"


settings = Settings()
