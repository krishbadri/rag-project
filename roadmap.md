Fullstack RAG MVP Project
Core pieces

Async ingestion pipeline

User uploads file → job queue (Redis + worker)

Worker does embeddings / OCR / ASR → stores results in DB + vector store

/jobs/{id} endpoint to poll status → demonstrates queues, background work, reliability

Search & retrieval API (/search returns top-k chunks from PGVector/Qdrant)

Chat / LLM interface → streams answer with citations

Observability basics (structured logs, optional metrics)

Product vision

A fast, minimal multimodal RAG MVP where users can upload docs (PDFs, images, short videos) and ask questions to get answers with explicit citations. Focus is on core retrieval + LLM functionality, not accounts or chat history.

Target users / use cases

Quick answers from messy materials

Summarize key points, find numbers/dates, compare content across documents, highlight sources

MVP feature set

Upload: Drag-and-drop PDF, PNG/JPG, MP4

Async ingestion: Automatic chunking, embedding, OCR/ASR

Search / Chat: Top-K retrieved chunks + optional LLM answer streaming

Citations: Show source document + page/frame/time

Delete / replace document: Optional, minimal UI

No auth, no dashboard, no chat history, no quotas

UX at a glance

Landing / Upload

Single-page app, drag-and-drop upload

Progress bar while uploading

File automatically ingested

Job status

Status chip: Processing… → Ready

Optionally poll /jobs/{id}

Query / Chat

Input box for questions

/search retrieves relevant chunks

Optional LLM generates answer streamed via SSE

Citations are clickable to highlight sources

Source verification

“Show retrieval” toggle reveals chunks used

System overview (conceptual)

Frontend SPA → Backend API → Worker → Storage/Indexes

Frontend calls: /uploads:init, /jobs/{id}, /search, /chat

Backend: orchestrates upload, ingestion, retrieval, chat streaming

Worker: processes uploaded file → chunks → embeddings → stores in DB + vector store

Storage: S3-compatible object store, Postgres + pgvector

Tech choices

Frontend: React + Next.js + TypeScript + Tailwind

Backend: FastAPI with SSE

DB: Postgres (+ pgvector)

Object store: S3-compatible (MinIO in dev)

Queue / Workers: Redis + RQ or Celery

No auth / JWT / multi-tenancy for MVP

Minimal API surface

POST /uploads:init → presigned URL + doc ID

POST /documents/{id}:ingest → enqueue ingestion job

GET /jobs/{job_id} → poll status

POST /search → top-K chunks

POST /chat → SSE stream of LLM answer + citations

Core data entities

Document: id, name, mime, bytes, status

Chunk: document ref, modality, content text, citation locator, embedding vector

Job: type, state, retries, error

No user / tenant entity for MVP

Non-functional requirements

Speed: perceived LLM response latency < 2s to first token

Reliability: uploads resilient; ingestion jobs retry on failure

Security: files private by default, signed uploads

Accessibility: keyboard navigation, readable contrast

Deployment plan

Dev: Docker Compose for Postgres, Redis, MinIO, backend, worker

Prod: Backend + worker on managed VM or Render/Fly, S3 bucket for uploads

Frontend: Vercel or Netlify

Success metrics (MVP)

Upload → “Ready” in <60s for a 20-page PDF

/search returns relevant chunks quickly

Chat / LLM streaming works with citations

Minimal UI errors, p95 API latency acceptable

Build milestones (2 weeks)

Week 1 — Foundations

Scaffold frontend / backend

Upload flow + presigned S3 URL

Async ingestion pipeline (PDF → chunks → embeddings)

Week 2 — Queries & LLM answers

/search endpoint + show retrieval panel

/chat SSE streaming with citations (optional LLM)

Minimal delete / replace document

Step 1: Scaffold your project

Frontend: Next.js + TS + Tailwind

Backend: FastAPI

Dev infra: Docker Compose for Postgres + Redis + MinIO + worker

Database setup: SQLAlchemy ORM for Document, Chunk, Job tables → auto-created on startup

Step 2: Presigned upload flow

POST /uploads:init → presigned URL + doc ID

Upload file directly to S3 / MinIO

Automatically enqueue ingestion job

Step 3: Async ingestion pipeline

Worker listens on Redis queue

Downloads file from S3

Extracts text (OCR/ASR)

Chunks content → computes embeddings → stores in Postgres + pgvector

GET /jobs/{job_id} shows status

All ingestion results stored via SQLAlchemy ORM

Step 4: Search / LLM query

POST /search → top-K chunks

POST /chat → streams LLM answer (for MVP, you can initially return the final answer without explicit citations; once the pipeline is stable, upgrade to streaming and add citations for transparency)

“Show retrieval” toggle highlights chunks