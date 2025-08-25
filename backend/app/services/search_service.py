from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from app.models import Chunk, Document
from app.services.embedding_service import get_embedding


async def search_relevant_chunks(
    query: str, 
    top_k: int, 
    db: Session
) -> List[Chunk]:
    """Search for relevant chunks using vector similarity"""
    
    # Get query embedding
    query_embedding = get_embedding(query)
    
    # Perform vector similarity search using pgvector
    # This uses cosine similarity to find the most relevant chunks
    sql = text("""
        SELECT c.*, d.name as document_name, d.mime_type as document_mime_type
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
        ORDER BY c.embedding <=> :query_embedding
        LIMIT :top_k
    """)
    
    try:
        result = db.execute(sql, {
            "query_embedding": query_embedding,
            "top_k": top_k
        })
        
        chunks = []
        for row in result:
            # Create Chunk object with document relationship
            chunk = Chunk(
                id=row.id,
                document_id=row.document_id,
                content=row.content,
                modality=row.modality,
                citation_locator=row.citation_locator,
                chunk_index=row.chunk_index
            )
            
            # Create Document object for the relationship
            document = Document(
                id=row.document_id,
                name=row.document_name,
                mime_type=row.document_mime_type
            )
            chunk.document = document
            
            chunks.append(chunk)
        
        return chunks
        
    except Exception as e:
        # Fallback to simple text search if vector search fails
        print(f"Vector search failed: {e}, falling back to text search")
        return _fallback_text_search(query, top_k, db)


def _fallback_text_search(query: str, top_k: int, db: Session) -> List[Chunk]:
    """Fallback text search when vector search is not available"""
    
    # Simple text search using ILIKE
    chunks = db.query(Chunk).join(Document).filter(
        Chunk.content.ilike(f"%{query}%")
    ).limit(top_k).all()
    
    return chunks
