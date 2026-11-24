# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Commands
- Backend (run from `booking_system_backend/`, imports are flat, e.g. `from models import ...`, so other cwd breaks): `python server.py` (port 8080), `pytest`
- Single test: `pytest tests/test_services.py::TestBookingService::test_name` (`pytest.ini` adds `-v --tb=short`)
- Frontend (from `booking_system_frontend/`): `npm run build` (= `tsc -b && vite build`, the only typecheck), `npm run lint`. No frontend test framework exists.
- `start.sh` is bash-only (no Windows equivalent). On Windows use `.venv\Scripts\python.exe`; `node`/`npm` may not be on PATH in the agent shell.
- `npm run lint` already has 9 errors and 2 warnings (`no-explicit-any`, etc.). Only worry about new ones.

## Backend gotchas
- No migrations. `Base.metadata.create_all` never alters existing tables, so after any model change delete `booking.db` (git-ignored).
- `server.py` lifespan calls `seed()` on every start, which WIPES all data. Seeded bookings do not decrement flight seats.
- Services return `ErrorResponse` (never raise). REST returns it with HTTP 200. MCP tools in `server.py` convert it to `raise Exception(result.details or result.error)`. Error codes are upper snake case, e.g. `NO_SEATS_AVAILABLE`.
- REST and MCP are both in `server.py` and must stay in sync (same service calls, docstrings are what AI agents read).
- Seat classes: `seat_classes.py` is the single source of truth (multipliers, perks). Inventory columns are `Flight.seats_<class>`, accessed dynamically via `getattr`/`setattr(flight, f"seats_{cls}")` in `services/booking.py`. Adding a class means: `seat_classes.py`, new `Flight` column, `schemas.py`, `seed.py`, plus frontend `SeatClass` type and `utils/seatClasses.ts`.
- Class price = `round(flight.price * multiplier)`, derived, never stored. `Flight.price` is the base price. `BookingRequest.seat_class` is validated in the schema (422 on REST), but the service re-validates (`INVALID_SEAT_CLASS`) because MCP bypasses the schema.
- Tests: `conftest.py` swaps in an in-memory SQLite DB and monkeypatches `server.SessionLocal` and `server.seed`. New tests must use the `db_session`/`client` fixtures, not `db.SessionLocal`.

## Frontend gotchas
- `services/api.ts` interceptor rejects with `error.response.data`, so error bodies are thrown, not returned. `isErrorResponse()` (checks `success === false`) is the type guard for 200-with-error responses.
- Perks text comes from the backend (`Flight.seat_classes[cls].description`). Do not duplicate it in the frontend. Labels and order live in `src/utils/seatClasses.ts`.
- `src/types/index.ts` must mirror `schemas.py` exactly. API base URL is `VITE_API_URL`, default `http://localhost:8080`.
- Files carry a trailing `// Made with Bob` comment. Keep it when editing.
