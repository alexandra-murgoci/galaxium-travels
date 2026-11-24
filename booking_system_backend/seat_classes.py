"""Single source of truth for seat classes: price multipliers and perks."""

DEFAULT_SEAT_CLASS = "economy"

SEAT_CLASSES = {
    "economy": {
        "multiplier": 1.5,
        "description": "Standard seat with onboard oxygen and a complimentary meal pouch.",
    },
    "business": {
        "multiplier": 2.5,
        "description": "Extra legroom, priority boarding and a gourmet zero-gravity menu.",
    },
    "galaxium": {
        "multiplier": 3,
        "description": "Private suite with panoramic viewport, personal concierge and lounge access.",
    },
}


def is_valid_seat_class(seat_class: str) -> bool:
    """Return True if seat_class is one of the defined classes."""
    return seat_class in SEAT_CLASSES


def class_price(base_price: int, seat_class: str) -> int:
    """Price for a seat class: round(base price x multiplier) as an int."""
    return round(base_price * SEAT_CLASSES[seat_class]["multiplier"])
