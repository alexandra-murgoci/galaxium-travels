import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import User, Flight, Booking
from schemas import ErrorResponse
from seat_classes import SEAT_CLASSES, class_price, is_valid_seat_class
from services import flight, user, booking


class TestFlightService:
    """Test flight service functions."""

    def test_list_flights_empty(self, db_session):
        """Test listing flights when database is empty."""
        result = flight.list_flights(db_session)
        assert result == []

    def test_list_flights_with_data(self, db_session):
        """Test listing flights with data in database."""
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

        result = flight.list_flights(db_session)
        assert len(result) == 1
        assert result[0].origin == "Earth"
        assert result[0].destination == "Mars"

    def test_list_flights_per_class_prices_and_seats(self, db_session, sample_flight_data):
        """Test list_flights returns per-class prices, seats and descriptions."""
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        result = flight.list_flights(db_session)
        assert len(result) == 1
        assert result[0].price == 1000000
        assert set(result[0].seat_classes) == {"economy", "business", "galaxium"}

        economy = result[0].seat_classes["economy"]
        business = result[0].seat_classes["business"]
        galaxium = result[0].seat_classes["galaxium"]

        assert (economy.price, economy.seats_available) == (1500000, 3)
        assert (business.price, business.seats_available) == (2500000, 1)
        assert (galaxium.price, galaxium.seats_available) == (3000000, 1)

        for name, seat_class in result[0].seat_classes.items():
            assert seat_class.description == SEAT_CLASSES[name]["description"]

    def test_list_flights_reflects_sold_out_class(self, db_session, sample_flight_data):
        """Test a sold-out class shows zero seats while other classes keep theirs."""
        sample_flight_data["seats_galaxium"] = 0
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        result = flight.list_flights(db_session)
        assert result[0].seat_classes["galaxium"].seats_available == 0
        assert result[0].seat_classes["economy"].seats_available == 3
        assert result[0].seat_classes["business"].seats_available == 1


class TestUserService:
    """Test user service functions."""

    def test_register_user_success(self, db_session):
        """Test successful user registration."""
        result = user.register_user(db_session, "Test User", "test@example.com")
        assert result.name == "Test User"
        assert result.email == "test@example.com"
        assert result.user_id > 0

    def test_register_user_duplicate_email(self, db_session):
        """Test registration with duplicate email."""
        user.register_user(db_session, "User 1", "test@example.com")
        result = user.register_user(db_session, "User 2", "test@example.com")

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "EMAIL_EXISTS"

    def test_get_user_success(self, db_session):
        """Test successful user retrieval."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()

        result = user.get_user(db_session, "Test User", "test@example.com")
        assert result.name == "Test User"
        assert result.email == "test@example.com"

    def test_get_user_not_found(self, db_session):
        """Test user retrieval when not found."""
        result = user.get_user(db_session, "NonExistent", "none@example.com")
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "USER_NOT_FOUND"


class TestBookingService:
    """Test booking service functions."""

    def test_book_flight_success(self, db_session):
        """Test successful flight booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id)
        assert result.status == "booked"
        assert result.user_id == user_obj.user_id
        assert result.flight_id == flight_obj.flight_id

        # Verify seat was decremented
        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 4

    def test_book_flight_not_found(self, db_session):
        """Test booking non-existent flight."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()
        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", 999)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "FLIGHT_NOT_FOUND"

    def test_book_flight_no_seats(self, db_session):
        """Test booking when no seats available."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=0,
            seats_business=0,
            seats_galaxium=0
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NO_SEATS_AVAILABLE"

    def test_book_flight_user_not_found(self, db_session):
        """Test booking with non-existent user."""
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
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, 999, "Fake User", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "USER_NOT_FOUND"

    def test_book_flight_name_mismatch(self, db_session):
        """Test booking with wrong name for user ID."""
        db_session.add(User(name="Real Name", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Wrong Name", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NAME_MISMATCH"

    def test_cancel_booking_success(self, db_session):
        """Test successful booking cancellation."""
        db_session.add(User(name="Test User", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="booked",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert result.status == "cancelled"

        # Verify seat was restored
        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 5

    def test_cancel_booking_not_found(self, db_session):
        """Test cancelling non-existent booking."""
        result = booking.cancel_booking(db_session, 999)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "BOOKING_NOT_FOUND"

    def test_cancel_booking_already_cancelled(self, db_session):
        """Test cancelling already cancelled booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="cancelled",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "ALREADY_CANCELLED"

    def test_get_bookings_success(self, db_session):
        """Test getting user bookings."""
        db_session.add(User(name="Test User", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="booked",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()

        result = booking.get_bookings(db_session, user_obj.user_id)
        assert len(result) == 1
        assert result[0].status == "booked"

    def test_get_bookings_empty(self, db_session):
        """Test getting bookings when user has none."""
        result = booking.get_bookings(db_session, 999)
        assert result == []

    def test_book_flight_each_class_decrements_only_that_class(self, db_session, sample_flight_data):
        """Test booking each seat class decrements only that class's seats."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        expected = {"economy": 3, "business": 1, "galaxium": 1}
        for seat_class in ("economy", "business", "galaxium"):
            result = booking.book_flight(
                db_session, user_obj.user_id, "Test User", flight_obj.flight_id, seat_class
            )
            assert result.status == "booked"
            assert result.seat_class == seat_class

            expected[seat_class] -= 1
            db_session.refresh(flight_obj)
            assert flight_obj.seats_economy == expected["economy"]
            assert flight_obj.seats_business == expected["business"]
            assert flight_obj.seats_galaxium == expected["galaxium"]

    def test_book_flight_default_class_is_economy(self, db_session, sample_flight_data):
        """Test booking without a seat class defaults to economy."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id)
        assert result.seat_class == "economy"

        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 2
        assert flight_obj.seats_business == 1
        assert flight_obj.seats_galaxium == 1

    def test_book_flight_invalid_seat_class(self, db_session, sample_flight_data):
        """Test booking with an invalid seat class."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "first_class"
        )
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "INVALID_SEAT_CLASS"

        # No seats should have been consumed and no booking created
        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 3
        assert db_session.query(Booking).count() == 0

    def test_book_flight_class_sold_out_others_bookable(self, db_session, sample_flight_data):
        """Test a sold-out class returns NO_SEATS_AVAILABLE while other classes remain bookable."""
        sample_flight_data["seats_business"] = 0
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        sold_out = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "business"
        )
        assert isinstance(sold_out, ErrorResponse)
        assert sold_out.error_code == "NO_SEATS_AVAILABLE"
        assert "business" in sold_out.details

        for seat_class in ("economy", "galaxium"):
            result = booking.book_flight(
                db_session, user_obj.user_id, "Test User", flight_obj.flight_id, seat_class
            )
            assert result.status == "booked"
            assert result.seat_class == seat_class

    def test_book_flight_class_exhausted_after_booking(self, db_session, sample_flight_data):
        """Test a class with one seat left is sold out after one booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        first = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "galaxium"
        )
        assert first.status == "booked"

        second = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "galaxium"
        )
        assert isinstance(second, ErrorResponse)
        assert second.error_code == "NO_SEATS_AVAILABLE"

    def test_cancel_booking_restores_seat_in_booking_class(self, db_session, sample_flight_data):
        """Test cancelling restores a seat only in the booking's own class."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        booked = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "business"
        )
        db_session.refresh(flight_obj)
        assert flight_obj.seats_business == 0

        result = booking.cancel_booking(db_session, booked.booking_id)
        assert result.status == "cancelled"
        assert result.seat_class == "business"

        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 3
        assert flight_obj.seats_business == 1
        assert flight_obj.seats_galaxium == 1

    def test_get_bookings_includes_seat_class(self, db_session, sample_flight_data):
        """Test retrieved bookings carry their seat class."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(**sample_flight_data))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "galaxium")

        result = booking.get_bookings(db_session, user_obj.user_id)
        assert len(result) == 1
        assert result[0].seat_class == "galaxium"


class TestSeatClasses:
    """Test seat class definitions and price calculation."""

    def test_class_price_multipliers(self):
        """Test class price applies the 1.5 / 2.5 / 3 multipliers."""
        assert class_price(1000000, "economy") == 1500000
        assert class_price(1000000, "business") == 2500000
        assert class_price(1000000, "galaxium") == 3000000

    def test_class_price_returns_int(self):
        """Test class price is an int even when the multiplier yields a fraction."""
        result = class_price(1001, "economy")  # 1501.5
        assert isinstance(result, int)
        assert result == round(1001 * 1.5)

        result = class_price(333, "business")  # 832.5
        assert isinstance(result, int)
        assert result == round(333 * 2.5)

        result = class_price(333, "galaxium")
        assert isinstance(result, int)
        assert result == 999

    def test_is_valid_seat_class(self):
        """Test seat class validation."""
        assert is_valid_seat_class("economy")
        assert is_valid_seat_class("business")
        assert is_valid_seat_class("galaxium")
        assert not is_valid_seat_class("first_class")
        assert not is_valid_seat_class("Economy")
        assert not is_valid_seat_class("")
