#!/usr/bin/env python3
"""
Quick test to verify EPUB RAG MCP Server is working.
"""
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("EPUB RAG MCP Server - Quick Test")
    logger.info("=" * 60)

    # Test 1: Import all modules
    logger.info("\n✓ Test 1: Importing modules...")
    try:
        from config import Config
        logger.info(f"  ✓ config imported")
        logger.info(f"  ✓ API Key configured: {bool(Config.OPENROUTER_API_KEY)}")
        logger.info(f"  ✓ LLM Model: {Config.LLM_MODEL}")
        logger.info(f"  ✓ Data directory: {Config.DATA_DIR}")
    except Exception as e:
        logger.error(f"  ✗ Error: {e}")
        return 1

    # Test 2: Check ChromaDB
    logger.info("\n✓ Test 2: ChromaDB...")
    try:
        from chroma_manager import ChromaManager
        chroma = ChromaManager()
        logger.info(f"  ✓ ChromaDB initialized")
        logger.info(f"  ✓ Vector DB path: {Config.VECTOR_DB_PATH}")
    except Exception as e:
        logger.error(f"  ✗ Error: {e}")
        return 1

    # Test 3: Load EPUB
    logger.info("\n✓ Test 3: EPUB Processing...")
    try:
        from epub_processor import EpubProcessor
        processor = EpubProcessor()
        epub_path = Path(__file__).parent.parent / "Myst,_Might,_and_Mayhem.epub"

        if not epub_path.exists():
            logger.error(f"  ✗ EPUB not found: {epub_path}")
            return 1

        logger.info(f"  ✓ Loading: {epub_path.name}")
        logger.info(f"  (This may take a minute...)")

        result = processor.process_epub(str(epub_path))
        stats = result['stats']

        logger.info(f"\n  ✓ EPUB Loaded Successfully!")
        logger.info(f"    Title: {stats['title']}")
        logger.info(f"    Chapters: {stats['chapter_count']}")
        logger.info(f"    Chunks: {stats['chunk_count']}")
        logger.info(f"    Total Tokens: {stats['total_tokens']:,}")
        logger.info(f"    Unique Chapters: {stats['unique_chapters']}")
        logger.info(f"    Avg Tokens/Chunk: {stats['avg_chunk_tokens']:.1f}")

    except Exception as e:
        logger.error(f"  ✗ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

    # Test 4: Check if stored in ChromaDB
    logger.info("\n✓ Test 4: Check ChromaDB Storage...")
    try:
        from chroma_manager import ChromaManager
        chroma = ChromaManager()
        info = chroma.get_collection_info("Myst, Might, and Mayhem")

        if info:
            logger.info(f"  ✓ Found in ChromaDB:")
            logger.info(f"    Stored chunks: {info['document_count']}")
            logger.info(f"    Unique chapters: {info['unique_chapters']}")
        else:
            logger.warning(f"  ! Not found in ChromaDB (may still be processing)")

    except Exception as e:
        logger.error(f"  ✗ Error: {e}")
        return 1

    # Test 5: Test retriever
    logger.info("\n✓ Test 5: Retriever...")
    try:
        from retriever import Retriever
        retriever = Retriever()
        logger.info(f"  ✓ Retriever initialized")
        logger.info(f"  ✓ Ready for queries")

    except Exception as e:
        logger.error(f"  ✗ Error: {e}")
        return 1

    # Test 6: Sample content preview
    logger.info("\n✓ Test 6: Content Preview...")
    try:
        from chroma_manager import ChromaManager
        chroma = ChromaManager()
        collection = chroma.get_or_create_collection("Myst, Might, and Mayhem")

        # Get a sample document
        sample = collection.get(limit=1, include=["documents", "metadatas"])

        if sample and sample['documents']:
            doc = sample['documents'][0]
            meta = sample['metadatas'][0]
            logger.info(f"  ✓ Sample content retrieved:")
            logger.info(f"    Chapter: {meta.get('chapter', 'Unknown')}")
            logger.info(f"    Chunk: {meta.get('chunk_index', 0)}")
            logger.info(f"    Tokens: {meta.get('token_count', 0)}")
            logger.info(f"    Preview: {doc[:200]}...")
        else:
            logger.warning(f"  ! No documents found yet")

    except Exception as e:
        logger.error(f"  ✗ Error: {e}")
        return 1

    logger.info("\n" + "=" * 60)
    logger.info("✓ All Tests Completed Successfully!")
    logger.info("=" * 60)
    logger.info("\nNext Steps:")
    logger.info("1. Start the MCP server: python server.py")
    logger.info("2. Configure Claude Code with the server path")
    logger.info("3. Load and query EPUBs using MCP tools")
    logger.info("")

    return 0

if __name__ == "__main__":
    sys.exit(main())
