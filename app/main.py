from fastapi import FastAPI
from .routes import router as api_router

app = FastAPI(title="Goride - Ride Hailing API")

app.include_router(api_router, prefix="/v1")

@app.get("/")
async def read_root():
    return {"message": "Goride API"}
