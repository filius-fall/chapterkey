"""Workspace configuration helpers for the simple ChapterKey CLI."""

from __future__ import annotations

import json
import os
import secrets
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from bookrag.services import BookRAGService


WORKSPACE_DIRNAME = ".bookrag"
CONFIG_FILENAME = "config.json"
SECRETS_FILENAME = "secrets.json"
OUTPUT_MANIFEST_FILENAME = ".bookrag-output.json"


def default_workspace_root() -> Path:
    """Return the default CLI workspace root."""
    return (Path.home() / "Documents" / "BookRAG").expanduser().resolve()


def workspace_dir(root: Path) -> Path:
    """Return the workspace metadata directory."""
    return root / WORKSPACE_DIRNAME


def config_path(root: Path) -> Path:
    """Return the workspace config path."""
    return workspace_dir(root) / CONFIG_FILENAME


def secrets_path(root: Path) -> Path:
    """Return the workspace secrets path."""
    return workspace_dir(root) / SECRETS_FILENAME


def default_input_dir(root: Path) -> Path:
    """Return the default workspace input directory."""
    return root / "input"


def default_output_dir(root: Path) -> Path:
    """Return the default workspace output directory."""
    return root / "output"


def find_workspace_root(start: Path | None = None) -> Path | None:
    """Search upward for a workspace config."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if config_path(candidate).exists():
            return candidate
    default_root = default_workspace_root()
    if config_path(default_root).exists():
        return default_root
    return None


def ensure_workspace_dirs(root: Path) -> None:
    """Create the workspace metadata directory."""
    workspace_dir(root).mkdir(parents=True, exist_ok=True)


def integrations_dir(root: Path) -> Path:
    """Return the generated integration bundle directory."""
    return workspace_dir(root) / "integrations"


def output_manifest_path(output_dir: Path) -> Path:
    """Return the generated output helper manifest path."""
    return output_dir / OUTPUT_MANIFEST_FILENAME


def load_workspace(root: Path | None = None) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Load workspace config and secrets."""
    found = root or find_workspace_root()
    if not found:
        raise ValueError("No ChapterKey workspace found. Run `bookrag setup` in this directory first.")
    config_file = config_path(found)
    secrets_file = secrets_path(found)
    if not config_file.exists():
        raise ValueError("Workspace config is missing. Run `bookrag setup` again.")
    config = json.loads(config_file.read_text())
    secrets_data = json.loads(secrets_file.read_text()) if secrets_file.exists() else {}
    return found, config, secrets_data


def save_workspace(root: Path, config: dict[str, Any], secrets_data: dict[str, Any]) -> None:
    """Persist workspace config and secrets."""
    ensure_workspace_dirs(root)
    config_path(root).write_text(json.dumps(config, indent=2, sort_keys=True))
    secrets_file = secrets_path(root)
    secrets_file.write_text(json.dumps(secrets_data, indent=2, sort_keys=True))
    os.chmod(secrets_file, 0o600)


def write_integration_bundle(root: Path, config: dict[str, Any]) -> Path:
    """Generate agent-facing docs and config snippets for external tools."""
    bundle_dir = integrations_dir(root)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    project_root = Path(__file__).resolve().parent.parent
    api_url = os.getenv("BOOKRAG_API_URL", f"http://127.0.0.1:{os.getenv('BOOKRAG_API_PORT', '8000')}")
    skill_text = f"""# ChapterKey Workspace Skill

Use this ChapterKey workspace as the retrieval backend for books instead of loading entire books directly into the coding agent.

## Workspace

- Workspace root: `{root}`
- Input folder: `{config["input_dir"]}`
- Output folder: `{config["output_dir"]}`
- Default library name: `{config.get("library_name", "Default Library")}`

## Agent Workflow

1. Use the ChapterKey MCP server or REST API instead of reading raw vector files.
2. Call `list_libraries` and `list_books` first.
3. For spoiler-safe reading, prefer `query_context` with:
   - `context_mode="no_spoiler"`
   - `active_book_id=<current book id>`
   - `active_chapter_index=<current chapter index>`
4. For full-book or full-series analysis, use `spoiler_mode="full_context"` or `through_series_boundary`.
5. When books in a series are not linked yet, call `suggest_series` and then confirm or adjust the order before connecting them.

## CLI Quick Reference

- `bookrag init` — Interactive first-run wizard (Ollama, OpenRouter, Custom with NVIDIA NIM/Mistral presets)
- `bookrag setup` — Initialize workspace with input/output directories
- `bookrag list` — List pending input books
- `bookrag convert --all` — Convert all pending books to vector DB
- `bookrag local scan --library-id 1` — Index books from input folder
- `bookrag local query --library-id 1 --question "..."` — Retrieve context passages
- `bookrag local answer --library-id 1 --question "..."` — Get LLM answer with citations
- `bookrag update` — Update ChapterKey (git/pip/dpkg depending on install mode)

## Supported Providers

- **Ollama** — Local, free, private. Default model: `nomic-embed-text`
- **OpenRouter** — Cloud, 200+ models. Default model: `openai/text-embedding-3-small`
- **NVIDIA NIM** — Cloud, free tier at build.nvidia.com. Model: `nvidia/nv-embedqa-e5-v5`
- **Mistral** — Cloud. Model: `mistral-embed`
- **Custom** — Any OpenAI-compatible endpoint (LiteLLM, vLLM, LocalAI, etc.)

## Series Assistant Guidance

When titles or filenames contain volume markers like `Vol 01`, `Book 2`, or `Part 3`, use `suggest_series` first.
If the suggestion is ambiguous, ask the user for confirmation instead of guessing.

## Spoiler-Safe Retrieval Modes

- `full_context` — Search everything indexed
- `book_only` — Restrict to one book
- `through_chapter` — Only use content up to the current chapter
- `through_series_boundary` — Only use content up to the current point in a series

## Installation Notes

- Start the ChapterKey API if the agent will talk through MCP.
- The MCP server entrypoint is `{project_root / "server.py"}`.
- The API base URL is currently `{api_url}`.
"""
    (bundle_dir / "BOOKRAG_SKILL.md").write_text(skill_text)

    mcp_command = "bookrag-mcp" if Path("/usr/bin/bookrag-mcp").exists() else str(sys.executable)
    mcp_args = [] if Path("/usr/bin/bookrag-mcp").exists() else [str(project_root / "server.py")]

    claude_config = {
        "mcpServers": {
            "bookrag": {
                "command": mcp_command,
                "args": mcp_args,
                "env": {
                    "BOOKRAG_API_URL": api_url,
                    "BOOKRAG_API_TOKEN": "paste-your-bookrag-api-token-here",
                },
            }
        }
    }
    (bundle_dir / "claude-code.mcp.json").write_text(json.dumps(claude_config, indent=2))
    (bundle_dir / "opencode.mcp.json").write_text(json.dumps(claude_config, indent=2))

    install_text = f"""# ChapterKey Agent Integrations

Generated for workspace: `{root}`

## Files

- `BOOKRAG_SKILL.md`: prompt/skill instructions for coding agents
- `claude-code.mcp.json`: MCP snippet for Claude Code
- `opencode.mcp.json`: MCP snippet for OpenCode

## Quick Setup

### OpenCode

Copy the contents of `opencode.mcp.json` into your OpenCode MCP configuration:

```bash
cat opencode.mcp.json
```

Then add it to your `~/.config/opencode/config.json` or project-level `.opencode.json`.

### Claude Code

Copy the contents of `claude-code.mcp.json` into your Claude Code MCP configuration:

```bash
claude mcp add bookrag -- bookrag-mcp
```

Or manually merge the JSON into `~/.claude/claude_desktop_config.json`.

### Other MCP Clients

Any client that supports MCP stdio can reuse the same command:
- If installed via deb: `bookrag-mcp`
- If running from source: `python {project_root / "server.py"}`

Set environment variables:
- `BOOKRAG_API_URL` — REST API URL (default: http://127.0.0.1:8000)
- `BOOKRAG_API_TOKEN` — Your API token

## REST API Endpoints

If the client only supports REST:

- `GET /health` — Health check
- `GET /libraries` — List libraries
- `GET /libraries/{{id}}/books` — List books
- `GET /providers` — List providers
- `POST /query/context` — Retrieve context with spoiler controls
- `POST /chat/answer` — Get LLM answer with citations
- `POST /series` — Create series
- `POST /series/{{id}}/books/reorder` — Reorder series books

## Start the API

```bash
# If installed via deb:
bookrag-api

# If running from source:
python {project_root / "app_server.py"}
```

The API is designed so an external agent can inspect books, propose series ordering, and then submit the final series linkage.
"""
    (bundle_dir / "INSTALL_AGENTS.md").write_text(install_text)
    return bundle_dir


def _output_helper_python() -> str:
    return f"""#!{sys.executable}
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

manifest_path = Path(__file__).resolve().parent / ".bookrag-output.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text())
    source_root = manifest.get("source_root")
    if source_root and source_root not in sys.path:
        sys.path.insert(0, source_root)

from bookrag.workspace import load_output_bundle, workspace_bundle_action


def _print_json(data):
    print(json.dumps(data, indent=2))


def main() -> None:
    manifest = load_output_bundle(Path(__file__).resolve().parent)
    parser = argparse.ArgumentParser(prog="bookrag_output_api", description="Direct helper for a specific ChapterKey output folder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")
    subparsers.add_parser("list-input")
    subparsers.add_parser("list-books")
    subparsers.add_parser("list-series")
    subparsers.add_parser("suggest-series")

    convert = subparsers.add_parser("convert")
    convert.add_argument("index", nargs="?", type=int)
    convert.add_argument("--all", action="store_true")
    convert.add_argument("--delete-original", choices=["yes", "no"])

    query = subparsers.add_parser("query-context")
    query.add_argument("--question", required=True)
    query.add_argument("--top-k", type=int)
    query.add_argument("--spoiler-mode", default="full_context")
    query.add_argument("--context-mode")
    query.add_argument("--active-book-id", type=int)
    query.add_argument("--active-chapter-index", type=int)

    answer = subparsers.add_parser("answer-question")
    answer.add_argument("--question", required=True)
    answer.add_argument("--chat-provider-id", type=int, required=True)
    answer.add_argument("--chat-model", required=True)
    answer.add_argument("--top-k", type=int)
    answer.add_argument("--spoiler-mode", default="full_context")
    answer.add_argument("--context-mode")
    answer.add_argument("--active-book-id", type=int)
    answer.add_argument("--active-chapter-index", type=int)
    answer.add_argument("--temperature", type=float, default=0.2)
    answer.add_argument("--max-tokens", type=int, default=1200)

    create_series = subparsers.add_parser("create-series")
    create_series.add_argument("name")

    connect_series = subparsers.add_parser("connect-series")
    connect_series.add_argument("series")
    connect_series.add_argument("book_ids")

    args = parser.parse_args()
    if args.command == "status":
        _print_json(workspace_bundle_action(manifest, "status"))
        return
    if args.command == "list-input":
        _print_json(workspace_bundle_action(manifest, "list_input"))
        return
    if args.command == "list-books":
        _print_json(workspace_bundle_action(manifest, "list_books"))
        return
    if args.command == "list-series":
        _print_json(workspace_bundle_action(manifest, "list_series"))
        return
    if args.command == "suggest-series":
        _print_json(workspace_bundle_action(manifest, "suggest_series"))
        return
    if args.command == "convert":
        delete_override = None
        if args.delete_original == "yes":
            delete_override = True
        elif args.delete_original == "no":
            delete_override = False
        _print_json(workspace_bundle_action(manifest, "convert", index=args.index, convert_all=args.all, delete_original=delete_override))
        return
    if args.command == "query-context":
        _print_json(workspace_bundle_action(manifest, "query_context", question=args.question, top_k=args.top_k, spoiler_mode=args.spoiler_mode, context_mode=args.context_mode, active_book_id=args.active_book_id, active_chapter_index=args.active_chapter_index))
        return
    if args.command == "answer-question":
        _print_json(workspace_bundle_action(manifest, "answer_question", question=args.question, chat_provider_id=args.chat_provider_id, chat_model=args.chat_model, top_k=args.top_k, spoiler_mode=args.spoiler_mode, context_mode=args.context_mode, active_book_id=args.active_book_id, active_chapter_index=args.active_chapter_index, temperature=args.temperature, max_tokens=args.max_tokens))
        return
    if args.command == "create-series":
        _print_json(workspace_bundle_action(manifest, "create_series", name=args.name))
        return
    if args.command == "connect-series":
        _print_json(workspace_bundle_action(manifest, "connect_series", series=args.series, book_ids=args.book_ids))
        return


if __name__ == "__main__":
    main()
"""


def _output_wrapper_contents(default_command: str | None = None) -> str:
    command = f" {default_command}" if default_command else ""
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
        f"exec \"$SCRIPT_DIR/bookrag_output_api.py\"{command} \"$@\"\n"
    )


def write_output_bundle(root: Path, config: dict[str, Any], output_dir: Path) -> Path:
    """Generate a Python helper and shell wrappers inside the output folder."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "workspace_root": str(root),
        "workspace_config": str(config_path(root)),
        "output_dir": str(output_dir),
        "input_dir": str(config["input_dir"]),
        "source_root": str(Path(__file__).resolve().parent.parent),
        "python_executable": sys.executable,
        "library_name": config.get("library_name", "Default Library"),
        "input_is_managed_default": bool(config.get("input_is_managed_default", False)),
        "delete_after_success": bool(config.get("delete_after_success", False)),
    }
    output_manifest_path(output_dir).write_text(json.dumps(manifest, indent=2, sort_keys=True))

    helper_path = output_dir / "bookrag_output_api.py"
    helper_path.write_text(_output_helper_python())
    general_wrapper = output_dir / "bookrag-output"
    query_wrapper = output_dir / "bookrag-output-query"
    admin_wrapper = output_dir / "bookrag-output-admin"
    general_wrapper.write_text(_output_wrapper_contents())
    query_wrapper.write_text(_output_wrapper_contents("query-context"))
    admin_wrapper.write_text(_output_wrapper_contents("status"))
    for path in (helper_path, general_wrapper, query_wrapper, admin_wrapper):
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return output_dir


def build_runtime_env(root: Path, config: dict[str, Any], secrets_data: dict[str, Any], output_override: Path | None = None) -> dict[str, str]:
    """Build environment overrides for a workspace service."""
    output_dir = (output_override or Path(config["output_dir"])).expanduser().resolve()
    input_dir = Path(config["input_dir"]).expanduser().resolve()
    app_secret = secrets_data.get("app_secret") or secrets.token_hex(32)
    return {
        "BOOKRAG_APP_SECRET": app_secret,
        "BOOKRAG_DEFAULT_LIBRARY_NAME": config.get("library_name", "Default Library"),
        "BOOKRAG_INPUT_DIR": str(input_dir),
        "BOOKRAG_OUTPUT_DIR": str(output_dir),
        "BOOKRAG_DATA_DIR": str(output_dir),
        "BOOKRAG_UPLOADS_DIR": str(output_dir / "uploads"),
        "BOOKRAG_MANAGED_BOOKS_DIR": str(output_dir / "managed_books"),
        "BOOKRAG_VECTOR_DB_DIR": str(output_dir / "chroma_db"),
        "BOOKRAG_SQLITE_PATH": str(output_dir / "bookrag.sqlite3"),
        "BOOKRAG_WATCH_INTERVAL_SEC": str(config.get("watch_interval_sec", 10)),
        "BOOKRAG_MIN_FILE_AGE_SEC": str(config.get("min_file_age_sec", 30)),
        "BOOKRAG_AUTO_DELETE_SOURCE": "true" if config.get("auto_delete_source", True) else "false",
    }


@contextmanager
def patched_environ(overrides: dict[str, str]) -> Iterator[None]:
    """Temporarily apply environment overrides."""
    old_values: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        yield
    finally:
        for key, old_value in old_values.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def configure_workspace_providers(
    service: BookRAGService,
    config: dict[str, Any],
    secrets_data: dict[str, Any],
) -> dict[str, Any]:
    """Upsert embedding/chat providers for this workspace and return resolved ids."""
    embedding = config["embedding"]
    embedding_provider = service.create_provider(
        name=embedding.get("name", "Workspace Embeddings"),
        provider_type=embedding["provider_type"],
        api_key=secrets_data.get("embedding_api_key", ""),
        base_url=embedding.get("base_url"),
        default_embedding_model=embedding["model"],
    )
    result: dict[str, Any] = {
        "embedding_provider_id": int(embedding_provider["id"]),
        "embedding_model": embedding["model"],
        "chat_provider_id": None,
        "chat_model": None,
    }
    chat = config.get("chat")
    if chat and chat.get("enabled"):
        chat_provider = service.create_provider(
            name=chat.get("name", "Workspace Chat"),
            provider_type=chat["provider_type"],
            api_key=secrets_data.get("chat_api_key", ""),
            base_url=chat.get("base_url"),
            default_chat_model=chat["model"],
        )
        result["chat_provider_id"] = int(chat_provider["id"])
        result["chat_model"] = chat["model"]
    return result


def workspace_service(root: Path, config: dict[str, Any], secrets_data: dict[str, Any], output_override: Path | None = None) -> tuple[BookRAGService, dict[str, Any], Path]:
    """Create a service and configure workspace providers."""
    overrides = build_runtime_env(root, config, secrets_data, output_override=output_override)
    secrets_data.setdefault("app_secret", overrides["BOOKRAG_APP_SECRET"])
    with patched_environ(overrides):
        service = BookRAGService()
        provider_info = configure_workspace_providers(service, config, secrets_data)
    return service, provider_info, Path(overrides["BOOKRAG_OUTPUT_DIR"])


def load_output_bundle(output_dir: Path) -> dict[str, Any]:
    """Load output helper manifest from an output folder."""
    manifest_file = output_manifest_path(output_dir)
    if not manifest_file.exists():
        raise ValueError(f"Output helper manifest is missing: {manifest_file}")
    manifest = json.loads(manifest_file.read_text())
    workspace_root = Path(manifest["workspace_root"]).expanduser().resolve()
    root, config, secrets_data = load_workspace(workspace_root)
    return {"root": root, "config": config, "secrets_data": secrets_data, "manifest": manifest}


def workspace_runtime(bundle: dict[str, Any]) -> tuple[BookRAGService, dict[str, Any], Path, int]:
    """Resolve service, provider info, output dir, and default library id for a bundle."""
    manifest = bundle["manifest"]
    service, provider_info, resolved_output = workspace_service(
        bundle["root"],
        bundle["config"],
        bundle["secrets_data"],
        output_override=Path(manifest["output_dir"]),
    )
    library = service.ensure_default_library()
    return service, provider_info, resolved_output, int(library["id"])


def workspace_input_listing(service: BookRAGService, library_id: int, input_dir: Path) -> list[dict[str, Any]]:
    """List input files with duplicate classification."""
    files = []
    if not input_dir.exists():
        return files
    supported = {".epub", ".pdf"}
    skipped = {".tmp", ".part", ".crdownload"}
    for path in sorted(input_dir.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in skipped or path.suffix.lower() not in supported:
            continue
        item = {"name": path.name, "path": str(path), "state": "pending", "book": None}
        try:
            fingerprint = service.file_fingerprint(path)
            book = service.find_verified_book_by_fingerprint(library_id, fingerprint)
            if book:
                item["state"] = "indexed_duplicate"
                item["book"] = {
                    "id": int(book["id"]),
                    "title": book["title"],
                    "series_name": book.get("series_name"),
                    "series_order": book.get("series_order"),
                }
        except Exception:
            pass
        files.append(item)
    return files


def workspace_status_data(bundle: dict[str, Any]) -> dict[str, Any]:
    """Return workspace status data for CLI or generated helpers."""
    service, _, resolved_output, library_id = workspace_runtime(bundle)
    config = bundle["config"]
    books = service.list_books(library_id)
    jobs = service.list_jobs()
    input_dir = Path(config["input_dir"]).expanduser().resolve()
    files = workspace_input_listing(service, library_id, input_dir)
    delete_policy = "auto-delete after verified conversion" if config.get("input_is_managed_default", False) else (
        "ask after each verified conversion" if config.get("delete_after_success", False) else "keep originals"
    )
    return {
        "workspace_root": str(bundle["root"]),
        "input_dir": str(input_dir),
        "output_dir": str(resolved_output),
        "input_mode": "managed default" if config.get("input_is_managed_default", False) else "custom",
        "delete_policy": delete_policy,
        "pending_input_files": len(files),
        "indexed_books": len([book for book in books if book["ingest_status"] == "ready"]),
        "failed_books": len([book for book in books if book["ingest_status"] == "failed"]),
        "series_count": len(service.list_series(library_id)),
        "jobs_tracked": len(jobs),
    }


def workspace_convert_books(bundle: dict[str, Any], *, index: int | None = None, convert_all: bool = False, delete_original: bool | None = None) -> dict[str, Any]:
    """Convert one or all pending files for a workspace bundle."""
    if not convert_all and index is None:
        raise ValueError("Provide an index or use convert_all=True")
    service, provider_info, resolved_output, library_id = workspace_runtime(bundle)
    input_dir = Path(bundle["config"]["input_dir"]).expanduser().resolve()
    files = workspace_input_listing(service, library_id, input_dir)
    if not files:
        return {"results": [], "output_dir": str(resolved_output)}
    if index is not None and (index < 1 or index > len(files)):
        raise ValueError(f"Index must be between 1 and {len(files)}")
    selected = files if convert_all else [files[index - 1]]
    results: list[dict[str, Any]] = []
    for item in selected:
        path = Path(item["path"])
        should_delete = delete_original
        if should_delete is None:
            should_delete = bool(bundle["config"].get("input_is_managed_default", False))
        result = service.ingest_file_from_path(
            path,
            library_id=library_id,
            embedding_provider_id=int(provider_info["embedding_provider_id"]),
            embedding_model=str(provider_info["embedding_model"]),
            delete_source=should_delete,
        )
        results.append(result)
    write_output_bundle(bundle["root"], bundle["config"], resolved_output)
    return {"results": results, "output_dir": str(resolved_output)}


def workspace_bundle_action(bundle: dict[str, Any], action: str, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """Dispatch output-bundle actions."""
    service, _, resolved_output, library_id = workspace_runtime(bundle)
    if action == "status":
        return workspace_status_data(bundle)
    if action == "list_input":
        return workspace_input_listing(service, library_id, Path(bundle["config"]["input_dir"]).expanduser().resolve())
    if action == "list_books":
        return service.list_books(library_id)
    if action == "list_series":
        return service.list_series(library_id)
    if action == "suggest_series":
        return service.suggest_series_groups(library_id)
    if action == "convert":
        return workspace_convert_books(bundle, index=kwargs.get("index"), convert_all=kwargs.get("convert_all", False), delete_original=kwargs.get("delete_original"))
    if action == "query_context":
        return service.query_context(
            library_id=library_id,
            question=kwargs["question"],
            top_k=kwargs.get("top_k"),
            spoiler_mode=kwargs.get("spoiler_mode", "full_context"),
            context_mode=kwargs.get("context_mode"),
            active_book_id=kwargs.get("active_book_id"),
            active_chapter_index=kwargs.get("active_chapter_index"),
        )
    if action == "answer_question":
        return service.answer_question(
            library_id=library_id,
            question=kwargs["question"],
            chat_provider_id=kwargs["chat_provider_id"],
            chat_model=kwargs["chat_model"],
            top_k=kwargs.get("top_k"),
            spoiler_mode=kwargs.get("spoiler_mode", "full_context"),
            context_mode=kwargs.get("context_mode"),
            active_book_id=kwargs.get("active_book_id"),
            active_chapter_index=kwargs.get("active_chapter_index"),
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 1200),
        )
    if action == "create_series":
        return service.create_series(library_id, kwargs["name"])
    if action == "connect_series":
        series_value = str(kwargs["series"])
        if series_value.isdigit():
            series_id = int(series_value)
        else:
            series_id = next((int(item["id"]) for item in service.list_series(library_id) if item["name"] == series_value), None)
            if series_id is None:
                raise ValueError(f"Series not found: {series_value}")
        payload = [
            {"book_id": int(book_id.strip()), "sort_order": index}
            for index, book_id in enumerate(str(kwargs["book_ids"]).split(","), start=1)
            if book_id.strip()
        ]
        return service.reorder_series_books(series_id, payload)
    raise ValueError(f"Unknown bundle action: {action}")
