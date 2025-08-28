import json
import os
from typing import List, Tuple, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models.models import Chunk

# Try to import faiss; if not available, we'll fall back to numpy scan
try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None  # type: ignore


VECTOR_DIR = os.getenv("VECTOR_DIR", "vector_index")
INDEX_PATH = os.path.join(VECTOR_DIR, "faiss.index")
META_PATH = os.path.join(VECTOR_DIR, "meta.json")

_index = None
_id_to_chunk_id: List[int] = []
_dim: Optional[int] = None


def _ensure_dir() -> None:
    if not os.path.isdir(VECTOR_DIR):
        os.makedirs(VECTOR_DIR, exist_ok=True)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _load_embeddings_from_db(db: Session) -> Tuple[np.ndarray, List[int]]:
    rows = db.query(Chunk.id, Chunk.embedding).filter(Chunk.embedding.isnot(None)).all()
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
        return np.zeros((0, 1), dtype="float32"), []
    arr = np.array(vecs, dtype="float32")
    return arr, ids


def load_or_build_index(db: Session) -> None:
    global _index, _id_to_chunk_id, _dim
    if _index is not None:
        return
    _ensure_dir()
    if faiss is not None and os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
        try:
            _index = faiss.read_index(INDEX_PATH)
            with open(META_PATH, "r", encoding="utf-8") as f:
                meta = json.load(f)
            _id_to_chunk_id = meta.get("ids", [])
            _dim = meta.get("dim")
            return
        except Exception:
            _index = None
            _id_to_chunk_id = []

    # Build from DB
    vectors, ids = _load_embeddings_from_db(db)
    if vectors.shape[0] == 0:
        _index = None
        _id_to_chunk_id = []
        _dim = None
        return

    _dim = int(vectors.shape[1])
    if faiss is not None:
        index = faiss.IndexFlatIP(_dim)
        vectors = _normalize(vectors)
        index.add(vectors)
        _index = index
        _id_to_chunk_id = ids
        _save_index()
    else:
        # No faiss; keep vectors in memory for numpy scan
        _index = vectors  # type: ignore[assignment]
        _id_to_chunk_id = ids


def rebuild_index(db: Session) -> None:
    """Rebuild the entire index from DB and persist to disk."""
    global _index, _id_to_chunk_id, _dim
    _ensure_dir()
    vectors, ids = _load_embeddings_from_db(db)
    if vectors.shape[0] == 0:
        _index = None
        _id_to_chunk_id = []
        _dim = None
        # Also clear on disk
        try:
            if os.path.exists(INDEX_PATH):
                os.remove(INDEX_PATH)
            if os.path.exists(META_PATH):
                os.remove(META_PATH)
        except Exception:
            pass
        return

    _dim = int(vectors.shape[1])
    if faiss is not None:
        index = faiss.IndexFlatIP(_dim)
        vectors = _normalize(vectors)
        index.add(vectors)
        _index = index
        _id_to_chunk_id = ids
        _save_index()
    else:
        _index = vectors  # type: ignore[assignment]
        _id_to_chunk_id = ids


def _save_index() -> None:
    if faiss is None or _index is None or _dim is None:
        return
    _ensure_dir()
    try:
        faiss.write_index(_index, INDEX_PATH)
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump({"ids": _id_to_chunk_id, "dim": _dim}, f)
    except Exception:
        pass


def add_embeddings(pairs: List[Tuple[int, List[float]]], db: Session) -> None:
    """Add (chunk_id, embedding) pairs to the index, creating if needed."""
    global _index, _id_to_chunk_id, _dim
    if not pairs:
        return
    # Ensure index exists
    if _index is None:
        load_or_build_index(db)

    # Prepare vectors
    ids = [int(cid) for cid, _ in pairs]
    vecs = np.array([[float(x) for x in emb] for _, emb in pairs], dtype="float32")
    if _dim is None:
        _dim = int(vecs.shape[1])

    if faiss is not None:
        if _index is None:
            _index = faiss.IndexFlatIP(_dim)
        vecs = _normalize(vecs)
        _index.add(vecs)
        _id_to_chunk_id.extend(ids)
        _save_index()
    else:
        # numpy in-memory list
        if _index is None:
            _index = vecs  # type: ignore[assignment]
            _id_to_chunk_id = ids
        else:
            _index = np.vstack([_index, vecs])  # type: ignore[assignment]
            _id_to_chunk_id.extend(ids)


def search(query_embedding: List[float], top_k: int, db: Session) -> List[int]:
    global _index, _id_to_chunk_id, _dim
    if _index is None:
        load_or_build_index(db)
    if _index is None or not _id_to_chunk_id:
        return []
    q = np.array([query_embedding], dtype="float32")
    if faiss is not None:
        q = _normalize(q)
        scores, idxs = _index.search(q, top_k)  # type: ignore[attr-defined]
        idxs = idxs[0]
        return [
            _id_to_chunk_id[i]
            for i in idxs
            if 0 <= i < len(_id_to_chunk_id)
        ]
    else:
        # cosine via numpy
        mat = _index  # type: ignore[assignment]
        mat_norm = _normalize(mat)
        qn = _normalize(q)
        sims = np.dot(mat_norm, qn.T).reshape(-1)
        best = np.argsort(-sims)[:top_k]
        return [_id_to_chunk_id[int(i)] for i in best]


