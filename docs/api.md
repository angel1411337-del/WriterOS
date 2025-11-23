# WriterOS API

## Base URL
```
http://localhost:8000
```

## Authentication
Currently no authentication (development mode).

## Endpoints

### Health Check
**GET** `/health`

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### Chat Completion
**POST** `/chat`

Submit a query to the Orchestrator agent.

**Request Body:**
```json
{
  "message": "Who is the main antagonist?",
  "vault_id": "uuid-here",
  "conversation_id": "optional-uuid"
}
```

**Response:**
```json
{
  "response": "Based on your manuscript...",
  "conversation_id": "uuid",
  "sources": ["chapter-1", "chapter-5"]
}
```

---

### Generate Graph
**POST** `/graphs/generate`

Generate a D3.js visualization of story entities.

**Request Body:**
```json
{
  "vault_id": "uuid",
  "graph_type": "force",
  "max_nodes": 100
}
```

**Response:**
```json
{
  "nodes": [...],
  "links": [...],
  "stats": {
    "node_count": 42,
    "link_count": 87
  }
}
```

---

### Entity Search
**GET** `/entities/search`

Semantic search for entities by description.

**Query Parameters:**
- `query` (string) - Search query
- `vault_id` (uuid) - Vault filter
- `limit` (int) - Max results

**Response:**
```json
{
  "results": [
    {
      "id": "uuid",
      "name": "John Doe",
      "type": "CHARACTER",
      "description": "..."
    }
  ]
}
```

---

## Running the API

### Development
```bash
writeros serve
```

### Docker
```bash
docker-compose up
```

## API Client Example

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/chat",
        json={
            "message": "Summarize the protagonist's arc",
            "vault_id": vault_id
        }
    )
    data = response.json()
    print(data["response"])
```
