from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
try:
    from app.api import routes
except Exception:
    from backend.app.api import routes
from backend.app.database import engine
from backend.app.models import models
from backend.app.config import settings
import os

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Qualitative Coding API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Qualitative Coding API"}
