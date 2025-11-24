from fastapi import FastAPI
from writeros.core.logging import setup_logging, get_logger
from writeros import __version__

# Initialize logging before app creation
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="WriterOS API",
    version=__version__,
    description="AI-Powered Creative Writing Assistant"
)

@app.on_event("startup")
async def startup_event():
    logger.info("api_startup", version=__version__)

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": __version__}
