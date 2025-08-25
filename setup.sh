#!/bin/bash

echo "🚀 Setting up RAG MVP Project..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "⚠️  Please edit .env and add your OpenAI API key!"
else
    echo "✅ .env file already exists"
fi

# Start infrastructure services
echo "🐳 Starting infrastructure services..."
docker-compose up -d postgres redis minio

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
pip install -r requirements.txt

# Initialize database
echo "🗄️  Initializing database..."
python -c "from app.database import init_db, create_tables; init_db(); create_tables()"

cd ..

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

cd ..

echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Edit .env and add your OpenAI API key"
echo "2. Start the backend: cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo "3. Start the frontend: cd frontend && npm run dev"
echo "4. Open http://localhost:3000 in your browser"
echo ""
echo "🔗 Services:"
echo "- Frontend: http://localhost:3000"
echo "- Backend API: http://localhost:8000"
echo "- MinIO Console: http://localhost:9001 (minio/minio123)"
