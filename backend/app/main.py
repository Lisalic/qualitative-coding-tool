from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import routes
from backend.app.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Qualitative Coding API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://qualitative-coding-tool-lisalics-projects.vercel.app",
        "https://qualitative-coding-tool.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Qualitative Coding API"}
