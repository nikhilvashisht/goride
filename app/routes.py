from fastapi import APIRouter, Depends, HTTPException, Header, Request
from . import db, models, services, schemas
from .db import init_db
from sqlalchemy import select, desc
from typing import Optional
from datetime import datetime, timezone
import logging
import asyncio
import httpx

logger = logging.getLogger(__name__)

# Driver discovery service URL (running as separate service on port 8001)
DRIVER_DISCOVERY_URL = "http://127.0.0.1:8001"

router = APIRouter()


async def get_conn():
    async with db.get_conn() as conn:
        yield conn


@router.on_event("startup")
async def on_startup():
    await init_db()


@router.post("/rides", response_model=schemas.RideOut)
async def create_ride(req: schemas.RideCreate, request: Request, idempotency_key: Optional[str] = Header(None), conn=Depends(get_conn)):
    # idempotency
    if idempotency_key:
        ik_sel = select(models.idempotency_keys).where(models.idempotency_keys.c.key == idempotency_key)
        ex_res = await conn.execute(ik_sel)
        ex = ex_res.first()
        if ex and ex[models.idempotency_keys.c.response]:
            return ex[models.idempotency_keys.c.response]

    logger.info("create_ride: rider=%s pickup=%s", req.rider_id, req.pickup.dict())
    async with conn.begin():
        res = await conn.execute(
            models.rides.insert().returning(models.rides.c.id).values(rider_id=req.rider_id, pickup=req.pickup.dict(), destination=req.destination.dict(), tier=req.tier, payment_method=req.payment_method, status=models.RIDE_SEARCHING, created_at=datetime.now(timezone.utc))
        )
        ride_id = res.scalar_one()
        status = models.RIDE_SEARCHING

    # Call driver discovery service to find a nearby driver
    try:
        async with httpx.AsyncClient() as client:
            match_resp = await client.post(
                f"{DRIVER_DISCOVERY_URL}/match",
                json={"ride_id": ride_id, "pickup_lat": req.pickup.lat, "pickup_lon": req.pickup.lon},
                timeout=5.0
            )
            if match_resp.status_code == 200:
                match_data = match_resp.json()
                driver_id = match_data.get("driver_id")
                if driver_id:
                    # Create assignment if driver found
                    async with db.engine.connect() as conn2:
                        await services.create_assignment(conn2, ride_id, driver_id)
                        status = models.RIDE_ASSIGNED
                        logger.info("assignment_created_from_discovery: ride=%s driver=%s", ride_id, driver_id)
            else:
                logger.warning("driver_discovery_error: ride=%s status=%s", ride_id, match_resp.status_code)
    except Exception as e:
        logger.error("driver_discovery_call_failed: ride=%s error=%s", ride_id, e)
        # Continue without assignment; ride remains in SEARCHING state

    output = schemas.RideOut(id=ride_id, status=status, pickup=req.pickup.dict(), destination=req.destination.dict())
    if idempotency_key:
        await conn.execute(models.idempotency_keys.insert().values(key=idempotency_key, response=output.dict()))
    logger.info("ride_created: id=%s status=%s", ride_id, status)
    return output


@router.get("/rides/{ride_id}")
async def get_ride(ride_id: int, conn=Depends(get_conn)):
    sel = select(models.rides).where(models.rides.c.id == ride_id)
    r_res = await conn.execute(sel)
    r = r_res.first()
    if not r:
        raise HTTPException(status_code=404, detail="ride not found")
    rm = r._mapping if hasattr(r, "_mapping") else None
    if rm is not None:
        resp = {"id": rm[models.rides.c.id], "status": rm[models.rides.c.status], "pickup": rm[models.rides.c.pickup], "destination": rm[models.rides.c.destination]}
    else:
        # fallback to positional access
        resp = {"id": r[0], "status": r[6] if len(r) > 6 else None, "pickup": r[3] if len(r) > 3 else None, "destination": r[4] if len(r) > 4 else None}
    a_sel = select(models.assignments).where(models.assignments.c.ride_id == ride_id)
    a_res = await conn.execute(a_sel)
    a = a_res.first()
    if a:
        am = a._mapping if hasattr(a, "_mapping") else None
        if am is not None:
            resp["assignment"] = {"id": am[models.assignments.c.id], "driver_id": am[models.assignments.c.driver_id], "status": am[models.assignments.c.status]}
        else:
            resp["assignment"] = {"id": a[0], "driver_id": a[2] if len(a) > 2 else None, "status": a[3] if len(a) > 3 else None}
    return resp


@router.post("/drivers/{driver_id}/location")
async def driver_location(driver_id: int, loc: schemas.Location, conn=Depends(get_conn)):
    # store location in redis (async)
    await services.update_driver_location(driver_id, loc.lat, loc.lon)
    logger.debug("driver_location: driver=%s lat=%s lon=%s", driver_id, loc.lat, loc.lon)
    # mark driver as available if not present
    sel = select(models.drivers).where(models.drivers.c.id == driver_id)
    d_res = await conn.execute(sel)
    d = d_res.first()
    if not d:
        await conn.execute(models.drivers.insert().values(id=driver_id, available=True))
    return {"status": "ok"}


@router.post("/drivers/{driver_id}/accept")
async def driver_accept(driver_id: int, payload: schemas.AcceptRequest, conn=Depends(get_conn)):
    logger.info("driver_accept: driver=%s assignment=%s", driver_id, payload.assignment_id)
    trip = await services.accept_assignment(conn, driver_id, payload.assignment_id)
    if not trip:
        raise HTTPException(status_code=400, detail="cannot accept assignment")
    return {"trip_id": trip.get('id'), "status": trip.get('status')}


@router.post("/trips/{trip_id}/end")
async def end_trip(trip_id: int, payload: schemas.EndTripRequest, conn=Depends(get_conn)):
    end_loc = None
    if payload.end_lat is not None and payload.end_lon is not None:
        end_loc = (payload.end_lat, payload.end_lon)
    logger.info("end_trip: trip=%s end_loc=%s", trip_id, end_loc)
    trip = await services.end_trip(conn, trip_id, end_loc)
    if not trip:
        raise HTTPException(status_code=404, detail="trip not found")
    return {"trip_id": trip.get('id'), "fare": trip.get('fare'), "status": trip.get('status')}


@router.post("/payments")
async def trigger_payment(req: schemas.PaymentRequest, conn=Depends(get_conn)):
    p_sel = select(models.payments).where(models.payments.c.trip_id == req.trip_id).order_by(desc(models.payments.c.id))
    p_res = await conn.execute(p_sel)
    p = p_res.first()
    if not p:
        raise HTTPException(status_code=404, detail="payment not found")
    if p[models.payments.c.status] == models.PAY_PENDING:
        logger.info("trigger_payment: scheduling payment simulation for payment_id=%s", p[models.payments.c.id])
        asyncio.create_task(services._simulate_payment(p[models.payments.c.id]))
    return {"payment_id": p[models.payments.c.id], "status": p[models.payments.c.status]}
