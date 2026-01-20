"""
Main Teams Bot Handler.

Handles incoming activities from Microsoft Teams and routes them
to the appropriate handlers and dialogs.
"""

import logging
from typing import Optional

from botbuilder.core import (
    ActivityHandler,
    ConversationState,
    MessageFactory,
    TurnContext,
    UserState,
)
from botbuilder.dialogs import Dialog, DialogSet, DialogTurnStatus
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    Attachment,
    ChannelAccount,
)

from src.auth import UserIdentity
from src.agents import HRHelpdeskAgent
from src.config import get_settings

from .sso_dialog import SSODialog
from .adaptive_cards import (
    create_leave_balance_card,
    create_leave_history_card,
    create_leave_request_card,
    create_approval_card,
    create_welcome_card,
)

logger = logging.getLogger(__name__)


class HRHelpdeskBot(ActivityHandler):
    """
    Main bot handler for the HR Helpdesk.
    
    Handles:
    - Message activities (user messages)
    - Member added events (welcome messages)
    - Invoke activities (Adaptive Card submissions)
    - SSO token exchange
    """
    
    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
        hr_agent: HRHelpdeskAgent,
    ):
        """
        Initialize the bot.
        
        Args:
            conversation_state: Bot Framework conversation state
            user_state: Bot Framework user state
            hr_agent: The LangChain HR agent
        """
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.hr_agent = hr_agent
        self.settings = get_settings()
        
        # Dialog state accessor
        self.dialog_state = self.conversation_state.create_property("DialogState")
        
        # User profile accessor
        self.user_profile = self.user_state.create_property("UserProfile")
        
        # Initialize dialogs
        self.sso_dialog = SSODialog()
        self.dialogs = DialogSet(self.dialog_state)
        self.dialogs.add(self.sso_dialog)
    
    async def on_turn(self, turn_context: TurnContext) -> None:
        """
        Handle all incoming activities.
        
        Override to save state after each turn.
        """
        await super().on_turn(turn_context)
        
        # Save state changes
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)
    
    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """
        Handle incoming message activities.
        
        This is where user messages are processed.
        """
        # Get or establish user identity
        user_identity = await self._get_user_identity(turn_context)
        
        if not user_identity:
            # Need to authenticate
            await self._run_dialog(turn_context, self.sso_dialog)
            user_identity = await SSODialog.get_user_identity(turn_context)
            
            if not user_identity:
                await turn_context.send_activity(
                    "I couldn't identify you. Please try again."
                )
                return
        
        # Get message text
        message_text = turn_context.activity.text
        if not message_text:
            # Could be an Adaptive Card submission
            await self._handle_card_action(turn_context, user_identity)
            return
        
        # Show typing indicator
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        
        # Process message through the HR agent
        try:
            response = await self.hr_agent.process_message(
                message=message_text,
                user_identity=user_identity,
            )
            
            # Send response
            await self._send_response(turn_context, response)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await turn_context.send_activity(
                "I'm sorry, I encountered an error. Please try again."
            )
    
    async def on_members_added_activity(
        self,
        members_added: list[ChannelAccount],
        turn_context: TurnContext,
    ) -> None:
        """
        Handle members being added to the conversation.
        
        Send a welcome message when the bot is added.
        """
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                # This is a user, not the bot
                welcome_card = create_welcome_card(member.name or "there")
                await turn_context.send_activity(
                    MessageFactory.attachment(
                        Attachment(
                            content_type="application/vnd.microsoft.card.adaptive",
                            content=welcome_card,
                        )
                    )
                )
    
    async def on_token_response_event(self, turn_context: TurnContext) -> None:
        """
        Handle token response events from SSO.
        """
        await self._run_dialog(turn_context, self.sso_dialog)
    
    async def on_invoke_activity(self, turn_context: TurnContext):
        """
        Handle invoke activities (Adaptive Card actions).
        """
        if turn_context.activity.name == "adaptiveCard/action":
            # Handle Adaptive Card action
            user_identity = await self._get_user_identity(turn_context)
            if user_identity:
                await self._handle_card_action(turn_context, user_identity)
                return self._create_invoke_response(200)
        
        return await super().on_invoke_activity(turn_context)
    
    async def _get_user_identity(
        self,
        turn_context: TurnContext,
    ) -> Optional[UserIdentity]:
        """Get user identity from context or state."""
        # Try to get from turn state first
        identity = await SSODialog.get_user_identity(turn_context)
        
        if identity:
            # Store in user state for later
            profile = await self.user_profile.get(turn_context, dict)
            profile["identity"] = {
                "user_id": identity.user_id,
                "email": identity.email,
                "display_name": identity.display_name,
                "tenant_id": identity.tenant_id,
            }
        else:
            # Try to get from user state
            profile = await self.user_profile.get(turn_context, dict)
            if "identity" in profile:
                identity = UserIdentity(**profile["identity"], upn="")
        
        return identity
    
    async def _run_dialog(
        self,
        turn_context: TurnContext,
        dialog: Dialog,
    ) -> None:
        """Run a dialog."""
        dialog_context = await self.dialogs.create_context(turn_context)
        
        results = await dialog_context.continue_dialog()
        if results.status == DialogTurnStatus.Empty:
            await dialog_context.begin_dialog(dialog.id)
    
    async def _send_response(
        self,
        turn_context: TurnContext,
        response,
    ) -> None:
        """
        Send the agent response to the user.
        
        May include Adaptive Cards for structured display.
        """
        from src.agents.intent_classifier import UserIntent
        
        # Check if we should send an Adaptive Card
        if response.adaptive_card:
            await turn_context.send_activity(
                MessageFactory.attachment(
                    Attachment(
                        content_type="application/vnd.microsoft.card.adaptive",
                        content=response.adaptive_card,
                    )
                )
            )
        
        # Always send the text response
        await turn_context.send_activity(
            MessageFactory.text(response.content)
        )
    
    async def _handle_card_action(
        self,
        turn_context: TurnContext,
        user_identity: UserIdentity,
    ) -> None:
        """
        Handle Adaptive Card action submissions.
        """
        value = turn_context.activity.value
        if not value:
            return
        
        action = value.get("action")
        
        if action == "submit_leave_request":
            # Extract leave request data from card
            leave_type = value.get("leave_type")
            start_date = value.get("start_date")
            end_date = value.get("end_date")
            reason = value.get("reason")
            
            # Build message for agent
            message = (
                f"Submit leave request: {leave_type} from {start_date} to {end_date}. "
                f"Reason: {reason}"
            )
            
            response = await self.hr_agent.process_message(
                message=message,
                user_identity=user_identity,
            )
            await self._send_response(turn_context, response)
        
        elif action == "approve_leave":
            request_id = value.get("request_id")
            comments = value.get("comments", "")
            
            message = f"Approve leave request {request_id}. Comments: {comments}"
            
            response = await self.hr_agent.process_message(
                message=message,
                user_identity=user_identity,
            )
            await self._send_response(turn_context, response)
        
        elif action == "reject_leave":
            request_id = value.get("request_id")
            reason = value.get("reason", "No reason provided")
            
            message = f"Reject leave request {request_id}. Reason: {reason}"
            
            response = await self.hr_agent.process_message(
                message=message,
                user_identity=user_identity,
            )
            await self._send_response(turn_context, response)
        
        elif action == "check_balance":
            response = await self.hr_agent.process_message(
                message="Show my leave balance",
                user_identity=user_identity,
            )
            await self._send_response(turn_context, response)
        
        elif action == "apply_leave":
            # Show leave request form
            card = create_leave_request_card()
            await turn_context.send_activity(
                MessageFactory.attachment(
                    Attachment(
                        content_type="application/vnd.microsoft.card.adaptive",
                        content=card,
                    )
                )
            )
    
    def _create_invoke_response(self, status: int, body: dict = None):
        """Create an invoke response."""
        from botbuilder.schema import InvokeResponse
        return InvokeResponse(status=status, body=body)
