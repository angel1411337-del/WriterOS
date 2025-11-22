# WriterOS Architecture Snapshot (Sample)

- Agents coordinate via async queries and shared Postgres graph storage.
- Producer routes to Local, Global, Drift, SQL, and Traversal modes.
- RAG contexts prefer on-disk vault content to keep answers grounded.
