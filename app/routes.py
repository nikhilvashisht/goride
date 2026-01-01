from fastapi import APIRouter, Depends, HTTPException, Header, Request
from . import db, models, services, schemas
from .db import init_db
from sqlalchemy import select, desc
from typing import Optional

router = APIRouter()


def get_conn():
    with db.get_conn() as conn:
        yield conn


@router.on_event("startup")
def on_startup():
    init_db()


@router.post("/rides", response_model=schemas.RideOut)
def create_ride(req: schemas.RideCreate, request: Request, idempotency_key: Optional[str] = Header(None), conn=Depends(get_conn)):
    # idempotency
    if idempotency_key:
        ik_sel = select(models.idempotency_keys).where(models.idempotency_keys.c.key == idempotency_key)
        ex = conn.execute(ik_sel).first()
        if ex and ex[models.idempotency_keys.c.response]:
            return ex[models.idempotency_keys.c.response]

    with conn.begin():
        res = conn.execute(
            models.rides.insert().values(rider_id=req.rider_id, pickup=req.pickup.dict(), destination=req.destination.dict(), tier=req.tier, payment_method=req.payment_method, status=models.RIDE_SEARCHING, created_at=datetime.utcnow())
        )
        ride_id = res.inserted_primary_key[0]
        # attempt match
        driver_id = services.find_nearest_driver((req.pickup.lat, req.pickup.lon))
        if driver_id:
            services.create_assignment(conn, ride_id, driver_id)
            status = models.RIDE_ASSIGNED
        else:
            conn.execute(models.rides.update().where(models.rides.c.id == ride_id).values(status=models.RIDE_NO_DRIVER))
            status = models.RIDE_NO_DRIVER

    output = schemas.RideOut(id=ride_id, status=status, pickup=req.pickup.dict(), destination=req.destination.dict())
    if idempotency_key:
        conn.execute(models.idempotency_keys.insert().values(key=idempotency_key, response=output.dict()))
    return output


@router.get("/rides/{ride_id}")
def get_ride(ride_id: int, conn=Depends(get_conn)):
    sel = select(models.rides).where(models.rides.c.id == ride_id)
    r = conn.execute(sel).first()
    if not r:
        raise HTTPException(status_code=404, detail="ride not found")
    resp = {"id": r[models.rides.c.id], "status": r[models.rides.c.status], "pickup": r[models.rides.c.pickup], "destination": r[models.rides.c.destination]}
    a_sel = select(models.assignments).where(models.assignments.c.ride_id == ride_id)
    a = conn.execute(a_sel).first()
    if a:
        resp["assignment"] = {"id": a[models.assignments.c.id], "driver_id": a[models.assignments.c.driver_id], "status": a[models.assignments.c.status]}
    return resp


@router.post("/drivers/{driver_id}/location")
def driver_location(driver_id: int, loc: schemas.Location, conn=Depends(get_conn)):
    # store location in memory (or cache)
    services.update_driver_location(driver_id, loc.lat, loc.lon)
    # mark driver as available if not present
    sel = select(models.drivers).where(models.drivers.c.id == driver_id)
    d = conn.execute(sel).first()
    if not d:
        conn.execute(models.drivers.insert().values(id=driver_id, available=True))
    return {"status": "ok"}


@router.post("/drivers/{driver_id}/accept")
def driver_accept(driver_id: int, payload: schemas.AcceptRequest, conn=Depends(get_conn)):
    trip = services.accept_assignment(conn, driver_id, payload.assignment_id)
    if not trip:
        raise HTTPException(status_code=400, detail="cannot accept assignment")
    return {"trip_id": trip.get('id'), "status": trip.get('status')}


@router.post("/trips/{trip_id}/end")
def end_trip(trip_id: int, payload: schemas.EndTripRequest, conn=Depends(get_conn)):
    end_loc = None
    if payload.end_lat is not None and payload.end_lon is not None:
        end_loc = (payload.end_lat, payload.end_lon)
    trip = services.end_trip(conn, trip_id, end_loc)
    if not trip:
        raise HTTPException(status_code=404, detail="trip not found")
    return {"trip_id": trip.get('id'), "fare": trip.get('fare'), "status": trip.get('status')}


@router.post("/payments")
def trigger_payment(req: schemas.PaymentRequest, conn=Depends(get_conn)):
    p_sel = select(models.payments).where(models.payments.c.trip_id == req.trip_id).order_by(desc(models.payments.c.id))
    p = conn.execute(p_sel).first()
    if not p:
        raise HTTPException(status_code=404, detail="payment not found")
    if p[models.payments.c.status] == models.PAY_PENDING:
        threading.Thread(target=services._simulate_payment, args=(p[models.payments.c.id],), daemon=True).start()
    return {"payment_id": p[models.payments.c.id], "status": p[models.payments.c.status]}
