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

For Debian/Ubuntu users, see [INSTALL_LINUX.md](/home/sreeram/Projects/BookRAG/INSTALL_LINUX.md).

### 1. Install BookRAG

```bash
python3 -m venv ~/.venvs/bookrag
source ~/.venvs/bookrag/bin/activate
pip install --upgrade pip
pip install .
```

### 2. Initialize the CLI workspace

```bash
bookrag setup
```

By default this creates:

```text
~/Documents/BookRAG
~/Documents/BookRAG/input
~/Documents/BookRAG/output
```

You can choose a custom workspace root or separate custom input/output folders during setup.

### Local folder workflow

After setup, put `.epub` and `.pdf` files into the configured input folder and run:

```bash
bookrag list
bookrag convert --all
```

The CLI validates successful vector creation before deleting originals. In the default managed input folder, verified conversions auto-delete the source file. For custom input folders, BookRAG can ask again before deleting each verified original.

### Optional web/API flow

If you want the web UI or MCP bridge:

```bash
cp .env.template .env
python app_server.py
```

## CLI

```bash
bookrag setup
bookrag list
bookrag convert --all
bookrag status
bookrag series books
bookrag series suggest
bookrag series create "Stormlight Archive"
bookrag series connect "Stormlight Archive" 1,2,3

bookrag --base-url http://127.0.0.1:8000 login --username admin --password your-password
bookrag libraries list
bookrag books upload --library-id 1 --file /path/to/book.epub
bookrag books ingest --book-id 1 --embedding-provider-id 1 --embedding-model text-embedding-3-small
bookrag chat --library-id 1 --question "What happens?" --chat-provider-id 1 --chat-model google/gemini-2.5-flash-preview
bookrag local query --question "Why did this happen?" --context-mode no_spoiler --active-book-id 1 --active-chapter-index 10
bookrag local series create --name "Stormlight Archive"
bookrag local series reorder --series-id 1 --book-ids 3,5,7
```

`bookrag setup` is the main onboarding path. It defaults to `~/Documents/BookRAG`, validates directory choices before continuing, and stores workspace metadata under `<workspace>/.bookrag/`.

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

If you used `bookrag setup`, a workspace-specific integration bundle is generated in `.bookrag/integrations/` with:

- `BOOKRAG_SKILL.md`
- `claude-code.mcp.json`
- `opencode.mcp.json`
- `INSTALL_AGENTS.md`

These files are meant to be copied into Claude Code, OpenCode, Factory Droid, or any custom MCP-capable workflow.

### External Agent Usage

External coding agents should use the API or MCP layer instead of reading Chroma files directly. The recommended flow is:

1. `list_libraries`
2. `list_books`
3. `suggest_series`
4. `query_context`
5. `answer_question` only if you want BookRAG to call a chat provider itself

`suggest_series` exists so tools like OpenCode or Claude Code can inspect the current library, infer likely volume order from titles and filenames, and then ask for confirmation before connecting the series.

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
