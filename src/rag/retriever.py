"""
Vector retriever for Azure AI Search.

Performs semantic search against indexed policy documents
and returns relevant chunks for RAG.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from src.config import get_settings

from .embeddings import EmbeddingsGenerator

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Represents a retrieved document chunk."""
    
    id: str
    document_name: str
    content: str
    score: float
    source_url: str
    chunk_index: int
    
    def __str__(self) -> str:
        return f"[{self.document_name}] (score: {self.score:.3f})\n{self.content}"


class PolicyRetriever:
    """
    Retrieves relevant policy document chunks using vector search.
    
    Supports:
    - Pure vector (semantic) search
    - Hybrid search (combining vector + keyword)
    - Context expansion (fetching adjacent chunks)
    """
    
    def __init__(self):
        """Initialize the policy retriever."""
        self.settings = get_settings()
        self.embeddings = EmbeddingsGenerator()
        
        credential = AzureKeyCredential(
            self.settings.azure_search_api_key.get_secret_value()
        )
        self.search_client = SearchClient(
            endpoint=self.settings.azure_search_endpoint,
            index_name=self.settings.azure_search_index_name,
            credential=credential,
        )
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.7,
        document_filter: Optional[str] = None,
    ) -> list[RetrievalResult]:
        """
        Perform vector search for relevant policy content.
        
        Args:
            query: Natural language query
            top_k: Maximum number of results to return
            min_score: Minimum relevance score threshold
            document_filter: Optional document name filter
            
        Returns:
            List of relevant document chunks
        """
        logger.debug(f"Searching for: {query}")
        
        # Generate query embedding
        query_vector = await self.embeddings.generate_embedding(query)
        
        # Create vector query
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k * 2,  # Get more for filtering
            fields="content_vector",
        )
        
        # Build filter if specified (escape quotes to prevent injection)
        filter_expr = None
        if document_filter:
            safe_filter = document_filter.replace("'", "''")
            filter_expr = f"document_name eq '{safe_filter}'"
        
        # Execute search
        results = self.search_client.search(
            search_text=query,  # Enable hybrid search
            vector_queries=[vector_query],
            filter=filter_expr,
            select=["id", "document_name", "content", "source_url", "chunk_index"],
            top=top_k * 2,
        )
        
        # Process results
        retrieval_results = []
        for result in results:
            score = result.get("@search.score", 0)
            
            # Apply minimum score threshold
            if score < min_score:
                continue
            
            retrieval_results.append(
                RetrievalResult(
                    id=result["id"],
                    document_name=result["document_name"],
                    content=result["content"],
                    score=score,
                    source_url=result.get("source_url", ""),
                    chunk_index=result.get("chunk_index", 0),
                )
            )
            
            if len(retrieval_results) >= top_k:
                break
        
        logger.info(f"Found {len(retrieval_results)} relevant chunks for query")
        return retrieval_results
    
    async def search_with_context(
        self,
        query: str,
        top_k: int = 3,
        context_chunks: int = 1,
    ) -> list[RetrievalResult]:
        """
        Search with context expansion.
        
        For each matched chunk, also retrieves adjacent chunks
        to provide more context.
        
        Args:
            query: Natural language query
            top_k: Number of primary results
            context_chunks: Number of chunks before/after to include
            
        Returns:
            List of chunks with expanded context
        """
        # Get primary results
        results = await self.search(query, top_k=top_k)
        
        if not results or context_chunks == 0:
            return results
        
        # Group by document
        docs_chunks: dict[str, list[int]] = {}
        for result in results:
            doc_name = result.document_name
            if doc_name not in docs_chunks:
                docs_chunks[doc_name] = []
            docs_chunks[doc_name].append(result.chunk_index)
        
        # Expand to include adjacent chunks
        expanded_results = list(results)
        
        for doc_name, chunk_indices in docs_chunks.items():
            # Determine which additional chunks to fetch
            additional_indices = set()
            for idx in chunk_indices:
                for offset in range(-context_chunks, context_chunks + 1):
                    new_idx = idx + offset
                    if new_idx >= 0 and new_idx not in chunk_indices:
                        additional_indices.add(new_idx)
            
            if additional_indices:
                # Fetch additional chunks
                idx_filter = " or ".join(
                    f"chunk_index eq {i}" for i in additional_indices
                )
                filter_expr = f"document_name eq '{doc_name}' and ({idx_filter})"
                
                additional_results = self.search_client.search(
                    search_text="*",
                    filter=filter_expr,
                    select=["id", "document_name", "content", "source_url", "chunk_index"],
                )
                
                for result in additional_results:
                    expanded_results.append(
                        RetrievalResult(
                            id=result["id"],
                            document_name=result["document_name"],
                            content=result["content"],
                            score=0.5,  # Lower score for context chunks
                            source_url=result.get("source_url", ""),
                            chunk_index=result.get("chunk_index", 0),
                        )
                    )
        
        # Sort by document and chunk index for coherent reading
        expanded_results.sort(
            key=lambda x: (x.document_name, x.chunk_index)
        )
        
        return expanded_results
    
    async def get_document_chunks(
        self,
        document_name: str,
        max_chunks: int = 50,
    ) -> list[RetrievalResult]:
        """
        Get all chunks from a specific document.
        
        Args:
            document_name: Name of the document
            max_chunks: Maximum chunks to return
            
        Returns:
            All chunks from the document in order
        """
        results = self.search_client.search(
            search_text="*",
            filter=f"document_name eq '{document_name}'",
            select=["id", "document_name", "content", "source_url", "chunk_index"],
            order_by=["chunk_index asc"],
            top=max_chunks,
        )
        
        return [
            RetrievalResult(
                id=r["id"],
                document_name=r["document_name"],
                content=r["content"],
                score=1.0,
                source_url=r.get("source_url", ""),
                chunk_index=r.get("chunk_index", 0),
            )
            for r in results
        ]
    
    def format_context(
        self,
        results: list[RetrievalResult],
        include_sources: bool = True,
    ) -> str:
        """
        Format retrieval results as context for the LLM.
        
        Args:
            results: List of retrieval results
            include_sources: Whether to include source citations
            
        Returns:
            Formatted context string
        """
        if not results:
            return "No relevant policy information found."
        
        context_parts = []
        
        # Group by document for cleaner formatting
        current_doc = None
        for result in results:
            if result.document_name != current_doc:
                current_doc = result.document_name
                context_parts.append(f"\n📄 **{current_doc}**")
            
            context_parts.append(result.content)
        
        context = "\n\n".join(context_parts)
        
        if include_sources:
            # Add source citations
            unique_docs = {r.document_name: r.source_url for r in results}
            sources = "\n".join(
                f"- [{name}]({url})" for name, url in unique_docs.items()
            )
            context += f"\n\n**Sources:**\n{sources}"
        
        return context
