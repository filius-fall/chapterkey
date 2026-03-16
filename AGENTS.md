# EPUB RAG MCP Server - AGENTS.md

## Overview

EPUB RAG MCP Server - A Model Context Protocol (MCP) server that enables Claude Code to answer questions about EPUB files using vector embeddings and RAG (Retrieval Augmented Generation).

## Project Structure

```
BookRAG/
├── server.py              # Main MCP server entry point
├── epub_processor.py      # EPUB text extraction and chunking
├── embedder.py           # OpenRouter embedding generation
├── chroma_manager.py     # ChromaDB vector storage operations
├── retriever.py          # RAG retrieval logic and query processing
├── openrouter_client.py  # OpenRouter API client (OpenAI-compatible)
├── config.py             # Configuration management
├── setup.py              # Package installation
├── requirements.txt      # Python dependencies
├── .env.template         # Environment variable template
├── README.md            # Main documentation
├── MCP_CONFIG.md        # MCP server configuration guide
├── QUICKSTART.md        # Quick start guide
└── data/                # ChromaDB persistent storage
```

## Build & Run Commands

### Installation
```bash
# Install in development mode
pip install -e .

# Install dependencies manually
pip install -r requirements.txt
```

### Starting the Server
```bash
# Activate virtual environment first
source venv/bin/activate

# Start the MCP server
python server.py
```

### Testing
```bash
# Run installation verification
python test_installation.py

# Run EPUB processing test
python test_epub.py

# Complete embedding generation
python complete_embeddings.py
```

### Development
```bash
# Rebuild package
python setup.py develop

# Uninstall
pip uninstall epub-rag-mcp
```

## Code Style Guidelines

### General Python Conventions
- **Python version**: >=3.9
- **Style**: Follow PEP 8
- **Type hints**: Use for all function signatures (required)
- **Imports**: Group as `stdlib`, `third-party`, `local` with blank lines between
- **Imports format**: Absolute imports preferred

### Naming Conventions
| Element | Convention | Example |
|---------|-----------|---------|
| Classes | PascalCase | `EpubProcessor`, `ChromaManager` |
| Functions | snake_case | `generate_embedding`, `query_chromadb` |
| Variables | snake_case | `epub_name`, `chunk_size` |
| Constants | UPPER_SNAKE_CASE | `CHUNK_SIZE`, `OPENROUTER_API_KEY` |
| Private | leading underscore | `_sanitize_collection_name` |

### Environment Variables - SECURITY CRITICAL
- **NEVER read `.env` file** - The `.env` file contains sensitive credentials (API keys, tokens)
- **NEVER read `.env` file** - The `.env` file contains sensitive credentials (API keys, tokens)
- **ALWAYS use `.env.template`** - This file contains the structure with placeholder values
- **USE environment variables** - Access via `$VAR_NAME` in shell, or `Config` class in Python
- **NEVER expose values** - Don't echo, print, or log actual environment variable values

The `.env.template` file shows the required structure:
```
OPENROUTER_API_KEY=your_openrouter_api_key_here
EMBEDDING_MODEL=openai/text-embedding-3-small
LLM_MODEL=google/gemini-2.5-flash-preview
CHUNK_SIZE=750
CHUNK_OVERLAP=100
TOP_K=5
```

Users must copy `.env.template` to `.env` and fill in their API key. The `.env` file should NEVER be committed to version control.

Example (CORRECT):
```python
# Use Config class to access environment variables
api_key = Config.OPENROUTER_API_KEY  # Reads from .env file via load_dotenv()
```

Example (WRONG - NEVER DO):
```python
# NEVER grep, cat, or read .env file
grep "API_KEY" ~/.env  # BAD
cat .env  # BAD
print(os.getenv("API_KEY"))  # BAD - may expose value in logs
```

### Type Hints
```python
# Required for all functions
def generate_embedding(self, text: str) -> List[float]:
    ...

# Use optional for nullable types
def my_function(arg: Optional[str] = None) -> str:
    ...

# Use specific types, not Any
from typing import List, Dict, Optional, Any

# Collections
List[str], Dict[str, Any], Optional[int]
```

### Imports
```python
# Standard library first
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Third-party
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Local project (use relative imports for same-package)
from config import Config
from chroma_manager import ChromaManager
```

### Error Handling
```python
# Use try/except for expected exceptions
try:
    result = self.process_epub(epub_path)
except FileNotFoundError as e:
    logger.error(f"EPUB not found: {epub_path}")
    return [TextContent(type="text", text=f"Error: {str(e)}")]
except Exception as e:
    logger.error(f"Error processing EPUB: {e}", exc_info=True)
    return [TextContent(type="text", text=f"Unexpected error: {str(e)}")]

# Validate before processing
is_valid, error = Config.validate()
if not is_valid:
    logger.error(f"Configuration error: {error}")
    return None
```

### Logging
```python
logger = logging.getLogger(__name__)

# Log levels
logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Non-critical issue")
logger.error("Error occurred", exc_info=True)  # Include traceback
logger.critical("Critical issue")
```

### String Formatting
```python
# Use f-strings (Python 3.6+)
f"Loaded EPUB: {epub_name}"
f"Processing {count} documents"

# Multi-line f-strings for complex output
response = f"""Summary:
- Title: {stats['title']}
- Chunks: {stats['chunk_count']}
- Cost: ${cost:.4f}
"""
```

### MCP Tool Implementation
```python
from mcp.types import Tool

# Define tools with clear descriptions and input schemas
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="load_epub",
            description="Load and process an EPUB file for RAG-based querying.",
            inputSchema={
                "type": "object",
                "properties": {
                    "epub_path": {
                        "type": "string",
                        "description": "Full path to the EPUB file"
                    }
                },
                "required": ["epub_path"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "load_epub":
        return await handle_load_epub(arguments)
    # ...
```

### ChromaDB Operations
```python
# Use sanitize_collection_name for EPUB names
collection_name = self._sanitize_collection_name(epub_name)

# Collections are identified by sanitized names
chroma_manager.add_documents(
    epub_name=epub_name,  # Used for user display
    embeddings=embeddings,
    texts=chunks,
    metadatas=metadata_list,
    ids=ids
)
```

### Configuration Management
```python
# Use Config class for all configuration
from config import Config

# Access configuration
chunk_size = Config.CHUNK_SIZE
api_key = Config.OPENROUTER_API_KEY

# Validate before use
is_valid, error = Config.validate()
if not is_valid:
    raise ValueError(error)
```

### EPUB Processing Patterns
```python
# Process EPUB in these steps:
# 1. Load EPUB file
book = self.load_epub(epub_path)

# 2. Extract text from chapters
chapters = self.extract_text(book)  # List of (title, text) tuples

# 3. Chunk text by token count
chunks, metadata = self.chunk_text(chapters, epub_name)

# 4. Calculate statistics
stats = {
    "title": title,
    "chapter_count": len(chapters),
    "chunk_count": len(chunks),
    "total_tokens": sum(m["token_count"] for m in metadata)
}
```

### Key Patterns

1. **Initialization**: All components initialize in `server.py` at module load
2. **Type safety**: Type hints required for all public methods
3. **Error handling**: Return error messages as `TextContent` for MCP
4. **Logging**: Use `logger` with `exc_info=True` for exceptions
5. **ChromaDB**: Collection names are sanitized; display names preserved in metadata
6. **Token counting**: Use `tiktoken` for accurate token estimation

## Configuration

### Environment Variables (`.env`)
```
OPENROUTER_API_KEY=your_openrouter_api_key_here
EMBEDDING_MODEL=openai/text-embedding-3-small
LLM_MODEL=google/gemini-2.5-flash-preview
CHUNK_SIZE=750
CHUNK_OVERLAP=100
TOP_K=5
```

### Data Storage
- Vector database: `data/chroma_db/` (persistent)
- Created automatically on first run

## API Services

### OpenRouter
- OpenAI-compatible API
- Base URL: `https://openrouter.ai/api/v1`
- Used for: Embeddings and LLM chat completions
- Cost-effective alternative to paid APIs

### Available LLM Models (via OpenRouter)
- `google/gemini-2.5-flash-preview`: Latest, fastest, default
- `google/gemini-2.5-pro`: Highest quality for complex tasks
- `google/gemini-1.5-flash`: Fast, reliable
- `google/gemini-1.5-pro`: High-quality reasoning
- `google/gemini-1.5-flash-8b`: Most cost-effective

## MCP Tools

| Tool | Purpose |
|------|---------|
| `load_epub` | Load and process EPUB file |
| `ask_question` | Query EPUB (Claude answers) |
| `ask_question_with_llm` | Get direct LLM answers |
| `list_epubs` | List loaded EPUBs |
| `get_epub_info` | Get EPUB statistics |
| `clear_epub` | Remove EPUB from storage |
| `list_available_models` | List available LLM models |

## Testing Guidelines

### Running Tests
```bash
# First-time setup
python test_installation.py  # Verify dependencies and config

# Process and test EPUB
python test_epub.py  # Full EPUB processing test

# Generate embeddings
python complete_embeddings.py  # Complete embedding generation
```

### Test EPUB
- Test file: `Myst,_Might,_and_Mayhem.epub` (in parent directory)
- This is the default EPUB used throughout tests

### Verification Checklist
- [ ] All modules import successfully
- [ ] `.env` has valid `OPENROUTER_API_KEY`
- [ ] Data directory is writable
- [ ] Components initialize without errors
- [ ] EPUB processing completes
- [ ] Embeddings generate successfully
- [ ] ChromaDB storage works

## Common Patterns

### Adding a New Tool
1. Add `Tool` definition in `list_tools()`
2. Add handler in `call_tool()`
3. Create handler function with proper error handling
4. Return `TextContent` objects for MCP compatibility

### Modifying Chunking
- Edit `CHUNK_SIZE` and `CHUNK_OVERLAP` in `.env`
- Or modify `chunk_text()` in `epub_processor.py`
- Re-process EPUB after changes

### Adding a New Query Filter
1. Implement filter logic in `retriever.py`
2. Add parameter to query method
3. Update MCP tool schema in `server.py`

## Troubleshooting

### Common Issues
1. **OPENROUTER_API_KEY error**: Ensure `.env` file exists with valid key
2. **EPUB not found**: Check file path is absolute and exists
3. **Embedding generation slow**: Normal for large EPUBs; use batches
4. **No results**: Try different query or increase `TOP_K`

### Logs
- Check logs for detailed error messages
- Use `exc_info=True` to include stack traces
- Logs show: timestamp, logger name, level, message
