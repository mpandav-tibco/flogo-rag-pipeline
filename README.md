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
eval/
  full_eval_flogo_smart.sh    # End-to-end eval: wipe → ingest → query → score
  run_queries_flogo_smart.py  # 50 RAG queries with ground-truth expectations
```

## RAG Evaluation

Quality is measured using [**rageval**](https://github.com/mpandav-tibco/rag-evaluator) — a lightweight RAG evaluation tool with an embedded dashboard.

```bash
# Run the full eval pipeline (wipe collection → ingest PDFs → run 50 queries)
cd eval
COLLECTION=FlogoSmartDocs bash full_eval_flogo_smart.sh
```

Rageval scores each query on faithfulness, context relevance, answer relevance, and hallucination rate using both embedding-based and LLM-as-a-judge metrics. Results are visible on the rageval dashboard at `http://localhost:9090`.

See the [rageval repo](https://github.com/mpandav-tibco/rag-evaluator) for setup and configuration.

## Prerequisites

- Docker & Docker Compose
- Ollama with `nomic-embed-text` and your chosen LLM model
- TIBCO Flogo CLI (for building the app)
