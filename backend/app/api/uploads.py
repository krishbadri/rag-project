from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
import boto3
import uuid
import os
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models.models import Document, DocumentStatus
from app.services.s3_service import get_s3_client
from app.services.ingest_service import ingest_document

router = APIRouter()


class UploadInitRequest(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int


class UploadInitResponse(BaseModel):
    document_id: str
    upload_url: str
    fields: dict


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    request: UploadInitRequest,
    db: Session = Depends(get_db)
):
    """Initialize file upload with presigned URL"""
    
    # Generate unique document ID
    document_id = str(uuid.uuid4())
    
    # Create S3 key
    s3_key = f"uploads/{document_id}/{request.filename}"
    
    # Create document record
    document = Document(
        id=document_id,
        name=request.filename,
        mime_type=request.mime_type,
        size_bytes=request.size_bytes,
        status=DocumentStatus.UPLOADING,
        s3_key=s3_key
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # For local dev without S3/MinIO, support direct upload via backend
    return UploadInitResponse(
        document_id=document_id,
        upload_url="/api/uploads/direct",
        fields={
            "document_id": document_id,
            "filename": request.filename,
            "direct": "true",
        }
    )


@router.post("/mock-upload")
async def mock_upload():
    """Mock upload endpoint for testing"""
    return {"message": "File uploaded successfully (mock)"}


@router.post("/direct")
async def direct_upload(
    document_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Accept file upload directly to the backend for local development."""
    # Ensure document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Save to local disk
    import pathlib
    import shutil

    uploads_root = pathlib.Path("uploaded_files")
    target_dir = uploads_root / document_id
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / file.filename
    with target_path.open("wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    # Update document record with local path
    document.s3_key = str(target_path)
    db.commit()

    return {"message": "File uploaded successfully (direct)", "path": str(target_path)}


@router.post("/{document_id}/complete")
async def complete_upload(
    document_id: str,
    db: Session = Depends(get_db)
):
    """Mark upload as complete and trigger ingestion"""
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != DocumentStatus.UPLOADING:
        raise HTTPException(status_code=400, detail="Document not in uploading state")
    
    # Update status to processing
    document.status = DocumentStatus.PROCESSING
    db.commit()

    # In local non-docker mode, ingest synchronously
    try:
        ingest_document(document, db)
    except Exception as e:
        document.status = DocumentStatus.FAILED
        db.commit()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return {"message": "Upload completed, document ready"}
