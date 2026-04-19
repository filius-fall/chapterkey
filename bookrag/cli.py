"""CLI wrapper for the BookRAG REST API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests


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


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(prog="bookrag", description="BookRAG REST API CLI")
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
    add_provider.add_argument("--type", required=True, choices=["openai_compatible", "anthropic", "google"])
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
    query.add_argument("--active-book-id", type=int)
    query.add_argument("--active-chapter-index", type=int)

    chat = subparsers.add_parser("chat")
    chat.add_argument("--library-id", type=int, required=True)
    chat.add_argument("--question", required=True)
    chat.add_argument("--chat-provider-id", type=int, required=True)
    chat.add_argument("--chat-model", required=True)
    chat.add_argument("--spoiler-mode", default="full_context")
    chat.add_argument("--active-book-id", type=int)
    chat.add_argument("--active-chapter-index", type=int)

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
                print_json(
                    request(
                        "POST",
                        f"/libraries/{args.library_id}/books/upload",
                        files={"file": (Path(args.file).name, handle)},
                    )
                )
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
        payload = [
            {"book_id": int(book_id.strip()), "sort_order": index}
            for index, book_id in enumerate(args.book_ids.split(","), start=1)
            if book_id.strip()
        ]
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
