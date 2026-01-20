"""
Microsoft Graph API client for SharePoint document access.

Provides access to SharePoint document libraries for fetching
HR policy documents to be indexed in the RAG pipeline.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from msal import ConfidentialClientApplication
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SharePointDocument:
    """Represents a document in SharePoint."""
    
    id: str
    name: str
    web_url: str
    download_url: str
    mime_type: str
    size: int
    created: datetime
    modified: datetime
    
    @property
    def is_pdf(self) -> bool:
        """Check if document is a PDF."""
        return self.mime_type == "application/pdf"
    
    @property
    def is_docx(self) -> bool:
        """Check if document is a Word document."""
        return self.mime_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        )
    
    @property
    def is_supported(self) -> bool:
        """Check if document type is supported for indexing."""
        return self.is_pdf or self.is_docx


class SharePointClient:
    """
    Client for accessing SharePoint via Microsoft Graph API.
    
    Uses MSAL for authentication and provides methods to list and
    download documents from SharePoint document libraries.
    """
    
    GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    
    def __init__(self):
        """Initialize the SharePoint client."""
        self.settings = get_settings()
        self._msal_app: Optional[ConfidentialClientApplication] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def msal_app(self) -> ConfidentialClientApplication:
        """Get or create MSAL confidential client application."""
        if self._msal_app is None:
            authority = f"https://login.microsoftonline.com/{self.settings.graph_tenant_id}"
            self._msal_app = ConfidentialClientApplication(
                client_id=self.settings.graph_client_id,
                client_credential=self.settings.graph_client_secret.get_secret_value(),
                authority=authority,
            )
        return self._msal_app
    
    async def _get_access_token(self) -> str:
        """Acquire access token for Graph API."""
        result = self.msal_app.acquire_token_silent(
            self.GRAPH_SCOPE, account=None
        )
        if not result:
            result = self.msal_app.acquire_token_for_client(scopes=self.GRAPH_SCOPE)
        
        if "access_token" in result:
            return result["access_token"]
        else:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise Exception(f"Failed to acquire Graph token: {error}")
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create authenticated HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            token = await self._get_access_token()
            self._http_client = httpx.AsyncClient(
                base_url=self.GRAPH_BASE_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=60.0,
            )
        return self._http_client
    
    async def close(self):
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def list_documents(
        self,
        folder_path: Optional[str] = None,
    ) -> list[SharePointDocument]:
        """
        List documents in the configured SharePoint document library.
        
        Args:
            folder_path: Optional subfolder path within the library.
                        If None, uses the configured folder path.
            
        Returns:
            List of SharePointDocument objects
        """
        client = await self._get_http_client()
        
        site_id = self.settings.sharepoint_site_id
        drive_id = self.settings.sharepoint_drive_id
        folder = folder_path or self.settings.sharepoint_folder_path
        
        # Build the Graph API URL for the folder
        if folder and folder != "/":
            # URL-encode the folder path
            folder_path_encoded = folder.lstrip("/")
            url = f"/sites/{site_id}/drives/{drive_id}/root:/{folder_path_encoded}:/children"
        else:
            url = f"/sites/{site_id}/drives/{drive_id}/root/children"
        
        logger.debug(f"Listing SharePoint documents: {url}")
        
        documents = []
        next_link = url
        
        while next_link:
            if next_link.startswith("http"):
                # It's a full URL from @odata.nextLink
                response = await client.get(next_link.replace(self.GRAPH_BASE_URL, ""))
            else:
                response = await client.get(next_link)
            
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("value", []):
                # Skip folders
                if "folder" in item:
                    continue
                
                # Parse document info
                doc = SharePointDocument(
                    id=item["id"],
                    name=item["name"],
                    web_url=item.get("webUrl", ""),
                    download_url=item.get("@microsoft.graph.downloadUrl", ""),
                    mime_type=item.get("file", {}).get("mimeType", ""),
                    size=item.get("size", 0),
                    created=datetime.fromisoformat(
                        item["createdDateTime"].replace("Z", "+00:00")
                    ),
                    modified=datetime.fromisoformat(
                        item["lastModifiedDateTime"].replace("Z", "+00:00")
                    ),
                )
                documents.append(doc)
            
            # Handle pagination
            next_link = data.get("@odata.nextLink")
        
        logger.info(f"Found {len(documents)} documents in SharePoint")
        return documents
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def download_document(self, document: SharePointDocument) -> bytes:
        """
        Download a document's content.
        
        Args:
            document: SharePointDocument to download
            
        Returns:
            Document content as bytes
        """
        if not document.download_url:
            # Need to get a fresh download URL
            client = await self._get_http_client()
            
            site_id = self.settings.sharepoint_site_id
            drive_id = self.settings.sharepoint_drive_id
            
            response = await client.get(
                f"/sites/{site_id}/drives/{drive_id}/items/{document.id}"
            )
            response.raise_for_status()
            data = response.json()
            document.download_url = data.get("@microsoft.graph.downloadUrl", "")
        
        if not document.download_url:
            raise ValueError(f"Could not get download URL for document {document.name}")
        
        logger.debug(f"Downloading document: {document.name}")
        
        # Download using a fresh client (download URL doesn't need auth)
        async with httpx.AsyncClient(timeout=120.0) as download_client:
            response = await download_client.get(document.download_url)
            response.raise_for_status()
            return response.content
    
    async def get_document_by_name(self, name: str) -> Optional[SharePointDocument]:
        """
        Find a document by name.
        
        Args:
            name: Document filename to search for
            
        Returns:
            SharePointDocument if found, None otherwise
        """
        documents = await self.list_documents()
        for doc in documents:
            if doc.name.lower() == name.lower():
                return doc
        return None
