import type { Flight, SeatClass } from '../types';

// Display order of seat classes
export const SEAT_CLASS_ORDER: SeatClass[] = ['economy', 'business', 'galaxium'];

// Display names for seat classes (perks descriptions come from the backend)
export const SEAT_CLASS_LABELS: Record<SeatClass, string> = {
  economy: 'Economy',
  business: 'Business',
  galaxium: 'Galaxium',
};

// First class with seats left, or undefined if the flight is sold out
export const getFirstAvailableClass = (flight: Flight): SeatClass | undefined =>
  SEAT_CLASS_ORDER.find((cls) => flight.seat_classes[cls].seats_available > 0);

// Made with Bob
