# Use the official lightweight Python image
FROM python:3.13-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies (if any) – none needed for pure Python
# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    "uvicorn[standard]"==0.30.6 \
    sqlmodel==0.0.22 \
    pgvector==0.2.5 \
    asyncpg==0.29.0 \
    "pydantic[email]"==2.9.2

# Copy the entire project into the container
COPY . /app

# Expose the FastAPI port
EXPOSE 8000

# Default command to run the API server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
