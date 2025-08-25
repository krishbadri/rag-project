from sentence_transformers import SentenceTransformer
import numpy as np
import os

# Global model instance
_model = None


def get_embedding_model():
    """Get or create the embedding model instance"""
    global _model
    if _model is None:
        # Use a lightweight model for MVP
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        _model = SentenceTransformer(model_name)
    return _model


def get_embedding(text: str) -> list:
    """Generate embedding for text"""
    model = get_embedding_model()
    embedding = model.encode(text)
    return embedding.tolist()


def get_embeddings(texts: list[str]) -> list[list]:
    """Generate embeddings for multiple texts"""
    model = get_embedding_model()
    embeddings = model.encode(texts)
    return embeddings.tolist()


def cosine_similarity(vec1: list, vec2: list) -> float:
    """Calculate cosine similarity between two vectors"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)
