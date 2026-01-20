"""
SharePoint MCP Server for document operations.

Provides tools for listing and retrieving policy documents
from SharePoint document libraries.
"""

import logging
from typing import Optional

from src.sharepoint import SharePointClient

from .base import MCPServer, MCPToolParameter, MCPToolResult

logger = logging.getLogger(__name__)


class SharePointMCPServer(MCPServer):
    """
    MCP Server for SharePoint document operations.
    
    Provides tools for:
    - Listing policy documents
    - Getting document content/metadata
    """
    
    def __init__(self):
        """Initialize the SharePoint MCP server."""
        self.client = SharePointClient()
        super().__init__(
            name="sharepoint",
            description="SharePoint document operations server for HR policies"
        )
    
    def _register_tools(self) -> None:
        """Register all SharePoint tools."""
        
        # List Policy Documents
        self.register_tool(
            name="list_policy_documents",
            description=(
                "List all available HR policy documents in the SharePoint library. "
                "Returns document names, types, and modification dates."
            ),
            parameters=[
                MCPToolParameter(
                    name="folder_path",
                    description="Optional subfolder path within HR Policies folder",
                    type="string",
                    required=False,
                ),
            ],
            handler=self._list_policy_documents,
        )
        
        # Get Document Info
        self.register_tool(
            name="get_document_info",
            description=(
                "Get detailed information about a specific policy document "
                "including its URL for viewing."
            ),
            parameters=[
                MCPToolParameter(
                    name="document_name",
                    description="Name of the document to get info for",
                    type="string",
                ),
            ],
            handler=self._get_document_info,
        )
    
    async def _list_policy_documents(
        self,
        folder_path: Optional[str] = None,
    ) -> MCPToolResult:
        """List all policy documents in SharePoint."""
        try:
            documents = await self.client.list_documents(folder_path)
            
            if not documents:
                return MCPToolResult.success({
                    "count": 0,
                    "documents": [],
                    "message": "No documents found in the specified location.",
                })
            
            doc_list = []
            for doc in documents:
                doc_list.append({
                    "name": doc.name,
                    "type": "PDF" if doc.is_pdf else ("Word" if doc.is_docx else "Other"),
                    "size_kb": round(doc.size / 1024, 1),
                    "modified": doc.modified.isoformat(),
                    "url": doc.web_url,
                })
            
            return MCPToolResult.success({
                "count": len(doc_list),
                "documents": doc_list,
            })
            
        except Exception as e:
            logger.error(f"Failed to list SharePoint documents: {e}")
            return MCPToolResult.error(str(e))
    
    async def _get_document_info(self, document_name: str) -> MCPToolResult:
        """Get detailed info about a specific document."""
        try:
            document = await self.client.get_document_by_name(document_name)
            
            if not document:
                return MCPToolResult.error(
                    f"Document not found: {document_name}. "
                    "Use list_policy_documents to see available documents."
                )
            
            return MCPToolResult.success({
                "name": document.name,
                "id": document.id,
                "type": "PDF" if document.is_pdf else ("Word" if document.is_docx else "Other"),
                "size_kb": round(document.size / 1024, 1),
                "created": document.created.isoformat(),
                "modified": document.modified.isoformat(),
                "url": document.web_url,
                "message": f"You can view this document at: {document.web_url}",
            })
            
        except Exception as e:
            logger.error(f"Failed to get document info: {e}")
            return MCPToolResult.error(str(e))
