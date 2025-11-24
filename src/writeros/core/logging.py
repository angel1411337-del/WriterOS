import sys
import logging
import structlog
from writeros.config import settings

def setup_logging():
    """
    Configures structured logging.
    - JSON for Production (Docker friendly)
    - Colorful text for Local Dev
    """
    
    # 1. Set the underlying standard logging level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.LOG_LEVEL.upper(),
    )

    # 2. Define shared processors (add timestamp, log level, etc.)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # 3. Configure Renderer based on Environment
    if settings.APP_ENV == "production":
        # Docker/Cloud -> JSON
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Local -> Pretty Colors
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]

    # 4. Wrap it up
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

def get_logger(name: str):
    """Return a logger bound with the module name"""
    return structlog.get_logger(name)
