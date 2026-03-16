# Quick Start Guide

Get started with EPUB RAG MCP Server in 5 minutes.

## Prerequisites

- Python 3.9 or higher
- OpenRouter API key (get free at https://openrouter.ai/keys)
- Claude Code installed

## Step 1: Install Dependencies

```bash
cd /home/sreeram/Downloads/Telegram\ Desktop/epub-rag-mcp
pip install -r requirements.txt
```

## Step 2: Configure API Key

```bash
cp .env.template .env
```

Edit `.env` and add your API key:
```
OPENROUTER_API_KEY=your_actual_key_here
```

## Step 3: Test Installation

```bash
python test_installation.py
```

All tests should pass. If not, follow the instructions to fix issues.

## Step 4: Start the Server

```bash
python server.py
```

The server is now running and waiting for MCP connections.

## Step 5: Configure Claude Code

Add this to your Claude Code settings (`~/.config/claude-code/config.json`):

```json
{
  "mcpServers": {
    "epub-rag-mcp": {
      "command": "python",
      "args": ["/home/sreeram/Downloads/Telegram Desktop/epub-rag-mcp/server.py"]
    }
  }
}
```

**Note:** Update the path if you installed the server elsewhere.

## Step 6: Restart Claude Code

Close and reopen Claude Code to load the MCP server.

## Step 7: Use It!

Now you can use the MCP tools in Claude Code:

### Load an EPUB
```
Use tool: load_epub
epub_path: "/home/sreeram/Downloads/Telegram Desktop/Myst,_Might,_and_Mayhem.epub"
```

### Ask a Question (with Gemini LLM)
```
Use tool: ask_question_with_llm
question: "What is the main plot about?"
model: "google/gemini-2.5-flash-preview"
```

### List Available Models
```
Use tool: list_available_models
```

### List Loaded EPUBs
```
Use tool: list_epubs
```

## Common Issues

### "OPENROUTER_API_KEY is required"
- Make sure you created `.env` from `.env.template`
- Add your actual API key (not the placeholder)

### "EPUB file not found"
- Use absolute paths
- Check file spelling and extension (.epub)

### Slow on First Load
- Normal! First load generates embeddings
- Subsequent queries will be fast (<1 second)

### Server Not Found in Claude Code
- Make sure `server.py` is running
- Check the path in Claude Code settings
- Restart Claude Code after configuration

## Example Workflow

1. **Load EPUB:**
   ```
   Use tool: load_epub
   epub_path: "/path/to/book.epub"
   ```

2. **Ask Questions (with LLM):**
   ```
   Use tool: ask_question_with_llm
   question: "Who are the main characters?"
   model: "google/gemini-2.5-flash-preview"
   ```

3. **Get Info:**
   ```
   Use tool: get_epub_info
   epub_name: "Book Title"
   ```

4. **Clear When Done:**
   ```
   Use tool: clear_epub
   epub_name: "Book Title"
   ```

## Cost Estimates

Typical costs for 1M tokens:
- **Embeddings**: ~₹0.03 (text-embedding-3-small)
- **Gemini 2.5 Flash LLM**: ~₹0.83 per 1M output tokens (default - best value)
- **Gemini 1.5 Flash LLM**: ~₹0.25 per 1M output tokens (cheaper)
- **Gemini 1.5 Flash-8B LLM**: ~₹0.08 per 1M output tokens (most cost-effective)
- **Total**: Very affordable compared to premium LLM services

## Need Help?

- Check `README.md` for detailed documentation
- Run `test_installation.py` to diagnose issues
- Review `.env.template` for configuration options

## Next Steps

- Try loading different EPUB files
- Experiment with `ask_question` for various queries
- Adjust `CHUNK_SIZE` and `TOP_K` in `.env` for better results
- Check `data/chroma_db/` for persistent storage
