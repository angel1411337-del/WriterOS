# WriterOS

AI-powered continuity engine for complex fiction

**License:** Proprietary - Source Available for Portfolio Viewing Only  
**Status:** Active Development - Not Open Source  


---

## Important Notice

This repository contains source code for portfolio demonstration purposes only.

### Permitted Uses

- View the code to understand the architecture
- Reference it in technical discussions  
- Learn from the implementation patterns

### Prohibited Uses

- Use this code in any project
- Fork or create derivatives
- Run this software
- Create competing products

For commercial licensing inquiries: angel@writerios.com

---

## What is WriterOS?

WriterOS is a commercial AI writing assistant for authors managing complex fictional worlds. This repository showcases the technical architecture for portfolio and recruitment purposes.

### Technical Highlights

- Multi-Agent System: Specialized AI agents (Architect, Profiler, Psychologist, Navigator, Mechanic)
- PostgreSQL + pgvector: Semantic search over 500,000+ word manuscripts  
- Local-First Architecture: Docker Desktop deployment
- 5-Mode Query Router: Intelligent query classification and routing (Local, Global, Drift, SQL, Traversal)

### Technology Stack

- Python 3.11
- SQLModel (SQLAlchemy + Pydantic)
- LangChain for LLM orchestration
- PostgreSQL 16 with pgvector extension
- OpenAI GPT-4o for reasoning tasks
- FastEmbed for local, free embeddings (BAAI/bge models)
- Docker Compose for orchestration

---

## Commercial Product

WriterOS is a commercial product that is currently in development and will be available for download in the future. 

**Product Offerings:**

- Obsidian Plugins: One-click validation tools
- SaaS Platform: Cloud sync and team collaboration  
- Target Users: Authors writing 100,000+ word manuscripts

**Pricing:** Free tier available, Pro starts at $12/month

---

## Community

This GitHub repository is for portfolio demonstration only.

**Join the WriterOS community:**

Coming Soon 

Note: This repository does not accept pull requests or contributions on GitHub.

---

## Architecture Overview

### Multi-Agent System Design

WriterOS uses a coordinated team of specialized AI agents:

- **Architect:** Validates plot structure, continuity, and tracks story anchors
- **Profiler:** Extracts entities, builds relationship graphs and family trees
- **Psychologist:** Tracks character psychology and arc consistency
- **Navigator:** Validates travel time and spatial consistency
- **Mechanic:** Enforces magic and technology system rules
- **Producer:** Orchestrates queries across five intelligent search modes

### Database Schema

- Entity-Relationship model with flexible JSONB properties
- Graph-based relationship tracking with recursive CTE support
- Vector embeddings for semantic similarity search
- Canon layer management for handling retcons and alternate timelines

### System Architecture

- Local-first deployment via Docker Desktop
- PostgreSQL 16 as primary data store
- pgvector extension for semantic search capabilities
- LangChain for LLM orchestration and prompt management
- SQLModel for type-safe database operations

---

## For Recruiters

This project demonstrates:

- Multi-agent AI system design and orchestration
- PostgreSQL database architecture with vector search
- Production-quality Python code with type safety
- Docker-based deployment strategies
- Commercial SaaS product development
- API design and integration patterns

**Technical Skills Showcased:**

- AI/ML: LangChain, OpenAI API, prompt engineering, semantic search
- Backend: Python 3.11, SQLModel, FastAPI, async/await patterns
- Database: PostgreSQL, pgvector, Alembic migrations, recursive CTEs
- DevOps: Docker Compose, local-first architecture
- Software Engineering: Type safety, testing, documentation

**Contact:** angel.s.pena77@gmail.com | LinkedIn: https://www.linkedin.com/in/angel-pena-6b77b618b/

---

## Project Structure

```
WriterOS/
├── agents/              # AI agent implementations
│   ├── architect.py     # Plot validation
│   ├── profiler.py      # Entity extraction
│   ├── psychologist.py  # Character analysis
│   ├── producer.py      # Query orchestration
│   └── schema.py        # Database models
├── utils/               # Utility functions
│   ├── db.py           # Database connection
│   └── writer.py        # File operations
├── tests/               # Test suite
├── docs/                # Technical documentation
├── docker-compose.yml   # Container orchestration
└── requirements.txt     # Python dependencies
```

---

## Documentation

- Architecture Overview: See docs/ARCHITECTURE.md
- Database Schema: See docs/SCHEMA.md
- Agent Design: See docs/AGENTS.md
- API Reference: See docs/API.md

---

## License

Copyright 2025 Angel Pena. All rights reserved.

This source code is made available for portfolio viewing only.  
See LICENSE file for full terms.

For commercial licensing inquiries: angel.s.pena77@gmail.com

---

## About the Author

Angel Pena  
Data Engineer | AI/ML  
Freelancer, Former Consultant, and Tech Enthusiast 

Specialized in multi-agent systems, data engineering, and production AI applications.

Contact: angel.s.pena77@gmail.com