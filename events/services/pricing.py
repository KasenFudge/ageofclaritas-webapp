from dataclasses import dataclass
from datetime import timedelta
from django.utils import timezone

from events.models import EventType


# Holds all of the logic for pricing for events.
@dataclass(frozen=True)
class PriceQuote:
    base_cents: int
    discounts: list[dict]
    additional_items: list[dict]
    final_cents: int

def attendee_price(event, user):
    # Convert UTC timestamp safely to localized target date
    local_event_date = timezone.localdate(event.start_time)
    age = user.age_on(local_event_date)

    # Find applicable price tier based on user age (if any)
    tier = (event.price_tiers
            .filter(min_age__lte=age, max_age__gte=age)
            .order_by('min_age')
            .first()
    )

    # Return the price of the user's tier if found or the event base price otherwise.
    return tier.price_cents if tier else event.base_price_cents


# Creates a PriceQuote object for the user and applies discounts/additional items.
def quote_price(*, event, user, registration_time, arrival_time, student_discount, weapon_rental) -> PriceQuote:
    # Initialize defaults for price information
    discounts: list[dict] = []
    additional_items: list[dict] = []

    # Calculate Base Price for price information
    base = attendee_price(event, user)
    
    # Enforce Clean Timezone Awareness Across Inputs
    if timezone.is_naive(registration_time):
        registration_time = timezone.make_aware(registration_time, timezone.get_current_timezone())
    if arrival_time and timezone.is_naive(arrival_time):
        arrival_time = timezone.make_aware(arrival_time, timezone.get_current_timezone())

    # Get local representation of the event start to prevent UTC shifting issues
    local_event_start = timezone.localtime(event.start_time)

    # Early Bird Cutoff: A week prior to the event start date at midnight
    early_bird_cutoff = (local_event_start - timedelta(weeks=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    
    # Late Arrival Cutoff: At 3pm the day the event starts (e.g., Saturday at 3:00 PM)
    late_arrival_cutoff_sat = local_event_start.replace(
        hour=15, minute=0, second=0, microsecond=0
    )

    # First Event Discount: Check if user has attended a main event before
    has_attended_main_event = (
        user.registrations
        .filter(
            checked_in=True,
            event__event_type__in=[EventType.JUNIOR, EventType.SENIOR],
        )
        .exists()
    )
    is_first_event = not has_attended_main_event

    # Process Universal Core Rules (Applies to ALL event types)
    # Early Bird Discount: $10 off if registering early.
    if registration_time < early_bird_cutoff:
        discounts.append({"type": "early_bird", "amount_cents": 1000, "reason": "Early Bird Discount (Registered 7+ days early)"})

    # First Event Discount: $35 off if it is their first event, and a free weapon rental
    if is_first_event:
        discounts.append({"type": "first_time", "amount_cents": 3500, "reason": "First-Time Player Discount"})
        additional_items.append({"type": "weapon_rental", "amount_cents": 0, "reason": "First-Time Player Token: Free Weapon Rental"})
    # Weapon Rental: $20 charge to rent weapons.
    elif weapon_rental:
        additional_items.append({"type": "weapon_rental", "amount_cents": 2000, "reason": "Weapon Rental"})

    # Process Type-Specific Rules
    if event.event_type == EventType.JUNIOR:
        if arrival_time:
            local_arrival = timezone.localtime(arrival_time)
            # weekday() returns 5 for Saturday, 6 for Sunday
            if local_arrival.weekday() == 6:
                discounts.append({"type": "late_arrival_sunday", "amount_cents": 2000, "reason": "Late Arrival Discount (Sunday-Only Attendance)"})
            elif local_arrival >= late_arrival_cutoff_sat:
                discounts.append({"type": "late_arrival_saturday", "amount_cents": 1000, "reason": "Late Arrival Discount (Saturday after 3:00 PM)"})

    elif event.event_type == EventType.SENIOR:
        if arrival_time:
            local_arrival = timezone.localtime(arrival_time)
            if local_arrival.weekday() == 6:
                discounts.append({"type": "late_arrival_sunday", "amount_cents": 1500, "reason": "Late Arrival Discount (Sunday-Only Attendance)"})
            elif local_arrival >= late_arrival_cutoff_sat:
                discounts.append({"type": "late_arrival_saturday", "amount_cents": 500, "reason": "Late Arrival Discount (Saturday after 3:00 PM)"})

        if student_discount:
            discounts.append({"type": "student_discount", "amount_cents": 500, "reason": "Active Student Discount"})

    # Compute final price and return a new PriceQuote object
    discount_total = sum(d["amount_cents"] for d in discounts)
    additional_items_total = sum(i["amount_cents"] for i in additional_items)
    
    # Clamping discounts to base ticket price protects your physical add-on balances
    ticket_subtotal = max(0, base - discount_total)
    final = ticket_subtotal + additional_items_total

    return PriceQuote(base_cents=base, discounts=discounts, additional_items=additional_items, final_cents=final)