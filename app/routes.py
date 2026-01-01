from fastapi import APIRouter, Depends, HTTPException, Header, Request
from . import db, models, services, schemas
from .db import init_db
from sqlalchemy import select, desc
from typing import Optional
from datetime import datetime, timezone
import asyncio

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

    async with conn.begin():
        res = await conn.execute(
            models.rides.insert().returning(models.rides.c.id).values(rider_id=req.rider_id, pickup=req.pickup.dict(), destination=req.destination.dict(), tier=req.tier, payment_method=req.payment_method, status=models.RIDE_SEARCHING, created_at=datetime.now(timezone.utc))
        )
        ride_id = res.scalar_one()
        # attempt match
        driver_id = await services.find_nearest_driver((req.pickup.lat, req.pickup.lon))
        if driver_id:
            await services.create_assignment(conn, ride_id, driver_id)
            status = models.RIDE_ASSIGNED
        else:
            await conn.execute(models.rides.update().where(models.rides.c.id == ride_id).values(status=models.RIDE_NO_DRIVER))
            status = models.RIDE_NO_DRIVER

    output = schemas.RideOut(id=ride_id, status=status, pickup=req.pickup.dict(), destination=req.destination.dict())
    if idempotency_key:
        await conn.execute(models.idempotency_keys.insert().values(key=idempotency_key, response=output.dict()))
    return output


@router.get("/rides/{ride_id}")
async def get_ride(ride_id: int, conn=Depends(get_conn)):
    sel = select(models.rides).where(models.rides.c.id == ride_id)
    r_res = await conn.execute(sel)
    r = r_res.first()
    if not r:
        raise HTTPException(status_code=404, detail="ride not found")
    resp = {"id": r[models.rides.c.id], "status": r[models.rides.c.status], "pickup": r[models.rides.c.pickup], "destination": r[models.rides.c.destination]}
    a_sel = select(models.assignments).where(models.assignments.c.ride_id == ride_id)
    a_res = await conn.execute(a_sel)
    a = a_res.first()
    if a:
        resp["assignment"] = {"id": a[models.assignments.c.id], "driver_id": a[models.assignments.c.driver_id], "status": a[models.assignments.c.status]}
    return resp


@router.post("/drivers/{driver_id}/location")
async def driver_location(driver_id: int, loc: schemas.Location, conn=Depends(get_conn)):
    # store location in redis (async)
    await services.update_driver_location(driver_id, loc.lat, loc.lon)
    # mark driver as available if not present
    sel = select(models.drivers).where(models.drivers.c.id == driver_id)
    d_res = await conn.execute(sel)
    d = d_res.first()
    if not d:
        await conn.execute(models.drivers.insert().values(id=driver_id, available=True))
    return {"status": "ok"}


@router.post("/drivers/{driver_id}/accept")
async def driver_accept(driver_id: int, payload: schemas.AcceptRequest, conn=Depends(get_conn)):
    trip = await services.accept_assignment(conn, driver_id, payload.assignment_id)
    if not trip:
        raise HTTPException(status_code=400, detail="cannot accept assignment")
    return {"trip_id": trip.get('id'), "status": trip.get('status')}


@router.post("/trips/{trip_id}/end")
async def end_trip(trip_id: int, payload: schemas.EndTripRequest, conn=Depends(get_conn)):
    end_loc = None
    if payload.end_lat is not None and payload.end_lon is not None:
        end_loc = (payload.end_lat, payload.end_lon)
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
        asyncio.create_task(services._simulate_payment(p[models.payments.c.id]))
    return {"payment_id": p[models.payments.c.id], "status": p[models.payments.c.status]}
