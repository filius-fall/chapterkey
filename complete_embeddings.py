#!/usr/bin/env python3
"""
Complete embedding generation for Myst, Might, and Mayhem.
This will store all embeddings in ChromaDB.
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from epub_processor import EpubProcessor
from embedder import Embedder
from chroma_manager import ChromaManager

def main():
    """Complete embedding generation and storage."""
    epub_path = Path(__file__).parent.parent / "Myst,_Might,_and_Mayhem.epub"

    logger.info("=" * 60)
    logger.info("Completing Embedding Generation")
    logger.info("=" * 60)

    # Clear existing collection
    logger.info("Step 1: Clearing existing collection...")
    chroma = ChromaManager()
    chroma.delete_collection("Myst, Might, and Mayhem")
    logger.info("✓ Cleared\n")

    # Process EPUB
    logger.info("Step 2: Processing EPUB...")
    processor = EpubProcessor()
    result = processor.process_epub(str(epub_path))
    stats = result['stats']

    logger.info(f"✓ Processed {stats['chunk_count']} chunks\n")

    # Generate embeddings
    logger.info("Step 3: Generating embeddings...")
    logger.info("  (This will take 8-10 minutes for 2.9M tokens)")
    embedder = Embedder()
    embeddings = embedder.generate_embeddings(result['chunks'])
    logger.info(f"✓ Generated {len(embeddings)} embeddings\n")

    # Store in ChromaDB
    logger.info("Step 4: Storing in ChromaDB...")
    epub_name = stats['title']
    ids = [f"{epub_name}_{i}" for i in range(len(result['chunks']))]

    chroma.add_documents(
        epub_name=epub_name,
        embeddings=embeddings,
        texts=result['chunks'],
        metadatas=result['metadata'],
        ids=ids
    )
    logger.info(f"✓ Stored {len(result['chunks'])} documents\n")

    # Verify storage
    logger.info("Step 5: Verifying storage...")
    info = chroma.get_collection_info(epub_name)
    if info:
        logger.info(f"✓ Verified:")
        logger.info(f"  - Document Count: {info['document_count']}")
        logger.info(f"  - Unique Chapters: {info['unique_chapters']}")
    else:
        logger.warning("✗ Verification failed!")

    logger.info("\n" + "=" * 60)
    logger.info("✓ Embedding Generation Complete!")
    logger.info("=" * 60)

    # Show cost
    cost = embedder.estimate_cost(stats['total_tokens'])
    logger.info(f"\nCost Estimate:")
    logger.info(f"  - Tokens: {cost['tokens']:,}")
    logger.info(f"  - Cost (USD): ${cost['cost_usd']:.4f}")
    logger.info(f"  - Cost (INR): ₹{cost['cost_inr']:.2f}")

    logger.info("\nReady to use!")
    logger.info("Start: python server.py")
    logger.info("Then use MCP tools to query the data.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
