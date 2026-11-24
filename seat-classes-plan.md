# Seat Classes Plan (Economy, Business, Galaxium)

## Top-Level Overview

**Goal:** Let customers choose a seat class (Economy, Business, Galaxium) when booking a flight. Each class has its own price and its own seat inventory per flight.

**Confirmed design decisions**
- **Classes:** `economy`, `business`, `galaxium` (lowercase identifiers in API/DB; display names Economy / Business / Galaxium in UI).
- **Pricing:** Multiplier on the flight's base `price`, defined once in backend code. No per-flight price storage, no `price_paid` on bookings (price is derived).
  - Economy 1.5x, Business 2.5x, Galaxium 3x.
  - Existing `Flight.price` stays as the *base* price.
- **Availability:** Replace `Flight.seats_available` with three columns: `seats_economy`, `seats_business`, `seats_galaxium`.
- **Booking requests:** `seat_class` is optional and defaults to `economy`. Old REST and MCP callers keep working.
- **Perks:** Short static description per class, defined in code and shown in the UI.
- **Data:** No migration. `seed.py` already wipes and re-seeds on startup, and there is no Alembic. The existing `booking.db` is recreated from the new schema (delete the old file if `create_all` doesn't alter existing tables).

**Non-goals**
- Per-seat selection (seat numbers or maps).
- Storing the price paid on a booking.
- Data migration framework.
- Changing the unrelated `0.0.0.0` binding in `server.py` `__main__` (noted only; outside this task's scope).

**Approach:** Backend first (single source of truth for classes, prices and perks), then tests, then frontend. Each sub-task leaves the system working and testable.

## Sub-Tasks

### 1. Backend: seat class definitions and data model
**Intent:** Establish one place that defines the classes, multipliers and perks, and move seat inventory to per-class columns.

**Expected Outcomes**
- A single backend module/constant defines the three classes with multiplier and description.
- `Flight` has `seats_economy`, `seats_business`, `seats_galaxium`; `seats_available` is gone.
- `Booking` has a `seat_class` column (String, default `economy`).
- Pydantic schemas expose class info and accept `seat_class` on booking.

**Todo List**
1. Add a seat class definition (enum or constants plus a helper to compute class price = round(base price × multiplier) as an int).
2. Update `Flight` and `Booking` in `models.py`.
3. Update `schemas.py`:
   - `FlightOut`: per-class seat counts and per-class prices (keep base `price`). Choose a shape that is simple for the frontend, e.g. a list or dict of class → {price, seats_available, description}.
   - `BookingRequest`: optional `seat_class` (validated against the allowed classes, default `economy`).
   - `BookingOut`: include `seat_class`.
4. Decide how `FlightOut` is built from the ORM object (computed fields or construction in `services/flight.py`).

**Relevant Context**
- `booking_system_backend/models.py` (Flight, Booking)
- `booking_system_backend/schemas.py` (FlightOut, BookingRequest, BookingOut)
- `booking_system_backend/services/flight.py` (`list_flights`)

**Status:** [x] done

**Implementation notes**
- New module `booking_system_backend/seat_classes.py`: `SEAT_CLASSES` (dict: name -> `{multiplier, description}`), `DEFAULT_SEAT_CLASS = "economy"`, `is_valid_seat_class(seat_class)`, `class_price(base_price, seat_class)` (int, `round(base * multiplier)`).
- `models.py`: `Flight.seats_economy/seats_business/seats_galaxium` (Integer, not null), `Booking.seat_class` (String, not null, default `"economy"`).
- `schemas.py`: `SeatClassOut {price, seats_available, description}`; `FlightOut` keeps `price` and has `seat_classes: dict[str, SeatClassOut]` (keys `economy|business|galaxium`); `BookingRequest.seat_class` defaults to `economy`, validated by a Pydantic `field_validator` (invalid value -> FastAPI 422 on REST); `BookingOut.seat_class` added.
- `services/flight.py`: `to_flight_out(flight)` builds `FlightOut` from the ORM object; `list_flights` uses it. `FlightOut` no longer has `from_attributes`.
- Existing `booking.db` may block the new schema (`create_all` does not alter tables); delete it so it is recreated. No migration was built.
- Not verified by running the app/tests: backend dependencies (sqlalchemy, pydantic) are not installed in this environment; files were only compile-checked.
- Still referencing removed `seats_available` (left for later sub-tasks): `services/booking.py` (lines ~19, 44, 77), `seed.py` (Flight entries, lines 31-40), `tests/conftest.py` (88), `tests/test_rest.py` (27, 105, 155, 197), `tests/test_services.py` (28, 84, 98, 119, 138, 156, 176, 198, 215, 245).

---

### 2. Backend: booking and cancellation logic per class
**Intent:** Make booking and cancelling operate on the selected class's inventory.

**Expected Outcomes**
- `book_flight` validates the class, checks that class's seats and decrements only that column.
- `cancel_booking` restores a seat in the booking's class.
- An invalid class returns an `ErrorResponse` (e.g. `INVALID_SEAT_CLASS`).
- A sold-out class returns `NO_SEATS_AVAILABLE`, with details naming the class.
- REST `/book` and the MCP `book_flight` tool accept the optional `seat_class`. Tool docstrings are updated so AI agents know about it.

**Todo List**
1. Update `book_flight(db, user_id, name, flight_id, seat_class="economy")`: validate class, check the per-class seat count, decrement it, store `seat_class` on the booking.
2. Update `cancel_booking` to increment the correct per-class column.
3. Pass `seat_class` through in `server.py` (REST endpoint and MCP tool); update docstrings.
4. Keep the existing `ErrorResponse` pattern and error code naming.

**Relevant Context**
- `booking_system_backend/services/booking.py`
- `booking_system_backend/server.py` (`book_flight_endpoint`, MCP `book_flight` / `cancel_booking`)
- From Sub-Task 1: use `from seat_classes import SEAT_CLASSES, DEFAULT_SEAT_CLASS, is_valid_seat_class, class_price`. Per-class seat column name is `f"seats_{seat_class}"` (use `getattr`/`setattr` on the `Flight`). `Booking.seat_class` must be set on creation. `BookingRequest.seat_class` is already validated on REST, but the service must still validate (MCP and direct callers) and return `INVALID_SEAT_CLASS`. `BookingOut` now requires `seat_class`. `FlightOut` shape: `{flight_id, origin, destination, departure_time, arrival_time, price, seat_classes: {economy|business|galaxium: {price, seats_available, description}}}`.

**Status:** [x] done

**Implementation notes**
- `services/booking.py`: `book_flight` now validates `seat_class` (returns `INVALID_SEAT_CLASS` `ErrorResponse`), checks `seats_{seat_class}` (returns `NO_SEATS_AVAILABLE` with class details if < 1), decrements that class's count, and persists `seat_class` on the `Booking`.
- `services/booking.py`: `cancel_booking` restores the seat in `seats_{booking.seat_class}`.
- `server.py`: REST `/book` endpoint passes `request.seat_class` to `book_flight`. MCP `book_flight` tool accepts optional `seat_class: str = "economy"`. Docstrings for `/book`, MCP `book_flight`, and MCP `list_flights` updated to reflect the three seat classes and new flight payload.
- Verified with `py_compile` and in-memory SQLite integration tests against `booking_system_backend/.venv`.

---

### 3. Backend: seed data
**Intent:** Seed realistic per-class inventory and bookings with classes.

**Expected Outcomes**
- Every seeded flight has per-class seat counts (replacing `seats_available`), with the three classes' totals roughly preserving the original seat counts and every flight having at least one bookable seat.
- Seeded bookings carry a `seat_class`.

**Todo List**
1. Update the `Flight(...)` entries in `seed.py` with the three seat counts.
2. Assign a random `seat_class` to each seeded booking.

**Relevant Context**
- `booking_system_backend/seed.py` (note: seeded bookings do not decrement seats today; keep that behaviour unless it is trivial to fix)
- `Flight` model columns: `seats_economy`, `seats_business`, `seats_galaxium` (replacing `seats_available`).
- `Booking` model column: `seat_class` (values `"economy"`, `"business"`, `"galaxium"`).
- `SEAT_CLASSES` keys from `seat_classes.py`: `"economy"`, `"business"`, `"galaxium"`.
- `services/booking.py` and `server.py` are now fully updated for seat classes.

**Status:** [x] done

**Implementation notes**
- `seed.py`: each `Flight(...)` now uses `seats_economy/seats_business/seats_galaxium`. Seeded bookings get `seat_class=random.choice(list(SEAT_CLASSES))` (imported from `seat_classes`). Seeded bookings still do not decrement seats (unchanged, out of scope).
- Seeded seat counts (economy, business, galaxium), flights 1-10 in order (originals in parens): 1 Earth→Mars (3,1,1)=5 (5); 2 Earth→Moon (2,1,0)=3 (3); 3 Mars→Earth (4,2,1)=7 (7); 4 Venus→Earth (1,1,0)=2 (2); 5 Jupiter→Europa (0,0,1)=1 (1); 6 Earth→Venus (2,2,0)=4 (4); 7 Moon→Mars (4,1,1)=6 (6); 8 Mars→Jupiter (1,0,1)=2 (2); 9 Europa→Earth (1,1,1)=3 (3); 10 Earth→Pluto (0,0,1)=1 (1). Totals match the originals exactly. Sold-out classes exist on flights 2, 4, 5, 6, 8, 10; every flight has at least one bookable seat.
- Verified by running `seed()` against a throwaway SQLite DB (temp working dir, since `db.py` uses `sqlite:///./booking.db`) with `booking_system_backend/.venv`, and printing `list_flights` output: per-class prices and seats_available were correct (e.g. flight 1 base 1,000,000 -> economy 1,500,000 / business 2,500,000 / galaxium 3,000,000). Seeded bookings had a mix of all three classes.
- The existing git-ignored `booking_system_backend/booking.db` still has the OLD schema (`seats_available`) and could NOT be deleted: it is locked by another process (likely a running backend server). Stop that process and delete the file before running the app or the real seed; it is recreated from the new schema afterwards. The real DB was not modified by the verification run.
- For Sub-Task 4: the seed uses `random` without a fixed seed, so booking classes vary per run; tests should not rely on seeded data (they use `conftest.py` fixtures). Tests still referencing `seats_available`: `tests/conftest.py`, `tests/test_rest.py`, `tests/test_services.py` (see Sub-Task 1 notes for lines).

---

### 4. Backend: tests
**Intent:** Keep the suite green and cover the new behaviour.

**Expected Outcomes**
- Existing tests and fixtures updated for the per-class columns.
- New tests cover class booking, default class, invalid class, per-class sold out, per-class cancel restore, and class price calculation.
- `pytest` passes.

**Todo List**
1. Update `sample_flight_data` in `conftest.py` and all references to `seats_available` in `test_services.py` and `test_rest.py`.
2. Add service tests (`TestBookingService`, `TestFlightService`) for the new cases.
3. Add REST tests (`/flights` response shape, `/book` with and without `seat_class`, invalid class).
4. Run `pytest` from `booking_system_backend`.

**Relevant Context**
- `booking_system_backend/tests/conftest.py`, `test_services.py`, `test_rest.py`

**Status:** [x] done

**Implementation notes**
- `tests/conftest.py`: `sample_flight_data` now uses `seats_economy=3, seats_business=1, seats_galaxium=1` (replaces `seats_available=5`).
- `tests/test_services.py` and `tests/test_rest.py`: every inline `Flight(...)` now uses per-class columns (`seats_economy` = the old count, business/galaxium = 0), so each existing test keeps its original intent. Assertions on `flight_obj.seats_available` became `seats_economy`. `test_book_flight_success` (REST) now also asserts `seat_class == "economy"`.
- New service tests: each class decrements only its own column; default class is economy; invalid class -> `INVALID_SEAT_CLASS` (no seat consumed, no booking row); sold-out class -> `NO_SEATS_AVAILABLE` (details name the class) while other classes stay bookable; class exhausted after its last seat is booked; cancel restores a seat only in the booking's class; `get_bookings` carries `seat_class`; `list_flights` returns per-class price/seats/description and reflects a sold-out class. New `TestSeatClasses`: `class_price` multipliers (1.5/2.5/3), int rounding, `is_valid_seat_class`.
- New REST tests: `/flights` shape (exact key set, no `seats_available` at flight level, per-class `{price, seats_available, description}`); `/book` without `seat_class` (defaults to economy); `/book` with each class; invalid class -> 422 (no seat consumed, no booking); sold-out class -> 200 with `NO_SEATS_AVAILABLE`; `/cancel` restores the booking's class seat and returns `seat_class`.
- Result: `booking_system_backend/.venv` -> `pytest` = 47 passed (29 existing tests kept + 18 new: 12 service, 6 REST). No application code changes were needed and no bugs were found.
- Remaining warnings are pre-existing (`declarative_base`, class-based Pydantic `Config`, `datetime.utcnow`) and unrelated to this task.

---

### 5. Frontend: types and API client
**Intent:** Align the frontend data layer with the new backend contract.

**Expected Outcomes**
- `Flight`, `Booking`, `BookingRequest` types match the new schemas, with a `SeatClass` type.
- `bookFlight` sends `seat_class`.

**Todo List**
1. Update `types/index.ts` (add `SeatClass`, class pricing/seat shape on `Flight`, `seat_class` on `Booking` and `BookingRequest`).
2. Update `services/api.ts` only if the request or response handling needs changes.

**Relevant Context**
- `booking_system_frontend/src/types/index.ts`
- `booking_system_frontend/src/services/api.ts`
- Final API shapes (verified by the backend tests):
  - `GET /flights` -> `FlightOut[]`: `{flight_id, origin, destination, departure_time, arrival_time, price, seat_classes}`. `price` is the BASE price; there is no flight-level `seats_available` any more. `seat_classes` is an object keyed by `economy | business | galaxium`, each value `{price: number, seats_available: number, description: string}` (`price` is already the class price: 1.5x / 2.5x / 3x base, rounded int). A class is sold out when its `seats_available === 0`; a flight is sold out only when all three are 0.
  - `POST /book` body: `{user_id, name, flight_id, seat_class?}`. `seat_class` is optional (default `"economy"`); an unknown value gives HTTP 422 (FastAPI validation error, not the `ErrorResponse` shape).
  - `POST /book` and `POST /cancel/{booking_id}` success -> `BookingOut`: `{booking_id, user_id, flight_id, status, booking_time, seat_class}`. `GET /bookings/{user_id}` returns `BookingOut[]` (each includes `seat_class`).
  - Business errors keep HTTP 200 with `ErrorResponse` `{success: false, error, error_code, details}`. New codes: `INVALID_SEAT_CLASS` (service/MCP path) and `NO_SEATS_AVAILABLE` (now per class; `details` names the class). Existing codes unchanged.
  - Class perks text comes from `seat_classes[name].description` in the flight payload, so the frontend does not need to hardcode descriptions (display names Economy / Business / Galaxium still need a frontend label map).
  - A booking's class price is not stored on the booking; derive it from `flight.seat_classes[booking.seat_class].price`.

**Status:** [x] done

**Implementation notes**
- `types/index.ts`: added `SeatClass = 'economy' | 'business' | 'galaxium'`, `SeatClassInfo { price: number; seats_available: number; description: string }`. Updated `Flight` to include `seat_classes: Record<SeatClass, SeatClassInfo>` and removed `seats_available` (kept base `price: number`). Added `seat_class: SeatClass` to `Booking` and optional `seat_class?: SeatClass` to `BookingRequest`.
- `services/api.ts`: checked and confirmed `bookFlight(data: BookingRequest)` already passes the full `data` object to `/book`, so `seat_class` is sent properly when provided without needing changes to `api.ts`.
- Verified with TypeScript typecheck (`tsc -b`). Confirmed only the expected type errors in `FlightCard.tsx` due to `flight.seats_available` removal.

---

### 6. Frontend: flight listing and booking UI
**Intent:** Let users see class options and pick one when booking.

**Expected Outcomes**
- `FlightCard` shows each class with its price and seats left. Sold-out classes are disabled. The "Sold Out" state applies only when all classes are sold out.
- The booking flow includes a class selection step, with perks text.
- `BookingModal` shows the selected class and the class-adjusted total price, and sends `seat_class`.
- Styling follows existing Tailwind tokens, `Card`, framer-motion and toast conventions.

**Todo List**
1. Update `FlightCard.tsx` (replace the single price and seats display).
2. Add class selection UI (new small component under `components/flights/` or inside `BookingModal`).
3. Update `Flights.tsx` state to carry the selected class from card to modal. Keep the "Book Now" login check.
4. Update `BookingModal.tsx` summary and booking call.
5. Reuse `formatCurrency`. Add a display-name/perks helper in `utils/` or a constants file if needed.

**Relevant Context**
- `booking_system_frontend/src/pages/Flights.tsx`
- `booking_system_frontend/src/components/flights/FlightCard.tsx`
- `booking_system_frontend/src/components/bookings/BookingModal.tsx`
- `booking_system_frontend/src/utils/formatters.ts`
- From Sub-Task 5:
  - Types available in `types/index.ts`:
    - `SeatClass = 'economy' | 'business' | 'galaxium'`
    - `SeatClassInfo = { price: number; seats_available: number; description: string }`
    - `Flight.seat_classes: Record<SeatClass, SeatClassInfo>` (base `Flight.price` is retained; `Flight.seats_available` was removed)
    - `Booking.seat_class: SeatClass`
    - `BookingRequest.seat_class?: SeatClass`
  - Spots needing updates in UI:
    - `FlightCard.tsx` (lines 13, 14, 78, 86): currently accesses removed `flight.seats_available` and displays base `flight.price`. Needs per-class tier/card display with `flight.seat_classes[cls].price`, `seats_available`, `description`, selection state, and whole-flight sold-out logic (when all 3 classes have `seats_available === 0`).
    - `Flights.tsx`: currently passes only `Flight` to modal and receives `handleBookFlight(flight)`. Needs to track selected seat class (defaulting to `'economy'`) to pass down to `BookingModal`.
    - `BookingModal.tsx` (lines 32-36, 131): currently calls `bookFlight` without `seat_class` and displays base `flight.price`. Needs to display selected `seat_class`, perks description, adjusted class price (`flight.seat_classes[selectedClass].price`), and pass `seat_class` to `bookFlight`.
    - `BookingCard.tsx` (for Sub-Task 7, line 97): currently displays base `flight.price` and does not display `booking.seat_class`.

**Status:** [x] done

**Implementation notes**
- New `utils/seatClasses.ts`: `SEAT_CLASS_ORDER` (economy, business, galaxium), `SEAT_CLASS_LABELS: Record<SeatClass, string>` (Economy / Business / Galaxium), `getFirstAvailableClass(flight)` (first class with seats left, or `undefined`).
- New `components/flights/SeatClassSelector.tsx`: radio-style list of the three classes (label, `formatCurrency(seat_classes[cls].price)`, seats left, low-seat warning at <= 2, "Sold Out" and disabled when 0). Props: `flight`, `value` (`SeatClass | undefined`), `onChange`, optional `showDescription` (renders the backend `description` perks text). Perks text is never hardcoded in the frontend.
- `FlightCard.tsx`: base price and flight-level seats removed; renders `SeatClassSelector`. Local state holds the picked class; the effective class falls back to the first available one if the pick is sold out (e.g. after a reload). "Sold Out" label and disabled Book button apply only when all classes are sold out. `onBook` is now `(flight, seatClass)`.
- `Flights.tsx`: new `selectedClass` state (set by `handleBookFlight(flight, seatClass)`), passed to `BookingModal` with `onSeatClassChange`. Login check flow unchanged.
- `BookingModal.tsx`: new props `seatClass` and `onSeatClassChange`; shows a "Seat Class" section (selector with perks), total price label `Total Price (<Label>)` using `flight.seat_classes[seatClass].price`, and sends `seat_class` in `bookFlight`. Flights are reloaded after booking as before.
- Verified with Node v26.13.1 found at `C:\Users\ZZ021L826\AppData\Roaming\fnm\node-versions\v26.13.1\installation` (not on PATH; prepend it to `$env:Path`): `npm run build` (`tsc -b && vite build`) passes with no errors. `npm run lint` reports 9 errors and 2 warnings, none in the new files and none newly introduced: `no-explicit-any` in `BookingModal.tsx`, `Flights.tsx`, `MyBookings.tsx`, `UserIdentification.tsx`, `api.ts`; `no-unused-vars` in `formatters.ts`; `react-refresh/only-export-components` in `useUser.tsx`; `exhaustive-deps` warnings in `Flights.tsx` and `MyBookings.tsx`. In the two files edited here, the findings are on unchanged pre-existing lines.
- Not verified: no manual/browser run of the UI and no end-to-end test against the backend.

---

### 7. Frontend: My Bookings
**Intent:** Show which class each booking is in, and the correct price.

**Expected Outcomes**
- `BookingCard` shows the seat class and the price computed from the flight base price and the class multiplier (or the class price from the flight data).
- Cancel flow unchanged.

**Todo List**
1. Update `BookingCard.tsx` (class label and correct price).
2. Verify `MyBookings.tsx` passes the data needed.

**Relevant Context**
- `booking_system_frontend/src/components/bookings/BookingCard.tsx` (currently shows `flight.price`)
- `booking_system_frontend/src/pages/MyBookings.tsx`
- From Sub-Task 6: reuse `SEAT_CLASS_LABELS[booking.seat_class]` from `booking_system_frontend/src/utils/seatClasses.ts` for the class label. Class price = `flight.seat_classes[booking.seat_class].price` (`formatCurrency`). `BookingCard.tsx` still compiles because base `flight.price` still exists on `Flight`, so `tsc` does not flag it; it just shows the wrong (base) price and must be switched manually. `SeatClassSelector` is for choosing a class and is not needed on the booking card. Node is not on PATH; see the Sub-Task 6 notes for the location.

**Status:** [x] done

**Implementation notes**
- `components/bookings/BookingCard.tsx`: imports `SEAT_CLASS_LABELS` from `utils/seatClasses.ts`. The price row is labelled `Price (<Class>)` and shows `formatCurrency(flight.seat_classes[booking.seat_class].price)` instead of base `flight.price`. When `flight` is missing, the existing "Flight ID" line is kept and a `Seat Class: <Class>` line is added so the class is still visible.
- `pages/MyBookings.tsx`: no change needed. It already passes `booking` (with `seat_class`) and the matching `flight` (with `seat_classes`) to `BookingCard`. Cancel flow untouched.
- Verified with Node v26.13.1 (prepended to `$env:Path`): `npm run build` passes (`tsc -b && vite build`). `npm run lint` reports the same 9 errors and 2 warnings as before, all pre-existing and none in `BookingCard.tsx` or `MyBookings.tsx` changed lines.
- Not verified: no manual/browser run of the My Bookings page and no end-to-end test against the backend.

---

### 8. Docs and verification
**Intent:** Keep docs accurate and confirm everything works end to end.

**Expected Outcomes**
- READMEs describe seat classes, multipliers, and the new request and response fields.
- Backend `pytest` passes; frontend `npm run build` and `npm run lint` pass; a manual end-to-end check (list, book each class, cancel) works.

**Todo List**
1. Update `README.md`, `booking_system_backend/README.md` (endpoints, MCP tools, schema) and the frontend README if it describes the booking UI.
2. Run backend tests, frontend lint and build.
3. Manually smoke test via the UI.

**Relevant Context**
- `README.md`, `booking_system_backend/README.md`, `booking_system_frontend/README.md`

**Status:** [x] done

**Implementation notes**
- Docs: `README.md` (feature bullet, booking steps with class choice, new "Seat Classes" multiplier table, demo data, note to delete an old `booking.db`), `booking_system_backend/README.md` (endpoint and MCP tool descriptions, new "Seat Classes" section with `FlightOut`/`BookingOut` JSON examples, "Error Codes" with `INVALID_SEAT_CLASS` / `NO_SEATS_AVAILABLE` and the REST 422 note, curl/MCP examples with `seat_class`, `seat_classes.py` in structure, per-class seed data, "Database Schema Change" note; also removed a stray `doc` line in the Demo Data section), `booking_system_frontend/README.md` (feature bullet, `SeatClassSelector.tsx` / `seatClasses.ts` in structure, `/book` `seat_class`, booking flow with class selection).
- Backend `pytest` (`booking_system_backend/.venv`): 47 passed, 19 pre-existing warnings.
- Frontend (Node v26.13.1): `npm run build` passes. `npm run lint` reports 9 errors and 2 warnings, identical to the known pre-existing set; no new findings.
- Backend end-to-end smoke test via FastAPI `TestClient` run from a temp directory (throwaway `booking.db`, deleted afterwards; the real `booking_system_backend/booking.db` was not touched): `GET /flights` (10 flights, class prices 1.5x/2.5x/3x, no flight-level `seats_available`); `POST /book` without `seat_class` and with each of economy/business/galaxium (each decremented only its own class); invalid class -> 422; sold-out class -> 200 `NO_SEATS_AVAILABLE` naming the class; `POST /cancel` restored the seat only in the booking's class; re-cancel -> `ALREADY_CANCELLED`.
- Not verified: no browser/UI smoke test (flights page, booking modal, My Bookings) was run; no MCP-transport call was made (the MCP `INVALID_SEAT_CLASS` path is covered only by the service-layer tests).
