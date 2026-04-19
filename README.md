# BookRAG

BookRAG is a self-hosted application for uploading books, indexing them into a local vector database, and querying them through a web UI, REST API, CLI, or MCP server.

## What It Supports

- Upload `EPUB` and `PDF` books
- Build local Chroma indexes per uploaded book
- Save your own provider keys for:
  - OpenAI-compatible APIs such as OpenRouter
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
  - `bookrag-cli`
  - `bookrag-mcp`

## Architecture

- `bookrag/api.py`: FastAPI app and built-in web UI
- `bookrag/services.py`: shared application logic
- `bookrag/providers.py`: provider adapters
- `bookrag/ingestion.py`: EPUB/PDF ingestion and OCR
- `bookrag/vector_store.py`: Chroma storage
- `bookrag/cli.py`: command-line interface
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
```

### 3. Start the app

```bash
python app_server.py
```

Visit `http://127.0.0.1:8000`, create the admin account, add providers, upload books, and index them.

## CLI

```bash
bookrag-cli --base-url http://127.0.0.1:8000 login --username admin --password your-password
bookrag-cli libraries list
bookrag-cli books upload --library-id 1 --file /path/to/book.epub
bookrag-cli books ingest --book-id 1 --embedding-provider-id 1 --embedding-model text-embedding-3-small
bookrag-cli chat --library-id 1 --question "What happens?" --chat-provider-id 1 --chat-model google/gemini-2.5-flash-preview
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
