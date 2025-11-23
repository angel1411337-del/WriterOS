FROM python:3.11-slim

WORKDIR /app

# 1. Install system deps (if needed for pgvector/extensions)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# 2. Copy dependency definition
COPY pyproject.toml .

# 3. Copy source code
COPY src/ src/


# 4. Install the package (Crucial for src/ layout)
# This makes 'import writeros' work anywhere in the container
RUN pip install --no-cache-dir .

# 5. Run via the entrypoint defined in pyproject.toml
CMD ["writeros", "serve"]
