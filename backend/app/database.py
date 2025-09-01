from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./rag_app.db"  # Default to SQLite for development
)

IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        pool_pre_ping=True,
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database"""
    try:
        with engine.connect() as conn:
            if IS_POSTGRES:
                try:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                except Exception as e:
                    print(f"Warning: Could not ensure pgvector extension: {e}")
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
        print("This is normal if database is not available")


def create_tables():
    """Create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        # Ensure new columns added post-initialization exist (idempotent)
        try:
            with engine.connect() as conn:
                if DATABASE_URL.startswith("sqlite"):
                    # Check if batch_id exists on documents
                    res = conn.execute(text("PRAGMA table_info(documents)")).fetchall()
                    cols = {row[1] for row in res}  # name is 2nd column
                    if "batch_id" not in cols:
                        conn.execute(text("ALTER TABLE documents ADD COLUMN batch_id VARCHAR"))
                else:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS batch_id VARCHAR"))
        except Exception as e:
            print(f"Warning: Could not ensure batch_id column: {e}")
        if IS_POSTGRES:
            try:
                # Create IVFFlat index if possible (requires ANALYZE after data grows; safe to attempt)
                engine.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_l2_ops)"
                ))
            except Exception as e:
                print(f"Warning: Could not create vector index: {e}")
    except Exception as e:
        print(f"Warning: Could not create tables: {e}")
        print("This is normal if database is not available")
