"""
Application settings management using Pydantic Settings.

Loads configuration from environment variables with type validation.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Azure Bot Service
    # =========================================================================
    microsoft_app_id: str = Field(
        ..., description="Microsoft Bot App ID from Azure Bot Service"
    )
    microsoft_app_password: SecretStr = Field(
        ..., description="Microsoft Bot App Password"
    )
    microsoft_app_tenant_id: str = Field(
        ..., description="Azure AD Tenant ID for the bot"
    )

    # =========================================================================
    # Azure AD / Entra ID (SSO)
    # =========================================================================
    azure_ad_client_id: str = Field(
        ..., description="Azure AD App Registration Client ID for SSO"
    )
    azure_ad_client_secret: SecretStr = Field(
        ..., description="Azure AD App Registration Client Secret"
    )
    azure_ad_tenant_id: str = Field(..., description="Azure AD Tenant ID")
    oauth_connection_name: str = Field(
        default="AzureADConnection",
        description="OAuth connection name configured in Bot Service",
    )

    # =========================================================================
    # OpenAI
    # =========================================================================
    openai_api_key: SecretStr = Field(..., description="OpenAI API Key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model for chat")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI model for embeddings"
    )

    # =========================================================================
    # Azure AI Search
    # =========================================================================
    azure_search_endpoint: str = Field(
        ..., description="Azure AI Search service endpoint"
    )
    azure_search_api_key: SecretStr = Field(
        ..., description="Azure AI Search admin API key"
    )
    azure_search_index_name: str = Field(
        default="hr-policies", description="Azure AI Search index name for HR policies"
    )

    # =========================================================================
    # Microsoft Dataverse
    # =========================================================================
    dataverse_url: str = Field(
        ..., description="Dataverse environment URL (e.g., https://org.crm.dynamics.com)"
    )
    dataverse_client_id: str = Field(
        ..., description="App registration Client ID for Dataverse access"
    )
    dataverse_client_secret: SecretStr = Field(
        ..., description="App registration Client Secret for Dataverse access"
    )
    dataverse_tenant_id: str = Field(..., description="Tenant ID for Dataverse")

    # =========================================================================
    # Microsoft Graph / SharePoint
    # =========================================================================
    graph_client_id: str = Field(
        ..., description="App registration Client ID for Graph API"
    )
    graph_client_secret: SecretStr = Field(
        ..., description="App registration Client Secret for Graph API"
    )
    graph_tenant_id: str = Field(..., description="Tenant ID for Graph API")
    sharepoint_site_id: str = Field(..., description="SharePoint site ID")
    sharepoint_drive_id: str = Field(
        ..., description="SharePoint document library drive ID"
    )
    sharepoint_folder_path: str = Field(
        default="/HR Policies", description="Folder path containing HR policy documents"
    )

    # =========================================================================
    # Application Settings
    # =========================================================================
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Application environment"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=3978, description="Server port")

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def graph_api_base_url(self) -> str:
        """Microsoft Graph API base URL."""
        return "https://graph.microsoft.com/v1.0"

    @property
    def dataverse_api_url(self) -> str:
        """Dataverse Web API URL."""
        base = self.dataverse_url.rstrip("/")
        return f"{base}/api/data/v9.2"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Returns:
        Settings: Application configuration instance
    """
    return Settings()
