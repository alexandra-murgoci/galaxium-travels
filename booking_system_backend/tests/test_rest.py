import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import User, Flight, Booking


class TestFlightsEndpoint:
    """Test /flights endpoint."""

    def test_get_flights_empty(self, client, db_session):
        """Test getting flights when database is empty."""
        response = client.get("/flights")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_flights_with_data(self, client, db_session):
        """Test getting flights with data."""
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=5,
            seats_business=0,
            seats_galaxium=0
        ))
        db_session.commit()

        response = client.get("/flights")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["origin"] == "Earth"
        assert data[0]["destination"] == "Mars"

    def test_get_flights_response_shape(self, client, db_session, sample_flight_data):
        """Test /flights returns base price and per-class price, seats and description."""
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        response = client.get("/flights")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        flight = data[0]
        assert set(flight) == {
            "flight_id", "origin", "destination", "departure_time",
            "arrival_time", "price", "seat_classes"
        }
        assert "seats_available" not in flight
        assert flight["price"] == 1000000
        assert set(flight["seat_classes"]) == {"economy", "business", "galaxium"}

        expected = {
            "economy": (1500000, 3),
            "business": (2500000, 1),
            "galaxium": (3000000, 1),
        }
        for name, (price, seats) in expected.items():
            seat_class = flight["seat_classes"][name]
            assert set(seat_class) == {"price", "seats_available", "description"}
            assert seat_class["price"] == price
            assert seat_class["seats_available"] == seats
            assert isinstance(seat_class["description"], str)
            assert seat_class["description"]


class TestRegisterEndpoint:
    """Test /register endpoint."""

    def test_register_success(self, client, db_session, sample_user_data):
        """Test successful user registration."""
        response = client.post("/register", json=sample_user_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_user_data["name"]
        assert data["email"] == sample_user_data["email"]
        assert "user_id" in data

    def test_register_duplicate_email(self, client, db_session, sample_user_data):
        """Test registration with duplicate email."""
        client.post("/register", json=sample_user_data)
        response = client.post("/register", json=sample_user_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "EMAIL_EXISTS"


class TestUserEndpoint:
    """Test /user endpoint."""

    def test_get_user_success(self, client, db_session, sample_user_data):
        """Test successful user retrieval."""
        client.post("/register", json=sample_user_data)

        response = client.get(
            "/user",
            params={"name": sample_user_data["name"], "email": sample_user_data["email"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_user_data["name"]

    def test_get_user_not_found(self, client, db_session):
        """Test user retrieval when not found."""
        response = client.get(
            "/user",
            params={"name": "NonExistent", "email": "none@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "USER_NOT_FOUND"


class TestBookEndpoint:
    """Test /book endpoint."""

    def test_book_flight_success(self, client, db_session, sample_user_data):
        """Test successful flight booking."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=5,
            seats_business=0,
            seats_galaxium=0
        ))
        db_session.commit()
        flight = db_session.query(Flight).first()

        # Book flight
        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "booked"
        assert data["user_id"] == user_id
        assert data["seat_class"] == "economy"

    def test_book_flight_without_seat_class_defaults_to_economy(
        self, client, db_session, sample_user_data, sample_flight_data
    ):
        """Test booking without seat_class books economy."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()
        flight = db_session.query(Flight).first()

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "booked"
        assert data["seat_class"] == "economy"

        db_session.refresh(flight)
        assert flight.seats_economy == 2
        assert flight.seats_business == 1
        assert flight.seats_galaxium == 1

    def test_book_flight_with_seat_class(
        self, client, db_session, sample_user_data, sample_flight_data
    ):
        """Test booking each seat class decrements only that class."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()
        flight = db_session.query(Flight).first()

        for seat_class in ("economy", "business", "galaxium"):
            response = client.post("/book", json={
                "user_id": user_id,
                "name": sample_user_data["name"],
                "flight_id": flight.flight_id,
                "seat_class": seat_class
            })
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "booked"
            assert data["seat_class"] == seat_class

        db_session.refresh(flight)
        assert flight.seats_economy == 2
        assert flight.seats_business == 0
        assert flight.seats_galaxium == 0

    def test_book_flight_invalid_seat_class(
        self, client, db_session, sample_user_data, sample_flight_data
    ):
        """Test booking with an invalid seat_class is rejected with 422."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()
        flight = db_session.query(Flight).first()

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
            "seat_class": "first_class"
        })

        assert response.status_code == 422
        db_session.refresh(flight)
        assert flight.seats_economy == 3
        assert db_session.query(Booking).count() == 0

    def test_book_flight_class_sold_out(
        self, client, db_session, sample_user_data, sample_flight_data
    ):
        """Test booking a sold-out class returns NO_SEATS_AVAILABLE."""
        sample_flight_data["seats_galaxium"] = 0
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()
        flight = db_session.query(Flight).first()

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
            "seat_class": "galaxium"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "NO_SEATS_AVAILABLE"

    def test_book_flight_not_found(self, client, db_session, sample_user_data):
        """Test booking non-existent flight."""
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": 999
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "FLIGHT_NOT_FOUND"


class TestBookingsEndpoint:
    """Test /bookings/{user_id} endpoint."""

    def test_get_bookings_success(self, client, db_session, sample_user_data):
        """Test getting user bookings."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight and booking
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=5,
            seats_business=0,
            seats_galaxium=0
        ))
        db_session.commit()
        flight = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_id,
            flight_id=flight.flight_id,
            status="booked",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()

        response = client.get(f"/bookings/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "booked"

    def test_get_bookings_empty(self, client, db_session):
        """Test getting bookings when user has none."""
        response = client.get("/bookings/999")
        assert response.status_code == 200
        assert response.json() == []


class TestCancelEndpoint:
    """Test /cancel/{booking_id} endpoint."""

    def test_cancel_booking_success(self, client, db_session, sample_user_data):
        """Test successful booking cancellation."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight and booking
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=4,
            seats_business=0,
            seats_galaxium=0
        ))
        db_session.commit()
        flight = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_id,
            flight_id=flight.flight_id,
            status="booked",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()
        booking = db_session.query(Booking).first()

        response = client.post(f"/cancel/{booking.booking_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_booking_restores_class_seat(
        self, client, db_session, sample_user_data, sample_flight_data
    ):
        """Test cancelling a booking restores the seat in the booking's class."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()
        flight = db_session.query(Flight).first()

        book_response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
            "seat_class": "business"
        })
        booking_id = book_response.json()["booking_id"]

        db_session.refresh(flight)
        assert flight.seats_business == 0

        response = client.post(f"/cancel/{booking_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["seat_class"] == "business"

        db_session.refresh(flight)
        assert flight.seats_economy == 3
        assert flight.seats_business == 1
        assert flight.seats_galaxium == 1

    def test_cancel_booking_not_found(self, client, db_session):
        """Test cancelling non-existent booking."""
        response = client.post("/cancel/999")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "BOOKING_NOT_FOUND"


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client, db_session):
        """Test health check returns OK."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "OK"}
