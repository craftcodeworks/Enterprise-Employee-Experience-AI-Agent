"""
AI-Powered Employee Helpdesk Agent for Microsoft Teams

Main FastAPI application entry point.
"""

import logging
import sys
from contextlib import asynccontextmanager

from aiohttp import web
from aiohttp.web import Request, Response
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    MemoryStorage,
    UserState,
)
from botbuilder.schema import Activity

from src.config import get_settings
from src.agents import HRHelpdeskAgent
from src.bot import HRHelpdeskBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class Application:
    """Main application class."""
    
    def __init__(self):
        """Initialize the application."""
        self.settings = get_settings()
        
        # Set logging level
        logging.getLogger().setLevel(self.settings.log_level)
        
        # Initialize Bot Framework adapter
        adapter_settings = BotFrameworkAdapterSettings(
            app_id=self.settings.microsoft_app_id,
            app_password=self.settings.microsoft_app_password.get_secret_value(),
        )
        self.adapter = BotFrameworkAdapter(adapter_settings)
        
        # Error handler
        async def on_error(context, error):
            logger.error(f"Bot error: {error}", exc_info=True)
            await context.send_activity(
                "I'm sorry, something went wrong. Please try again."
            )
        
        self.adapter.on_turn_error = on_error
        
        # Initialize storage
        # WARNING: MemoryStorage is for development only!
        # For production, use Azure Blob Storage or Cosmos DB:
        # from botbuilder.azure import BlobStorage, CosmosDbPartitionedStorage
        # storage = CosmosDbPartitionedStorage(cosmos_db_config)
        storage = MemoryStorage()
        
        # Initialize states
        self.conversation_state = ConversationState(storage)
        self.user_state = UserState(storage)
        
        # Initialize HR Agent
        self.hr_agent = HRHelpdeskAgent()
        
        # Initialize Bot
        self.bot = HRHelpdeskBot(
            conversation_state=self.conversation_state,
            user_state=self.user_state,
            hr_agent=self.hr_agent,
        )
        
        logger.info("Application initialized successfully")
    
    async def messages_handler(self, request: Request) -> Response:
        """
        Handle incoming messages from Bot Framework.
        
        This is the main webhook endpoint that receives activities
        from Microsoft Teams.
        """
        if "application/json" not in request.headers.get("Content-Type", ""):
            return Response(status=415)
        
        body = await request.json()
        activity = Activity().deserialize(body)
        auth_header = request.headers.get("Authorization", "")
        
        try:
            response = await self.adapter.process_activity(
                activity, auth_header, self.bot.on_turn
            )
            
            if response:
                return Response(
                    body=response.body,
                    status=response.status,
                    content_type="application/json",
                )
            
            return Response(status=201)
            
        except Exception as e:
            logger.error(f"Error processing activity: {e}", exc_info=True)
            return Response(status=500)
    
    async def health_handler(self, request: Request) -> Response:
        """Health check endpoint."""
        return Response(
            text='{"status": "healthy", "service": "hr-helpdesk-agent"}',
            content_type="application/json",
        )
    
    def create_app(self) -> web.Application:
        """Create the aiohttp web application."""
        app = web.Application()
        
        # Add routes
        app.router.add_post("/api/messages", self.messages_handler)
        app.router.add_get("/health", self.health_handler)
        app.router.add_get("/", self.health_handler)
        
        return app


def main():
    """Main entry point."""
    try:
        settings = get_settings()
        application = Application()
        app = application.create_app()
        
        logger.info(f"Starting HR Helpdesk Agent on {settings.host}:{settings.port}")
        
        web.run_app(
            app,
            host=settings.host,
            port=settings.port,
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
