from pydantic import BaseModel, Field, conlist
from typing import Optional
from enum import Enum
from datetime import datetime


class Location(BaseModel):
    lat: float
    lon: float


class RideCreate(BaseModel):
    rider_id: Optional[int]
    pickup: Location
    destination: Location
    tier: Optional[str] = "standard"
    payment_method: Optional[str] = "card"


class RideOut(BaseModel):
    id: int
    status: str
    pickup: dict
    destination: dict


class AcceptRequest(BaseModel):
    assignment_id: int


class EndTripRequest(BaseModel):
    end_lat: Optional[float]
    end_lon: Optional[float]


class PaymentRequest(BaseModel):
    trip_id: int
    method: Optional[str] = "card"
