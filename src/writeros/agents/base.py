import os
from dotenv import load_dotenv

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

        self.log.info("agent_initialized", model=self.model_name)

    async def run(self, *args, **kwargs):
        """
        Every agent must implement this method.
        It is the standard entry point for the Swarm.
        """
        raise NotImplementedError("Subclasses must implement the `run` method.")