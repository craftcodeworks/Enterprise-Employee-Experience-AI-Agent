"""
Azure AD Single Sign-On (SSO) handler for Teams authentication.

Provides user identity extraction and token validation for Teams SSO flow.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import jwt
from jwt import PyJWKClient

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class UserIdentity:
    """Represents an authenticated user from Azure AD."""
    
    user_id: str  # Azure AD Object ID
    email: str  # User's email address
    display_name: str  # User's display name
    tenant_id: str  # Azure AD Tenant ID
    upn: str  # User Principal Name
    
    def __str__(self) -> str:
        return f"{self.display_name} ({self.email})"


class SSOHandler:
    """
    Handles Azure AD SSO token validation and user identity extraction.
    
    This class validates JWT tokens from Teams SSO and extracts user information
    for identifying employees in the HR system.
    """
    
    # Microsoft identity platform JWKS endpoint
    JWKS_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    ISSUER_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/v2.0"
    
    def __init__(self):
        """Initialize the SSO handler with settings."""
        self.settings = get_settings()
        self._jwk_client: Optional[PyJWKClient] = None
    
    @property
    def jwks_url(self) -> str:
        """Get the JWKS URL for token validation."""
        return self.JWKS_URL_TEMPLATE.format(tenant_id=self.settings.azure_ad_tenant_id)
    
    @property
    def issuer(self) -> str:
        """Get the expected token issuer."""
        return self.ISSUER_TEMPLATE.format(tenant_id=self.settings.azure_ad_tenant_id)
    
    @property
    def jwk_client(self) -> PyJWKClient:
        """Get or create the JWK client for key retrieval."""
        if self._jwk_client is None:
            self._jwk_client = PyJWKClient(self.jwks_url)
        return self._jwk_client
    
    async def validate_token(self, token: str) -> Optional[UserIdentity]:
        """
        Validate a JWT token and extract user identity.
        
        Args:
            token: The JWT token from Teams SSO
            
        Returns:
            UserIdentity if token is valid, None otherwise
        """
        try:
            # Get the signing key from Microsoft's JWKS
            signing_key = self.jwk_client.get_signing_key_from_jwt(token)
            
            # Decode and validate the token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.azure_ad_client_id,
                issuer=self.issuer,
            )
            
            # Extract user identity from claims
            user_identity = UserIdentity(
                user_id=payload.get("oid", ""),  # Object ID
                email=payload.get("preferred_username", payload.get("email", "")),
                display_name=payload.get("name", ""),
                tenant_id=payload.get("tid", ""),
                upn=payload.get("upn", payload.get("preferred_username", "")),
            )
            
            logger.info(f"Successfully validated token for user: {user_identity.email}")
            return user_identity
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidAudienceError:
            logger.warning("Token has invalid audience")
            return None
        except jwt.InvalidIssuerError:
            logger.warning("Token has invalid issuer")
            return None
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return None
    
    def extract_identity_from_claims(self, claims: dict) -> UserIdentity:
        """
        Extract user identity from pre-validated token claims.
        
        This is used when the Bot Framework has already validated the token
        and provides the claims directly.
        
        Args:
            claims: Dictionary of token claims
            
        Returns:
            UserIdentity extracted from claims
        """
        return UserIdentity(
            user_id=claims.get("oid", claims.get("sub", "")),
            email=claims.get("preferred_username", claims.get("email", "")),
            display_name=claims.get("name", "Unknown User"),
            tenant_id=claims.get("tid", ""),
            upn=claims.get("upn", claims.get("preferred_username", "")),
        )
    
    @staticmethod
    def extract_email_from_activity(activity_from: dict) -> Optional[str]:
        """
        Extract email from Teams activity 'from' field.
        
        In Teams, the 'from' field contains the user's AAD object ID.
        We need to map this to email through our Dataverse records or
        use the token claims.
        
        Args:
            activity_from: The 'from' field from a Teams activity
            
        Returns:
            User's email if available
        """
        # Teams provides the AAD object ID in the 'aadObjectId' field
        aad_id = activity_from.get("aadObjectId")
        if aad_id:
            logger.debug(f"Found AAD Object ID: {aad_id}")
        
        # The name field might contain the email in some configurations
        name = activity_from.get("name", "")
        if "@" in name:
            return name
        
        return None
