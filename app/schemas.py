from pydantic import BaseModel, Field, conlist, field_validator
from typing import Optional
from enum import Enum
from datetime import datetime


class Location(BaseModel):
    lat: float
    lon: float


class RideCreate(BaseModel):
    rider_id: Optional[int] = Field(None, gt=0)
    pickup: Location
    destination: Location
    tier: Optional[str] = Field("standard", max_length=50)
    payment_method: Optional[str] = Field("card", max_length=50)
    
    @field_validator('rider_id')
    @classmethod
    def validate_rider_id(cls, v):
        if v is not None and (not isinstance(v, int) or v <= 0):
            raise ValueError('rider_id must be a positive integer')
        return v


class RideOut(BaseModel):
    id: int
    status: str
    pickup: dict
    destination: dict


class AcceptRequest(BaseModel):
    assignment_id: int = Field(..., gt=0)
    
    @field_validator('assignment_id')
    @classmethod
    def validate_assignment_id(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError('assignment_id must be a positive integer')
        return v


class EndTripRequest(BaseModel):
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None


class PaymentRequest(BaseModel):
    trip_id: int = Field(..., gt=0)
    method: Optional[str] = Field("card", max_length=50)
    
    @field_validator('trip_id')
    @classmethod
    def validate_trip_id(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError('trip_id must be a positive integer')
        return v


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
