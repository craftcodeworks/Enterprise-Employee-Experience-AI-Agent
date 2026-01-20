"""
Teams SSO Authentication Dialog.

Handles Single Sign-On authentication flow for Microsoft Teams,
acquiring user tokens for identity verification.
"""

import logging
from typing import Optional

from botbuilder.core import (
    BotFrameworkAdapter,
    ConversationState,
    TurnContext,
    UserState,
)
from botbuilder.dialogs import (
    ComponentDialog,
    DialogTurnResult,
    DialogTurnStatus,
    OAuthPrompt,
    OAuthPromptSettings,
    WaterfallDialog,
    WaterfallStepContext,
)
from botbuilder.schema import TokenResponse

from src.auth import SSOHandler, UserIdentity
from src.config import get_settings

logger = logging.getLogger(__name__)


class SSODialog(ComponentDialog):
    """
    Dialog for handling Teams SSO authentication.
    
    This dialog uses the Bot Framework's OAuthPrompt to acquire
    a user token via Teams SSO. The token can then be validated
    to extract user identity.
    """
    
    CONNECTION_NAME_SETTING = "connection_name"
    
    def __init__(
        self,
        dialog_id: str = "SSODialog",
    ):
        """
        Initialize the SSO dialog.
        
        Args:
            dialog_id: Unique identifier for this dialog
        """
        super().__init__(dialog_id)
        
        self.settings = get_settings()
        self.sso_handler = SSOHandler()
        
        # Add OAuth prompt
        self.add_dialog(
            OAuthPrompt(
                "OAuthPrompt",
                OAuthPromptSettings(
                    connection_name=self.settings.oauth_connection_name,
                    text="Please sign in to continue.",
                    title="Sign In",
                    timeout=300000,  # 5 minutes
                ),
            )
        )
        
        # Add main waterfall dialog
        self.add_dialog(
            WaterfallDialog(
                "WaterfallDialog",
                [
                    self.prompt_step,
                    self.login_step,
                ],
            )
        )
        
        self.initial_dialog_id = "WaterfallDialog"
    
    async def prompt_step(
        self,
        step_context: WaterfallStepContext,
    ) -> DialogTurnResult:
        """
        First step: Prompt for OAuth login.
        
        In Teams, this typically happens silently via SSO.
        """
        return await step_context.begin_dialog("OAuthPrompt")
    
    async def login_step(
        self,
        step_context: WaterfallStepContext,
    ) -> DialogTurnResult:
        """
        Second step: Process the login result.
        
        Validates the token and extracts user identity.
        """
        token_response: Optional[TokenResponse] = step_context.result
        
        if token_response and token_response.token:
            # Validate token and extract identity
            user_identity = await self.sso_handler.validate_token(
                token_response.token
            )
            
            if user_identity:
                logger.info(f"SSO successful for: {user_identity.email}")
                # Store identity in turn state for later use
                step_context.context.turn_state["user_identity"] = user_identity
                return await step_context.end_dialog(user_identity)
            else:
                await step_context.context.send_activity(
                    "I couldn't verify your identity. Please try again."
                )
                return await step_context.end_dialog(None)
        else:
            await step_context.context.send_activity(
                "Login was not successful. Please try again."
            )
            return await step_context.end_dialog(None)
    
    @staticmethod
    async def get_user_identity(
        turn_context: TurnContext,
    ) -> Optional[UserIdentity]:
        """
        Get user identity from turn context or Teams activity.
        
        Attempts to extract identity from:
        1. Previously stored turn state
        2. Teams channel data
        3. Activity 'from' field
        
        Args:
            turn_context: Current turn context
            
        Returns:
            UserIdentity if available, None otherwise
        """
        # Check turn state first
        if "user_identity" in turn_context.turn_state:
            return turn_context.turn_state["user_identity"]
        
        # Try to extract from Teams channel data
        activity = turn_context.activity
        
        if activity.channel_id == "msteams":
            # Teams provides user info in the 'from' field
            from_user = activity.from_property
            
            if from_user:
                # Extract AAD object ID and name
                aad_id = from_user.aad_object_id
                name = from_user.name or "Unknown User"
                
                # In Teams, we can get email from channel data in some cases
                channel_data = activity.channel_data or {}
                tenant_id = channel_data.get("tenant", {}).get("id", "")
                
                # Create basic identity (will be enriched later)
                return UserIdentity(
                    user_id=aad_id or from_user.id,
                    email=name if "@" in name else f"{from_user.id}@teams.user",
                    display_name=name,
                    tenant_id=tenant_id,
                    upn=name if "@" in name else "",
                )
        
        return None
