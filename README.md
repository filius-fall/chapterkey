# BookRAG

BookRAG is a self-hosted application for uploading books, indexing them into a local vector database, and querying them through a web UI, REST API, CLI, or MCP server.

## What It Supports

- Upload `EPUB` and `PDF` books
- Build local Chroma indexes per uploaded book
- Save your own provider keys for:
  - local Ollama
  - hosted Ollama-compatible endpoints
  - OpenAI-compatible APIs such as OpenRouter
  - NVIDIA embedding APIs such as `nvidia/nv-embedqa-e5-v5`
  - Anthropic
  - Google Gemini
- Choose separate models for:
  - Embeddings
  - Chat
  - OCR / vision extraction
- Query with spoiler modes:
  - `full_context`
  - `book_only`
  - `through_chapter`
  - `through_series_boundary`
- Link books into an ordered series
- Use the same backend from:
  - built-in web app
  - REST API
  - `bookrag` / `bookrag-cli`
  - `bookrag-mcp`
- Watch an input folder and auto-ingest books into a shared output store
- Query locally without running the API server

## Architecture

- `bookrag/api.py`: FastAPI app and built-in web UI
- `bookrag/services.py`: shared application logic
- `bookrag/providers.py`: provider adapters
- `bookrag/ingestion.py`: EPUB/PDF ingestion and OCR
- `bookrag/vector_store.py`: Chroma storage
- `bookrag/cli.py`: command-line interface
- `bookrag/folder_ingest.py`: input-folder scan/watch workflow
- `bookrag/local_api.py`: direct local query helpers
- `bookrag/mcp_bridge.py`: MCP server that proxies to the REST API

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.template .env
```

Set at least:

```bash
BOOKRAG_APP_SECRET=change-this-secret-before-deploying
BOOKRAG_API_TOKEN=replace-later
BOOKRAG_OLLAMA_EMBEDDING_MODEL=embeddinggemma
BOOKRAG_OLLAMA_CHAT_MODEL=qwen3:latest
```

### 3. Start the app

```bash
python app_server.py
```

Visit `http://127.0.0.1:8000`, create the admin account, add providers, upload books, and index them.

### Local folder workflow

If you prefer a file-drop pipeline, put `.epub` and `.pdf` files into `BOOKRAG_INPUT_DIR` and run:

```bash
bookrag local providers sync
bookrag local scan
```

Or keep a watcher running:

```bash
bookrag local watch
```

Successful ingests are verified against the output Chroma store and then removed from the input folder.

## CLI

```bash
bookrag --base-url http://127.0.0.1:8000 login --username admin --password your-password
bookrag libraries list
bookrag books upload --library-id 1 --file /path/to/book.epub
bookrag books ingest --book-id 1 --embedding-provider-id 1 --embedding-model text-embedding-3-small
bookrag chat --library-id 1 --question "What happens?" --chat-provider-id 1 --chat-model google/gemini-2.5-flash-preview
bookrag local query --question "Why did this happen?" --context-mode no_spoiler --active-book-id 1 --active-chapter-index 10
bookrag local series create --name "Stormlight Archive"
bookrag local series reorder --series-id 1 --book-ids 3,5,7
```

## MCP

Start the BookRAG API first, then run:

```bash
BOOKRAG_API_URL=http://127.0.0.1:8000 \
BOOKRAG_API_TOKEN=your-api-token \
python server.py
```

Example Claude Code MCP config:

```json
{
  "mcpServers": {
    "bookrag": {
      "command": "python",
      "args": ["/absolute/path/to/BookRAG/server.py"],
      "env": {
        "BOOKRAG_API_URL": "http://127.0.0.1:8000",
        "BOOKRAG_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

## Docker Compose

```bash
cp .env.template .env
docker compose up --build
```

The app stores SQLite data, uploads, and Chroma indexes in `./data`.

## OCR Notes

- OCR is intended for scanned PDFs, comics, and manga.
- OCR uses the selected vision-capable provider/model and may be significantly more expensive than text-only indexing.
- The app requires explicit OCR confirmation for indexing requests.
