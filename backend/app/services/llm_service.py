import os
from typing import List, AsyncGenerator

try:
    from openai import OpenAI  # new SDK (>=1.0)
    _OPENAI_NEW = True
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore
    try:
        import openai as openai_legacy  # old SDK (<1.0)
        _OPENAI_NEW = False
    except Exception:  # pragma: no cover
        openai_legacy = None  # type: ignore
        _OPENAI_NEW = False

from app.models.models import Chunk
from dotenv import load_dotenv, find_dotenv, dotenv_values
from pathlib import Path
import json
import urllib.request
import urllib.error


def get_client():
    """Create OpenAI client lazily so fresh env vars are picked up."""
    # Ensure environment from root .env is loaded even if backend started elsewhere
    try:
        load_dotenv(find_dotenv())
    except Exception:
        pass
    # If neither new nor legacy client is available, bail
    if not (OpenAI or openai_legacy):
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    if not api_key:
        # Fallback: read root .env directly
        try:
            # backend/app/services -> parents[3] == project root
            root_env = Path(__file__).resolve().parents[3] / ".env"
            if root_env.exists():
                vals = dotenv_values(str(root_env))
                api_key = vals.get("OPENAI_API_KEY") or api_key
        except Exception:
            pass
    if not api_key:
        return None
    try:
        if OpenAI:
            if base_url:
                return OpenAI(api_key=api_key, base_url=base_url)
            return OpenAI(api_key=api_key)
        # Legacy fallback
        if openai_legacy:
            openai_legacy.api_key = api_key
            if base_url:
                openai_legacy.base_url = base_url
            return openai_legacy
        return None
    except Exception:
        return None


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


def _http_chat_completion(system_prompt: str, user_message: str, stream: bool = False) -> str:
    """HTTP fallback that calls OpenAI Chat Completions without SDK.
    Returns the full answer text (non-stream)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "LLM unavailable (no OPENAI_API_KEY set)."
    base = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 1000,
        "temperature": 0.7,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            obj = json.loads(body)
            choice = obj.get("choices", [{}])[0]
            message = choice.get("message", {})
            return message.get("content", "")
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode("utf-8")
            return f"Error generating answer: {err}"
        except Exception:
            return f"Error generating answer: HTTP {e.code}"
    except Exception as e:
        return f"Error generating answer: {str(e)}"


async def generate_answer(query: str, chunks: List[Chunk]) -> str:
    """Generate complete answer (non-streaming)."""
    system_prompt, user_message = _build_prompts(query, chunks)
    client = get_client()
    if not client:
        # HTTP fallback
        return _http_chat_completion(system_prompt, user_message, stream=False)
    try:
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content or ""
        else:
            # legacy client
            response = client.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return response["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error generating answer: {str(e)}"


async def generate_answer_stream(query: str, chunks: List[Chunk]) -> AsyncGenerator[str, None]:
    """Stream answer tokens as they arrive from the LLM."""
    system_prompt, user_message = _build_prompts(query, chunks)
    client = get_client()
    if not client:
        # HTTP fallback (non-stream) then yield in chunks
        text = _http_chat_completion(system_prompt, user_message, stream=False)
        if not text:
            return
        # yield in small pieces to mimic streaming
        step = 80
        for i in range(0, len(text), step):
            yield text[i:i+step]
        return
    try:
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        if hasattr(client, "chat"):
            stream = client.chat.completions.create(
                model=model,
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
        else:
            # legacy streaming
            stream = client.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=1000,
                temperature=0.7,
                stream=True
            )
            for chunk in stream:
                delta = chunk["choices"][0]["delta"].get("content") if "choices" in chunk else None
                if delta:
                    yield delta
    except Exception as e:
        yield f"Error generating answer: {str(e)}"
