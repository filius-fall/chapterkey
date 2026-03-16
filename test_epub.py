#!/usr/bin/env python3
"""
Test script to load and analyze Myst,_Might,_and_Mayhem.epub
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

from epub_processor import EpubProcessor
from embedder import Embedder
from chroma_manager import ChromaManager
from retriever import Retriever

def main():
    """Main test function."""
    epub_path = Path(__file__).parent.parent / "Myst,_Might,_and_Mayhem.epub"

    if not epub_path.exists():
        logger.error(f"EPUB not found: {epub_path}")
        return 1

    logger.info("=" * 60)
    logger.info("Testing EPUB RAG MCP Server")
    logger.info("=" * 60)
    logger.info(f"Loading: {epub_path.name}")
    logger.info("")

    # Initialize components
    try:
        processor = EpubProcessor()
        embedder = Embedder()
        chroma_manager = ChromaManager()
        retriever = Retriever()
        logger.info("✓ Components initialized successfully\n")
    except Exception as e:
        logger.error(f"✗ Failed to initialize: {e}")
        return 1

    # Check if already loaded
    collection_info = chroma_manager.get_collection_info("Myst, Might, and Mayhem")
    if collection_info:
        logger.info("✓ EPUB already loaded in database")
        logger.info(f"  - Stored chunks: {collection_info['document_count']}")
        logger.info(f"  - Unique chapters: {collection_info['unique_chapters']}")
        logger.info("")

        # Clear and reload
        logger.info("Clearing to reload...")
        chroma_manager.delete_collection("Myst, Might, and Mayhem")
        logger.info("✓ Cleared\n")

    # Process EPUB
    logger.info("Processing EPUB...")
    try:
        result = processor.process_epub(str(epub_path))
        chunks = result["chunks"]
        metadata_list = result["metadata"]
        stats = result["stats"]

        logger.info(f"✓ EPUB processed successfully\n")
        logger.info(f"  - Title: {stats['title']}")
        logger.info(f"  - Chapters: {stats['chapter_count']}")
        logger.info(f"  - Chunks: {stats['chunk_count']}")
        logger.info(f"  - Total Tokens: {stats['total_tokens']:,}")
        logger.info(f"  - Unique Chapters: {stats['unique_chapters']}")
        logger.info(f"  - Avg Tokens per Chunk: {stats['avg_chunk_tokens']:.1f}")
        logger.info("")

        # Generate embeddings
        logger.info("Generating embeddings...")
        embeddings = embedder.generate_embeddings(chunks)
        logger.info(f"✓ Generated {len(embeddings)} embeddings\n")

        # Calculate cost
        cost = embedder.estimate_cost(stats['total_tokens'])
        logger.info(f"Cost Estimate:")
        logger.info(f"  - Tokens: {cost['tokens']:,}")
        logger.info(f"  - Cost (USD): ${cost['cost_usd']:.4f}")
        logger.info(f"  - Cost (INR): ₹{cost['cost_inr']:.2f}")
        logger.info("")

        # Store in ChromaDB
        logger.info("Storing in ChromaDB...")
        epub_name = stats['title']
        ids = [f"{epub_name}_{i}" for i in range(len(chunks))]

        chroma_manager.add_documents(
            epub_name=epub_name,
            embeddings=embeddings,
            texts=chunks,
            metadatas=metadata_list,
            ids=ids
        )
        logger.info(f"✓ Stored {len(chunks)} documents\n")

        # Test queries with limits
        logger.info("=" * 60)
        logger.info("Testing Queries with Spoiler-Free Search")
        logger.info("=" * 60)
        logger.info("")

        # Test 1: Full search
        logger.info("Test 1: Full Search (No Limit)")
        logger.info("-" * 40)
        query1_results = retriever.query(
            "What is the main plot about?",
            epub_name
        )
        summary1 = retriever.summarize_results(query1_results)
        logger.info(f"✓ Found {summary1['total_passages']} passages")
        logger.info(f"  - From {summary1['unique_chapters']} chapters")
        logger.info(f"  - Average similarity: {summary1['average_similarity']:.3f}")
        logger.info(f"  - Best match: {summary1['best_match']:.3f}")
        logger.info("")

        # Test 2: Limited search (50%)
        logger.info("Test 2: Limited Search (First 50%)")
        logger.info("-" * 40)
        query2_results = retriever.query(
            "What has happened in the story so far?",
            epub_name,
            progress_percent=50
        )
        summary2 = retriever.summarize_results(query2_results)
        logger.info(f"✓ Limited to first 50% of book")
        logger.info(f"✓ Found {summary2['total_passages']} passages")
        logger.info(f"  - From {summary2['unique_chapters']} chapters")
        logger.info(f"  - Average similarity: {summary2['average_similarity']:.3f}")
        logger.info(f"  - Best match: {summary2['best_match']:.3f}")
        logger.info("")

        # Test 3: Limited search (before chapter 5)
        logger.info("Test 3: Limited Search (Before Chapter 5)")
        logger.info("-" * 40)
        query3_results = retriever.query(
            "Who are the main characters?",
            epub_name,
            chapter_limit="Chapter 5"
        )
        summary3 = retriever.summarize_results(query3_results)
        logger.info(f"✓ Limited to content before 'Chapter 5'")
        logger.info(f"✓ Found {summary3['total_passages']} passages")
        logger.info(f"  - From {summary3['unique_chapters']} chapters")
        logger.info(f"  - Average similarity: {summary3['average_similarity']:.3f}")
        logger.info(f"  - Best match: {summary3['best_match']:.3f}")
        logger.info("")

        # Test 4: Limited search (first 50 chunks)
        logger.info("Test 4: Limited Search (First 50 Chunks)")
        logger.info("-" * 40)
        query4_results = retriever.query(
            "What is the setting like?",
            epub_name,
            chunk_count=50
        )
        summary4 = retriever.summarize_results(query4_results)
        logger.info(f"✓ Limited to first 50 chunks")
        logger.info(f"✓ Found {summary4['total_passages']} passages")
        logger.info(f"  - From {summary4['unique_chapters']} chapters")
        logger.info(f"  - Average similarity: {summary4['average_similarity']:.3f}")
        logger.info(f"  - Best match: {summary4['best_match']:.3f}")
        logger.info("")

        # Show content samples
        logger.info("=" * 60)
        logger.info("Content Samples")
        logger.info("=" * 60)
        logger.info("")

        if query1_results['results']:
            best_result = query1_results['results'][0]
            meta = best_result['metadata']
            logger.info(f"Best Match (Similarity: {best_result['similarity_score']:.3f}):")
            logger.info(f"  - Chapter: {meta.get('chapter', 'Unknown')}")
            logger.info(f"  - Chunk Index: {meta.get('chunk_index', 0)}")
            logger.info(f"  - Token Count: {meta.get('token_count', 0)}")
            logger.info(f"  - Content Preview:")
            content_preview = best_result['content'][:300]
            logger.info(f"    {content_preview}...")
            logger.info("")

        # Show chapter distribution
        logger.info("Chapter Distribution:")
        chapter_counts = {}
        for meta in metadata_list:
            chapter = meta.get('chapter', 'Unknown')
            chapter_counts[chapter] = chapter_counts.get(chapter, 0) + 1

        for chapter, count in sorted(chapter_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  - {chapter}: {count} chunks")

        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ All tests completed successfully!")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"✗ Error during processing: {e}")
        logger.error(f"✗ {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
