import os
import json
from pathlib import Path
from typing import Optional, Literal, Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Import the new Universal Schema
# This ensures all Agents have access to Entity, Relationship, etc.
from writeros.schema import Entity, Relationship, Fact, EntityType, CanonInfo

# Import the custom LLM client with function calling support
from writeros.utils.llm_client import LLMClient

# Setup Environment
load_dotenv()

# Setup Logging
from writeros.core.logging import get_logger
logger = get_logger(__name__)

# --- BASE OUTPUT SCHEMA ---
class BaseAgentOutput(BaseModel):
    verdict: Literal["FEASIBLE", "IMPOSSIBLE", "CONDITIONAL", "INSUFFICIENT_DATA"]
    reasoning: str = Field(..., description="Explanation of the verdict")
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    missing_info: Optional[str] = Field(None, description="What info is needed if verdict is INSUFFICIENT_DATA")

class BaseAgent:
    # ✅ UPDATED: Default is now 'gpt-5.1' (The SOTA Thinking Model)
    def __init__(self, model_name="gpt-5.1"):
        self.model_name = model_name
        self.agent_name = self.__class__.__name__
        self.log = logger.bind(agent=self.agent_name)

        # Ensure API Key exists
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.log.error("api_key_missing", env_var="OPENAI_API_KEY")
            raise ValueError("OPENAI_API_KEY is missing.")

        # Initialize the LLM with function calling support
        # This is the brain that all agents share
        self.llm = LLMClient(
            model_name=self.model_name,
            temperature=0.7,  # 0.7 works well with 5.1 for creative+logic balance
            api_key=api_key
        )
        
        # Load Data Cache
        self.data_cache: Dict[str, Any] = {}

        self.log.info("agent_initialized", model=self.model_name)

    def load_data(self, filename: str) -> Any:
        """
        Loads a JSON data file from src/writeros/data.
        Uses caching to avoid repeated I/O.
        """
        if filename in self.data_cache:
            return self.data_cache[filename]
            
        # Construct path relative to this file
        # Assumes this file is in src/writeros/agents/base.py
        # Data is in src/writeros/data/
        base_dir = Path(__file__).parent.parent
        data_path = base_dir / "data" / filename
        
        if not data_path.exists():
            self.log.error("data_file_missing", path=str(data_path))
            return None
            
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.data_cache[filename] = data
                return data
        except json.JSONDecodeError as e:
            self.log.error("data_file_malformed", path=str(data_path), error=str(e))
            return None

    async def should_respond(self, query: str, context: str = "") -> tuple[bool, float, str]:
        """
        Determines if this agent should respond to the query.
        
        This enables agent autonomy - agents can opt-out of irrelevant queries.
        Subclasses should override this to implement domain-specific relevance checks.
        
        Args:
            query: The user's query
            context: Additional context from RAG or previous messages
            
        Returns:
            tuple: (should_respond, confidence, reasoning)
                - should_respond (bool): Whether agent wants to respond
                - confidence (float): 0.0-1.0 confidence in relevance
                - reasoning (str): Why agent chose to respond/skip
        """
        # Default: Always respond (backward compatible)
        # Subclasses should override with smart keyword detection
        return (True, 1.0, "Agent explicitly invoked")

    async def run(self, *args, **kwargs):
        """
        Every agent must implement this method.
        It is the standard entry point for the Swarm.
        """
        raise NotImplementedError("Subclasses must implement the `run` method.")