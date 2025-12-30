from pathlib import Path
from pydantic_settings import BaseSettings

BACKEND_ROOT = Path(__file__).resolve().parent.parent  # backend folder
DATABASE_DIR = BACKEND_ROOT / "data" / "databases"
FILTERED_DATABASE_DIR = BACKEND_ROOT / "data" / "filtered_databases"


class Settings(BaseSettings):
    model_config = {"extra": "allow", "env_file": ".env"}
    database_url: str = ""
    database_dir: str = str(DATABASE_DIR)
    filtered_database_dir: str = str(FILTERED_DATABASE_DIR)
    secret_key: str = "your-secret-key-here"

    auth_database_url: str = ""  
    jwt_secret_key: str = ""    
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

settings = Settings()