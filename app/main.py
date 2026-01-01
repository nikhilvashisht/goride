from fastapi import FastAPI
from .routes import router as api_router
from .logging_setup import configure_logging
import logging

# configure file logging for the app
configure_logging()
logger = logging.getLogger("app.main")

app = FastAPI(title="Goride - Ride Hailing API")

app.include_router(api_router, prefix="/v1")


@app.on_event("startup")
async def _startup_log():
    logger.info("Starting Goride API application")


@app.get("/")
async def read_root():
    return {"message": "Goride API"}
