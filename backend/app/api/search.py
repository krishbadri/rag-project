from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.models import Chunk, Document
from app.services.embedding_service import get_embedding

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class ChunkResponse(BaseModel):
    id: int
    content: str
    modality: str
    citation_locator: Optional[dict]
    chunk_index: int
    document: dict

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    chunks: List[ChunkResponse]
    query: str
    total_results: int


@router.post("/", response_model=SearchResponse)
async def search_chunks(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Search for relevant chunks using vector similarity"""
    
    # Get query embedding
    query_embedding = get_embedding(request.query)
    
    # Perform vector similarity search
    # Note: This is a simplified version. In production, you'd use pgvector's similarity functions
    chunks = db.query(Chunk).filter(
        Chunk.embedding.isnot(None)
    ).limit(request.top_k).all()
    
    # TODO: Implement proper vector similarity search with pgvector
    # For now, return all chunks with embeddings
    
    chunk_responses = []
    for chunk in chunks:
        document = db.query(Document).filter(Document.id == chunk.document_id).first()
        chunk_responses.append(ChunkResponse(
            id=chunk.id,
            content=chunk.content,
            modality=chunk.modality.value,
            citation_locator=chunk.citation_locator,
            chunk_index=chunk.chunk_index,
            document={
                "id": document.id,
                "name": document.name,
                "mime_type": document.mime_type
            }
        ))
    
    return SearchResponse(
        chunks=chunk_responses,
        query=request.query,
        total_results=len(chunk_responses)
    )
