"""Workspace configuration helpers for the simple BookRAG CLI."""

from __future__ import annotations

import json
import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from bookrag.services import BookRAGService


WORKSPACE_DIRNAME = ".bookrag"
CONFIG_FILENAME = "config.json"
SECRETS_FILENAME = "secrets.json"


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


def load_workspace(root: Path | None = None) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Load workspace config and secrets."""
    found = root or find_workspace_root()
    if not found:
        raise ValueError("No BookRAG workspace found. Run `bookrag setup` in this directory first.")
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
    skill_text = f"""# BookRAG Workspace Skill

Use this BookRAG workspace as the retrieval backend for books instead of loading entire books directly into the coding agent.

## Workspace

- Workspace root: `{root}`
- Input folder: `{config["input_dir"]}`
- Output folder: `{config["output_dir"]}`
- Default library name: `{config.get("library_name", "Default Library")}`

## Agent Workflow

1. Use the BookRAG MCP server or REST API instead of reading raw vector files.
2. Call `list_libraries` and `list_books` first.
3. For spoiler-safe reading, prefer `query_context` with:
   - `context_mode=\"no_spoiler\"`
   - `active_book_id=<current book id>`
   - `active_chapter_index=<current chapter index>`
4. For full-book or full-series analysis, use `spoiler_mode=\"full_context\"` or `through_series_boundary`.
5. When books in a series are not linked yet, call `suggest_series` and then confirm or adjust the order before connecting them.

## Series Assistant Guidance

When titles or filenames contain volume markers like `Vol 01`, `Book 2`, or `Part 3`, use `suggest_series` first.
If the suggestion is ambiguous, ask the user for confirmation instead of guessing.

## Installation Notes

- Start the BookRAG API if the agent will talk through MCP.
- The MCP server entrypoint is `{project_root / "server.py"}`.
- The API base URL is currently `{api_url}`.
"""
    (bundle_dir / "BOOKRAG_SKILL.md").write_text(skill_text)

    claude_config = {
        "mcpServers": {
            "bookrag": {
                "command": "python",
                "args": [str(project_root / "server.py")],
                "env": {
                    "BOOKRAG_API_URL": api_url,
                    "BOOKRAG_API_TOKEN": "paste-your-bookrag-api-token-here",
                },
            }
        }
    }
    (bundle_dir / "claude-code.mcp.json").write_text(json.dumps(claude_config, indent=2))
    (bundle_dir / "opencode.mcp.json").write_text(json.dumps(claude_config, indent=2))

    install_text = f"""# BookRAG Agent Integrations

Generated for workspace: `{root}`

## Files

- `BOOKRAG_SKILL.md`: prompt/skill instructions for coding agents
- `claude-code.mcp.json`: MCP snippet for Claude Code style clients
- `opencode.mcp.json`: MCP snippet for OpenCode style clients

## Recommended Setup

1. Start the API:
   `python {project_root / "app_server.py"}`
2. Create an API token by logging into the web UI or using the REST login endpoint.
3. Merge one of the MCP JSON snippets into your tool config.
4. Copy the contents of `BOOKRAG_SKILL.md` into your agent skill or project instructions.

## Factory Droid / Custom Clients

Any client that supports MCP stdio can reuse the same `server.py` command.
If the client only supports REST, use these endpoints:

- `GET /libraries`
- `GET /libraries/{{id}}/books`
- `GET /libraries/{{id}}/series/suggestions`
- `POST /query/context`
- `POST /chat/answer`
- `POST /series`
- `POST /series/{{id}}/books/reorder`

The API is designed so an external agent can inspect books, propose series ordering, and then submit the final series linkage.
"""
    (bundle_dir / "INSTALL_AGENTS.md").write_text(install_text)
    return bundle_dir


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
