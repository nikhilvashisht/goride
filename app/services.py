from math import radians, cos, sin, asin, sqrt
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
from .config import settings
from . import db, models
from sqlalchemy import select, insert, update, and_, desc
import threading
import time
import h3
from .cache import redis_client
import h3


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km


def update_driver_location(driver_id: int, lat: float, lon: float):
    # compute h3 cell
    new_h3 = h3.geo_to_h3(lat, lon, settings.H3_RESOLUTION)
    driver_key = f"driver:{driver_id}"
    # fetch old h3
    old_h3 = redis_client.hget(driver_key, "h3")
    pipe = redis_client.pipeline()
    pipe.hset(driver_key, mapping={"lat": lat, "lon": lon, "h3": new_h3})
    # remove from old cell set if changed
    if old_h3 and old_h3 != new_h3:
        pipe.srem(f"h3:{old_h3}", driver_id)
    # add to new cell set
    pipe.sadd(f"h3:{new_h3}", driver_id)
    pipe.execute()

def get_driver_location(driver_id: int) -> Optional[Tuple[float, float]]:
    driver_key = f"driver:{driver_id}"
    data = redis_client.hgetall(driver_key)
    if not data:
        return None
    try:
        return (float(data.get("lat")), float(data.get("lon")))
    except Exception:
        return None


def find_nearest_driver(pickup: Tuple[float, float], max_km: float = None) -> Optional[int]:
    max_km = max_km or settings.MATCH_RADIUS_KM
    origin_h3 = h3.geo_to_h3(pickup[0], pickup[1], settings.H3_RESOLUTION)
    candidates = set()
    hexes = h3.k_ring(origin_h3, settings.H3_MAX_K_RING)
    for hx in hexes:
        members = redis_client.smembers(f"h3:{hx}")
        if members:
            candidates.update(int(d) for d in members)

    best = None
    best_dist = None
    for did in candidates:
        loc = get_driver_location(did)
        if not loc:
            continue
        dist = haversine_km(pickup, loc)
        if dist <= max_km and (best_dist is None or dist < best_dist):
            best = did
            best_dist = dist
    return best


def create_assignment(conn, ride_id: int, driver_id: int) -> int:
    # insert assignment and update ride status
    res = conn.execute(
        insert(models.assignments).values(ride_id=ride_id, driver_id=driver_id, status=models.ASSIGN_OFFERED, offered_at=datetime.now(timezone.utc))
    )
    assign_id = res.inserted_primary_key[0]
    conn.execute(
        update(models.rides).where(models.rides.c.id == ride_id).values(status=models.RIDE_ASSIGNED)
    )
    # start expiry watcher
    threading.Thread(target=_expire_assignment_worker, args=(assign_id,), daemon=True).start()
    return assign_id


def _expire_assignment_worker(assignment_id: int):
    ttl = settings.ASSIGNMENT_TTL_SEC
    time.sleep(ttl)
    with db.engine.connect() as conn:
        sel = select(models.assignments).where(models.assignments.c.id == assignment_id)
        row = conn.execute(sel).first()
        if row and row[models.assignments.c.status] == models.ASSIGN_OFFERED:
            conn.execute(
                update(models.assignments).where(models.assignments.c.id == assignment_id).values(status=models.ASSIGN_EXPIRED)
            )
            # set ride back to searching
            conn.execute(
                update(models.rides).where(models.rides.c.id == row[models.assignments.c.ride_id]).values(status=models.RIDE_SEARCHING)
            )



def accept_assignment(conn, driver_id: int, assignment_id: int) -> Optional[dict]:
    sel = select(models.assignments).where(and_(models.assignments.c.id == assignment_id, models.assignments.c.driver_id == driver_id))
    row = conn.execute(sel).first()
    if not row:
        return None
    if row[models.assignments.c.status] != models.ASSIGN_OFFERED:
        return None
    conn.execute(
        update(models.assignments).where(models.assignments.c.id == assignment_id).values(status=models.ASSIGN_ACCEPTED)
    )
    # create trip
    res = conn.execute(
        insert(models.trips).values(ride_id=row[models.assignments.c.ride_id], driver_id=driver_id, start_at=datetime.now(timezone.utc), status=models.TRIP_ONGOING)
    )
    trip_id = res.inserted_primary_key[0]
    trip_sel = select(models.trips).where(models.trips.c.id == trip_id)
    trip_row = conn.execute(trip_sel).first()
    return dict(trip_row)



def end_trip(conn, trip_id: int, end_loc: Optional[Tuple[float, float]] = None) -> Optional[dict]:
    sel = select(models.trips).where(models.trips.c.id == trip_id)
    row = conn.execute(sel).first()
    if not row:
        return None
    # convert to mutable dict
    trip = dict(row)
    end_at = datetime.now(timezone.utc)
    distance_km = trip.get("distance_km", 0.0)
    if end_loc:
        start_loc = get_driver_location(trip.get("driver_id"))
        if start_loc:
            distance_km = haversine_km(start_loc, end_loc)
    duration_sec = 0
    if trip.get("start_at"):
        duration_sec = int((end_at - trip.get("start_at")).total_seconds())
    base = 2.0
    per_km = 1.5
    per_min = 0.2
    fare = base + distance_km * per_km + (duration_sec / 60.0) * per_min
    conn.execute(
        update(models.trips)
        .where(models.trips.c.id == trip_id)
        .values(end_at=end_at, distance_km=distance_km, duration_sec=duration_sec, fare=fare, status=models.TRIP_COMPLETED)
    )
    # create payment
    res = conn.execute(insert(models.payments).values(trip_id=trip_id, amount=fare, status=models.PAY_PENDING))
    payment_id = res.inserted_primary_key[0]
    # simulate payment in background
    threading.Thread(target=_simulate_payment, args=(payment_id,), daemon=True).start()
    trip.update({"end_at": end_at, "distance_km": distance_km, "duration_sec": duration_sec, "fare": fare, "status": models.TRIP_COMPLETED})
    return trip


def _simulate_payment(payment_id: int):
    with db.engine.connect() as conn:
        sel = select(models.payments).where(models.payments.c.id == payment_id)
        row = conn.execute(sel).first()
        if not row:
            return
        time.sleep(1)
        conn.execute(
            update(models.payments).where(models.payments.c.id == payment_id).values(status=models.PAY_SUCCESS, provider_response={"provider": "simulated", "id": f"pay_{payment_id}"})
        )
