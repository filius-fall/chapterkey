# MCP Server Configuration for Opencode/Claude Code

## Directory: /home/sreeram/Projects/BookRAG

Add this to your Opencode/Claude Code config:

```json
{
  "mcpServers": {
    "epub-rag-mcp": {
      "command": "python",
      "args": ["/home/sreeram/Projects/BookRAG/server.py"]
    }
  }
}
```

## Setup Steps

1. **Create .env file** (if it doesn't exist):
```bash
cd /home/sreeram/Projects/BookRAG
cp .env.template .env  # Or create manually
```

2. **Get OpenRouter API Key**:
   - Visit https://openrouter.ai/keys
   - Copy your API key
   - Add to `.env`: `OPENROUTER_API_KEY=your_actual_key_here`

3. **Activate virtual environment**:
```bash
source venv/bin/activate
```

4. **Test the server directly** (optional):
```bash
python server.py
```
The server should start and wait for MCP connections.

5. **Restart Opencode/Claude Code** to load the new MCP server.

## Available Tools in Claude Code

Once configured, you'll see these tools in Claude Code:

| Tool | Usage |
|------|-------|
| `load_epub` | Load and process an EPUB file for RAG |
| `ask_question` | Ask questions about loaded EPUB (Claude answers) |
| `ask_question_with_llm` | Get direct answers using Gemini via OpenRouter |
| `list_epubs` | List all loaded EPUBs |
| `get_epub_info` | Get detailed info about an EPUB |
| `clear_epub` | Remove an EPUB from storage |
| `list_available_models` | List available Gemini models |

## Example Usage in Claude Code

```
Use tool: load_epub
epub_path: "/path/to/your/book.epub"
```

Then ask questions:
```
Use tool: ask_question_with_llm
question: "Who are the main characters?"
model: "google/gemini-2.5-flash-preview"
```

## Troubleshooting

### "Configuration error: OPENROUTER_API_KEY is required"
- Make sure `.env` file exists in `/home/sreeram/Projects/BookRAG/`
- File should contain: `OPENROUTER_API_KEY=your_actual_key`

### "EPUB file not found"
- Use absolute paths (e.g., `/home/user/books/book.epub`)
- Check the file exists with: `ls -la /path/to/book.epub`

### Server not appearing in Claude Code
- Restart Opencode/Claude Code after adding config
- Check Claude Code logs for MCP connection errors
- Ensure the path to `server.py` is correct
