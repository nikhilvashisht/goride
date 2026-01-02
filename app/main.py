from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router as api_router
from .logging_setup import configure_logging
from . import services
import logging
import asyncio

# configure file logging for the app
configure_logging()
logger = logging.getLogger("app.main")

app = FastAPI(title="Goride - Ride Hailing API")

# Enable CORS for UI dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/v1")


async def periodic_cache_cleanup():
    """Run cache cleanup every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        await services.cleanup_stale_drivers()


@app.on_event("startup")
async def _startup_log():
    logger.info("Starting Goride API application")
    # Start background cleanup task
    asyncio.create_task(periodic_cache_cleanup())
    logger.info("Started periodic cache cleanup task")


@app.get("/")
async def read_root():
    return {"message": "Goride API"}
