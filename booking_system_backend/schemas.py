from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from seat_classes import DEFAULT_SEAT_CLASS, is_valid_seat_class


class SeatClassOut(BaseModel):
    price: int
    seats_available: int
    description: str


class FlightOut(BaseModel):
    flight_id: int
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    price: int
    seat_classes: dict[str, SeatClassOut]


class BookingRequest(BaseModel):
    user_id: int
    name: str
    flight_id: int
    seat_class: str = DEFAULT_SEAT_CLASS

    @field_validator("seat_class")
    @classmethod
    def validate_seat_class(cls, value: str) -> str:
        if not is_valid_seat_class(value):
            raise ValueError("Invalid seat class")
        return value


class BookingOut(BaseModel):
    booking_id: int
    user_id: int
    flight_id: int
    status: str
    booking_time: str
    seat_class: str

    class Config:
        from_attributes = True


class UserRegistration(BaseModel):
    name: str
    email: EmailStr


class UserOut(BaseModel):
    user_id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    error_code: str
    details: Optional[str] = None
