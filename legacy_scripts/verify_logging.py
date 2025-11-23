import os
import asyncio
from src.writeros.core.logging import setup_logging, get_logger
from src.writeros.agents.producer import ProducerAgent
from src.writeros.agents.architect import ArchitectAgent

# Force local env for colorful logs
os.environ["APP_ENV"] = "local"
os.environ["LOG_LEVEL"] = "INFO"

setup_logging()
logger = get_logger("verify_logging")

async def main():
    logger.info("starting_verification", env=os.environ.get("APP_ENV"))
    
    try:
        # Initialize an agent to trigger its logging
        logger.info("initializing_producer")
        producer = ProducerAgent(vault_root=".")
        
        logger.info("initializing_architect")
        architect = ArchitectAgent()
        
        logger.info("verification_complete", status="success")
    except Exception as e:
        logger.error("verification_failed", error=str(e))

if __name__ == "__main__":
    asyncio.run(main())
