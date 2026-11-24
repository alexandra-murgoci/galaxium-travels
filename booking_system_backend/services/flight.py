from sqlalchemy.orm import Session
from models import Flight
from schemas import FlightOut, SeatClassOut
from seat_classes import SEAT_CLASSES, class_price


def to_flight_out(flight: Flight) -> FlightOut:
    """Build a FlightOut with per-class price, seats and description."""
    return FlightOut(
        flight_id=flight.flight_id,
        origin=flight.origin,
        destination=flight.destination,
        departure_time=flight.departure_time,
        arrival_time=flight.arrival_time,
        price=flight.price,
        seat_classes={
            name: SeatClassOut(
                price=class_price(flight.price, name),
                seats_available=getattr(flight, f"seats_{name}"),
                description=info["description"],
            )
            for name, info in SEAT_CLASSES.items()
        },
    )


def list_flights(db: Session) -> list[FlightOut]:
    """List all available flights."""
    flights = db.query(Flight).all()
    return [to_flight_out(f) for f in flights]
