# Flogo RAG Pipeline

Retrieval-Augmented Generation pipeline built with TIBCO Flogo, Weaviate, and Ollama.

## Architecture

- **Flogo App** — REST API (`POST /rag/weaviate/query/generate`) that embeds queries, searches Weaviate, and generates answers via an LLM
- **Weaviate** — vector database (Docker, port 18080)
- **Docling** — PDF/document parser API (Docker, port 8001)
- **Ollama** — runs natively on the host (port 11434) for embeddings (`nomic-embed-text`) and generation (`deepseek-r1`)

## Quick Start

```bash
# 1. Start Weaviate + Docling
docker compose up -d

# 2. Build & start the Flogo app (requires Flogo CLI)
cd flogo-apps
# build produces bin/weaviate-rag-mcp
./bin/weaviate-rag-mcp &

# 3. Query
curl -s http://localhost:9191/rag/weaviate/query/generate \
  -X POST -H 'Content-Type: application/json' \
  -d '{"query":"What is the system architecture?","collection":"MyCollection","topK":10}'
```

## Project Structure

```
docker-compose.yml        # Weaviate + Docling services
flogo-apps/
  weaviate-rag-mcp.flogo  # Flogo application definition
```

## Prerequisites

- Docker & Docker Compose
- Ollama with `nomic-embed-text` and your chosen LLM model
- TIBCO Flogo CLI (for building the app)
