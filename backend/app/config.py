from pathlib import Path

from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    # backend/.env, not the cwd -- uvicorn runs from the repo root.
    model_config = {"extra": "allow", "env_file": Path(__file__).resolve().parents[1] / ".env"}
    database_url: str = ""
    secret_key: str = "your-secret-key-here"

    auth_database_url: str = ""  
    jwt_secret_key: str = ""    
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480
    jwt_refresh_token_expire_minutes: int = 10080

    # Password-reset email (Brevo transactional API). The reset link is built
    # from frontend_url, never from the request's Host/Origin, so a forged
    # header can't redirect a victim's token to an attacker's domain.
    brevo_api_key: str = ""
    brevo_sender_email: str = ""
    brevo_sender_name: str = "Qualitative Coding Tool"
    frontend_url: str = "http://localhost:5173"
    password_reset_token_expire_minutes: int = 30
    password_reset_cooldown_seconds: int = 60

settings = Settings()