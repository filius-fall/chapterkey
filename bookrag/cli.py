"""CLI wrapper for REST and local BookRAG workflows."""

from __future__ import annotations

import argparse
import getpass
import json
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any

import requests

from bookrag.folder_ingest import FolderIngestor, LocalIngestConfig, SKIP_SUFFIXES, SUPPORTED_EXTENSIONS
from bookrag.services import BookRAGService
from bookrag.settings import AppSettings
from bookrag.workspace import (
    default_input_dir,
    default_output_dir,
    default_workspace_root,
    ensure_workspace_dirs,
    find_workspace_root,
    load_workspace,
    save_workspace,
    write_integration_bundle,
    workspace_dir,
    workspace_service,
)


CONFIG_PATH = Path.home() / ".config" / "bookrag-cli.json"


def load_config() -> dict[str, Any]:
    """Load CLI config."""
    if not CONFIG_PATH.exists():
        return {"base_url": "http://127.0.0.1:8000", "token": None}
    return json.loads(CONFIG_PATH.read_text())


def save_config(config: dict[str, Any]) -> None:
    """Save CLI config."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def request(method: str, path: str, *, json_body: dict[str, Any] | None = None, files: dict[str, Any] | None = None) -> Any:
    """Issue an authenticated request."""
    config = load_config()
    headers = {}
    if config.get("token"):
        headers["Authorization"] = f"Bearer {config['token']}"
    response = requests.request(
        method,
        config["base_url"].rstrip("/") + path,
        json=json_body,
        files=files,
        headers=headers,
        timeout=300,
    )
    response.raise_for_status()
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    return response.text


def print_json(data: Any) -> None:
    """Pretty-print JSON output."""
    print(json.dumps(data, indent=2))


def _prompt(prompt: str, default: str | None = None, secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    message = f"{prompt}{suffix}: "
    if secret:
        value = getpass.getpass(message)
    else:
        value = input(message)
    value = value.strip()
    return value or (default or "")


def _prompt_yes_no(prompt: str, default: bool = True) -> bool:
    default_label = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{default_label}]: ").strip().lower()
    if not value:
        return default
    if value in {"y", "yes"}:
        return True
    if value in {"n", "no"}:
        return False
    raise ValueError("Please answer yes or no")


def _validate_directory_candidate(path: Path, *, create_if_missing: bool = True) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"Path is not a directory: {resolved}")
    parent = resolved if resolved.exists() else resolved.parent
    if not parent.exists():
        if not create_if_missing:
            raise ValueError(f"Parent directory does not exist: {parent}")
        parent.mkdir(parents=True, exist_ok=True)
    if create_if_missing:
        resolved.mkdir(parents=True, exist_ok=True)
    test_file = resolved / ".bookrag-write-test"
    try:
        test_file.write_text("ok")
        test_file.unlink()
    except OSError as exc:
        raise ValueError(f"Directory is not writable: {resolved}") from exc
    return resolved


def _prompt_directory(prompt: str, default: Path) -> Path:
    while True:
        candidate = Path(_prompt(prompt, str(default)))
        try:
            return _validate_directory_candidate(candidate)
        except ValueError as exc:
            print(exc)


def _convert_delete_source_choice(config: dict[str, Any], path: Path) -> bool:
    if not config.get("delete_after_success", False):
        return False
    if config.get("input_is_managed_default", False):
        return True
    while True:
        try:
            return _prompt_yes_no(f"Delete original after verified conversion: {path.name}", default=False)
        except ValueError as exc:
            print(exc)


def _headers_for_validation(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key and api_key != "ollama":
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _detect_custom_provider_type(base_url: str, model: str) -> str:
    lowered = f"{base_url} {model}".lower()
    if "nvidia" in lowered or model.startswith("nvidia/"):
        return "nvidia_nim"
    return "openai_compatible"


def _validate_embedding_provider(provider_type: str, base_url: str, api_key: str, model: str) -> tuple[bool, str]:
    try:
        payload: dict[str, Any] = {"model": model, "input": ["validation ping"], "encoding_format": "float"}
        if provider_type == "nvidia_nim":
            payload["input_type"] = "passage"
        response = requests.post(
            f"{base_url.rstrip('/')}/embeddings",
            headers=_headers_for_validation(api_key),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        if "data" not in data:
            return False, f"Unexpected response: {data}"
        return True, "Validation succeeded."
    except Exception as exc:
        return False, str(exc)


def _workspace_pending_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    files = []
    for path in sorted(input_dir.iterdir()):
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() not in SKIP_SUFFIXES
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ):
            files.append(path)
    return files


def _workspace_file_statuses(service: BookRAGService, library_id: int, input_dir: Path) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for path in _workspace_pending_files(input_dir):
        status = {
            "path": path,
            "state": "pending",
            "book": None,
        }
        try:
            fingerprint = service.file_fingerprint(path)
            book = service.find_verified_book_by_fingerprint(library_id, fingerprint)
            if book:
                status["state"] = "indexed_duplicate"
                status["book"] = book
        except Exception:
            status["state"] = "pending"
        statuses.append(status)
    return statuses


def _print_pending_files(files: list[dict[str, Any]], input_dir: Path) -> None:
    print(f"Input directory: {input_dir}")
    if not files:
        print("No pending EPUB/PDF files found.")
        return
    for index, item in enumerate(files, start=1):
        path = Path(item["path"])
        if item["state"] == "indexed_duplicate" and item.get("book"):
            book = item["book"]
            print(f"{index}. {path.name} [indexed duplicate -> book_id={book['id']}, title={book['title']}]")
        else:
            print(f"{index}. {path.name} [pending]")


def _resolve_series_id(service: BookRAGService, library_id: int, value: str) -> int:
    if value.isdigit():
        return int(value)
    for series in service.list_series(library_id):
        if series["name"] == value:
            return int(series["id"])
    raise ValueError(f"Series not found: {value}")


def _run_setup(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="bookrag setup", description="Initialize a BookRAG workspace")
    parser.parse_args(argv)

    suggested_root = default_workspace_root()
    print(f"Default BookRAG workspace: {suggested_root}")
    use_default_root = _prompt_yes_no("Use the default workspace in Documents?", default=True)
    root = _prompt_directory("Workspace root", suggested_root if use_default_root else Path.cwd())
    ensure_workspace_dirs(root)
    use_default_io = _prompt_yes_no("Use default input/output folders inside the workspace root?", default=True)
    default_in = default_input_dir(root)
    default_out = default_output_dir(root)
    print(f"Setting up BookRAG workspace in {root}")
    if use_default_io:
        input_dir = _validate_directory_candidate(default_in)
        output_dir = _validate_directory_candidate(default_out)
        input_is_managed_default = True
        delete_after_success = True
    else:
        input_dir = _prompt_directory("Custom input directory", default_in)
        output_dir = _prompt_directory("Custom output directory", default_out)
        input_is_managed_default = False
        while True:
            try:
                delete_after_success = _prompt_yes_no("Delete original files after verified conversion?", default=False)
                break
            except ValueError as exc:
                print(exc)
    library_name = _prompt("Default library name", "Default Library")
    print("Choose embedding provider:")
    print("1. Ollama")
    print("2. OpenRouter")
    print("3. Custom endpoint")
    provider_choice = _prompt("Provider choice", "1")

    embedding: dict[str, Any]
    secrets_data: dict[str, Any] = {"app_secret": secrets.token_hex(32)}
    if provider_choice == "1":
        base_url = _prompt("Ollama base URL", "http://127.0.0.1:11434/v1")
        model = _prompt("Ollama embedding model", "embeddinggemma")
        if shutil.which("ollama") is None:
            print("Ollama is not installed. Install it from https://ollama.com and run `ollama pull embeddinggemma`.")
        ok, message = _validate_embedding_provider("ollama", base_url, "ollama", model)
        print(f"Ollama validation: {message}")
        embedding = {
            "name": "Workspace Embeddings",
            "provider_type": "ollama",
            "base_url": base_url,
            "model": model,
        }
        secrets_data["embedding_api_key"] = "ollama"
    elif provider_choice == "2":
        base_url = _prompt("OpenRouter base URL", "https://openrouter.ai/api/v1")
        model = _prompt("OpenRouter embedding model", "qwen/qwen3-embedding-8b")
        api_key = _prompt("OpenRouter API key", secret=True)
        ok, message = _validate_embedding_provider("openrouter", base_url, api_key, model)
        print(f"OpenRouter validation: {message}")
        embedding = {
            "name": "Workspace Embeddings",
            "provider_type": "openrouter",
            "base_url": base_url,
            "model": model,
        }
        secrets_data["embedding_api_key"] = api_key
    else:
        base_url = _prompt("Custom endpoint base URL")
        model = _prompt("Custom embedding model")
        api_key = _prompt("Custom API key (leave blank if none)", secret=True)
        provider_type = _detect_custom_provider_type(base_url, model)
        ok, message = _validate_embedding_provider(provider_type, base_url, api_key, model)
        print(f"Custom endpoint validation: {message}")
        embedding = {
            "name": "Workspace Embeddings",
            "provider_type": provider_type,
            "base_url": base_url,
            "model": model,
        }
        secrets_data["embedding_api_key"] = api_key

    enable_chat = _prompt("Also configure local Ollama chat for workspace answers? (y/N)", "n").lower() == "y"
    chat: dict[str, Any] = {"enabled": False}
    if enable_chat:
        base_url = _prompt("Ollama chat base URL", "http://127.0.0.1:11434/v1")
        model = _prompt("Ollama chat model", "qwen3:4b")
        if shutil.which("ollama") is None:
            print("Ollama is not installed. Install it from https://ollama.com and run the model you want locally.")
        else:
            ok, message = _validate_embedding_provider("ollama", base_url, "ollama", embedding["model"])
            print(f"Ollama server check: {message}")
        chat = {
            "enabled": True,
            "name": "Workspace Chat",
            "provider_type": "ollama",
            "base_url": base_url,
            "model": model,
        }
        secrets_data["chat_api_key"] = "ollama"

    config = {
        "workspace_root": str(root),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "library_name": library_name,
        "watch_interval_sec": 10,
        "min_file_age_sec": 30,
        "auto_delete_source": delete_after_success,
        "delete_after_success": delete_after_success,
        "input_is_managed_default": input_is_managed_default,
        "embedding": embedding,
        "chat": chat,
    }
    save_workspace(root, config, secrets_data)
    bundle_dir = write_integration_bundle(root, config)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Workspace saved in {workspace_dir(root)}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    if input_is_managed_default:
        print("Delete policy: verified conversions auto-delete files from the managed default input folder.")
    elif delete_after_success:
        print("Delete policy: custom input keeps originals unless you confirm deletion after each verified conversion.")
    else:
        print("Delete policy: originals in the custom input folder are never deleted automatically.")
    print(f"Agent integration bundle: {bundle_dir}")


def _run_list(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="bookrag list", description="List pending input books in the current workspace")
    parser.parse_args(argv)
    root, config, secrets_data = load_workspace()
    input_dir = Path(config["input_dir"]).expanduser().resolve()
    service, _, _ = workspace_service(root, config, secrets_data)
    library = service.ensure_default_library()
    _print_pending_files(_workspace_file_statuses(service, int(library["id"]), input_dir), input_dir)


def _run_status(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="bookrag status", description="Show workspace status")
    parser.parse_args(argv)
    root, config, secrets_data = load_workspace()
    service, _, output_dir = workspace_service(root, config, secrets_data)
    library = service.ensure_default_library()
    books = service.list_books(int(library["id"]))
    jobs = service.list_jobs()
    pending = _workspace_pending_files(Path(config["input_dir"]).expanduser().resolve())
    delete_policy = "auto-delete after verified conversion" if config.get("input_is_managed_default", False) else (
        "ask after each verified conversion" if config.get("delete_after_success", False) else "keep originals"
    )
    print(f"Workspace: {root}")
    print(f"Input: {config['input_dir']}")
    print(f"Output: {output_dir}")
    print(f"Input mode: {'managed default' if config.get('input_is_managed_default', False) else 'custom'}")
    print(f"Delete policy: {delete_policy}")
    print(f"Pending input files: {len(pending)}")
    print(f"Indexed books: {len([book for book in books if book['ingest_status'] == 'ready'])}")
    print(f"Failed books: {len([book for book in books if book['ingest_status'] == 'failed'])}")
    print(f"Series: {len(service.list_series(int(library['id'])))}")
    print(f"Jobs tracked: {len(jobs)}")


def _run_convert(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="bookrag convert", description="Convert workspace input books into a vector DB")
    parser.add_argument("index", nargs="?", type=int, help="Numeric index from `bookrag list`")
    parser.add_argument("--all", action="store_true", help="Convert every pending file")
    parser.add_argument("--output", help="Override output directory for this conversion run")
    args = parser.parse_args(argv)
    if not args.all and args.index is None:
        raise ValueError("Provide an index from `bookrag list` or use --all")
    root, config, secrets_data = load_workspace()
    input_dir = Path(config["input_dir"]).expanduser().resolve()
    pending = _workspace_pending_files(input_dir)
    if not pending:
        print("No pending EPUB/PDF files found.")
        return
    if args.index is not None and (args.index < 1 or args.index > len(pending)):
        raise ValueError(f"Index must be between 1 and {len(pending)}")
    selected = pending if args.all else [pending[args.index - 1]]
    output_override = Path(args.output).expanduser().resolve() if args.output else None
    service, provider_info, resolved_output = workspace_service(root, config, secrets_data, output_override=output_override)
    library = service.ensure_default_library()
    results: list[dict[str, Any]] = []
    for path in selected:
        delete_source = _convert_delete_source_choice(config, path)
        result = service.ingest_file_from_path(
            path,
            library_id=int(library["id"]),
            embedding_provider_id=int(provider_info["embedding_provider_id"]),
            embedding_model=str(provider_info["embedding_model"]),
            delete_source=delete_source,
        )
        results.append(result)
    for item in results:
        book = item.get("book", {})
        if item.get("duplicate"):
            print(f"Skipped duplicate: {book.get('title') or book.get('file_name')}")
        else:
            print(f"Converted: {book.get('title')} (book_id={book.get('id')}, job_id={item.get('job_id')})")
    print(f"Output stored in: {resolved_output}")


def _run_series(argv: list[str]) -> bool:
    if find_workspace_root() is None or "--library-id" in argv:
        return False
    parser = argparse.ArgumentParser(prog="bookrag series", description="Manage connected books in the current workspace")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list")
    create = subparsers.add_parser("create")
    create.add_argument("name")
    subparsers.add_parser("suggest")
    connect = subparsers.add_parser("connect")
    connect.add_argument("series", help="Series id or exact series name")
    connect.add_argument("book_ids", help="Comma-separated ordered book ids")
    books = subparsers.add_parser("books")
    args = parser.parse_args(argv)
    root, config, secrets_data = load_workspace()
    service, _, _ = workspace_service(root, config, secrets_data)
    library = service.ensure_default_library()
    library_id = int(library["id"])
    if args.action == "list":
        series = service.list_series(library_id)
        if not series:
            print("No series configured.")
            return True
        for item in series:
            print(f"{item['id']}. {item['name']} -> {[book['id'] for book in item['books']]}")
        return True
    if args.action == "create":
        created = service.create_series(library_id, args.name)
        print(f"Created series {created['id']}: {created['name']}")
        return True
    if args.action == "suggest":
        suggestions = service.suggest_series_groups(library_id)
        if not suggestions["suggestions"]:
            print("No series suggestions found.")
            return True
        for item in suggestions["suggestions"]:
            print(f"{item['series_name_guess']} [{item['confidence']}]")
            for book in item["books"]:
                marker = book["guessed_position"] if book["guessed_position"] is not None else "?"
                print(f"  {book['book_id']}. {book['title']} ({book['file_name']}) -> {marker}")
        return True
    if args.action == "books":
        books_data = service.list_books(library_id)
        if not books_data:
            print("No books indexed yet.")
            return True
        for book in books_data:
            print(f"{book['id']}. {book['title']} [{book['ingest_status']}]")
        return True
    series_id = _resolve_series_id(service, library_id, args.series)
    payload = [{"book_id": int(book_id.strip()), "sort_order": index} for index, book_id in enumerate(args.book_ids.split(","), start=1) if book_id.strip()]
    updated = service.reorder_series_books(series_id, payload)
    print(f"Connected books in series {updated['name']}: {[book['id'] for book in updated['books']]}")
    return True


def _run_simple_cli(argv: list[str]) -> bool:
    if not argv:
        return False
    command = argv[0]
    if command == "setup":
        _run_setup(argv[1:])
        return True
    if command == "list":
        _run_list(argv[1:])
        return True
    if command == "status":
        _run_status(argv[1:])
        return True
    if command == "convert":
        _run_convert(argv[1:])
        return True
    if command == "series":
        return _run_series(argv[1:])
    return False


def _local_service() -> BookRAGService:
    return BookRAGService(settings=AppSettings.load())


def _default_local_models(service: BookRAGService, args: argparse.Namespace) -> tuple[int, str, int | None, str | None]:
    defaults = service.default_provider_ids()
    embedding_provider_id = args.embedding_provider_id or defaults.get("embedding_provider")
    chat_provider_id = args.chat_provider_id or defaults.get("chat_provider")
    if embedding_provider_id is None:
        raise ValueError("No embedding provider selected. Set --embedding-provider-id or BOOKRAG_DEFAULT_EMBEDDING_PROVIDER_NAME.")
    embedding_model = args.embedding_model
    if not embedding_model:
        provider = service._provider_config(int(embedding_provider_id))
        embedding_model = provider.default_embedding_model
    if not embedding_model:
        raise ValueError("No embedding model configured. Set --embedding-model or the provider default in .env/UI.")
    chat_model = args.chat_model
    if chat_provider_id and not chat_model:
        provider = service._provider_config(int(chat_provider_id))
        chat_model = provider.default_chat_model
    return int(embedding_provider_id), embedding_model, chat_provider_id, chat_model


def _local_ingest_config(service: BookRAGService, args: argparse.Namespace) -> LocalIngestConfig:
    embedding_provider_id, embedding_model, chat_provider_id, chat_model = _default_local_models(service, args)
    ocr_provider_id = args.ocr_provider_id or service.default_provider_ids().get("ocr_provider")
    if ocr_provider_id and not args.ocr_model:
        provider = service._provider_config(int(ocr_provider_id))
        ocr_model = provider.default_ocr_model
    else:
        ocr_model = args.ocr_model
    return LocalIngestConfig(
        library_id=args.library_id,
        embedding_provider_id=embedding_provider_id,
        embedding_model=embedding_model,
        chat_provider_id=chat_provider_id,
        chat_model=chat_model,
        ocr_provider_id=ocr_provider_id,
        ocr_model=ocr_model,
        ocr_mode=args.ocr_mode,
        confirm_ocr_cost=args.confirm_ocr_cost,
        delete_source=args.delete_source,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )


def main() -> None:
    """CLI entrypoint."""
    if _run_simple_cli(sys.argv[1:]):
        return

    parser = argparse.ArgumentParser(prog="bookrag", description="BookRAG REST and local CLI")
    parser.add_argument("--base-url", help="Override API base URL for this invocation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login")
    login.add_argument("--username", required=True)
    login.add_argument("--password", required=True)

    providers = subparsers.add_parser("providers")
    providers_sub = providers.add_subparsers(dest="action", required=True)
    providers_sub.add_parser("list")
    add_provider = providers_sub.add_parser("add")
    add_provider.add_argument("--name", required=True)
    add_provider.add_argument("--type", required=True, choices=["ollama", "openrouter", "nvidia_nim", "openai_compatible", "anthropic", "google"])
    add_provider.add_argument("--api-key", required=True)
    add_provider.add_argument("--base-url")
    add_provider.add_argument("--embedding-model")
    add_provider.add_argument("--chat-model")
    add_provider.add_argument("--ocr-model")

    libraries = subparsers.add_parser("libraries")
    libraries_sub = libraries.add_subparsers(dest="action", required=True)
    libraries_sub.add_parser("list")
    create_library = libraries_sub.add_parser("create")
    create_library.add_argument("--name", required=True)
    create_library.add_argument("--description")

    books = subparsers.add_parser("books")
    books_sub = books.add_subparsers(dest="action", required=True)
    upload = books_sub.add_parser("upload")
    upload.add_argument("--library-id", type=int, required=True)
    upload.add_argument("--file", required=True)
    ingest = books_sub.add_parser("ingest")
    ingest.add_argument("--book-id", type=int, required=True)
    ingest.add_argument("--embedding-provider-id", type=int, required=True)
    ingest.add_argument("--embedding-model", required=True)
    ingest.add_argument("--ocr-provider-id", type=int)
    ingest.add_argument("--ocr-model")
    ingest.add_argument("--ocr-mode", default="disabled")
    ingest.add_argument("--confirm-ocr-cost", action="store_true")

    series = subparsers.add_parser("series")
    series_sub = series.add_subparsers(dest="action", required=True)
    create_series = series_sub.add_parser("create")
    create_series.add_argument("--library-id", type=int, required=True)
    create_series.add_argument("--name", required=True)
    reorder_series = series_sub.add_parser("reorder")
    reorder_series.add_argument("--series-id", type=int, required=True)
    reorder_series.add_argument("--book-ids", required=True, help="Comma-separated ordered book ids")

    boundary = subparsers.add_parser("boundary")
    boundary.add_argument("--library-id", type=int, required=True)
    boundary.add_argument("--scope-type", choices=["book", "series"], required=True)
    boundary.add_argument("--scope-id", type=int, required=True)
    boundary.add_argument("--boundary-type", required=True)
    boundary.add_argument("--active-book-id", type=int)
    boundary.add_argument("--active-chapter-index", type=int)

    jobs = subparsers.add_parser("jobs")
    jobs.add_argument("--job-id", type=int)

    query = subparsers.add_parser("query")
    query.add_argument("--library-id", type=int, required=True)
    query.add_argument("--question", required=True)
    query.add_argument("--spoiler-mode", default="full_context")
    query.add_argument("--context-mode")
    query.add_argument("--active-book-id", type=int)
    query.add_argument("--active-chapter-index", type=int)

    chat = subparsers.add_parser("chat")
    chat.add_argument("--library-id", type=int, required=True)
    chat.add_argument("--question", required=True)
    chat.add_argument("--chat-provider-id", type=int, required=True)
    chat.add_argument("--chat-model", required=True)
    chat.add_argument("--spoiler-mode", default="full_context")
    chat.add_argument("--context-mode")
    chat.add_argument("--active-book-id", type=int)
    chat.add_argument("--active-chapter-index", type=int)

    local = subparsers.add_parser("local")
    local_sub = local.add_subparsers(dest="local_action", required=True)
    local_scan = local_sub.add_parser("scan")
    local_watch = local_sub.add_parser("watch")
    local_query = local_sub.add_parser("query")
    local_answer = local_sub.add_parser("answer")
    local_books = local_sub.add_parser("books")
    local_jobs = local_sub.add_parser("jobs")
    local_providers = local_sub.add_parser("providers")
    local_series = local_sub.add_parser("series")

    for ingest_cmd in (local_scan, local_watch):
        ingest_cmd.add_argument("--library-id", type=int)
        ingest_cmd.add_argument("--embedding-provider-id", type=int)
        ingest_cmd.add_argument("--embedding-model")
        ingest_cmd.add_argument("--chat-provider-id", type=int)
        ingest_cmd.add_argument("--chat-model")
        ingest_cmd.add_argument("--ocr-provider-id", type=int)
        ingest_cmd.add_argument("--ocr-model")
        ingest_cmd.add_argument("--ocr-mode", default="disabled")
        ingest_cmd.add_argument("--confirm-ocr-cost", action="store_true")
        ingest_cmd.add_argument("--delete-source", action=argparse.BooleanOptionalAction, default=None)
        ingest_cmd.add_argument("--chunk-size", type=int)
        ingest_cmd.add_argument("--chunk-overlap", type=int)
    local_scan.add_argument("--limit", type=int)
    local_watch.add_argument("--interval-sec", type=int)
    local_watch.add_argument("--limit-per-scan", type=int)

    for query_cmd in (local_query, local_answer):
        query_cmd.add_argument("--library-id", type=int)
        query_cmd.add_argument("--question", required=True)
        query_cmd.add_argument("--context-mode")
        query_cmd.add_argument("--spoiler-mode", default="full_context")
        query_cmd.add_argument("--active-book-id", type=int)
        query_cmd.add_argument("--active-chapter-index", type=int)
        query_cmd.add_argument("--top-k", type=int)
    local_answer.add_argument("--chat-provider-id", type=int)
    local_answer.add_argument("--chat-model")
    local_answer.add_argument("--temperature", type=float, default=0.2)
    local_answer.add_argument("--max-tokens", type=int, default=1200)

    local_books.add_argument("action", choices=["list"])
    local_books.add_argument("--library-id", type=int)
    local_jobs.add_argument("action", choices=["list"])
    local_providers.add_argument("action", choices=["list", "sync"])
    local_series.add_argument("action", choices=["list", "create", "reorder"])
    local_series.add_argument("--library-id", type=int)
    local_series.add_argument("--name")
    local_series.add_argument("--series-id", type=int)
    local_series.add_argument("--book-ids", help="Comma-separated ordered book ids")

    args = parser.parse_args()
    config = load_config()
    if args.base_url:
        config["base_url"] = args.base_url
        save_config(config)

    if args.command == "login":
        result = request("POST", "/auth/login", json_body={"username": args.username, "password": args.password})
        config = load_config()
        config["token"] = result["token"]
        save_config(config)
        print("Logged in.")
        return

    if args.command == "providers":
        if args.action == "list":
            print_json(request("GET", "/providers"))
            return
        print_json(
            request(
                "POST",
                "/providers",
                json_body={
                    "name": args.name,
                    "provider_type": args.type,
                    "api_key": args.api_key,
                    "base_url": args.base_url,
                    "default_embedding_model": args.embedding_model,
                    "default_chat_model": args.chat_model,
                    "default_ocr_model": args.ocr_model,
                },
            )
        )
        return

    if args.command == "libraries":
        if args.action == "list":
            print_json(request("GET", "/libraries"))
            return
        print_json(request("POST", "/libraries", json_body={"name": args.name, "description": args.description}))
        return

    if args.command == "books":
        if args.action == "upload":
            with open(args.file, "rb") as handle:
                print_json(request("POST", f"/libraries/{args.library_id}/books/upload", files={"file": (Path(args.file).name, handle)}))
            return
        print_json(
            request(
                "POST",
                f"/books/{args.book_id}/ingest",
                json_body={
                    "embedding_provider_id": args.embedding_provider_id,
                    "embedding_model": args.embedding_model,
                    "ocr_provider_id": args.ocr_provider_id,
                    "ocr_model": args.ocr_model,
                    "ocr_mode": args.ocr_mode,
                    "confirm_ocr_cost": args.confirm_ocr_cost,
                },
            )
        )
        return

    if args.command == "query":
        print_json(
            request(
                "POST",
                "/query/context",
                json_body={
                    "library_id": args.library_id,
                    "question": args.question,
                    "spoiler_mode": args.spoiler_mode,
                    "context_mode": args.context_mode,
                    "active_book_id": args.active_book_id,
                    "active_chapter_index": args.active_chapter_index,
                },
            )
        )
        return

    if args.command == "chat":
        print_json(
            request(
                "POST",
                "/chat/answer",
                json_body={
                    "library_id": args.library_id,
                    "question": args.question,
                    "chat_provider_id": args.chat_provider_id,
                    "chat_model": args.chat_model,
                    "spoiler_mode": args.spoiler_mode,
                    "context_mode": args.context_mode,
                    "active_book_id": args.active_book_id,
                    "active_chapter_index": args.active_chapter_index,
                },
            )
        )
        return

    if args.command == "series":
        if args.action == "create":
            print_json(request("POST", "/series", json_body={"library_id": args.library_id, "name": args.name}))
            return
        payload = [{"book_id": int(book_id.strip()), "sort_order": index} for index, book_id in enumerate(args.book_ids.split(","), start=1) if book_id.strip()]
        print_json(request("POST", f"/series/{args.series_id}/books/reorder", json_body=payload))
        return

    if args.command == "boundary":
        print_json(
            request(
                "PUT",
                "/boundaries",
                json_body={
                    "library_id": args.library_id,
                    "scope_type": args.scope_type,
                    "scope_id": args.scope_id,
                    "boundary_type": args.boundary_type,
                    "active_book_id": args.active_book_id,
                    "active_chapter_index": args.active_chapter_index,
                },
            )
        )
        return

    if args.command == "jobs":
        if args.job_id:
            print_json(request("GET", f"/jobs/{args.job_id}"))
            return
        print_json(request("GET", "/jobs"))
        return

    service = _local_service()
    if args.local_action == "providers":
        if args.action == "sync":
            service.sync_env_providers()
        print_json(service.list_providers())
        return
    if args.local_action == "books":
        library_id = args.library_id or service.ensure_default_library()["id"]
        print_json(service.list_books(library_id))
        return
    if args.local_action == "jobs":
        print_json(service.list_jobs())
        return
    if args.local_action == "series":
        library_id = args.library_id or service.ensure_default_library()["id"]
        if args.action == "list":
            print_json(service.list_series(library_id))
            return
        if args.action == "create":
            if not args.name:
                raise ValueError("--name is required for local series create")
            print_json(service.create_series(library_id, args.name))
            return
        if not args.series_id or not args.book_ids:
            raise ValueError("--series-id and --book-ids are required for local series reorder")
        payload = [{"book_id": int(book_id.strip()), "sort_order": index} for index, book_id in enumerate(args.book_ids.split(","), start=1) if book_id.strip()]
        print_json(service.reorder_series_books(args.series_id, payload))
        return
    if args.local_action in {"scan", "watch"}:
        ingestor = FolderIngestor(service)
        config_obj = _local_ingest_config(service, args)
        if args.local_action == "scan":
            print_json(ingestor.scan_once(config=config_obj, limit=args.limit))
            return
        ingestor.watch_forever(config=config_obj, interval_sec=args.interval_sec, limit_per_scan=args.limit_per_scan)
        return
    if args.local_action == "query":
        library_id = args.library_id or service.ensure_default_library()["id"]
        print_json(
            service.query_context(
                library_id=library_id,
                question=args.question,
                top_k=args.top_k,
                spoiler_mode=args.spoiler_mode,
                context_mode=args.context_mode,
                active_book_id=args.active_book_id,
                active_chapter_index=args.active_chapter_index,
            )
        )
        return
    if args.local_action == "answer":
        library_id = args.library_id or service.ensure_default_library()["id"]
        _, _, default_chat_provider_id, default_chat_model = _default_local_models(service, args)
        chat_provider_id = args.chat_provider_id or default_chat_provider_id
        chat_model = args.chat_model or default_chat_model
        if not chat_provider_id or not chat_model:
            raise ValueError("No chat provider/model configured. Set CLI args or default chat provider env vars.")
        print_json(
            service.answer_question(
                library_id=library_id,
                question=args.question,
                chat_provider_id=int(chat_provider_id),
                chat_model=chat_model,
                top_k=args.top_k,
                spoiler_mode=args.spoiler_mode,
                context_mode=args.context_mode,
                active_book_id=args.active_book_id,
                active_chapter_index=args.active_chapter_index,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
        )


if __name__ == "__main__":
    main()
