#!/bin/bash
# Database setup script for WriterOS
# Compatible with Docker Compose environment

set -e

echo "🗄️  Setting up WriterOS database..."

# Check if running in Docker Compose
if command -v docker-compose &> /dev/null; then
    echo "📦 Using Docker Compose..."
    
    # Enable pgvector extension
    docker-compose exec -T db psql -U writer -d writeros -c "CREATE EXTENSION IF NOT EXISTS vector;"
    
    echo "✅ Database setup complete!"
else
    echo "⚠️  Docker Compose not found. Please ensure PostgreSQL is running locally."
    echo "   To setup manually, run:"
    echo "   psql -U writer -d writeros -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
    exit 1
fi
