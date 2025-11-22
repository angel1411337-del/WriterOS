import os
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Import the new Universal Schema
# This ensures all Agents have access to Entity, Relationship, etc.
from .schema import Entity, Relationship, Fact, EntityType, CanonInfo

# Setup Environment
load_dotenv()

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class BaseAgent:
    # ✅ UPDATED: Default is now 'gpt-5.1' (The SOTA Thinking Model)
    def __init__(self, model_name="gpt-5.1"):
        self.model_name = model_name

        # Ensure API Key exists
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("❌ OPENAI_API_KEY not found in environment variables.")
            raise ValueError("OPENAI_API_KEY is missing.")

        # Initialize the LLM (Language Model)
        # This is the brain that all agents share
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=0.7, # 0.7 works well with 5.1 for creative+logic balance
            openai_api_key=api_key
        )

        logger.info(f"🤖 Agent initialized with model: {self.model_name}")

    async def run(self, *args, **kwargs):
        """
        Every agent must implement this method.
        It is the standard entry point for the Swarm.
        """
        raise NotImplementedError("Subclasses must implement the `run` method.")