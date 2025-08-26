import os
from typing import List, AsyncGenerator

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

from app.models.models import Chunk

# Configure OpenAI client (optional)
client = None
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
if OpenAI and api_key:
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        client = None


def _build_prompts(query: str, chunks: List[Chunk]):
    context = "\n\n".join([
        f"Document: {chunk.document.name}\n"
        f"Content: {chunk.content}\n"
        f"Location: {chunk.citation_locator or 'Unknown'}"
        for chunk in chunks
    ])
    system_prompt = (
        "You are a helpful assistant that answers questions based on the provided document context. "
        "Always cite your sources by referring to the document name and location when possible. "
        "If the context doesn't contain enough information to answer the question, say so clearly. "
        "Keep your answers concise and accurate."
    )
    user_message = f"""Context from documents:
{context}

Question: {query}

Please answer the question based on the context provided above."""
    return system_prompt, user_message


async def generate_answer(query: str, chunks: List[Chunk]) -> str:
    """Generate complete answer (non-streaming)."""
    system_prompt, user_message = _build_prompts(query, chunks)
    if not client:
        return "LLM unavailable (no OPENAI_API_KEY set)."
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"Error generating answer: {str(e)}"


async def generate_answer_stream(query: str, chunks: List[Chunk]) -> AsyncGenerator[str, None]:
    """Stream answer tokens as they arrive from the LLM."""
    system_prompt, user_message = _build_prompts(query, chunks)
    if not client:
        yield "LLM unavailable (no OPENAI_API_KEY set)."
        return
    try:
        stream = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7,
            stream=True
        )
        for event in stream:
            delta = getattr(event.choices[0].delta, "content", None)
            if delta:
                yield delta
    except Exception as e:
        yield f"Error generating answer: {str(e)}"
