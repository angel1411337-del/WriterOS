"""
LangSmith Configuration and Tracing Utilities

This module handles LangSmith tracing configuration for WriterOS.
LangSmith provides automatic observability for all LangChain/LangGraph operations.
"""
import os
from typing import Optional
from dotenv import load_dotenv
from writeros.core.logging import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()


def configure_langsmith(
    enabled: Optional[bool] = None,
    project_name: Optional[str] = None,
    api_key: Optional[str] = None
) -> bool:
    """
    Configure LangSmith tracing for the current session.

    LangSmith automatically traces:
    - All LLM calls (OpenAI, etc.)
    - Agent executions
    - Chain invocations
    - Tool calls
    - LangGraph workflow states

    Args:
        enabled: Whether to enable tracing. Defaults to LANGCHAIN_TRACING_V2 env var
        project_name: Project name in LangSmith. Defaults to LANGCHAIN_PROJECT env var
        api_key: LangSmith API key. Defaults to LANGCHAIN_API_KEY env var

    Returns:
        True if tracing is enabled and configured, False otherwise

    Example:
        >>> # Enable tracing for debugging
        >>> configure_langsmith(enabled=True, project_name="writeros-debug")
        >>>
        >>> # Disable tracing for production
        >>> configure_langsmith(enabled=False)
    """
    # Determine if tracing should be enabled
    if enabled is None:
        enabled_str = os.getenv("LANGCHAIN_TRACING_V2", "false").lower()
        enabled = enabled_str in ("true", "1", "yes")

    # Get project name
    if project_name is None:
        project_name = os.getenv("LANGCHAIN_PROJECT", "writeros")

    # Get API key
    if api_key is None:
        api_key = os.getenv("LANGCHAIN_API_KEY")

    # Configure environment variables for LangSmith
    if enabled:
        if not api_key or api_key == "your-langsmith-api-key-here":
            logger.warning(
                "langsmith_not_configured",
                reason="LANGCHAIN_API_KEY not set or using placeholder",
                hint="Get your API key at https://smith.langchain.com/settings"
            )
            # Disable tracing if no valid API key
            os.environ["LANGCHAIN_TRACING_V2"] = "false"
            return False

        # Enable tracing
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = project_name
        os.environ["LANGCHAIN_API_KEY"] = api_key

        logger.info(
            "langsmith_enabled",
            project=project_name,
            endpoint="https://smith.langchain.com"
        )
        return True
    else:
        # Explicitly disable tracing
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        logger.info("langsmith_disabled")
        return False


def get_langsmith_url(run_id: Optional[str] = None) -> Optional[str]:
    """
    Get the LangSmith dashboard URL for a specific run or project.

    Args:
        run_id: Optional run ID to link directly to a trace

    Returns:
        URL to LangSmith dashboard, or None if tracing is disabled

    Example:
        >>> url = get_langsmith_url()
        >>> print(f"View traces at: {url}")
    """
    if os.getenv("LANGCHAIN_TRACING_V2", "false").lower() not in ("true", "1", "yes"):
        return None

    project = os.getenv("LANGCHAIN_PROJECT", "writeros")

    if run_id:
        return f"https://smith.langchain.com/public/{run_id}/r"
    else:
        return f"https://smith.langchain.com/projects/p/{project}"


def is_langsmith_enabled() -> bool:
    """
    Check if LangSmith tracing is currently enabled.

    Returns:
        True if tracing is enabled, False otherwise
    """
    enabled_str = os.getenv("LANGCHAIN_TRACING_V2", "false").lower()
    return enabled_str in ("true", "1", "yes")


# Auto-configure on module import
configure_langsmith()
