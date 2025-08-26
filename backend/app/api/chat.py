from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import json

from app.database import get_db
from app.services.llm_service import generate_answer, generate_answer_stream
from app.services.search_service import search_relevant_chunks

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    top_k: int = 5
    stream: bool = True


class ChatResponse(BaseModel):
    answer: str
    citations: List[dict]


@router.post("/", response_model=ChatResponse)
async def chat_without_streaming(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """Chat with LLM (non-streaming version)"""

    chunks = search_relevant_chunks(request.query, request.top_k, db)
    answer = await generate_answer(request.query, chunks)

    citations = []
    for chunk in chunks:
        citations.append({
            "chunk_id": chunk.id,
            "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
            "document": {
                "id": chunk.document.id,
                "name": chunk.document.name
            },
            "citation_locator": chunk.citation_locator
        })

    return ChatResponse(answer=answer, citations=citations)


@router.post("/stream")
async def chat_with_streaming(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """Chat with LLM (streaming version)"""

    async def generate_stream():
        chunks = search_relevant_chunks(request.query, request.top_k, db)

        citations = []
        for chunk in chunks:
            citations.append({
                "chunk_id": chunk.id,
                "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                "document": {
                    "id": chunk.document.id,
                    "name": chunk.document.name
                },
                "citation_locator": chunk.citation_locator
            })
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

        async for token in generate_answer_stream(request.query, chunks):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        yield f"data: {json.dumps({'type': 'end'})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )
