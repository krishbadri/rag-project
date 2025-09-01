from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict
import json
import numpy as np
from app.models.models import Chunk, Document
from app.services.embedding_service import get_embedding
from app.database import IS_POSTGRES
from app.services.vector_store import search as vs_search, load_or_build_index


def search_relevant_chunks(
    query: str,
    top_k: int,
    db: Session,
    document_ids: Optional[List[str]] = None,
    batch_id: Optional[str] = None,
) -> List[Chunk]:
    """Search for relevant chunks using vector similarity"""

    # Get query embedding
    query_embedding = get_embedding(query)

    # If batch_id is provided, resolve its documents then do filtered vector search (preferred)
    if batch_id:
        doc_rows = db.query(Document.id).filter(Document.batch_id == batch_id).all()
        scoped_ids = [row[0] for row in doc_rows]
        if not scoped_ids:
            return []
        return _filtered_vector_search(query_embedding, top_k, db, scoped_ids)

    # If specific documents are provided, do an ephemeral, filtered vector search over just those
    if document_ids:
        return _filtered_vector_search(query_embedding, top_k, db, document_ids)

    # Otherwise, use the global index across all chunks
    try:
        load_or_build_index(db)
        ids = vs_search(query_embedding, top_k, db)
        if not ids:
            return _fallback_text_search(query, top_k, db)
        chunks = db.query(Chunk).filter(Chunk.id.in_(ids)).all()
        # Preserve ranking order
        order: Dict[int, int] = {cid: i for i, cid in enumerate(ids)}
        chunks.sort(key=lambda c: order.get(c.id, 1_000_000))
        return chunks
    except Exception:
        return _fallback_text_search(query, top_k, db)


def _fallback_text_search(query: str, top_k: int, db: Session) -> List[Chunk]:
    """Fallback text search when vector search is not available"""

    # Simple text search using ILIKE
    chunks = db.query(Chunk).join(Document).filter(
        Chunk.content.ilike(f"%{query}%")
    ).limit(top_k).all()

    return chunks


def _filtered_vector_search(
    query_embedding: List[float],
    top_k: int,
    db: Session,
    document_ids: List[str],
) -> List[Chunk]:
    """Vector search restricted to specific document IDs (ephemeral in-memory)."""
    # Load candidate chunk embeddings for the specified documents
    rows = (
        db.query(Chunk.id, Chunk.embedding)
        .filter(Chunk.document_id.in_(document_ids), Chunk.embedding.isnot(None))
        .all()
    )
    if not rows:
        return []

    ids: List[int] = []
    vecs: List[List[float]] = []
    for cid, emb_json in rows:
        try:
            vec = json.loads(emb_json)
            if isinstance(vec, list) and len(vec) > 0:
                ids.append(int(cid))
                vecs.append([float(x) for x in vec])
        except Exception:
            continue

    if not vecs:
        return []

    mat = np.array(vecs, dtype="float32")
    # Normalize for cosine similarity
    mat_norms = np.linalg.norm(mat, axis=1, keepdims=True)
    mat_norms[mat_norms == 0] = 1.0
    mat = mat / mat_norms

    q = np.array([query_embedding], dtype="float32")
    q_norm = np.linalg.norm(q, axis=1, keepdims=True)
    q_norm[q_norm == 0] = 1.0
    q = q / q_norm

    sims = np.dot(mat, q.T).reshape(-1)
    best = np.argsort(-sims)[:top_k]
    best_ids = [ids[int(i)] for i in best]

    # Fetch chunks and preserve ranking order
    chunks = db.query(Chunk).filter(Chunk.id.in_(best_ids)).all()
    order: Dict[int, int] = {cid: i for i, cid in enumerate(best_ids)}
    chunks.sort(key=lambda c: order.get(c.id, 1_000_000))
    return chunks
