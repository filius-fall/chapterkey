#!/usr/bin/env python3
"""
Ingest books from input_books directory using NVIDIA embeddings.
Handles rate limiting with delays between batches.
"""
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# IMPORTANT: Override Config BEFORE importing services that use it
# NVIDIA nv-embedqa-e5-v5 has 512 token limit per input
# Using 400 to be safe since NVIDIA's tokenizer counts differently than tiktoken
from config import Config
Config.CHUNK_SIZE = 400
Config.CHUNK_OVERLAP = 40

from bookrag.services import BookRAGService
from bookrag.folder_ingest import FolderIngestor, LocalIngestConfig


def main():
    """Ingest all books from input_books using NVIDIA."""
    logger.info("=" * 60)
    logger.info("Book Ingestion with NVIDIA Embeddings")
    logger.info("=" * 60)
    
    service = BookRAGService()
    
    # Get NVIDIA provider from service
    providers = service.list_providers()
    nvidia = [p for p in providers if p['name'] == 'NVIDIA']
    if not nvidia:
        logger.error("NVIDIA provider not found!")
        return 1
    nvidia = nvidia[0]
    logger.info(f"Using NVIDIA provider (ID: {nvidia['id']})")
    logger.info(f"Model: {nvidia['default_embedding_model']}")
    
    # Get or create library
    libraries = service.list_libraries()
    if not libraries:
        library = service.create_library('Default Library', 'Auto-created library')
        library_id = library['id']
        logger.info(f"Created new library (ID: {library_id})")
    else:
        library_id = libraries[0]['id']
        logger.info(f"Using existing library (ID: {library_id})")
    
    # Find books to ingest (use fixed EPUB for ReturnoftheMountHuaSect)
    input_dir = Path('./data/input_books')
    ingestor = FolderIngestor(service)
    files = ingestor.stable_files(input_dir=input_dir)
    
    # Replace broken EPUB with fixed version
    files = [f for f in files if 'ReturnoftheMountHuaSect.epub' not in f.name or '_fixed' in f.name]
    # If fixed version exists, use it
    fixed_epub = input_dir / 'ReturnoftheMountHuaSect_fixed.epub'
    if fixed_epub.exists() and not any('ReturnoftheMountHuaSect' in f.name for f in files):
        files.append(fixed_epub)
    
    if not files:
        logger.warning("No books found in input_books directory!")
        return 0
    
    logger.info(f"\nFound {len(files)} book(s) to process:")
    for f in files:
        logger.info(f"  - {f.name}")
    
    # Process each book with rate limiting
    results = []
    for i, file_path in enumerate(files, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {i}/{len(files)}: {file_path.name}")
        logger.info(f"{'='*60}")
        
        # Create config for this book
        # NOTE: Config.CHUNK_SIZE already set to 400 for NVIDIA 512 token limit
        config = LocalIngestConfig(
            library_id=library_id,
            embedding_provider_id=nvidia['id'],
            embedding_model=nvidia['default_embedding_model'],
            chunk_size=400,
            chunk_overlap=40,
            ocr_mode='disabled',
            delete_source=False
        )
        
        try:
            result = service.ingest_file_from_path(
                file_path,
                library_id=config.library_id,
                embedding_provider_id=config.embedding_provider_id,
                embedding_model=config.embedding_model,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                ocr_provider_id=config.ocr_provider_id,
                ocr_model=config.ocr_model,
                ocr_mode=config.ocr_mode,
                confirm_ocr_cost=config.confirm_ocr_cost,
                delete_source=config.delete_source,
            )
            results.append(result)
            logger.info(f"✓ Successfully ingested: {file_path.name}")
            logger.info(f"  - Book ID: {result.get('book_id')}")
            logger.info(f"  - Job ID: {result.get('job_id')}")
            
            # Rate limiting: wait 2 seconds between books
            if i < len(files):
                logger.info("Waiting 2 seconds before next book (rate limiting)...")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"✗ Failed to ingest {file_path.name}: {e}")
            # Wait longer on error
            time.sleep(5)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Ingestion Complete!")
    logger.info(f"{'='*60}")
    logger.info(f"Total books processed: {len(results)}/{len(files)}")
    for r in results:
        logger.info(f"  - Book ID {r.get('book_id')}: {r.get('title', 'Unknown')}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
