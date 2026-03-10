from pathlib import Path
from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    model_config = {"extra": "allow", "env_file": ".env"}
    database_url: str = ""
    secret_key: str = "your-secret-key-here"

    auth_database_url: str = ""  
    jwt_secret_key: str = ""    
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480
    jwt_refresh_token_expire_minutes: int = 10080

settings = Settings()