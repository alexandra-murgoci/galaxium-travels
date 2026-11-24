# Galaxium Booking System

A unified booking system for Galaxium Travels that serves both **REST API** and **MCP (Model Context Protocol)** from a single server.

## Features

- **Dual Protocol Support**: Same business logic exposed via REST and MCP
- **Single Server**: One codebase, one port, both protocols
- **SQLite Database**: Simple file-based storage for demos
- **Demo Data**: Pre-seeded with space travel flights and users
- **Seat Classes**: Economy, Business and Galaxium with per-class pricing and seat inventory

## Quick Start

### Install Dependencies

```bash
cd booking_system
pip install -r requirements.txt
```

### Run the Server

```bash
python server.py
```

The server starts on port **8080** with:
- REST endpoints at `/api/*`
- MCP tools at `/mcp`
- Health check at `/`

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/flights` | List all available flights with per-class prices and seats |
| POST | `/api/book` | Book a flight (optional `seat_class`, defaults to `economy`) |
| GET | `/api/bookings/{user_id}` | Get user's bookings |
| POST | `/api/cancel/{booking_id}` | Cancel a booking (restores the seat in its class) |
| POST | `/api/register` | Register a new user |
| GET | `/api/user?name=...&email=...` | Get user by name and email |

### MCP Tools

| Tool | Description |
|------|-------------|
| `list_flights` | List all available flights with per-class prices and seats |
| `book_flight` | Book a seat on a flight (optional `seat_class`, defaults to `economy`) |
| `get_bookings` | Get user's bookings |
| `cancel_booking` | Cancel a booking (restores the seat in its class) |
| `register_user` | Register a new user |
| `get_user_id` | Get user by name and email |

### Seat Classes

Each flight has a base `price` and a separate seat count per class. The class price is `round(base price x multiplier)` as an integer. Multipliers and perk descriptions are defined in `seat_classes.py`.

| Class | Multiplier | Seat column on `flights` |
|-------|------------|--------------------------|
| `economy` (default) | 1.5x | `seats_economy` |
| `business` | 2.5x | `seats_business` |
| `galaxium` | 3x | `seats_galaxium` |

`GET /flights` (and the MCP `list_flights` tool) returns `FlightOut`. `price` is the base price; there is no flight-level `seats_available`. Each entry in `seat_classes` holds the class price, remaining seats and perks text:

```json
{
  "flight_id": 1,
  "origin": "Earth",
  "destination": "Mars",
  "departure_time": "...",
  "arrival_time": "...",
  "price": 1000000,
  "seat_classes": {
    "economy":  {"price": 1500000, "seats_available": 3, "description": "..."},
    "business": {"price": 2500000, "seats_available": 1, "description": "..."},
    "galaxium": {"price": 3000000, "seats_available": 1, "description": "..."}
  }
}
```

`POST /book` and `POST /cancel/{booking_id}` return `BookingOut`, which includes `seat_class` (the class price is not stored on the booking; derive it from the flight's `seat_classes`):

```json
{"booking_id": 21, "user_id": 1, "flight_id": 1, "status": "booked", "booking_time": "...", "seat_class": "business"}
```

### Error Codes

Business errors are returned as HTTP 200 with an `ErrorResponse` (`success`, `error`, `error_code`, `details`); the MCP tools raise an error with the same message instead. Seat-class related codes:

| Code | Meaning |
|------|---------|
| `INVALID_SEAT_CLASS` | `seat_class` is not `economy`, `business` or `galaxium` (returned by the service layer, e.g. via MCP) |
| `NO_SEATS_AVAILABLE` | The requested class has no seats left on that flight (other classes may still be bookable) |

On the REST `/book` endpoint an unknown `seat_class` is rejected earlier by request validation with HTTP 422 (FastAPI validation error), so `INVALID_SEAT_CLASS` is not returned there.

## Usage Examples

### REST API

```bash
# List flights
curl http://localhost:8080/api/flights

# Register a user
curl -X POST http://localhost:8080/api/register \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com"}'

# Book a flight (defaults to economy)
curl -X POST http://localhost:8080/api/book \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "name": "Alice", "flight_id": 1}'

# Book a flight in a specific seat class
curl -X POST http://localhost:8080/api/book \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "name": "Alice", "flight_id": 1, "seat_class": "business"}'

# Get bookings
curl http://localhost:8080/api/bookings/1

# Cancel a booking
curl -X POST http://localhost:8080/api/cancel/1
```

### MCP (with Claude Code or MCP Inspector)

Connect to `http://localhost:8080/mcp` and use the available tools:

```
list_flights()
register_user(name="John Doe", email="john@example.com")
book_flight(user_id=1, name="Alice", flight_id=1)
book_flight(user_id=1, name="Alice", flight_id=1, seat_class="galaxium")
get_bookings(user_id=1)
cancel_booking(booking_id=1)
```

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_services.py
pytest tests/test_rest.py
```

## Project Structure

```
booking_system/
├── server.py          # Main server - exposes REST & MCP
├── seat_classes.py    # Seat class multipliers and perks
├── services/          # Business logic layer
│   ├── booking.py     # Booking operations
│   ├── flight.py      # Flight operations
│   └── user.py        # User operations
├── models.py          # SQLAlchemy ORM models
├── schemas.py         # Pydantic request/response schemas
├── db.py              # Database configuration
├── seed.py            # Demo data seeding
├── tests/             # Test suite
│   ├── test_services.py
│   └── test_rest.py
├── requirements.txt
├── Dockerfile
└── pytest.ini
```

## Demo Data

The server seeds the database with:
- **10 users**: Alice, Bob, Charlie, Diana, Eve, Frank, Grace, Heidi, Ivan, Judy
- **10 flights**: Interplanetary routes (Earth, Mars, Moon, Venus, Jupiter, Europa, Pluto), each with its own `seats_economy`, `seats_business` and `seats_galaxium` counts (some classes are seeded as sold out)
- **20 bookings**: Random bookings across users and flights, each with a random `seat_class` (seeded bookings do not decrement seat counts)

### Database Schema Change

`flights.seats_available` was replaced by `seats_economy`, `seats_business` and `seats_galaxium`, and `bookings` gained a `seat_class` column (not null, default `economy`). There is no migration and `create_all` does not alter existing tables, so an existing `booking.db` with the previous schema must be deleted (stop the server first); it is recreated and re-seeded on the next start.

## Docker

```bash
# Build
docker build -t galaxium-booking .

# Run
docker run -p 8080:8080 galaxium-booking
```

## Architecture

The system uses a **service layer** pattern:

1. **Services** (`services/`) - Pure business logic functions
2. **Server** (`server.py`) - Thin wrappers exposing services via REST and MCP
3. **Models** (`models.py`) - SQLAlchemy ORM definitions
4. **Schemas** (`schemas.py`) - Pydantic validation schemas

This architecture ensures:
- Business logic is tested independently of transport layer
- Same validation and error handling for both REST and MCP
- Easy to add new transport layers (GraphQL, gRPC, etc.)
