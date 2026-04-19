# ChapterKey

ChapterKey is a self-hosted book indexing and retrieval tool for `EPUB` and `PDF` files.

It is designed for a CLI-first workflow:

- drop books into an input folder
- convert them into a local vector database
- keep each book separately indexed inside the output database
- query with spoiler-aware retrieval rules
- group books into series and restrict retrieval by book/chapter/series boundary

ChapterKey can also expose the same indexed books through a web API and MCP server for tools like Claude Code, OpenCode, and similar agent clients.

`ChapterKey` is the product name. The command, Python package, and compatibility surface remain `bookrag`.

## Features

- Supports `EPUB` and `PDF`
- Creates a local Chroma-based vector database
- Stores book metadata in SQLite
- Supports local and hosted embedding providers
- Supports:
  - Ollama
  - OpenRouter
  - NVIDIA NIM / build.nvidia.com style embedding endpoints
  - other OpenAI-compatible endpoints
- Interactive first-run wizard (`bookrag init`) with provider presets
- Spoiler-aware retrieval modes:
  - `full_context`
  - `book_only`
  - `through_chapter`
  - `through_series_boundary`
- Series suggestions from filenames and titles like `Vol 01`, `Book 2`, `Part 3`
- CLI workspace setup with default folders in `~/Documents/BookRAG`
- Optional API + MCP access for external agent tools

## Install

### Option 1: pip + venv

This is the main recommended install path.

```bash
python3 -m venv ~/.venvs/bookrag
source ~/.venvs/bookrag/bin/activate
pip install --upgrade pip
pip install .
```

If you publish the package later, users can replace `pip install .` with:

```bash
pip install bookrag
```

### Option 2: Debian package

ChapterKey currently targets Debian-based Linux best, especially:

- Debian 12
- Ubuntu 22.04
- Ubuntu 24.04

Build the package from this repo:

```bash
./scripts/build_deb.sh
```

That creates:

```text
dist/bookrag_<version>_amd64.deb
```

Install it with:

```bash
sudo dpkg -i ./dist/bookrag_<version>_amd64.deb
```

The Debian package installs:

- `bookrag`
- `bookrag-api`
- `bookrag-mcp`
- man page (`man bookrag`)

Sample runtime env file:

```text
/etc/bookrag/bookrag.env
```

The `.deb` builds its virtual environment on the target machine during install instead of shipping a CI-created venv.
That avoids broken interpreter paths and Python ABI mismatches across machines.

Notes for `.deb` installs:

- internet access is required during installation so dependencies can be installed into `/opt/bookrag/venv`
- if bootstrap fails, re-run `sudo dpkg --configure bookrag`
- bootstrap logs are written to `/var/log/bookrag-bootstrap.log`

You can also download the `.deb` from GitHub Releases once a tagged release has been built.

### Option 3: Docker from the repo

Docker images are not published publicly. Docker users should build locally from the repo.

Recommended flow:

```bash
cp .env.example .env
./scripts/docker_local.sh up
```

The helper script also supports:

```bash
./scripts/docker_local.sh build
./scripts/docker_local.sh logs
./scripts/docker_local.sh down
```

## Environment file

Use this as the source of truth for what `.env` should look like:

- [`.env.example`](/home/sreeram/Projects/BookRAG/.env.example:1)

Typical workflow:

```bash
cp .env.example .env
```

Important variables:

- `BOOKRAG_INPUT_DIR`
- `BOOKRAG_OUTPUT_DIR`
- `BOOKRAG_SQLITE_PATH`
- `BOOKRAG_VECTOR_DB_DIR`
- `BOOKRAG_DEFAULT_EMBEDDING_PROVIDER_NAME`
- `BOOKRAG_OPENROUTER_API_KEY`
- `BOOKRAG_NVIDIA_API_KEY`
- `BOOKRAG_OLLAMA_EMBEDDING_MODEL`

Do not commit `.env`.

## Quick Start

### 1. Initialize the workspace

Run:

```bash
bookrag init
```

This launches an interactive wizard that:

1. Asks how you want to run ChapterKey (Ollama, OpenRouter, or Custom)
2. If Ollama: checks if Ollama is installed, starts it, pulls an embedding model
3. If OpenRouter: prompts for API key and embedding model
4. If Custom: offers presets for NVIDIA NIM and Mistral, or manual endpoint setup
5. Validates the embedding endpoint before finishing
6. Creates a default library

For the Custom option, sub-menu presets include:

- **NVIDIA NIM** (build.nvidia.com, free tier) — model `nvidia/nv-embedqa-e5-v5`
- **Mistral** (mistral.ai) — model `mistral-embed`
- **Other** — manual setup for any OpenAI-compatible API (LiteLLM, vLLM, LocalAI, etc.)

Alternatively, for workspace-based workflows:

```bash
bookrag setup
```

### 2. Add books

Drop `.epub` or `.pdf` files into the input folder (default: `~/BookRAG_Input`).

Then list them:

```bash
bookrag list
```

### 3. Index books

Using the local CLI:

```bash
bookrag local scan --library-id 1
```

Or using workspace convert:

```bash
bookrag convert --all
```

### 4. Query

Retrieve context passages:

```bash
bookrag local query --library-id 1 --question "What happens in chapter 5?"
```

Get an LLM answer with citations:

```bash
bookrag local answer --library-id 1 --question "Who is the traveler?"
```

Check workspace status:

```bash
bookrag status
```

## Releases

ChapterKey release distribution is:

- source from the GitHub repo
- `.deb` from GitHub Releases
- Docker built locally from the repo

Tagged releases are built by GitHub Actions and attach:

- `bookrag_<version>_amd64.deb`
- `SHA256SUMS.txt`

Docker is intentionally not published to any public registry.

## Input and deletion behavior

ChapterKey treats default and custom input folders differently.

### Default managed input

If you use the default workspace input folder, ChapterKey treats it as managed.

Behavior:

- file is converted
- vector DB is verified
- original input file is deleted automatically after success

### Custom input folder

If you use a custom input folder, ChapterKey asks whether originals should be deleted after verified conversion.

Behavior:

- if you choose no:
  - originals stay in the custom input folder
- if you choose yes:
  - ChapterKey asks one more time per file after verified conversion before deleting it

If a kept original is already indexed, `bookrag list` shows it as an indexed duplicate instead of plain pending.

## Output layout

The output folder contains the working ChapterKey database:

- `bookrag.sqlite3`
- `chroma_db/`
- `managed_books/`
- `bookrag_output_api.py`
- `bookrag-output`
- `bookrag-output-query`
- `bookrag-output-admin`
- `.bookrag-output.json`

Each indexed book remains separately identifiable inside the shared output database, which is important for:

- spoiler-safe retrieval
- series linking
- per-book context restrictions

The generated helper files let another local tool operate directly from the output folder without needing to know your workspace internals.

Example:

```bash
cd ~/Documents/BookRAG/output
./bookrag-output status
./bookrag-output list-books
./bookrag-output-query --question "What happened here?"
```

## CLI commands

### First-run setup

```bash
bookrag init
```

### Workspace commands

```bash
bookrag setup
bookrag list
bookrag status
bookrag update --check
bookrag update
bookrag convert 1
bookrag convert --all
bookrag convert --all --output /path/to/another/output
```

`bookrag update` uses the current install mode:

- if ChapterKey is running from a git checkout, it runs `git pull --ff-only` and reinstalls from the checkout
- if ChapterKey is installed as a normal Python package, it upgrades from the GitHub repo using the current Python interpreter
- if ChapterKey is installed from a `.deb`, it downloads the latest matching `.deb` from GitHub Releases and installs it with `dpkg`

Use `bookrag update --check` to see what it would do without changing anything.

### Series commands

Show indexed books:

```bash
bookrag series books
```

Show suggested series ordering from titles and filenames:

```bash
bookrag series suggest
```

Create a series:

```bash
bookrag series create "Stormlight Archive"
```

Connect books to a series in order:

```bash
bookrag series connect "Stormlight Archive" 1,2,3
```

List series:

```bash
bookrag series list
```

### Advanced/local commands

ChapterKey still includes the older local/API-oriented CLI surface for direct service usage:

```bash
bookrag local providers sync
bookrag local scan
bookrag local query --question "Why did this happen?"
bookrag local answer --question "Explain this scene"
```

### REST/API-oriented commands

If you run the API server, you can also use:

```bash
bookrag --base-url http://127.0.0.1:8000 login --username admin --password your-password
bookrag libraries list
bookrag books upload --library-id 1 --file /path/to/book.epub
bookrag books ingest --book-id 1 --embedding-provider-id 1 --embedding-model your-model
```

## Spoiler-safe retrieval

ChapterKey is designed for both spoiler and no-spoiler reading workflows.

### Modes

- `full_context`
  - search everything indexed
- `book_only`
  - restrict to one book
- `through_chapter`
  - only use content up to the current chapter
- `through_series_boundary`
  - only use content up to the current point in a series

### Example idea

If you are reading a book for the first time and only want safe context:

- use `context_mode=no_spoiler`
- provide:
  - `active_book_id`
  - `active_chapter_index`

For full spoilers and full context:

- use `spoiler_mode=full_context`

## Series support

ChapterKey can infer likely series order from filenames and titles.

Examples:

- `Chronicle Vol 01.epub`
- `Chronicle Vol 02.epub`
- `Book 1`
- `Part 3`

Use:

```bash
bookrag series suggest
```

Then confirm and connect the books with:

```bash
bookrag series connect "Series Name" 1,2,3
```

This is useful when the files already contain the volume order and you do not want to enter everything manually.

## Web API and MCP

The main workflow is CLI-first, but ChapterKey can also run as an API and MCP backend.

### Start API server

```bash
cp .env.example .env
python app_server.py
```

This starts the FastAPI app.

### Start MCP server

```bash
BOOKRAG_API_URL=http://127.0.0.1:8000 \
BOOKRAG_API_TOKEN=your-api-token \
python server.py
```

### MCP tools

The MCP bridge exposes tools like:

- `list_libraries`
- `list_books`
- `list_providers`
- `suggest_series`
- `query_context`
- `answer_question`
- `list_jobs`

## Agent integrations

When you run `bookrag setup`, ChapterKey generates an integration bundle in:

```text
<workspace>/.bookrag/integrations/
```

That folder includes:

- `BOOKRAG_SKILL.md`
- `claude-code.mcp.json`
- `opencode.mcp.json`
- `INSTALL_AGENTS.md`

These files are intended to help connect ChapterKey to:

- Claude Code
- OpenCode
- Factory Droid
- other MCP-capable clients

Recommended external-agent workflow:

1. connect through ChapterKey API or MCP
2. call `list_books`
3. call `suggest_series` when needed
4. use `query_context` for retrieval
5. use `answer_question` only if you want ChapterKey to call a chat model directly

## Current repo data

At the time of inspection, the current default runtime config in this repo points to:

- output DB: `data/bookrag_output`
- input folder: `data/input_books`

That is controlled by `.env`.

## Troubleshooting

### `bookrag list` shows indexed duplicate

That means the original file still exists in a custom input folder, but ChapterKey has already indexed it successfully.

### No workspace found

Run:

```bash
bookrag setup
```

If you are using a custom workspace, run commands from inside that workspace root or point your shell at the correct environment/home setup.

### Provider validation fails

Check:

- base URL
- API key
- model name
- whether the provider supports `/embeddings`

### Large book conversion is slow

Large EPUB/PDF conversions depend heavily on:

- embedding provider speed
- network latency
- model throughput
- chunk count

Cloud embeddings may take longer on very large books.

## Related docs

- [INSTALL_LINUX.md](/home/sreeram/Projects/BookRAG/INSTALL_LINUX.md:1)
- [QUICKSTART.md](/home/sreeram/Projects/BookRAG/QUICKSTART.md:1)
- [MCP_CONFIG.md](/home/sreeram/Projects/BookRAG/MCP_CONFIG.md:1)
