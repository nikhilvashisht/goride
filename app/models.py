from datetime import datetime
from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    Boolean,
    MetaData,
)


# Status constants
RIDE_SEARCHING = "searching"
RIDE_ASSIGNED = "assigned"
RIDE_NO_DRIVER = "no_driver"
RIDE_CANCELLED = "cancelled"

ASSIGN_OFFERED = "offered"
ASSIGN_DECLINED = "declined"
ASSIGN_ACCEPTED = "accepted"
ASSIGN_EXPIRED = "expired"

TRIP_ONGOING = "ongoing"
TRIP_PAUSED = "paused"
TRIP_COMPLETED = "completed"

PAY_PENDING = "pending"
PAY_SUCCESS = "success"
PAY_FAILED = "failed"


metadata = MetaData()

riders = Table(
    "riders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=True),
)

drivers = Table(
    "drivers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=True),
    Column("available", Boolean, default=True),
)

rides = Table(
    "rides",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("rider_id", Integer, nullable=True),
    Column("pickup", JSON),
    Column("destination", JSON),
    Column("tier", String),
    Column("payment_method", String),
    Column("status", String, default=RIDE_SEARCHING),
    Column("created_at", DateTime, default=datetime.timezone.utc),
)

assignments = Table(
    "assignments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ride_id", Integer),
    Column("driver_id", Integer),
    Column("status", String, default=ASSIGN_OFFERED),
    Column("offered_at", DateTime, default=datetime.timezone.utc),
    Column("metadata", JSON, nullable=True),
)

trips = Table(
    "trips",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ride_id", Integer),
    Column("driver_id", Integer),
    Column("start_at", DateTime, default=datetime.utcnow),
    Column("end_at", DateTime, nullable=True),
    Column("distance_km", Float, default=0.0),
    Column("duration_sec", Integer, default=0),
    Column("fare", Float, default=0.0),
    Column("status", String, default=TRIP_ONGOING),
)

payments = Table(
    "payments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("trip_id", Integer),
    Column("amount", Float),
    Column("status", String, default=PAY_PENDING),
    Column("provider_response", JSON, nullable=True),
)

idempotency_keys = Table(
    "idempotency_keys",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("key", String, unique=True),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("response", JSON, nullable=True),
)
