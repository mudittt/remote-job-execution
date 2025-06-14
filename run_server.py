import uvicorn
from utils.logger import setup_logger

logger = setup_logger(__name__)

if __name__ == "__main__":
    logger.info("🌐 Starting Job Queue Web Server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes during development
        log_level="info"
    )