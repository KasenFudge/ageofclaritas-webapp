from events.models import EventRegistration


def attendee_user_ids(event):
    return set(EventRegistration.objects.filter(event=event, checked_in=True).values_list("user_id", flat=True))


def is_first_event_for_user(user_id, event):
    first = (
        EventRegistration.objects.filter(user_id=user_id, checked_in=True)
        .order_by("event__start_time", "id")
        .first()
    )
    return bool(first and first.event_id == event.id)


def new_player_user_ids(event):
    candidates = EventRegistration.objects.filter(event=event, checked_in=True, user__is_veteran=False)
    return [reg.user_id for reg in candidates if is_first_event_for_user(reg.user_id, event)]


def is_new_player_for_event(user, event):
    return not user.is_veteran and is_first_event_for_user(user.id, event)
