# Flogo RAG Pipeline

Retrieval-Augmented Generation pipeline built with TIBCO Flogo, Weaviate, and Ollama.

## Architecture

- **Flogo App** — REST API (`POST /rag/weaviate/query/generate`) that embeds queries, searches Weaviate, and generates answers via an LLM
- **Weaviate** — vector database (Docker, port 18080)
- **Docling** — PDF/document parser API (Docker, port 8001)
- **Ollama** — runs natively on the host (port 11434) for embeddings (`nomic-embed-text`) and generation (`deepseek-r1`)

```
[PDF files]
     │
     ▼
[Docling container :8001]  ─── parses PDFs into chunks
     │
     ▼
[Weaviate container :18080] ── vector DB (nomic-embed-text via Ollama)
     │
     ▼
[weaviate-rag-pipeline binary :9191] ── Flogo RAG ReST server
     │
     ▼
[Rageval :8080]  ── LLM evaluation (native, runs separately)
[Ollama  :11434] ── LLM inference  (native, runs separately)
```

## Quick Start

```bash
# 1. Start Weaviate + Docling
docker compose up -d

# 2. Build & start the Flogo app (requires Flogo CLI)
cd flogo-apps
# build produces bin/weaviate-rag-pipeline
./bin/weaviate-rag-pipeline &

# 3. Query
curl -s http://localhost:9191/rag/weaviate/query/generate \
  -X POST -H 'Content-Type: application/json' \
  -d '{"query":"What is the system architecture?","collection":"MyCollection","topK":10}'
```

## Project Structure

```
docker-compose.yml        # Weaviate + Docling services
docling/
  Dockerfile              # Docling PDF parser Docker image
  docling-local-api.py    # Docling API server (PDF → Markdown / chunked text)
flogo-apps/
  weaviate-rag-pipeline.flogo  # Flogo application definition
eval/
  full_eval_flogo_smart.sh    # End-to-end eval: wipe → ingest → query → score
  run_queries_flogo_smart.py  # 50 RAG queries with ground-truth expectations
```
 </br>
- RAG Pipeline

<img width="2078" height="651" alt="image" src="https://github.com/user-attachments/assets/64ed47ca-1617-4b10-bfa9-0a686c45677a" /> </br>

- weaviate-rag-pipeline -> Query Pipeline

<img width="1345" height="563" alt="image" src="https://github.com/user-attachments/assets/6b8cb5d6-180e-416b-876b-6a6ec73f1f5d" /> </br>

- weaviate-rag-pipeline -> Ingest Pipeline

<img width="1683" height="567" alt="image" src="https://github.com/user-attachments/assets/212be3ce-b787-45cb-ad25-c7e3d4a785ba" />


## Custom Extensions

This pipeline uses the [**flogo-custom-extensions**](https://github.com/mpandav-tibco/flogo-custom-extensions) repo for Flogo activities, connectors, and functions:

- **VectorDB Connector** — multi-provider vector database connector (Weaviate, Chroma, Milvus, Qdrant) with collection management, document ingestion, and semantic search  
  [`connectors/VectorDB/`](https://github.com/mpandav-tibco/flogo-custom-extensions/tree/main/connectors/VectorDB)

## RAG Evaluation

Quality is measured using [**rageval**](https://github.com/mpandav-tibco/rag-evaluator) — a lightweight RAG evaluation tool with an embedded dashboard.

```bash
# Run the full eval pipeline (wipe collection → ingest PDFs → run 50 queries)
cd eval
COLLECTION=FlogoSmartDocs bash full_eval_flogo_smart.sh
```

Rageval scores each query on faithfulness, context relevance, answer relevance, and hallucination rate using both embedding-based and LLM-as-a-judge metrics. Results are visible on the rageval dashboard at `http://localhost:9090`.

---
Overall RAG Pipeline Metrics

<img width="2564" height="1124" alt="image" src="https://github.com/user-attachments/assets/8d5ea4d2-17bc-4bdf-a84b-6883ea2ef033" />

---
Individua Query Results

<img width="1556" height="1067" alt="image" src="https://github.com/user-attachments/assets/12d869b5-8d29-444f-ba8d-c607bbcbe8c4" />


See the [rageval repo](https://github.com/mpandav-tibco/rag-evaluator) for setup and configuration.

## Prerequisites

- Docker & Docker Compose
- Ollama with `nomic-embed-text` and your chosen LLM model
- TIBCO Flogo CLI (for building the app)
