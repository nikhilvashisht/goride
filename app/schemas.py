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


class RiderRegister(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    mobile_number: str = Field(..., min_length=10, max_length=15)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=500)


class DriverRegister(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    mobile_number: str = Field(..., min_length=10, max_length=15)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=500)


class UserRegistrationResponse(BaseModel):
    user_id: int
    message: str


class Receipt(BaseModel):
    payment_id: int
    trip_id: int
    rider_id: Optional[int]
    driver_id: int
    amount: float
    payment_method: str
    status: str
    distance_km: float
    duration_sec: int
    pickup: dict
    destination: dict
    timestamp: datetime
