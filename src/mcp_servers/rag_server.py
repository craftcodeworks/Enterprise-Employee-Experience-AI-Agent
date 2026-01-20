"""
RAG MCP Server for policy document search.

Provides tools for semantic search against indexed policy
documents using the RAG pipeline.
"""

import logging
from typing import Optional

from src.rag import PolicyRetriever

from .base import MCPServer, MCPToolParameter, MCPToolResult

logger = logging.getLogger(__name__)


class RAGMCPServer(MCPServer):
    """
    MCP Server for RAG (Retrieval Augmented Generation) operations.
    
    Provides tools for:
    - Semantic search over policy documents
    - Getting policy context with expanded context
    """
    
    def __init__(self):
        """Initialize the RAG MCP server."""
        self.retriever = PolicyRetriever()
        super().__init__(
            name="rag",
            description="Policy document search and retrieval server"
        )
    
    def _register_tools(self) -> None:
        """Register all RAG tools."""
        
        # Search Policies
        self.register_tool(
            name="search_policies",
            description=(
                "Search HR policy documents using natural language. "
                "Use this to answer questions about company policies, "
                "procedures, guidelines, and rules. Returns relevant excerpts "
                "from policy documents."
            ),
            parameters=[
                MCPToolParameter(
                    name="query",
                    description="Natural language query about policies",
                    type="string",
                ),
                MCPToolParameter(
                    name="top_k",
                    description="Number of results to return (default: 5)",
                    type="integer",
                    required=False,
                    default=5,
                ),
                MCPToolParameter(
                    name="document_filter",
                    description="Optional: filter to a specific document name",
                    type="string",
                    required=False,
                ),
            ],
            handler=self._search_policies,
        )
        
        # Get Policy Context
        self.register_tool(
            name="get_policy_context",
            description=(
                "Get expanded context around a policy topic. "
                "Similar to search_policies but includes adjacent sections "
                "for more complete context."
            ),
            parameters=[
                MCPToolParameter(
                    name="query",
                    description="Natural language query about policies",
                    type="string",
                ),
                MCPToolParameter(
                    name="top_k",
                    description="Number of primary results (default: 3)",
                    type="integer",
                    required=False,
                    default=3,
                ),
            ],
            handler=self._get_policy_context,
        )
        
        # Get Document Summary
        self.register_tool(
            name="get_document_summary",
            description=(
                "Get a summary view of a specific policy document's contents. "
                "Use this when someone asks about what a specific document covers."
            ),
            parameters=[
                MCPToolParameter(
                    name="document_name",
                    description="Name of the policy document",
                    type="string",
                ),
            ],
            handler=self._get_document_summary,
        )
    
    async def _search_policies(
        self,
        query: str,
        top_k: int = 5,
        document_filter: Optional[str] = None,
    ) -> MCPToolResult:
        """Search policy documents."""
        try:
            results = await self.retriever.search(
                query=query,
                top_k=top_k,
                document_filter=document_filter,
            )
            
            if not results:
                return MCPToolResult.success({
                    "found": False,
                    "message": (
                        "No relevant policy information found for your query. "
                        "Try rephrasing your question or ask about a different topic."
                    ),
                    "results": [],
                })
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "document": result.document_name,
                    "content": result.content,
                    "relevance_score": round(result.score, 3),
                    "source_url": result.source_url,
                })
            
            # Create formatted context for LLM
            context = self.retriever.format_context(results)
            
            return MCPToolResult.success({
                "found": True,
                "query": query,
                "result_count": len(formatted_results),
                "context": context,
                "results": formatted_results,
            })
            
        except Exception as e:
            logger.error(f"Failed to search policies: {e}")
            return MCPToolResult.error(str(e))
    
    async def _get_policy_context(
        self,
        query: str,
        top_k: int = 3,
    ) -> MCPToolResult:
        """Get expanded policy context."""
        try:
            results = await self.retriever.search_with_context(
                query=query,
                top_k=top_k,
                context_chunks=1,  # Include 1 chunk before/after
            )
            
            if not results:
                return MCPToolResult.success({
                    "found": False,
                    "message": "No relevant policy information found.",
                    "context": "",
                })
            
            # Format the expanded context
            context = self.retriever.format_context(results, include_sources=True)
            
            # Group by document
            docs_mentioned = list(set(r.document_name for r in results))
            
            return MCPToolResult.success({
                "found": True,
                "query": query,
                "documents_referenced": docs_mentioned,
                "context": context,
            })
            
        except Exception as e:
            logger.error(f"Failed to get policy context: {e}")
            return MCPToolResult.error(str(e))
    
    async def _get_document_summary(
        self,
        document_name: str,
    ) -> MCPToolResult:
        """Get a summary of a specific document."""
        try:
            # Get all chunks from the document
            chunks = await self.retriever.get_document_chunks(
                document_name=document_name,
                max_chunks=10,  # Get first 10 chunks for summary
            )
            
            if not chunks:
                return MCPToolResult.error(
                    f"Document not found or not indexed: {document_name}. "
                    "Make sure the document has been indexed."
                )
            
            # Combine chunk contents for summary
            full_text = "\n\n".join(chunk.content for chunk in chunks[:5])
            
            return MCPToolResult.success({
                "document_name": document_name,
                "chunk_count": len(chunks),
                "source_url": chunks[0].source_url if chunks else "",
                "content_preview": full_text[:2000] + ("..." if len(full_text) > 2000 else ""),
                "message": (
                    f"Found {len(chunks)} sections in {document_name}. "
                    "Showing preview of the document content."
                ),
            })
            
        except Exception as e:
            logger.error(f"Failed to get document summary: {e}")
            return MCPToolResult.error(str(e))
