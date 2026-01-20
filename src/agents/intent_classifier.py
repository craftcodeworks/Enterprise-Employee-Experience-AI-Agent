"""
Intent classifier for routing user queries.

Classifies incoming messages to determine the appropriate
handling strategy and tools to use.
"""

import logging
from enum import Enum
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings

from .prompts import INTENT_CLASSIFIER_PROMPT

logger = logging.getLogger(__name__)


class UserIntent(Enum):
    """Classified intent categories."""
    
    POLICY_QUERY = "policy_query"
    PERSONAL_DATA = "personal_data"
    LEAVE_ACTION = "leave_action"
    APPROVAL_ACTION = "approval_action"
    GENERAL = "general"
    
    @classmethod
    def from_string(cls, value: str) -> "UserIntent":
        """Convert string to UserIntent enum."""
        mapping = {
            "POLICY_QUERY": cls.POLICY_QUERY,
            "PERSONAL_DATA": cls.PERSONAL_DATA,
            "LEAVE_ACTION": cls.LEAVE_ACTION,
            "APPROVAL_ACTION": cls.APPROVAL_ACTION,
            "GENERAL": cls.GENERAL,
        }
        return mapping.get(value.upper().strip(), cls.GENERAL)


class IntentClassifier:
    """
    Classifies user messages to determine query intent.
    
    Uses a lightweight LLM call to classify messages into
    categories that determine which tools to use.
    """
    
    def __init__(self):
        """Initialize the intent classifier."""
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            api_key=self.settings.openai_api_key.get_secret_value(),
            model="gpt-4o-mini",  # Use smaller model for classification
            temperature=0,
            max_tokens=50,
        )
    
    async def classify(self, message: str) -> UserIntent:
        """
        Classify a user message.
        
        Args:
            message: User's message text
            
        Returns:
            Classified UserIntent
        """
        try:
            prompt = INTENT_CLASSIFIER_PROMPT.format(message=message)
            
            response = await self.llm.ainvoke([
                HumanMessage(content=prompt)
            ])
            
            intent_str = response.content.strip().upper()
            intent = UserIntent.from_string(intent_str)
            
            logger.debug(f"Classified message as: {intent.value}")
            return intent
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            # Default to GENERAL on error
            return UserIntent.GENERAL
    
    def get_recommended_tools(self, intent: UserIntent) -> list[str]:
        """
        Get recommended tool names for an intent.
        
        Args:
            intent: Classified user intent
            
        Returns:
            List of tool names to consider
        """
        tool_mapping = {
            UserIntent.POLICY_QUERY: [
                "rag.search_policies",
                "rag.get_policy_context",
                "sharepoint.list_policy_documents",
            ],
            UserIntent.PERSONAL_DATA: [
                "dataverse.get_employee_info",
                "dataverse.get_leave_balance",
                "dataverse.get_leave_history",
            ],
            UserIntent.LEAVE_ACTION: [
                "dataverse.get_leave_balance",
                "dataverse.submit_leave_request",
            ],
            UserIntent.APPROVAL_ACTION: [
                "dataverse.get_pending_approvals",
                "dataverse.approve_leave_request",
                "dataverse.reject_leave_request",
            ],
            UserIntent.GENERAL: [],
        }
        return tool_mapping.get(intent, [])
