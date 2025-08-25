# RAG MVP Project

A fast, minimal multimodal RAG (Retrieval-Augmented Generation) MVP where users can upload documents (PDFs, images, short videos) and ask questions to get answers with explicit citations.

## Features

- **Multimodal Support**: PDFs, PNG/JPG images, MP4 videos
- **Async Processing**: Automatic chunking, embedding, OCR/ASR
- **Real-time Chat**: LLM-powered Q&A with streaming responses
- **Citations**: Clickable source references with document/page/frame locations
- **No Authentication**: Simple, immediate use

## Tech Stack

- **Frontend**: Next.js + TypeScript + Tailwind CSS
- **Backend**: FastAPI with SSE streaming
- **Database**: PostgreSQL + pgvector
- **Storage**: MinIO (S3-compatible)
- **Queue**: Redis + background workers
- **LLM**: OpenAI API integration

## Quick Start

1. **Clone and setup**:
   ```bash
   git clone <repository>
   cd rag-project
   ```

2. **Set up environment variables**:
   ```bash
   cp env.example .env
   # Edit .env and add your OpenAI API key
   ```

3. **Start infrastructure**:
   ```bash
   docker-compose up -d postgres redis minio
   ```

4. **Install dependencies**:
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt
   
   # Frontend
   cd ../frontend
   npm install
   ```

5. **Initialize database**:
   ```bash
   cd backend
   python -c "from app.database import init_db, create_tables; init_db(); create_tables()"
   ```

6. **Run the application**:
   ```bash
   # Backend (from backend directory)
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   
   # Frontend (from frontend directory)
   npm run dev
   ```

7. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - MinIO Console: http://localhost:9001 (minio/minio123)

## Docker Setup (Alternative)

For a complete Docker setup:

```bash
# Copy environment file
cp env.example .env
# Edit .env and add your OpenAI API key

# Start all services
docker-compose up -d

# Access the application
# Frontend: http://localhost:3000 (run separately for now)
# Backend API: http://localhost:8000
# MinIO Console: http://localhost:9001 (minio/minio123)
```

## Project Structure

```
rag-project/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── models/         # SQLAlchemy models
│   │   ├── api/            # API routes
│   │   ├── services/       # Business logic
│   │   └── workers/        # Background job workers
│   ├── requirements.txt
│   └── main.py
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Next.js pages
│   │   └── styles/         # Tailwind styles
│   ├── package.json
│   └── next.config.js
├── docker-compose.yml      # Infrastructure services
└── roadmap.md             # Project roadmap
```

## API Endpoints

- `POST /uploads/init` - Get presigned URL for file upload
- `POST /documents/{id}/ingest` - Enqueue ingestion job
- `GET /jobs/{job_id}` - Get job status
- `POST /search` - Search for relevant chunks
- `POST /chat` - Stream LLM answer with citations

## Development

This project follows a 2-week development plan:

**Week 1**: Foundations (scaffolding, upload flow, async ingestion)
**Week 2**: Queries & LLM answers (search, chat streaming, citations)

## License

MIT
