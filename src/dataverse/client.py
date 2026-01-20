"""
Async Dataverse Web API client.

Provides authenticated access to Microsoft Dataverse using MSAL
for acquiring access tokens and httpx for async HTTP requests.
"""

import logging
from typing import Any, Optional
from uuid import UUID

import httpx
from msal import ConfidentialClientApplication
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings

logger = logging.getLogger(__name__)


class DataverseClient:
    """
    Async client for Microsoft Dataverse Web API.
    
    Uses MSAL for OAuth2 client credentials flow to authenticate
    and provides CRUD operations for Dataverse entities.
    """
    
    # Dataverse API scope for client credentials
    SCOPE = [".default"]
    
    def __init__(self):
        """Initialize the Dataverse client with settings."""
        self.settings = get_settings()
        self._msal_app: Optional[ConfidentialClientApplication] = None
        self._access_token: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def msal_app(self) -> ConfidentialClientApplication:
        """Get or create MSAL confidential client application."""
        if self._msal_app is None:
            authority = f"https://login.microsoftonline.com/{self.settings.dataverse_tenant_id}"
            self._msal_app = ConfidentialClientApplication(
                client_id=self.settings.dataverse_client_id,
                client_credential=self.settings.dataverse_client_secret.get_secret_value(),
                authority=authority,
            )
        return self._msal_app
    
    async def _get_access_token(self) -> str:
        """
        Acquire access token for Dataverse API.
        
        Uses MSAL token cache when possible.
        
        Returns:
            str: Valid access token
        """
        # Define the resource scope for Dataverse
        scope = [f"{self.settings.dataverse_url}/.default"]
        
        # Try to get token from cache first
        result = self.msal_app.acquire_token_silent(scope, account=None)
        
        if not result:
            # No cached token, acquire new one
            logger.debug("Acquiring new Dataverse access token")
            result = self.msal_app.acquire_token_for_client(scopes=scope)
        
        if "access_token" in result:
            return result["access_token"]
        else:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise Exception(f"Failed to acquire Dataverse token: {error}")
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """
        Get or create authenticated HTTP client.
        
        Note: In production, you should implement token refresh
        by checking token expiration time and refreshing before it expires.
        """
        if self._http_client is None or self._http_client.is_closed:
            token = await self._get_access_token()
            self._access_token = token
            self._http_client = httpx.AsyncClient(
                base_url=self.settings.dataverse_api_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "OData-MaxVersion": "4.0",
                    "OData-Version": "4.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json; charset=utf-8",
                    "Prefer": "return=representation",
                },
                timeout=30.0,
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
    async def get(
        self,
        entity_set: str,
        record_id: Optional[UUID] = None,
        select: Optional[list[str]] = None,
        expand: Optional[list[str]] = None,
        filter_query: Optional[str] = None,
        order_by: Optional[str] = None,
        top: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Retrieve records from a Dataverse entity set.
        
        Args:
            entity_set: Name of the entity set (e.g., "hr_employees")
            record_id: Optional specific record GUID
            select: Optional list of columns to select
            expand: Optional list of navigation properties to expand
            filter_query: Optional OData filter expression
            order_by: Optional OData orderby expression
            top: Optional limit on number of records
            
        Returns:
            dict: Response containing record(s)
        """
        client = await self._get_http_client()
        
        # Build URL
        url = f"/{entity_set}"
        if record_id:
            url += f"({record_id})"
        
        # Build query parameters
        params = {}
        if select:
            params["$select"] = ",".join(select)
        if expand:
            params["$expand"] = ",".join(expand)
        if filter_query:
            params["$filter"] = filter_query
        if order_by:
            params["$orderby"] = order_by
        if top:
            params["$top"] = str(top)
        
        logger.debug(f"Dataverse GET: {url} with params: {params}")
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def create(self, entity_set: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new record in a Dataverse entity set.
        
        Args:
            entity_set: Name of the entity set
            data: Record data to create
            
        Returns:
            dict: Created record with generated ID
        """
        client = await self._get_http_client()
        
        logger.debug(f"Dataverse CREATE: {entity_set}")
        
        response = await client.post(f"/{entity_set}", json=data)
        response.raise_for_status()
        
        return response.json()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def update(
        self,
        entity_set: str,
        record_id: UUID,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update an existing record in Dataverse.
        
        Args:
            entity_set: Name of the entity set
            record_id: GUID of the record to update
            data: Updated field values
            
        Returns:
            dict: Updated record
        """
        client = await self._get_http_client()
        
        url = f"/{entity_set}({record_id})"
        logger.debug(f"Dataverse UPDATE: {url}")
        
        response = await client.patch(url, json=data)
        response.raise_for_status()
        
        return response.json()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def delete(self, entity_set: str, record_id: UUID) -> bool:
        """
        Delete a record from Dataverse.
        
        Args:
            entity_set: Name of the entity set
            record_id: GUID of the record to delete
            
        Returns:
            bool: True if successfully deleted
        """
        client = await self._get_http_client()
        
        url = f"/{entity_set}({record_id})"
        logger.debug(f"Dataverse DELETE: {url}")
        
        response = await client.delete(url)
        response.raise_for_status()
        
        return True
    
    async def execute_function(
        self,
        function_name: str,
        parameters: Optional[dict[str, Any]] = None,
        entity_set: Optional[str] = None,
        record_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """
        Execute a Dataverse function.
        
        Args:
            function_name: Name of the function
            parameters: Function parameters
            entity_set: Optional entity set for bound functions
            record_id: Optional record ID for bound functions
            
        Returns:
            dict: Function result
        """
        client = await self._get_http_client()
        
        # Build URL for bound or unbound function
        if entity_set and record_id:
            url = f"/{entity_set}({record_id})/Microsoft.Dynamics.CRM.{function_name}"
        else:
            url = f"/{function_name}"
        
        # Add parameters to URL
        if parameters:
            param_str = ",".join(f"{k}=@{k}" for k in parameters.keys())
            url += f"({param_str})"
            params = {f"@{k}": str(v) for k, v in parameters.items()}
        else:
            params = {}
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
