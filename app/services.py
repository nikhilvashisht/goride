from math import radians, cos, sin, asin, sqrt
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
from .config import settings
from . import db, models
from sqlalchemy import select, insert, update, and_, desc
import asyncio
from .cache import redis_client


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


async def update_driver_location(driver_id: int, lat: float, lon: float):
    driver_key = f"driver:{driver_id}"
    # store lat/lon in hash for quick lookup
    await redis_client.hset(driver_key, mapping={"lat": lat, "lon": lon})
    await redis_client.execute_command("GEOADD", "drivers_geo", lon, lat, driver_id)

async def get_driver_location(driver_id: int) -> Optional[Tuple[float, float]]:
    driver_key = f"driver:{driver_id}"
    data = await redis_client.hgetall(driver_key)
    if not data:
        return None
    try:
        return (float(data.get("lat")), float(data.get("lon")))
    except Exception:
        return None


async def find_nearest_driver(pickup: Tuple[float, float], max_km: float = None) -> Optional[int]:
    """Use Redis GEOSEARCH/GEORADIUS to find nearest drivers within `max_km`.

    Returns the nearest driver id or None.
    """
    max_km = max_km or settings.MATCH_RADIUS_KM
    lat, lon = pickup[0], pickup[1]
    # GEORADIUS: drivers_geo lon lat radius km WITHDIST COUNT 50 ASC
    try:
        res = await redis_client.execute_command("GEORADIUS", "drivers_geo", lon, lat, max_km, "km", "WITHDIST", "COUNT", 50, "ASC")
    except Exception:
        return None
    if not res:
        return None
    # res elements are [member, dist] when WITHDIST used
    for entry in res:
        # entry may be [member, dist] or (member, dist)
        try:
            member = entry[0]
        except Exception:
            continue
        try:
            did = int(member)
        except Exception:
            # member might be bytes/str
            try:
                did = int(member.decode() if isinstance(member, bytes) else member)
            except Exception:
                continue
        # verify location exists and distance constraint
        loc = await get_driver_location(did)
        if not loc:
            continue
        dist = haversine_km(pickup, loc)
        if dist <= max_km:
            return did
    return None


async def create_assignment(conn, ride_id: int, driver_id: int) -> int:
    # atomically insert assignment and update ride status
    async with conn.begin():
        res = await conn.execute(
            insert(models.assignments).returning(models.assignments.c.id).values(ride_id=ride_id, driver_id=driver_id, status=models.ASSIGN_OFFERED, offered_at=datetime.now(timezone.utc))
        )
        assign_id = res.scalar_one()
        await conn.execute(
            update(models.rides).where(models.rides.c.id == ride_id).values(status=models.RIDE_ASSIGNED)
        )
    # start expiry watcher after commit
    asyncio.create_task(_expire_assignment_worker(assign_id))
    return assign_id


async def _expire_assignment_worker(assignment_id: int):
    ttl = settings.ASSIGNMENT_TTL_SEC
    await asyncio.sleep(ttl)
    async with db.engine.connect() as conn:
        sel = select(models.assignments).where(models.assignments.c.id == assignment_id)
        res = await conn.execute(sel)
        row = res.first()
        if row and row[models.assignments.c.status] == models.ASSIGN_OFFERED:
            async with conn.begin():
                await conn.execute(
                    update(models.assignments).where(models.assignments.c.id == assignment_id).values(status=models.ASSIGN_EXPIRED)
                )
                # set ride back to searching
                await conn.execute(
                    update(models.rides).where(models.rides.c.id == row[models.assignments.c.ride_id]).values(status=models.RIDE_SEARCHING)
                )



async def accept_assignment(conn, driver_id: int, assignment_id: int) -> Optional[dict]:
    sel = select(models.assignments).where(and_(models.assignments.c.id == assignment_id, models.assignments.c.driver_id == driver_id))
    # perform select + update + insert in a transaction
    async with conn.begin():
        res = await conn.execute(sel)
        row = res.first()
        if not row:
            return None
        if row[models.assignments.c.status] != models.ASSIGN_OFFERED:
            return None
        await conn.execute(
            update(models.assignments).where(models.assignments.c.id == assignment_id).values(status=models.ASSIGN_ACCEPTED)
        )
        # create trip
        res2 = await conn.execute(
            insert(models.trips).returning(models.trips.c.id).values(ride_id=row[models.assignments.c.ride_id], driver_id=driver_id, start_at=datetime.now(timezone.utc), status=models.TRIP_ONGOING)
        )
        trip_id = res2.scalar_one()
    trip_sel = select(models.trips).where(models.trips.c.id == trip_id)
    trip_row = (await conn.execute(trip_sel)).first()
    return dict(trip_row) if trip_row else None



async def end_trip(conn, trip_id: int, end_loc: Optional[Tuple[float, float]] = None) -> Optional[dict]:
    sel = select(models.trips).where(models.trips.c.id == trip_id)
    res = await conn.execute(sel)
    row = res.first()
    if not row:
        return None
    trip = dict(row)
    end_at = datetime.now(timezone.utc)
    distance_km = trip.get("distance_km", 0.0)
    if end_loc:
        start_loc = await get_driver_location(trip.get("driver_id"))
        if start_loc:
            distance_km = haversine_km(start_loc, end_loc)
    duration_sec = 0
    if trip.get("start_at"):
        duration_sec = int((end_at - trip.get("start_at")).total_seconds())
    base = 2.0
    per_km = 1.5
    per_min = 0.2
    fare = base + distance_km * per_km + (duration_sec / 60.0) * per_min
    # update trip and insert payment atomically
    async with conn.begin():
        await conn.execute(
            update(models.trips)
            .where(models.trips.c.id == trip_id)
            .values(end_at=end_at, distance_km=distance_km, duration_sec=duration_sec, fare=fare, status=models.TRIP_COMPLETED)
        )
        res2 = await conn.execute(insert(models.payments).returning(models.payments.c.id).values(trip_id=trip_id, amount=fare, status=models.PAY_PENDING))
        payment_id = res2.scalar_one()
    # simulate payment in background
    asyncio.create_task(_simulate_payment(payment_id))
    trip.update({"end_at": end_at, "distance_km": distance_km, "duration_sec": duration_sec, "fare": fare, "status": models.TRIP_COMPLETED})
    return trip


async def _simulate_payment(payment_id: int):
    # small delay to simulate external call
    await asyncio.sleep(1)
    async with db.engine.begin() as conn:
        await conn.execute(
            update(models.payments).where(models.payments.c.id == payment_id).values(status=models.PAY_SUCCESS, provider_response={"provider": "simulated", "id": f"pay_{payment_id}"})
        )
