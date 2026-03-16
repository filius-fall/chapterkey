"""
EPUB RAG MCP Server - Main entry point.

Provides MCP tools for loading and querying EPUB files using
vector embeddings and RAG (Retrieval Augmented Generation).
"""
import logging
import sys
from typing import Optional
from pathlib import Path

# Set up logging before importing other modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from epub_processor import EpubProcessor
from embedder import Embedder
from chroma_manager import ChromaManager
from retriever import Retriever
from config import Config
from openrouter_client import OpenRouterClient

# Initialize components
try:
    processor = EpubProcessor()
    embedder = Embedder()
    chroma_manager = ChromaManager()
    retriever = Retriever()
    llm_client = OpenRouterClient()
    logger.info("All components initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize components: {e}")
    sys.exit(1)

# Create MCP server
server = Server("epub-rag-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="load_epub",
            description="Load and process an EPUB file for RAG-based querying. Extracts text, chunks it, generates embeddings via OpenRouter, and stores in ChromaDB. Returns summary of loaded content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "epub_path": {
                        "type": "string",
                        "description": "Full path to the EPUB file to load"
                    }
                },
                "required": ["epub_path"]
            }
        ),
        Tool(
            name="ask_question",
            description="Ask a question about a loaded EPUB. Uses vector similarity search to find relevant passages and returns them for Claude Code to answer. Supports limiting search to avoid spoilers (use progress_percent, chapter_limit, or chunk_count). Returns relevant chunks with sources and similarity scores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask about the EPUB content"
                    },
                    "epub_name": {
                        "type": "string",
                        "description": "Optional: Name of specific EPUB to query (uses last loaded if not specified)"
                    },
                    "progress_percent": {
                        "type": "integer",
                        "description": "Optional: Limit search to first X% of book (0-100). Use to avoid spoilers while reading.",
                        "minimum": 0,
                        "maximum": 100
                    },
                    "chapter_limit": {
                        "type": "string",
                        "description": "Optional: Limit search to content before this chapter name. Include everything up to (but not including) this chapter."
                    },
                    "chunk_count": {
                        "type": "integer",
                        "description": "Optional: Limit search to first N chunks from the start of the book.",
                        "minimum": 1
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="list_epubs",
            description="List all loaded EPUBs in the vector database. Shows available EPUBs with metadata including word count, chunk count, and load time.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_epub_info",
            description="Get detailed information about a specific loaded EPUB including word count, chapter count, chunk count, and storage statistics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "epub_name": {
                        "type": "string",
                        "description": "Name of the EPUB to get information about"
                    }
                },
                "required": ["epub_name"]
            }
        ),
        Tool(
            name="clear_epub",
            description="Clear an EPUB from vector storage. Removes the EPUB and all its chunks from ChromaDB to free up storage space.",
            inputSchema={
                "type": "object",
                "properties": {
                    "epub_name": {
                        "type": "string",
                        "description": "Name of the EPUB to clear from storage"
                    }
                },
                "required": ["epub_name"]
            }
        ),
        Tool(
            name="ask_question_with_llm",
            description="Ask a question about a loaded EPUB and get a complete answer using OpenRouter LLM (e.g., Gemini 2.5). Uses RAG to find relevant passages and then generates a complete answer using the specified LLM model. Supports limiting search to avoid spoilers (use progress_percent, chapter_limit, or chunk_count). Faster and more cost-effective than using Claude Code's native LLM.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask about the EPUB content"
                    },
                    "epub_name": {
                        "type": "string",
                        "description": "Optional: Name of specific EPUB to query (uses last loaded if not specified)"
                    },
                    "model": {
                        "type": "string",
                        "description": "OpenRouter model to use for answering. Popular options: 'google/gemini-2.5-flash-preview', 'google/gemini-2.5-pro', 'google/gemini-flash-1.5-8b'. Defaults to configured LLM_MODEL."
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature (0-2). Lower = more focused, Higher = more creative. Default: 0.7"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to generate. Default: 1000"
                    },
                    "progress_percent": {
                        "type": "integer",
                        "description": "Optional: Limit search to first X% of book (0-100). Use to avoid spoilers while reading.",
                        "minimum": 0,
                        "maximum": 100
                    },
                    "chapter_limit": {
                        "type": "string",
                        "description": "Optional: Limit search to content before this chapter name. Include everything up to (but not including) this chapter."
                    },
                    "chunk_count": {
                        "type": "integer",
                        "description": "Optional: Limit search to first N chunks from the start of the book.",
                        "minimum": 1
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="list_available_models",
            description="List available Gemini models for question answering via OpenRouter. Shows model names and descriptions to help you choose the best Gemini model for your needs.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    try:
        if name == "load_epub":
            return await handle_load_epub(arguments)

        elif name == "ask_question":
            return await handle_ask_question(arguments)

        elif name == "list_epubs":
            return await handle_list_epubs(arguments)

        elif name == "get_epub_info":
            return await handle_get_epub_info(arguments)

        elif name == "clear_epub":
            return await handle_clear_epub(arguments)

        elif name == "ask_question_with_llm":
            return await handle_ask_question_with_llm(arguments)

        elif name == "list_available_models":
            return await handle_list_available_models(arguments)

        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    except Exception as e:
        logger.error(f"Error handling tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

async def handle_load_epub(arguments: dict) -> list[TextContent]:
    """Handle load_epub tool call."""
    epub_path = arguments.get("epub_path")

    if not epub_path:
        return [TextContent(
            type="text",
            text="Error: epub_path is required"
        )]

    try:
        logger.info(f"Loading EPUB: {epub_path}")

        # Process EPUB
        result = processor.process_epub(epub_path)
        chunks = result["chunks"]
        metadata_list = result["metadata"]
        stats = result["stats"]

        # Generate embeddings
        embeddings = embedder.generate_embeddings(chunks)

        # Store in ChromaDB
        epub_name = stats["title"]
        ids = [f"{epub_name}_{i}" for i in range(len(chunks))]

        chroma_manager.add_documents(
            epub_name=epub_name,
            embeddings=embeddings,
            texts=chunks,
            metadatas=metadata_list,
            ids=ids
        )

        # Generate response
        cost_estimate = embedder.estimate_cost(stats["total_tokens"])

        response = f"""✅ EPUB loaded successfully!

## Summary
- **Title:** {stats['title']}
- **Path:** {stats['path']}
- **Chapters:** {stats['chapter_count']}
- **Chunks:** {stats['chunk_count']}
- **Total Tokens:** {stats['total_tokens']:,}
- **Unique Chapters:** {stats['unique_chapters']}
- **Avg Tokens per Chunk:** {stats['avg_chunk_tokens']:.1f}

## Cost Estimate
- **Embeddings Cost:** ₹{cost_estimate['cost_inr']}
- **Tokens Processed:** {cost_estimate['tokens']:,}

The EPUB is now ready for querying! Use the `ask_question` tool to ask questions about its content.
"""

        logger.info(f"Successfully loaded EPUB: {epub_name}")
        return [TextContent(type="text", text=response)]

    except FileNotFoundError as e:
        return [TextContent(
            type="text",
            text=f"Error: EPUB file not found - {str(e)}"
        )]
    except Exception as e:
        logger.error(f"Error loading EPUB: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error loading EPUB: {str(e)}"
        )]

async def handle_ask_question(arguments: dict) -> list[TextContent]:
    """Handle ask_question tool call."""
    question = arguments.get("question")
    epub_name = arguments.get("epub_name")
    progress_percent = arguments.get("progress_percent")
    chapter_limit = arguments.get("chapter_limit")
    chunk_count = arguments.get("chunk_count")

    if not question:
        return [TextContent(
            type="text",
            text="Error: question is required"
        )]

    # Check that only one limit option is specified
    limit_count = sum(1 for x in [progress_percent, chapter_limit, chunk_count] if x is not None)
    if limit_count > 1:
        return [TextContent(
            type="text",
            text="Error: Please specify only one of progress_percent, chapter_limit, or chunk_count (not multiple)."
        )]

    try:
        logger.info(f"Asking question: {question[:50]}...")

        # If no EPUB specified, try to use the most recently loaded one
        if not epub_name:
            collections = chroma_manager.list_collections()
            if collections:
                epub_name = collections[-1]["name"]
                logger.info(f"Using most recently loaded EPUB: {epub_name}")
            else:
                return [TextContent(
                    type="text",
                    text="Error: No EPUBs loaded. Use load_epub tool first."
                )]

        # Query the retriever
        # Query retriever with search limit
        query_results = retriever.query(
            question,
            epub_name,
            progress_percent=progress_percent,
            chapter_limit=chapter_limit,
            chunk_count=chunk_count
        )

        # Format for Claude
        formatted_output = retriever.format_for_claude(query_results)

        # Get summary
        summary = retriever.summarize_results(query_results)

        # Add summary to output
        if summary['found']:
            summary_text = f"""
## Query Summary
- Found {summary['total_passages']} relevant passages
- From {summary['unique_chapters']} different chapters
- Average similarity: {summary['average_similarity']}

"""
            formatted_output = summary_text + formatted_output
        else:
            formatted_output = "No relevant content found for your question.\n\n" + formatted_output

        logger.info(f"Retrieved {query_results['total_results']} results")
        return [TextContent(type="text", text=formatted_output)]

    except Exception as e:
        logger.error(f"Error asking question: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error processing question: {str(e)}"
        )]

async def handle_list_epubs(arguments: dict) -> list[TextContent]:
    """Handle list_epubs tool call."""
    try:
        collections = chroma_manager.list_collections()

        if not collections:
            return [TextContent(
                type="text",
                text="No EPUBs loaded. Use load_epub tool to add an EPUB."
            )]

        # Format the list
        output = ["## Loaded EPUBs\n"]

        for col in collections:
            output.append(f"### {col['name']}")
            output.append(f"- **Document Count:** {col['document_count']}")
            output.append(f"- **Status:** Loaded and ready for querying\n")

        response = "\n".join(output)
        return [TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Error listing EPUBs: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error listing EPUBs: {str(e)}"
        )]

async def handle_get_epub_info(arguments: dict) -> list[TextContent]:
    """Handle get_epub_info tool call."""
    epub_name = arguments.get("epub_name")

    if not epub_name:
        return [TextContent(
            type="text",
            text="Error: epub_name is required"
        )]

    try:
        info = chroma_manager.get_collection_info(epub_name)

        if not info:
            return [TextContent(
                type="text",
                text=f"Error: EPUB '{epub_name}' not found in storage."
            )]

        response = f"""## EPUB Information

- **Name:** {info['name']}
- **Stored Chunks:** {info['document_count']:,}
- **Unique Chapters:** {info['unique_chapters']}
- **Status:** Ready for querying

The EPUB is loaded and ready. Use `ask_question` to query its content.
"""
        return [TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Error getting EPUB info: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error getting EPUB info: {str(e)}"
        )]

async def handle_clear_epub(arguments: dict) -> list[TextContent]:
    """Handle clear_epub tool call."""
    epub_name = arguments.get("epub_name")

    if not epub_name:
        return [TextContent(
            type="text",
            text="Error: epub_name is required"
        )]

    try:
        # Get info before deleting
        info = chroma_manager.get_collection_info(epub_name)

        if not info:
            return [TextContent(
                type="text",
                text=f"Error: EPUB '{epub_name}' not found in storage."
            )]

        # Delete the collection
        chroma_manager.delete_collection(epub_name)

        response = f"""✅ EPUB cleared successfully!

## Removed
- **Name:** {info['name']}
- **Stored Chunks:** {info['document_count']:,}
- **Unique Chapters:** {info['unique_chapters']}

The EPUB has been removed from storage. Use `load_epub` to load it again if needed.
"""
        logger.info(f"Cleared EPUB: {epub_name}")
        return [TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Error clearing EPUB: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error clearing EPUB: {str(e)}"
        )]

async def handle_ask_question_with_llm(arguments: dict) -> list[TextContent]:
    """Handle ask_question_with_llm tool call - uses OpenRouter LLM directly."""
    question = arguments.get("question")
    epub_name = arguments.get("epub_name")
    model = arguments.get("model")
    temperature = arguments.get("temperature", 0.7)
    max_tokens = arguments.get("max_tokens", 1000)
    progress_percent = arguments.get("progress_percent")
    chapter_limit = arguments.get("chapter_limit")
    chunk_count = arguments.get("chunk_count")

    if not question:
        return [TextContent(
            type="text",
            text="Error: question is required"
        )]

    # Check that only one limit option is specified
    limit_count = sum(1 for x in [progress_percent, chapter_limit, chunk_count] if x is not None)
    if limit_count > 1:
        return [TextContent(
            type="text",
            text="Error: Please specify only one of progress_percent, chapter_limit, or chunk_count (not multiple)."
        )]

    try:
        logger.info(f" Asking question with LLM: {question[:50]}...")

        # If no EPUB specified, try to use most recently loaded one
        if not epub_name:
            collections = chroma_manager.list_collections()
            if collections:
                epub_name = collections[-1]["name"]
                logger.info(f"Using most recently loaded EPUB: {epub_name}")
            else:
                return [TextContent(
                    type="text",
                    text="Error: No EPUBs loaded. Use load_epub tool first."
                )]

        # Query retriever to get relevant chunks
        # Query retriever with search limit
        query_results = retriever.query(
            question,
            epub_name,
            progress_percent=progress_percent,
            chapter_limit=chapter_limit,
            chunk_count=chunk_count
        )

        if not query_results['results']:
            return [TextContent(
                type="text",
                text=f"No relevant content found for your question: '{question}'"
            )]

        # Build context from retrieved chunks
        context_chunks = []
        for i, result in enumerate(query_results['results'], 1):
            meta = result['metadata']
            context_chunks.append(f"[Passage {i} - {meta.get('chapter', 'Unknown')} (similarity: {result['similarity_score']:.3f})]\n{result['content']}\n")

        context = "\n".join(context_chunks)

        # Create prompt for LLM
        system_prompt = """You are a helpful assistant answering questions about EPUB book content.
Use the provided passages to answer the user's question.
Be accurate, concise, and cite your sources.
If the passages don't contain enough information to answer the question, say so."""

        # Add search limit info to prompt if present
        search_limit_info = ""
        if query_results.get('search_limit'):
            limit = query_results['search_limit']
            limit_type = limit.get('type')

            if limit_type == 'progress_percent':
                search_limit_info = f"\n\nIMPORTANT: Search was limited to the first {limit['value']}% of the book (up to chapter {limit['max_chapter_index']} of {limit['max_chapters']})."
            elif limit_type == 'chapter_limit':
                search_limit_info = f"\n\nIMPORTANT: Search was limited to content before chapter '{limit['value']}'."
            elif limit_type == 'chunk_count':
                search_limit_info = f"\n\nIMPORTANT: Search was limited to the first {limit['value']} chunks from the start of the book."

            if search_limit_info:
                search_limit_info += " Base your answer ONLY on the provided passages (no information from later in the book)."

        user_prompt = f"""Based on the following passages from the book, answer this question:

**Question:** {question}{search_limit_info}

**Relevant Passages:**
{context}

**Answer:"""

        # Use specified model or default
        llm_to_use = model or Config.LLM_MODEL

        # Generate answer using OpenRouter LLM
        logger.info(f"Using LLM model: {llm_to_use}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        answer = llm_client.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Format response
        summary = retriever.summarize_results(query_results)

        # Add search limit info to response
        search_limit_text = ""
        if query_results.get('search_limit'):
            limit = query_results['search_limit']
            limit_type = limit.get('type')

            if limit_type == 'progress_percent':
                search_limit_text = f"- **Search Limit:** First {limit['value']}% of book (chapters 0-{limit['max_chapter_index']} of {limit['max_chapters']})"
            elif limit_type == 'chapter_limit':
                search_limit_text = f"- **Search Limit:** Before chapter '{limit['value']}'"
            elif limit_type == 'chunk_count':
                search_limit_text = f"- **Search Limit:** First {limit['value']} chunks"

            if search_limit_text:
                search_limit_text += "\n- **⚠️ Note:** Answer based ONLY on content within limit (no spoilers)"

        response = f"""## Answer (Generated using {llm_to_use})

{answer}

---

## Query Summary
- **Question:** {question}
- **EPUB:** {epub_name}
- **Model Used:** {llm_to_use}
- **Sources Used:** {summary['total_passages']} passages
- **From Chapters:** {', '.join(summary['chapters'][:5])}{'...' if len(summary['chapters']) > 5 else ''}
{search_limit_text}
- **Average Relevance:** {summary['average_similarity']:.3f}
"""

        logger.info(f"Generated answer with LLM")
        return [TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Error asking question with LLM: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error processing question with LLM: {str(e)}"
        )]

async def handle_list_available_models(arguments: dict) -> list[TextContent]:
    """Handle list_available_models tool call."""
    try:
        # Gemini models available for question answering via OpenRouter
        models = [
            {
                "name": "google/gemini-2.5-flash-preview",
                "provider": "Google",
                "description": "Gemini 2.5 Flash - Latest, fastest model with excellent reasoning (DEFAULT)",
                "best_for": "Fast answers, general questions, cost-effective",
                "cost": "Low cost - Best value"
            },
            {
                "name": "google/gemini-2.5-pro",
                "provider": "Google",
                "description": "Gemini 2.5 Pro - Highest quality model for complex reasoning",
                "best_for": "Complex analysis, detailed answers, research",
                "cost": "Medium cost - Premium quality"
            },
            {
                "name": "google/gemini-1.5-flash",
                "provider": "Google",
                "description": "Gemini 1.5 Flash - Fast, efficient model",
                "best_for": "General use, balanced performance",
                "cost": "Low cost - Reliable"
            },
            {
                "name": "google/gemini-1.5-pro",
                "provider": "Google",
                "description": "Gemini 1.5 Pro - High-quality reasoning",
                "best_for": "Complex questions requiring detailed answers",
                "cost": "Medium cost - High quality"
            },
            {
                "name": "google/gemini-1.5-flash-8b",
                "provider": "Google",
                "description": "Gemini 1.5 Flash 8B - Smallest, most cost-effective model",
                "best_for": "Simple questions, maximum cost savings",
                "cost": "Very low cost - Cheapest option"
            }
        ]

        # Format output
        output = ["## Available Gemini Models for Question Answering\n"]
        output.append("Using only Google Gemini models via OpenRouter API - fast, cost-effective, and high-quality.\n")

        for i, model in enumerate(models, 1):
            output.append(f"### {i}. {model['name']}")
            output.append(f"- **Provider:** {model['provider']}")
            output.append(f"- **Description:** {model['description']}")
            output.append(f"- **Best For:** {model['best_for']}")
            output.append(f"- **Cost:** {model['cost']}\n")

        output.append("\n**Recommended:** Use `google/gemini-2.5-flash-preview` (default) - latest, fastest, and best value!\n")

        output.append("**Usage:**")
        output.append("```")
        output.append('ask_question_with_llm("Your question", model="google/gemini-2.5-flash-preview")')
        output.append("```")

        response = "\n".join(output)
        return [TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error listing models: {str(e)}"
        )]

async def main():
    """Main entry point."""
    # Validate configuration
    is_valid, error = Config.validate()
    if not is_valid:
        logger.error(f"Configuration error: {error}")
        logger.error("Please ensure OPENROUTER_API_KEY is set in .env file")
        sys.exit(1)

    logger.info("Starting EPUB RAG MCP Server...")
    logger.info("Use MCP tools to load and query EPUB files")

    # Start the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
