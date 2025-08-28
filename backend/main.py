from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
from dotenv import load_dotenv
from pathlib import Path

from app.database import engine, Base, init_db, create_tables
from app.api import uploads, documents, jobs, search, chat
from app.services.s3_service import create_bucket_if_not_exists
from app.database import get_db
from app.services.vector_store import rebuild_index


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: force-load root .env regardless of CWD
    try:
        ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=ROOT_ENV, override=False)
    except Exception:
        # Best-effort only
        pass
    
    # Initialize database with pgvector extension
    init_db()
    
    # Create all tables
    create_tables()
    
    # Create S3 bucket if it doesn't exist
    bucket_name = os.getenv("S3_BUCKET", "rag-bucket")
    create_bucket_if_not_exists(bucket_name)
    
    yield
    # Shutdown
    pass


app = FastAPI(
    title="RAG MVP API",
    description="A fast, minimal multimodal RAG MVP API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])


@app.get("/")
async def root():
    return {"message": "RAG MVP API is running!"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/test")
async def test_endpoint():
    return {"message": "Backend is working!"}


@app.get("/env-status")
async def env_status():
    import os
    key = os.getenv("OPENAI_API_KEY")
    return {
        "has_openai_key": bool(key),
        "openai_key_prefix": (key[:4] + "***") if key else None,
    }


@app.post("/admin/reindex")
async def admin_reindex(db = Depends(get_db)):
    rebuild_index(db)
    return {"message": "Reindex completed"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
