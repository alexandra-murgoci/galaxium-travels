import { useState } from 'react';
import type { Flight, SeatClass } from '../../types';
import { Card, Button } from '../common';
import { SeatClassSelector } from './SeatClassSelector';
import { Plane, Clock } from 'lucide-react';
import { formatDate, formatTime, calculateDuration } from '../../utils/formatters';
import { getFirstAvailableClass } from '../../utils/seatClasses';
import { motion } from 'framer-motion';

interface FlightCardProps {
  flight: Flight;
  onBook: (flight: Flight, seatClass: SeatClass) => void;
}

export const FlightCard = ({ flight, onBook }: FlightCardProps) => {
  const [pickedClass, setPickedClass] = useState<SeatClass | null>(null);
  const firstAvailable = getFirstAvailableClass(flight);
  const isSoldOut = firstAvailable === undefined;
  // Use the picked class only while it still has seats (flights reload after booking)
  const selectedClass =
    pickedClass && flight.seat_classes[pickedClass].seats_available > 0
      ? pickedClass
      : firstAvailable;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.3 }}
    >
      <Card className="h-full flex flex-col">
        {/* Route Header */}
        <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cosmic-gradient">
              <Plane className="text-white" size={24} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-star-white">
                {flight.origin} → {flight.destination}
              </h3>
              <p className="text-sm text-star-white/60">
                Flight #{flight.flight_id}
              </p>
            </div>
          </div>
        </div>

        {/* Flight Details */}
        <div className="space-y-3 mb-6 flex-1">
          {/* Departure & Arrival */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-star-white/60 mb-1">Departure</p>
              <p className="text-sm font-medium text-star-white">
                {formatDate(flight.departure_time, 'MMM dd, yyyy')}
              </p>
              <p className="text-lg font-bold text-cosmic-purple">
                {formatTime(flight.departure_time)}
              </p>
            </div>
            <div>
              <p className="text-xs text-star-white/60 mb-1">Arrival</p>
              <p className="text-sm font-medium text-star-white">
                {formatDate(flight.arrival_time, 'MMM dd, yyyy')}
              </p>
              <p className="text-lg font-bold text-cosmic-purple">
                {formatTime(flight.arrival_time)}
              </p>
            </div>
          </div>

          {/* Duration */}
          <div className="flex items-center gap-2 text-star-white/70">
            <Clock size={16} />
            <span className="text-sm">
              Duration: {calculateDuration(flight.departure_time, flight.arrival_time)}
            </span>
          </div>

          {/* Seat classes: price and seats left per class */}
          <SeatClassSelector
            flight={flight}
            value={selectedClass}
            onChange={setPickedClass}
          />
        </div>

        {/* Book Button */}
        <Button
          onClick={() => selectedClass && onBook(flight, selectedClass)}
          disabled={isSoldOut}
          className="w-full"
        >
          {isSoldOut ? 'Sold Out' : 'Book Now'}
        </Button>
      </Card>
    </motion.div>
  );
};

// Made with Bob
