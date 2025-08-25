import os
from celery import Celery
from app.database import SessionLocal
from app.models import Document, DocumentStatus

# Initialize Celery
celery_app = Celery(
    "rag_worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379")
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


@celery_app.task
def process_document(document_id: str):
    """Process uploaded document - extract text, chunk, and generate embeddings"""
    try:
        db = SessionLocal()
        
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"status": "error", "message": "Document not found"}
        
        # Update status to processing
        document.status = DocumentStatus.PROCESSING
        db.commit()
        
        # TODO: Implement full ingestion pipeline
        # 1. Download file from S3/MinIO
        # 2. Extract text based on file type (PDF, OCR, ASR)
        # 3. Chunk content
        # 4. Generate embeddings
        # 5. Store in database
        
        # For now, just mark as ready
        document.status = DocumentStatus.READY
        db.commit()
        
        return {"status": "success", "message": "Document processed successfully"}
        
    except Exception as e:
        # Update status to failed
        try:
            document.status = DocumentStatus.FAILED
            db.commit()
        except:
            pass
        
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    celery_app.start()
