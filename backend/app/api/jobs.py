from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models import Job, JobStatus, JobType

router = APIRouter()


class JobResponse(BaseModel):
    id: str
    document_id: str
    job_type: JobType
    status: JobStatus
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get job status by ID"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/document/{document_id}", response_model=list[JobResponse])
async def get_document_jobs(document_id: str, db: Session = Depends(get_db)):
    """Get all jobs for a document"""
    jobs = db.query(Job).filter(Job.document_id == document_id).order_by(Job.created_at.desc()).all()
    return jobs
