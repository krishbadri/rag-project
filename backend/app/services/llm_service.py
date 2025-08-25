import openai
import os
from typing import List, AsyncGenerator
from app.models import Chunk

# Configure OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


async def generate_answer(
    query: str, 
    chunks: List[Chunk], 
    stream: bool = False
) -> str | AsyncGenerator[str, None]:
    """Generate answer using LLM with context from chunks"""
    
    # Format context from chunks
    context = "\n\n".join([
        f"Document: {chunk.document.name}\n"
        f"Content: {chunk.content}\n"
        f"Location: {chunk.citation_locator or 'Unknown'}"
        for chunk in chunks
    ])
    
    # Create system prompt
    system_prompt = """You are a helpful assistant that answers questions based on the provided document context. 
    Always cite your sources by referring to the document name and location when possible.
    If the context doesn't contain enough information to answer the question, say so clearly.
    Keep your answers concise and accurate."""
    
    # Create user message
    user_message = f"""Context from documents:
{context}

Question: {query}

Please answer the question based on the context provided above."""
    
    try:
        if stream:
            return await _generate_streaming_answer(system_prompt, user_message)
        else:
            return await _generate_complete_answer(system_prompt, user_message)
    except Exception as e:
        if stream:
            yield f"Error generating answer: {str(e)}"
        else:
            return f"Error generating answer: {str(e)}"


async def _generate_complete_answer(system_prompt: str, user_message: str) -> str:
    """Generate complete answer (non-streaming)"""
    response = await openai.ChatCompletion.acreate(
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=1000,
        temperature=0.7
    )
    
    return response.choices[0].message.content


async def _generate_streaming_answer(system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
    """Generate streaming answer"""
    stream = await openai.ChatCompletion.acreate(
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=1000,
        temperature=0.7,
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
