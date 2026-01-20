"""
Script to index SharePoint documents to Azure AI Search.

Run this script to initially populate the vector index with
HR policy documents from SharePoint.

Usage:
    python scripts/index_documents.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.rag import DocumentIndexer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to index documents."""
    logger.info("Starting document indexing...")
    
    try:
        # Initialize settings to validate configuration
        settings = get_settings()
        logger.info(f"Using Azure AI Search index: {settings.azure_search_index_name}")
        logger.info(f"SharePoint folder: {settings.sharepoint_folder_path}")
        
        # Initialize indexer
        indexer = DocumentIndexer()
        
        # Index all documents
        results = await indexer.index_all_documents()
        
        # Print results
        logger.info("\n" + "=" * 50)
        logger.info("INDEXING COMPLETE")
        logger.info("=" * 50)
        
        total_chunks = 0
        for doc_name, chunk_count in results.items():
            status = "✅" if chunk_count > 0 else "❌"
            logger.info(f"{status} {doc_name}: {chunk_count} chunks")
            total_chunks += chunk_count
        
        logger.info("-" * 50)
        logger.info(f"Total documents processed: {len(results)}")
        logger.info(f"Total chunks indexed: {total_chunks}")
        
    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        await indexer.sharepoint.close()


if __name__ == "__main__":
    asyncio.run(main())
