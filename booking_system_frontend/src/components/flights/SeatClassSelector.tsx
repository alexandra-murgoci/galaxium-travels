import type { Flight, SeatClass } from '../../types';
import { formatCurrency } from '../../utils/formatters';
import { SEAT_CLASS_ORDER, SEAT_CLASS_LABELS } from '../../utils/seatClasses';
import { Users } from 'lucide-react';
import clsx from 'clsx';

interface SeatClassSelectorProps {
  flight: Flight;
  value: SeatClass | undefined;
  onChange: (seatClass: SeatClass) => void;
  showDescription?: boolean;
}

export const SeatClassSelector = ({
  flight,
  value,
  onChange,
  showDescription = false,
}: SeatClassSelectorProps) => {
  return (
    <div className="space-y-2" role="radiogroup" aria-label="Seat class">
      {SEAT_CLASS_ORDER.map((cls) => {
        const info = flight.seat_classes[cls];
        const isSoldOut = info.seats_available === 0;
        const isLowSeats = !isSoldOut && info.seats_available <= 2;
        const isSelected = value === cls;

        return (
          <button
            key={cls}
            type="button"
            role="radio"
            aria-checked={isSelected}
            disabled={isSoldOut}
            onClick={() => onChange(cls)}
            className={clsx(
              'w-full text-left p-3 rounded-lg border transition-all duration-200',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              isSelected
                ? 'border-cosmic-purple bg-cosmic-purple/20'
                : 'border-white/10 bg-white/5 hover:border-white/30'
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="font-semibold text-star-white">{SEAT_CLASS_LABELS[cls]}</span>
              <span className="font-bold text-star-white">{formatCurrency(info.price)}</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <Users size={14} className={isLowSeats ? 'text-solar-orange' : 'text-star-white/70'} />
              <span
                className={clsx(
                  'text-xs',
                  isSoldOut && 'text-nebula-pink font-semibold',
                  isLowSeats && 'text-solar-orange font-semibold',
                  !isSoldOut && !isLowSeats && 'text-star-white/70'
                )}
              >
                {isSoldOut ? 'Sold Out' : `${info.seats_available} seats left`}
              </span>
            </div>
            {showDescription && (
              <p className="text-xs text-star-white/60 mt-2">{info.description}</p>
            )}
          </button>
        );
      })}
    </div>
  );
};

// Made with Bob
