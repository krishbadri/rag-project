from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import Document, DocumentStatus
from app.services.s3_service import delete_file

router = APIRouter()


class DocumentResponse(BaseModel):
    id: str
    name: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(db: Session = Depends(get_db)):
    """List all documents"""
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    return documents


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get document by ID"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Delete document and all associated chunks"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete from S3/MinIO
    try:
        delete_file(document.s3_key)
    except Exception as e:
        # Log error but continue with database deletion
        print(f"Error deleting file from S3: {e}")
    
    # Delete from database (cascade will delete chunks)
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}


@router.post("/{document_id}/ingest")
async def trigger_ingestion(document_id: str, db: Session = Depends(get_db)):
    """Manually trigger ingestion for a document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status == DocumentStatus.READY:
        raise HTTPException(status_code=400, detail="Document already processed")
    
    # Update status to processing
    document.status = DocumentStatus.PROCESSING
    db.commit()
    
    # TODO: Enqueue ingestion job
    # This will be implemented when we add the job queue
    
    return {"message": "Ingestion job enqueued"}
