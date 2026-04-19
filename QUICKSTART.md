# Quick Start

## Local Workspace Flow

```bash
python3 -m venv ~/.venvs/bookrag
source ~/.venvs/bookrag/bin/activate
pip install --upgrade pip
pip install .
bookrag setup
```

By default, setup creates:

```text
~/Documents/BookRAG
~/Documents/BookRAG/input
~/Documents/BookRAG/output
```

After setup:

1. Drop `.epub` or `.pdf` files into the workspace input folder.
2. Run `bookrag list`.
3. Run `bookrag convert 1` or `bookrag convert --all`.
4. Inspect output in the workspace output folder.

If you choose custom folders during setup, BookRAG validates them before saving the workspace.

Deletion behavior:

- default managed input folder: auto-delete after verified conversion
- custom input folder: optional delete preference, with one more confirmation before each deletion

`bookrag setup` also creates:

```text
~/Documents/BookRAG/.bookrag/integrations/
```

That folder contains ready-to-copy integration files for Claude Code, OpenCode, and other MCP-capable agent clients.

## Series Workflow

```bash
bookrag series books
bookrag series suggest
bookrag series create "My Series"
bookrag series connect "My Series" 1,2,3
```

Use `bookrag series suggest` when filenames contain markers like `Vol 01`, `Book 2`, or `Part 3`.

## Agent Workflow

If you want Claude Code, OpenCode, or Factory Droid to use BookRAG:

1. Start the API:

```bash
python app_server.py
```

2. Configure the MCP server using files from `.bookrag/integrations/`.
3. Give the agent the generated `BOOKRAG_SKILL.md` instructions.
4. Have the agent use `suggest_series` before connecting books into a series.

## Spoiler-Safe Retrieval

For first-time reading:

- use `context_mode=no_spoiler`
- provide `active_book_id`
- provide `active_chapter_index`

For full analysis:

- use `spoiler_mode=full_context`

For series-aware spoiler limits:

- use `spoiler_mode=through_series_boundary`
