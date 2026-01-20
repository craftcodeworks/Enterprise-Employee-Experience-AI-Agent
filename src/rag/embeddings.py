"""
OpenAI embeddings generator for RAG pipeline.

Provides text embedding generation using OpenAI's embedding models
for both document indexing and query processing.
"""

import logging
from typing import Optional

import tiktoken
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingsGenerator:
    """
    Generates text embeddings using OpenAI's embedding API.
    
    Handles text chunking, token counting, and batch processing
    for efficient embedding generation.
    """
    
    # Token limits for embedding models
    MODEL_TOKEN_LIMITS = {
        "text-embedding-3-small": 8191,
        "text-embedding-3-large": 8191,
        "text-embedding-ada-002": 8191,
    }
    
    # Embedding dimensions
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }
    
    def __init__(self):
        """Initialize the embeddings generator."""
        self.settings = get_settings()
        self.model = self.settings.openai_embedding_model
        self._client: Optional[AsyncOpenAI] = None
        self._encoding: Optional[tiktoken.Encoding] = None
    
    @property
    def client(self) -> AsyncOpenAI:
        """Get or create async OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )
        return self._client
    
    @property
    def encoding(self) -> tiktoken.Encoding:
        """Get or create tiktoken encoding for the model."""
        if self._encoding is None:
            try:
                self._encoding = tiktoken.encoding_for_model(self.model)
            except KeyError:
                # Fallback for newer models
                self._encoding = tiktoken.get_encoding("cl100k_base")
        return self._encoding
    
    @property
    def token_limit(self) -> int:
        """Get token limit for the current model."""
        return self.MODEL_TOKEN_LIMITS.get(self.model, 8191)
    
    @property
    def dimensions(self) -> int:
        """Get embedding dimensions for the current model."""
        return self.MODEL_DIMENSIONS.get(self.model, 1536)
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))
    
    def truncate_to_token_limit(self, text: str, max_tokens: Optional[int] = None) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum tokens (defaults to model limit)
            
        Returns:
            Truncated text
        """
        max_tokens = max_tokens or self.token_limit
        tokens = self.encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return self.encoding.decode(truncated_tokens)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        # Ensure text is within token limits
        text = self.truncate_to_token_limit(text)
        
        if not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimensions
        
        logger.debug(f"Generating embedding for text ({self.count_tokens(text)} tokens)")
        
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        
        return response.data[0].embedding
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call
            
        Returns:
            List of embedding vectors
        """
        # Preprocess texts
        processed_texts = []
        for text in texts:
            truncated = self.truncate_to_token_limit(text)
            if truncated.strip():
                processed_texts.append(truncated)
            else:
                processed_texts.append(" ")  # Placeholder for empty texts
        
        embeddings = []
        
        for i in range(0, len(processed_texts), batch_size):
            batch = processed_texts[i:i + batch_size]
            
            logger.debug(f"Generating embeddings batch {i // batch_size + 1}")
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=batch,
            )
            
            # Sort by index to maintain order
            batch_embeddings = sorted(response.data, key=lambda x: x.index)
            embeddings.extend([e.embedding for e in batch_embeddings])
        
        return embeddings
