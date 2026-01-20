"""
Main HR Helpdesk Agent using LangChain.

Orchestrates the conversation flow, tool execution, and response
generation for the HR helpdesk bot.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.config import get_settings
from src.auth import UserIdentity
from src.mcp_servers import (
    DataverseMCPServer,
    SharePointMCPServer,
    RAGMCPServer,
    MCPToolResult,
)

from .intent_classifier import IntentClassifier, UserIntent
from .prompts import HR_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """Tracks conversation state for multi-turn interactions."""
    
    user_identity: UserIdentity
    messages: list = field(default_factory=list)
    pending_leave_request: Optional[dict] = None
    context: dict = field(default_factory=dict)
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self.messages.append(HumanMessage(content=content))
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to history."""
        self.messages.append(AIMessage(content=content))
    
    def get_recent_messages(self, limit: int = 10) -> list:
        """Get the most recent messages."""
        return self.messages[-limit:] if len(self.messages) > limit else self.messages


@dataclass
class AgentResponse:
    """Response from the HR agent."""
    
    content: str
    intent: UserIntent
    tools_used: list[str] = field(default_factory=list)
    adaptive_card: Optional[dict] = None
    metadata: dict = field(default_factory=dict)


class HRHelpdeskAgent:
    """
    Main HR Helpdesk Agent.
    
    Orchestrates the conversation flow by:
    1. Classifying user intent
    2. Executing appropriate tools via MCP servers
    3. Generating natural language responses
    4. Managing multi-turn conversations for complex actions
    """
    
    def __init__(self):
        """Initialize the HR Helpdesk Agent."""
        self.settings = get_settings()
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            api_key=self.settings.openai_api_key.get_secret_value(),
            model=self.settings.openai_model,
            temperature=0.7,
        )
        
        # Initialize components
        self.intent_classifier = IntentClassifier()
        
        # Initialize MCP servers
        self.dataverse_server = DataverseMCPServer()
        self.sharepoint_server = SharePointMCPServer()
        self.rag_server = RAGMCPServer()
        
        # Build LangChain tools from MCP servers
        self.tools = self._build_tools()
        
        # Build the agent
        self.agent_executor = self._build_agent()
        
        # Conversation states (keyed by user ID)
        self.conversations: dict[str, ConversationState] = {}
    
    def _build_tools(self) -> list[StructuredTool]:
        """Build LangChain tools from MCP server tools."""
        tools = []
        
        # Get tools from all MCP servers
        all_mcp_tools = (
            self.dataverse_server.list_tools() +
            self.sharepoint_server.list_tools() +
            self.rag_server.list_tools()
        )
        
        for mcp_tool in all_mcp_tools:
            # Create a wrapper function for each tool
            async def tool_wrapper(mcp_t=mcp_tool, **kwargs) -> str:
                result = await mcp_t.execute(**kwargs)
                if result.is_success:
                    return str(result.data)
                else:
                    return f"Error: {result.error}"
            
            # Extract parameters for the tool
            tool_schema = mcp_tool.to_openai_function()
            
            # Create LangChain tool
            lc_tool = StructuredTool.from_function(
                coroutine=tool_wrapper,
                name=mcp_tool.name,
                description=mcp_tool.description,
                args_schema=self._create_args_schema(mcp_tool.parameters),
            )
            tools.append(lc_tool)
        
        logger.info(f"Built {len(tools)} LangChain tools from MCP servers")
        return tools
    
    def _create_args_schema(self, parameters: list) -> type:
        """Create a Pydantic model for tool arguments."""
        from pydantic import BaseModel, Field, create_model
        from typing import Optional
        
        fields = {}
        for param in parameters:
            field_type = str  # Default to string
            if param.type == "integer":
                field_type = int
            elif param.type == "boolean":
                field_type = bool
            elif param.type == "number":
                field_type = float
            
            if param.required:
                fields[param.name] = (field_type, Field(description=param.description))
            else:
                fields[param.name] = (Optional[field_type], Field(default=param.default, description=param.description))
        
        return create_model("ToolArgs", **fields)
    
    def _build_agent(self) -> AgentExecutor:
        """Build the LangChain agent executor."""
        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create the agent
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt,
        )
        
        # Create the executor
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
        )
    
    def get_or_create_conversation(
        self,
        user_identity: UserIdentity,
    ) -> ConversationState:
        """Get or create a conversation state for a user."""
        user_id = user_identity.user_id
        
        if user_id not in self.conversations:
            self.conversations[user_id] = ConversationState(
                user_identity=user_identity,
            )
        
        return self.conversations[user_id]
    
    def _build_system_prompt(
        self,
        state: ConversationState,
    ) -> str:
        """Build the system prompt with user context."""
        return HR_AGENT_SYSTEM_PROMPT.format(
            user_name=state.user_identity.display_name,
            user_email=state.user_identity.email,
            department=state.context.get("department", "Unknown"),
            designation=state.context.get("designation", "Unknown"),
            current_date=date.today().strftime("%Y-%m-%d (%A)"),
        )
    
    async def process_message(
        self,
        message: str,
        user_identity: UserIdentity,
    ) -> AgentResponse:
        """
        Process a user message and generate a response.
        
        Args:
            message: User's message text
            user_identity: Authenticated user identity
            
        Returns:
            AgentResponse with the assistant's reply
        """
        logger.info(f"Processing message from {user_identity.email}: {message[:100]}...")
        
        # Get conversation state
        state = self.get_or_create_conversation(user_identity)
        
        # Classify intent
        intent = await self.intent_classifier.classify(message)
        logger.debug(f"Classified intent: {intent.value}")
        
        # Handle simple greetings without tools
        if intent == UserIntent.GENERAL and self._is_greeting(message):
            response_content = self._generate_greeting_response(state)
            state.add_user_message(message)
            state.add_assistant_message(response_content)
            return AgentResponse(
                content=response_content,
                intent=intent,
            )
        
        # Add message to history
        state.add_user_message(message)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(state)
        
        # Run the agent
        try:
            result = await self.agent_executor.ainvoke({
                "system_prompt": system_prompt,
                "chat_history": state.get_recent_messages(limit=6),
                "input": message,
            })
            
            response_content = result.get("output", "I'm sorry, I couldn't process your request.")
            
            # Track tools used
            tools_used = []
            if "intermediate_steps" in result:
                for step in result["intermediate_steps"]:
                    if hasattr(step, "tool"):
                        tools_used.append(step.tool)
            
            # Add response to history
            state.add_assistant_message(response_content)
            
            # Check if we should generate an Adaptive Card
            adaptive_card = self._maybe_generate_adaptive_card(
                intent, response_content, result
            )
            
            return AgentResponse(
                content=response_content,
                intent=intent,
                tools_used=tools_used,
                adaptive_card=adaptive_card,
            )
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            error_response = (
                "I apologize, but I encountered an error processing your request. "
                "Please try again or contact IT support if the issue persists."
            )
            state.add_assistant_message(error_response)
            return AgentResponse(
                content=error_response,
                intent=intent,
                metadata={"error": str(e)},
            )
    
    def _is_greeting(self, message: str) -> bool:
        """Check if message is a simple greeting."""
        greetings = [
            "hi", "hello", "hey", "good morning", "good afternoon",
            "good evening", "howdy", "greetings", "what's up",
        ]
        normalized = message.lower().strip().rstrip("!")
        return normalized in greetings or len(message.split()) <= 2
    
    def _generate_greeting_response(self, state: ConversationState) -> str:
        """Generate a greeting response."""
        name = state.user_identity.display_name.split()[0]  # First name
        return (
            f"Hello {name}! 👋 Welcome to the HR Helpdesk.\n\n"
            "I can help you with:\n"
            "• 📋 Company policies and procedures\n"
            "• 📊 Leave balance and history\n"
            "• 📝 Leave applications\n"
            "• ✅ Approval workflows (for managers)\n\n"
            "How can I assist you today?"
        )
    
    def _maybe_generate_adaptive_card(
        self,
        intent: UserIntent,
        response: str,
        result: dict,
    ) -> Optional[dict]:
        """
        Generate an Adaptive Card for structured data display.
        
        For now, returns None - Adaptive Card templates are in the bot module.
        The bot layer will check intent and data to render appropriate cards.
        """
        # This will be handled by the bot layer which has access to
        # the adaptive card templates
        return None
    
    async def enrich_user_context(self, state: ConversationState) -> None:
        """
        Enrich the conversation state with user data from Dataverse.
        
        Called when a new conversation starts to load user profile.
        """
        if "enriched" in state.context:
            return
        
        try:
            result = await self.dataverse_server.execute_tool(
                "dataverse.get_employee_info",
                email=state.user_identity.email,
            )
            
            if result.is_success and result.data:
                state.context.update({
                    "department": result.data.get("department", "Unknown"),
                    "designation": result.data.get("designation", "Unknown"),
                    "employee_code": result.data.get("employee_code"),
                    "manager": result.data.get("manager"),
                    "enriched": True,
                })
                logger.debug(f"Enriched context for {state.user_identity.email}")
        except Exception as e:
            logger.warning(f"Failed to enrich user context: {e}")
            state.context["enriched"] = True  # Don't retry
    
    def clear_conversation(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        if user_id in self.conversations:
            del self.conversations[user_id]
            logger.debug(f"Cleared conversation for user {user_id}")
