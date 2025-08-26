import json
import os
from typing import List

from sqlalchemy.orm import Session

from app.models.models import Document, DocumentStatus, Chunk, Modality
from app.services.embedding_service import get_embeddings
from app.services.vector_store import add_embeddings


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        if end == length:
            break
        start = max(0, end - overlap)
    return chunks


def _extract_text_from_pdf(file_path: str) -> str:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        pages_text = []
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
        return "\n".join(pages_text)
    except Exception as e:
        return f"[PDF text extraction failed: {e}]"


def _extract_text_generic(file_path: str) -> str:
    try:
        # For txt/markdown simple read
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def ingest_document(document: Document, db: Session) -> None:
    """Synchronously ingest a document from local file into chunks with embeddings."""
    file_path = document.s3_key  # For direct uploads we stored local path here
    if not file_path or not os.path.exists(file_path):
        document.status = DocumentStatus.FAILED
        db.commit()
        return

    # Very simple modality detection
    mime = (document.mime_type or "").lower()
    text: str = ""
    modality = Modality.TEXT

    if "/pdf" in mime or file_path.lower().endswith(".pdf"):
        text = _extract_text_from_pdf(file_path)
    elif mime.startswith("text/") or file_path.lower().endswith((".txt", ".md")):
        text = _extract_text_generic(file_path)
    else:
        # For images/audio/video, skip heavy OCR/ASR in local mode
        text = f"Uploaded file '{document.name}' (type {document.mime_type})"

    # Create chunks
    chunks_text = _chunk_text(text)
    if not chunks_text:
        chunks_text = [text or f"No extractable text for {document.name}"]

    # Embeddings
    embeddings = get_embeddings(chunks_text)

    # Persist chunks
    chunk_ids = []
    to_add = []
    for idx, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings)):
        chunk = Chunk(
            document_id=document.id,
            content=chunk_text,
            modality=modality,
            citation_locator=None,
            embedding=json.dumps(embedding),
            chunk_index=idx,
        )
        db.add(chunk)
        db.flush()  # assign id
        chunk_ids.append(chunk.id)
        to_add.append((chunk.id, embedding))

    # Update status
    document.status = DocumentStatus.READY
    db.commit()
    try:
        add_embeddings(to_add, db)
    except Exception:
        pass


