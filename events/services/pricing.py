from dataclasses import dataclass
from datetime import time, timedelta
from django.utils import timezone

from events.models import EventType


# Holds all of the logic for pricing for events.
@dataclass(frozen=True)
class PriceQuote:
    base_cents: int
    discounts: list[dict]
    additional_items: list[dict]
    final_cents: int

def attendee_price(event, profile):
    # Calculate user's age on event start date
    age = profile.age_on(event.start_time.date())

    # Find applicable price tier based on user age (if any)
    tier = (event.price_tiers
            .filter(min_age__lte=age, max_age__gte=age)
            .order_by('min_age')
            .first()
    )

    # Return the price of the user's tier if found or the event base price otherwise.
    return tier.price_cents if tier else event.base_price_cents

# Creates a PriceQuote object for the user and applies discounts/additional items.
def quote_price(*, event, profile, registration_time, arrival_time, student_discount, weapon_rental) -> PriceQuote:
    # Initialize defaults for price information:
    discounts: list[dict] = []
    additional_items: list[dict] = []

    # Calculate Base Price for price information (see user_price function)
    base = attendee_price(event, profile)

    # Early Bird Cutoff: A week prior to the event start date at midnight
    early_bird_cutoff = timezone.make_aware(
        timezone.datetime.combine(event.start_time.date() - timedelta(weeks=1), time(0, 0)),
        timezone.get_current_timezone()
    )
    # Make sure registration time is aware:
    if timezone.is_naive(registration_time):
        registration_time = timezone.make_aware(registration_time, timezone.get_current_timezone())

    # Late Arrival Cutoff: At 3pm the day the event startes (I.E. Saturday at 3pm)
    late_arrival_cutoff = timezone.make_aware(
        timezone.datetime.combine(event.start_time.date, time(15, 0)),
        timezone.get_current_timezone()
    )
    # Make sure arrival time is aware:
    if timezone.is_naive(arrival_time):
        arrival_time = timezone.make_aware(arrival_time, timezone.get_current_timezone())

    # First-Time Discount: Check if user has attended a main event before:
    has_attended_main_event = (
        profile.registrations
        .filter(
            checked_in=True,
            event__event_type__in=[EventType.JUNIOR, EventType.SENIOR],
        )
        .exists()
    )
    is_first_event = not has_attended_main_event
    
    # Compute Discounts/Additional Items for Junior Events
    if event.event_type == EventType.JUNIOR:
        # Early Bird: Registered a week prior to the event for a $10 discount
        if registration_time < early_bird_cutoff:
            discounts.append({"type": "early_bird", "amount_cents": 1000, "reason": "Registered a week prior to the Event"})

        # Late Arrival: Determine if arrival time is after the late arrival cutoff for $10 discount.
        if arrival_time >= late_arrival_cutoff:
            discounts.append({"type": "late_arrival", "amount_cents": 1000, "reason": "Arriving after 3:00pm Saturday"})

        # First-time Discount: Applies a $35 discount if this is the user's first event. Comes with free weapon rental.
        if is_first_event:
            discounts.append({"type": "first_time", "amount_cents": 3500, "reason": "First time attending a main event"})
            additional_items.append({"type": "weapon_rental", "amount_cents": 0, "reason": "Free weapon rental for first time attendees"})

        # Weapon Rental: Applies a $20 charge if user requested weapon
        if weapon_rental and not is_first_event:
            additional_items.append({"type": "weapon_rental", "amount_cents": 2000, "reason": "Weapon rental"})

    # Compute Discounts/Additional Items for Senior Events
    elif event.event_type == EventType.SENIOR:
        # Early Bird: Registered a week prior to the event for a $10 discount
        if registration_time < early_bird_cutoff:
            discounts.append({"type": "early_bird", "amount_cents": 1000, "reason": "Registered a week prior to the Event"})

        # Late Arrival: Determine if arrival time is after the late arrival cutoff for $5 discount.
        if arrival_time >= late_arrival_cutoff:
            discounts.append({"type": "late_arrival", "amount_cents": 500, "reason": "Arriving after 3:00pm Saturday"})

        # Student Discount: Applies a $5 discount if the user registers as a student.
        if student_discount:
            discounts.append({"type": "student_discount", "amount_cents": 500, "reason": "Registered as a student"})

        # First-time Discount: Applies a $35 discount if this is the user's first event. Comes with free weapon rental.
        if is_first_event:
            discounts.append({"type": "first_time", "amount_cents": 3500, "reason": "First time attending a main event"})
            additional_items.append({"type": "weapon_rental", "amount_cents": 0, "reason": "Free weapon rental for first time attendees"})

        # Weapon Rental: Applies a $20 charge if user requested weapon
        if weapon_rental and not is_first_event:
            additional_items.append({"type": "weapon_rental", "amount_cents": 2000, "reason": "Weapon rental"})

    # Compute final price and return a new PriceQuote object
    discount_total = sum(d["amount_cents"] for d in discounts)
    additional_items_total = sum(i["amount_cents"] for i in additional_items)
    final = max(0, base - discount_total + additional_items_total)

    return PriceQuote(base_cents=base, discounts=discounts, additional_items=additional_items, final_cents=final)