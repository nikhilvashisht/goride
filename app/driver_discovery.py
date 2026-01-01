from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
from . import services
from .logging_setup import configure_logging

# ensure logging is configured when run standalone
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Driver Discovery Service")


class MatchRequest(BaseModel):
    """Request to find a driver for a ride."""
    ride_id: int
    pickup_lat: float
    pickup_lon: float
    max_distance_km: float = 5.0  # optional, defaults to config setting


class MatchResponse(BaseModel):
    """Response with matched driver or None if no driver found."""
    ride_id: int
    driver_id: int | None
    distance_km: float | None = None


@app.post("/match", response_model=MatchResponse)
async def find_driver(req: MatchRequest):
    """Find the nearest available driver for a ride."""
    logger.info("match_request: ride=%s pickup=(%s,%s) max_distance=%s", req.ride_id, req.pickup_lat, req.pickup_lon, req.max_distance_km)
    
    pickup = (req.pickup_lat, req.pickup_lon)
    driver_id = await services.find_nearest_driver(pickup, max_km=req.max_distance_km)
    
    distance_km = None
    if driver_id:
        driver_loc = await services.get_driver_location(driver_id)
        if driver_loc:
            distance_km = services.haversine_km(pickup, driver_loc)
        logger.info("match_found: ride=%s driver=%s distance_km=%s", req.ride_id, driver_id, distance_km)
    else:
        logger.info("match_not_found: ride=%s", req.ride_id)
    
    return MatchResponse(ride_id=req.ride_id, driver_id=driver_id, distance_km=distance_km)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
