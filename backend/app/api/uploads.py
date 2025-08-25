from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import boto3
import uuid
import os
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models import Document, DocumentStatus
from app.services.s3_service import get_s3_client

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
    
    # Generate presigned URL for upload
    s3_client = get_s3_client()
    
    # Create presigned POST URL (allows direct upload to S3/MinIO)
    presigned_post = s3_client.generate_presigned_post(
        Bucket=os.getenv("S3_BUCKET", "rag-bucket"),
        Key=s3_key,
        Fields={
            "Content-Type": request.mime_type,
        },
        Conditions=[
            {"Content-Type": request.mime_type},
            ["content-length-range", 1, request.size_bytes + 1000]  # Allow some buffer
        ],
        ExpiresIn=3600  # 1 hour
    )
    
    return UploadInitResponse(
        document_id=document_id,
        upload_url=presigned_post["url"],
        fields=presigned_post["fields"]
    )


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
    
    # TODO: Enqueue ingestion job
    # This will be implemented when we add the job queue
    
    return {"message": "Upload completed, processing started"}
