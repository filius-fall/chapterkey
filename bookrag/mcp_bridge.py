"""MCP bridge that talks to the BookRAG REST API."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


API_URL = os.getenv("BOOKRAG_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("BOOKRAG_API_TOKEN", "")
server = Server("bookrag-mcp")


def api_request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    """Call the BookRAG REST API."""
    headers = {}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    response = requests.request(
        method,
        API_URL + path,
        json=payload,
        headers=headers,
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Expose a query-oriented MCP surface."""
    return [
        Tool(
            name="list_libraries",
            description="List available libraries in the deployed BookRAG app.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_books",
            description="List indexed books for a library.",
            inputSchema={
                "type": "object",
                "properties": {"library_id": {"type": "integer"}},
                "required": ["library_id"],
            },
        ),
        Tool(
            name="list_providers",
            description="List configured providers and default models.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="query_context",
            description="Retrieve context passages from the vector database with spoiler controls.",
            inputSchema={
                "type": "object",
                "properties": {
                    "library_id": {"type": "integer"},
                    "question": {"type": "string"},
                    "spoiler_mode": {"type": "string"},
                    "active_book_id": {"type": "integer"},
                    "active_chapter_index": {"type": "integer"},
                    "top_k": {"type": "integer"},
                },
                "required": ["library_id", "question"],
            },
        ),
        Tool(
            name="answer_question",
            description="Answer a question using the configured backend and a selected chat provider/model.",
            inputSchema={
                "type": "object",
                "properties": {
                    "library_id": {"type": "integer"},
                    "question": {"type": "string"},
                    "chat_provider_id": {"type": "integer"},
                    "chat_model": {"type": "string"},
                    "spoiler_mode": {"type": "string"},
                    "active_book_id": {"type": "integer"},
                    "active_chapter_index": {"type": "integer"},
                    "top_k": {"type": "integer"},
                },
                "required": ["library_id", "question", "chat_provider_id", "chat_model"],
            },
        ),
        Tool(
            name="list_jobs",
            description="List recent ingest jobs from the deployed BookRAG app.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle MCP tool calls through the REST API."""
    try:
        if name == "list_libraries":
            payload = api_request("GET", "/libraries")
        elif name == "list_books":
            payload = api_request("GET", f"/libraries/{arguments['library_id']}/books")
        elif name == "list_providers":
            payload = api_request("GET", "/providers")
        elif name == "query_context":
            payload = api_request("POST", "/query/context", arguments)
        elif name == "answer_question":
            payload = api_request("POST", "/chat/answer", arguments)
        elif name == "list_jobs":
            payload = api_request("GET", "/jobs")
        else:
            raise ValueError(f"Unknown tool: {name}")
        return [TextContent(type="text", text=str(payload))]
    except Exception as exc:
        return [TextContent(type="text", text=f"Error: {exc}")]


async def main() -> None:
    """Run the MCP stdio server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """Sync entrypoint."""
    asyncio.run(main())
