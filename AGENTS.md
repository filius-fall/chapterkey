# BookRAG - AGENTS.md

## Overview

BookRAG is a self-hosted RAG (Retrieval Augmented Generation) application for indexing and querying books (EPUB/PDF) using vector embeddings. It provides multiple interfaces: Web UI, REST API, CLI, and MCP server.

## Architecture

```
BookRAG/
├── app_server.py          # Entry point for FastAPI app
├── server.py              # MCP server entry point (proxies to REST API)
├── bookrag/
│   ├── api.py            # FastAPI app with web UI and REST endpoints
│   ├── services.py       # Core business logic (auth, providers, libraries, ingestion)
│   ├── db.py             # SQLite database operations
│   ├── providers.py      # LLM provider adapters (OpenRouter, Anthropic, Gemini)
│   ├── ingestion.py      # EPUB/PDF text extraction and OCR
│   ├── vector_store.py   # ChromaDB vector storage operations
│   ├── cli.py            # Command-line interface
│   ├── mcp_bridge.py     # MCP server that proxies to REST API
│   ├── security.py       # Password hashing, token management, encryption
│   ├── settings.py       # Configuration management
│   └── web.py            # HTML template rendering
├── data/                  # Persistent storage (SQLite, ChromaDB, uploads)
├── .env.template          # Environment configuration template
└── requirements.txt       # Python dependencies
```

### Key Components

1. **FastAPI App** (`bookrag/api.py`): Serves web UI and REST API endpoints
2. **Service Layer** (`bookrag/services.py`): Shared business logic for all interfaces
3. **Database** (`bookrag/db.py`): SQLite for users, providers, libraries, books, series
4. **Vector Store** (`bookrag/vector_store.py`): ChromaDB for document embeddings
5. **Ingestion** (`bookrag/ingestion.py`): EPUB/PDF parsing with optional OCR
6. **MCP Bridge** (`bookrag/mcp_bridge.py`): MCP server exposing REST API as tools

## Build & Run Commands

### Installation
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration
```bash
# Copy environment template
cp .env.template .env
# Edit .env with your settings
```

### Running the Application

#### Web UI + REST API
```bash
source venv/bin/activate
python app_server.py
# Visit http://127.0.0.1:8000
```

#### MCP Server (requires REST API running)
```bash
export BOOKRAG_API_URL=http://127.0.0.1:8000
export BOOKRAG_API_TOKEN=your-api-token
python server.py
```

#### CLI
```bash
bookrag-cli --base-url http://127.0.0.1:8000 login --username admin --password your-password
bookrag-cli libraries list
bookrag-cli books upload --library-id 1 --file /path/to/book.epub
bookrag-cli chat --library-id 1 --question "What happens?" --chat-provider-id 1
```

#### Docker Compose
```bash
docker compose up --build
```

## Environment Variables

### Core Application
- `BOOKRAG_APP_NAME`: Application name (default: BookRAG)
- `BOOKRAG_APP_SECRET`: Secret key for session encryption (required)
- `BOOKRAG_API_HOST`: API bind host (default: 0.0.0.0)
- `BOOKRAG_API_PORT`: API port (default: 8000)

### Storage Paths
- `BOOKRAG_DATA_DIR`: Base data directory
- `BOOKRAG_UPLOADS_DIR`: Book upload storage
- `BOOKRAG_VECTOR_DB_DIR`: ChromaDB storage
- `BOOKRAG_SQLITE_PATH`: SQLite database path

### Retrieval Defaults
- `BOOKRAG_TOP_K`: Number of context passages (default: 5)
- `BOOKRAG_CHUNK_SIZE`: Text chunk size in tokens (default: 750)
- `BOOKRAG_CHUNK_OVERLAP`: Chunk overlap in tokens (default: 100)

### MCP Bridge
- `BOOKRAG_API_URL`: REST API URL (default: http://127.0.0.1:8000)
- `BOOKRAG_API_TOKEN`: API authentication token

**SECURITY**: Never commit `.env` files. Never echo or log sensitive values.

## Code Style Guidelines

### General Python
- **Python version**: >=3.9
- **Style**: PEP 8
- **Type hints**: Required for all function signatures
- **Imports**: Group as stdlib, third-party, local (blank lines between)

### Naming Conventions
| Element | Convention | Example |
|---------|-----------|---------|
| Classes | PascalCase | `BookRAGService`, `VectorStore` |
| Functions | snake_case | `generate_embedding`, `query_context` |
| Variables | snake_case | `library_id`, `chunk_size` |
| Constants | UPPER_SNAKE_CASE | `CHUNK_SIZE`, `BOOKRAG_API_PORT` |
| Private | leading underscore | `_sanitize_provider` |

### Type Hints
```python
# Required for all functions
def generate_embedding(text: str) -> List[float]:
    ...

# Use Optional for nullable types
def get_provider(provider_id: Optional[int] = None) -> Dict[str, Any]:
    ...

# Use specific types, not Any
from typing import List, Dict, Optional, Any
```

### Error Handling
```python
# Service layer raises ValueError for expected errors
if not provider:
    raise ValueError("Provider not found")

# API layer catches and returns as JSONResponse
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=400)
```

### Logging
```python
logger = logging.getLogger(__name__)

logger.info("General information")
logger.warning("Non-critical issue")
logger.error("Error occurred", exc_info=True)  # Include traceback
```

### Database Operations
```python
# Use parameterized queries (sqlite3)
self.db.execute(
    "INSERT INTO libraries(name, description) VALUES (?, ?)",
    (name, description),
)

# Fetch one or many
library = self.db.fetch_one("SELECT * FROM libraries WHERE id = ?", (library_id,))
libraries = self.db.fetch_all("SELECT * FROM libraries")
```

### Provider Pattern
```python
# Providers store encrypted API keys
# decrypt_secret() used internally when calling LLM APIs
# Never log or expose decrypted keys
api_key = decrypt_secret(provider["api_key_encrypted"], self.settings.app_secret)
```

## Key Features

### Spoiler Modes
- `full_context`: Search all indexed content
- `book_only`: Restrict to current book
- `through_chapter`: Up to active chapter
- `through_series_boundary`: Up to current book in series

### Series Management
- Link books into ordered series
- Set series boundaries for spoiler-free reading
- Reorder books within series

### OCR Support
- Optional OCR for scanned PDFs, comics, manga
- Requires vision-capable provider/model
- Explicit cost confirmation required

## REST API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/providers` | GET/POST | Manage LLM providers |
| `/libraries` | GET/POST | Manage libraries |
| `/libraries/{id}/books/upload` | POST | Upload book |
| `/books/{id}/ingest` | POST | Index book with embeddings |
| `/query/context` | POST | Retrieve context passages |
| `/chat/answer` | POST | Get LLM answer with citations |
| `/series` | POST | Create series |
| `/series/{id}/books/reorder` | POST | Reorder series books |

## MCP Tools

| Tool | Purpose |
|------|---------|
| `list_libraries` | List available libraries |
| `list_books` | List books in a library |
| `list_providers` | List configured providers |
| `query_context` | Retrieve context with spoiler controls |
| `answer_question` | Get LLM answer with citations |
| `list_jobs` | List recent ingest jobs |

## Testing

```bash
# Verify installation
python test_installation.py

# Test EPUB processing
python test_epub.py

# Complete embeddings
python complete_embeddings.py
```

## Troubleshooting

### Common Issues
1. **Authentication errors**: Ensure `BOOKRAG_API_TOKEN` is set and valid
2. **Provider not found**: Create provider via web UI or `/providers` endpoint
3. **No search results**: Verify book is indexed (check ingest job status)
4. **OCR costs**: OCR requires explicit confirmation before indexing

### Logs
- Check application logs for detailed errors
- Use `exc_info=True` for full stack traces
- Ingest jobs show progress and cost estimates
