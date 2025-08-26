from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from app.models.models import Chunk, Document
from app.services.embedding_service import get_embedding
from app.database import IS_POSTGRES
from app.services.vector_store import search as vs_search, load_or_build_index


def search_relevant_chunks(
    query: str, 
    top_k: int, 
    db: Session
) -> List[Chunk]:
    """Search for relevant chunks using vector similarity"""
    
    # Get query embedding
    query_embedding = get_embedding(query)

    try:
        load_or_build_index(db)
        ids = vs_search(query_embedding, top_k, db)
        if not ids:
            return _fallback_text_search(query, top_k, db)
        return db.query(Chunk).filter(Chunk.id.in_(ids)).all()
    except Exception:
        return _fallback_text_search(query, top_k, db)


def _fallback_text_search(query: str, top_k: int, db: Session) -> List[Chunk]:
    """Fallback text search when vector search is not available"""
    
    # Simple text search using ILIKE
    chunks = db.query(Chunk).join(Document).filter(
        Chunk.content.ilike(f"%{query}%")
    ).limit(top_k).all()
    
    return chunks
