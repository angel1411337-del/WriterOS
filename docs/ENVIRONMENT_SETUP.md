# Environment Configuration Guide

## 🔒 Security-First Configuration

WriterOS now **requires** environment variables for all sensitive configuration. This prevents accidental credential exposure and follows security best practices.

---

## System Requirements

### Windows Prerequisites (IMPORTANT)

If you're on Windows, you **must** install the Visual C++ Redistributable for FastEmbed (local embeddings) to work:

**Download and Install:**
[Microsoft Visual C++ 2015-2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe)

**Why is this needed?**
- FastEmbed uses ONNX Runtime which requires Visual C++ runtime libraries
- This is a one-time installation required for Python ML libraries on Windows
- Without it, you'll see: `DLL load failed while importing onnxruntime_pybind11_state`

**After Installation:**
1. Download and run the installer from the link above
2. Restart your terminal/IDE
3. Verify: `python -c "from fastembed import TextEmbedding; print('OK')"`

### Linux/Mac Prerequisites

No additional system dependencies required. FastEmbed works out of the box.

---

## Quick Start

### 1. Copy the Template

```bash
cp .env.example .env
```

### 2. Edit Your Configuration

Open `.env` in your text editor and fill in your actual values:

```bash
# Required
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/writeros
OPENAI_API_KEY=sk-proj-your-actual-key-here

# Optional
YOUTUBE_API_KEY=your-youtube-key  # Only if using legacy scripts
OBSIDIAN_VAULT_PATH=/path/to/your/vault
LOG_LEVEL=INFO
```

### 3. Verify Configuration

Run the database initialization to verify your setup:

```bash
python -m writeros.utils.db
```

Expected output:
```
[info] connecting_to_database attempt=1
[info] creating_vector_indexes
[info] vector_indexes_created status=success
[info] database_initialized status=success
```

---

## Required Environment Variables

### DATABASE_URL (Required)

PostgreSQL connection string for the WriterOS database.

**Format:**
```
postgresql://username:password@host:port/database
```

**Examples:**

**Local Development:**
```bash
DATABASE_URL=postgresql://writer:mypassword@localhost:5432/writeros
```

**Docker Container:**
```bash
DATABASE_URL=postgresql://writer:password@db:5432/writeros
```

**Cloud Provider (e.g., Heroku, Render):**
```bash
DATABASE_URL=postgresql://user:pass@host.cloud.com:5432/prod_db?sslmode=require
```

**What Happens If Missing?**
```python
EnvironmentError: DATABASE_URL environment variable is not set.
Please set it to your PostgreSQL connection string.
Example: postgresql://user:password@host:port/database
```

---

### OPENAI_API_KEY (Required)

OpenAI API key for LLM agents.

**Get Your Key:**
1. Visit https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-proj-` or `sk-`)

**Format:**
```bash
OPENAI_API_KEY=sk-proj-abc123...xyz789
```

**Used For:**
- LLM-powered agents (GPT-4, GPT-4o)
- Smart content analysis
- Entity extraction

**What Happens If Missing?**
```python
ValueError: OPENAI_API_KEY is missing.
```

**Cost Considerations:**
- GPT-4o: ~$2.50 per 1M input tokens
- Set usage limits in OpenAI dashboard
- **Note:** Embeddings now run locally with FastEmbed (FREE!)

---

## Optional Environment Variables

### YOUTUBE_API_KEY (Optional)

Google Cloud YouTube Data API v3 key for fetching video metadata.

**Get Your Key:**
1. Visit https://console.cloud.google.com/apis/credentials
2. Enable YouTube Data API v3
3. Create credentials → API key

**Format:**
```bash
YOUTUBE_API_KEY=AIzaSyC...abc123
```

**Used For:**
- Legacy YouTube transcript scripts only
- Fetching video titles, thumbnails, metadata
- Not required for core WriterOS functionality

---

### OBSIDIAN_VAULT_PATH (Optional)

Path to your Obsidian vault for automatic note interlinking.

**Format:**

**Windows:**
```bash
OBSIDIAN_VAULT_PATH=C:\Users\Username\Documents\Obsidian\MyVault
```

**Mac/Linux:**
```bash
OBSIDIAN_VAULT_PATH=/Users/Username/Documents/Obsidian/MyVault
```

**Default:** `./output` (creates folder in project root)

**Used For:**
- Scanning existing notes to create Wikilinks
- Automatic [[Concept]] interlinking
- Cross-referencing entities across notes

---

### LOG_LEVEL (Optional)

Controls logging verbosity.

**Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Default:** `INFO`

**Examples:**

**Development (verbose):**
```bash
LOG_LEVEL=DEBUG
```

**Production (minimal):**
```bash
LOG_LEVEL=WARNING
```

**Debugging Issues:**
```bash
LOG_LEVEL=DEBUG
```

---

## Advanced Configuration

### Database Connection Pool Tuning

For high-performance production deployments:

```bash
# Connection pool size (default: 20)
# Increase for high-concurrency workloads
DB_POOL_SIZE=50

# Maximum overflow connections (default: 40)
# Temporary connections beyond pool size
DB_MAX_OVERFLOW=100

# Connection recycle time in seconds (default: 3600)
# Prevents stale connections
DB_POOL_RECYCLE=1800
```

**When to Tune:**
- Pool size too small → Connection timeouts under load
- Pool size too large → Database connection limit exceeded
- Recycle time too long → Stale connection errors

---

## Different Environments

### Local Development

Create `.env` in project root:

```bash
DATABASE_URL=postgresql://writer:password@localhost:5432/writeros
OPENAI_API_KEY=sk-proj-dev-key
LOG_LEVEL=DEBUG
```

### Docker Development

Use `docker-compose.yml` environment section:

```yaml
services:
  app:
    environment:
      DATABASE_URL: postgresql://writer:password@db:5432/writeros
      OPENAI_API_KEY: ${OPENAI_API_KEY}  # Read from host .env
      LOG_LEVEL: INFO
```

Then run:
```bash
docker-compose up
```

### Testing

Tests use a separate database to avoid polluting dev data:

```python
# tests/conftest.py
TEST_DATABASE_URL = "postgresql://writer:password@127.0.0.1:5433/writeros_test"
```

Run tests with test database:
```bash
# Make sure test DB is running on port 5433
docker run -d \
  -e POSTGRES_USER=writer \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=writeros_test \
  -p 5433:5432 \
  pgvector/pgvector:pg16

# Run tests
pytest tests/ -v
```

### Production Deployment

**Option 1: Cloud Platform Environment Variables**

Most cloud platforms (Heroku, Render, Railway) provide a UI for setting environment variables:

1. Go to app settings
2. Add environment variables:
   - `DATABASE_URL`: Automatically set by platform
   - `OPENAI_API_KEY`: Your production key
   - `LOG_LEVEL`: `INFO` or `WARNING`

**Option 2: Secret Management Service**

For enterprise deployments, use a secret manager:

```python
# Example with AWS Secrets Manager
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

secrets = get_secret('writeros/production')
os.environ['DATABASE_URL'] = secrets['database_url']
os.environ['OPENAI_API_KEY'] = secrets['openai_key']
```

---

## Security Best Practices

### ✅ DO

- ✅ Use `.env` file for local development
- ✅ Add `.env` to `.gitignore` (already done)
- ✅ Use environment variables in CI/CD pipelines
- ✅ Rotate API keys regularly
- ✅ Use different keys for dev/staging/production
- ✅ Set OpenAI usage limits to prevent surprise bills
- ✅ Use read-only database credentials where possible

### ❌ DON'T

- ❌ Commit `.env` file to git
- ❌ Share API keys in Slack, email, or docs
- ❌ Use production credentials in development
- ❌ Hardcode credentials in source code
- ❌ Use the same password across environments
- ❌ Store credentials in plain text documentation

---

## Troubleshooting

### Error: "DATABASE_URL environment variable is not set"

**Cause:** Missing or incorrectly formatted DATABASE_URL

**Fix:**
```bash
# 1. Check if .env exists
ls -la .env

# 2. Verify DATABASE_URL is set
cat .env | grep DATABASE_URL

# 3. Test loading environment
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DATABASE_URL'))"
```

### Error: "OPENAI_API_KEY is missing"

**Cause:** Missing OpenAI API key

**Fix:**
```bash
# 1. Verify key is in .env
cat .env | grep OPENAI_API_KEY

# 2. Check key format (should start with sk-)
# 3. Verify key is valid at https://platform.openai.com/api-keys
```

### Error: "connection to server failed"

**Cause:** Database not running or incorrect connection string

**Fix:**
```bash
# 1. Check if PostgreSQL is running
docker ps | grep postgres

# 2. Test connection manually
psql postgresql://writer:password@localhost:5432/writeros

# 3. Check connection string format
# Correct: postgresql://user:pass@host:port/db
# Wrong: postgres://... (missing 'ql')
```

### Error: "pgvector extension not found"

**Cause:** Using standard PostgreSQL instead of pgvector/pgvector image

**Fix:**
```bash
# 1. Stop current PostgreSQL
docker-compose down

# 2. Use pgvector image in docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16  # NOT postgres:16

# 3. Restart
docker-compose up -d
```

---

## Migration from Hardcoded Credentials

If you're upgrading from an older version with hardcoded credentials:

### Before (Insecure ❌)

```python
# src/writeros/utils/db.py
DATABASE_URL = "postgresql://writer:password@localhost:5432/writeros"
```

### After (Secure ✅)

```python
# src/writeros/utils/db.py
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise EnvironmentError("DATABASE_URL must be set")
```

### Migration Checklist

- [ ] Create `.env` file from `.env.example`
- [ ] Add all required environment variables
- [ ] Test database connection: `python -m writeros.utils.db`
- [ ] Run tests: `pytest tests/ -v`
- [ ] Verify `.env` is in `.gitignore`
- [ ] Update deployment scripts to use environment variables
- [ ] Document environment variables for your team

---

## Related Documentation

- [Vector Indexes Guide](./VECTOR_INDEXES.md) - Database performance optimization
- [Error Handling Guide](./ERROR_HANDLING.md) - Debugging and logging
- [Testing Guide](../tests/README.md) - Running tests with environment setup

---

## Summary

**Minimum Required Setup:**

```bash
# 1. Copy template
cp .env.example .env

# 2. Edit .env with your values
DATABASE_URL=postgresql://writer:password@localhost:5432/writeros
OPENAI_API_KEY=sk-proj-your-key

# 3. Verify
python -m writeros.utils.db
```

**That's it!** You're now using secure, environment-based configuration. 🎉
