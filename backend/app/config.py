from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REDDIT_DB_PATH = BASE_DIR / "reddit_data.db"


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{REDDIT_DB_PATH}"
    reddit_db_path: str = str(REDDIT_DB_PATH)
    secret_key: str = "your-secret-key-here"

    class Config:
        env_file = ".env"


settings = Settings()
