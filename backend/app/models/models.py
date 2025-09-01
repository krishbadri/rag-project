from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float, JSON
import os
from app.database import IS_POSTGRES
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, enum.Enum):
    INGEST = "ingest"
    DELETE = "delete"


class DocumentStatus(str, enum.Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Modality(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    batch_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADING)
    s3_key = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="document", cascade="all, delete-orphan")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    modality = Column(Enum(Modality), nullable=False)
    citation_locator = Column(JSON, nullable=True)  # page number, frame, timestamp, etc.
    # In SQLite dev mode, store as JSON string; in Postgres, expect pgvector installed and use TEXT as placeholder
    # Note: Proper pgvector type binding would be ideal; here we keep TEXT for compatibility, and let search handle pgvector path.
    embedding = Column(Text, nullable=True)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="chunks")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    job_type = Column(Enum(JobType), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    document = relationship("Document", back_populates="jobs")
