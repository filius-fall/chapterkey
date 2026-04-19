# ChapterKey MCP Configuration

ChapterKey exposes a stable MCP server so external agent tools can use the same indexed books without reading Chroma files directly.

`ChapterKey` is the product name. The MCP server command and package names remain `bookrag` for compatibility.

## Supported Client Types

- Claude Code
- OpenCode
- Factory Droid
- Any other client that supports stdio MCP servers

## Start the Backend

Run the ChapterKey API first:

```bash
source venv/bin/activate
python app_server.py
```

Then start the MCP bridge:

```bash
BOOKRAG_API_URL=http://127.0.0.1:8000 \
BOOKRAG_API_TOKEN=your-api-token \
python server.py
```

## Claude Code / OpenCode Example

```json
{
  "mcpServers": {
    "bookrag": {
      "command": "python",
      "args": ["/absolute/path/to/chapterkey/server.py"],
      "env": {
        "BOOKRAG_API_URL": "http://127.0.0.1:8000",
        "BOOKRAG_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

## Generated Workspace Bundle

If you used `bookrag setup`, ChapterKey writes agent integration files into:

```text
.bookrag/integrations/
```

That folder includes:

- `BOOKRAG_SKILL.md`
- `claude-code.mcp.json`
- `opencode.mcp.json`
- `INSTALL_AGENTS.md`

These files are meant to be copied or merged into your preferred coding-agent environment.

## Tool Surface

The MCP bridge exposes these agent-friendly tools:

- `list_libraries`
- `list_books`
- `list_providers`
- `suggest_series`
- `query_context`
- `answer_question`
- `list_jobs`

## Recommended Agent Workflow

1. Call `list_libraries`.
2. Call `list_books` for the target library.
3. If books appear to be part of a series, call `suggest_series`.
4. Ask the user to confirm any ambiguous series order.
5. Use `query_context` with spoiler controls for retrieval.
6. Use `answer_question` only when you want ChapterKey itself to call a chat model.

## REST Fallback

If a client does not support MCP, it can use the REST API directly. The most useful endpoints are:

- `GET /libraries`
- `GET /libraries/{id}/books`
- `GET /libraries/{id}/series/suggestions`
- `POST /query/context`
- `POST /chat/answer`
- `POST /series`
- `POST /series/{id}/books/reorder`
