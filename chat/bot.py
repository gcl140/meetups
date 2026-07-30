"""Rule-based bot commands for the event chat room. No external LLM/API
calls, every command just reads the event's own data."""

from django.utils import timezone

HELP_TEXT = (
    "Commands: /help, this message · /attendees, who's going · "
    "/schedule, upcoming planning calls · /actions, pending before/after-event actions"
)


def handle_command(text, event):
    command = text.strip().split()[0].lower()

    if command == '/help':
        return HELP_TEXT

    if command == '/attendees':
        from events.models import EventMembership
        going = EventMembership.objects.filter(
            event=event, rsvp_status=EventMembership.STATUS_GOING,
        ).select_related('user')
        if not going:
            return 'No one has RSVP’d Going yet.'
        names = ', '.join(str(m.user) for m in going)
        return f'Going ({going.count()}): {names}'

    if command == '/schedule':
        calls = event.planning_calls.filter(scheduled_at__gte=timezone.now())
        if not calls:
            return 'No upcoming planning calls scheduled.'
        lines = [f'- {c.title} at {c.scheduled_at:%Y-%m-%d %H:%M UTC}' for c in calls]
        return 'Upcoming planning calls:\n' + '\n'.join(lines)

    if command == '/actions':
        actions = event.actions.filter(deadline__gte=timezone.now())
        if not actions:
            return 'No pending action items.'
        lines = [
            f'- [{a.get_action_type_display()}] {a.title} (due {a.deadline:%Y-%m-%d %H:%M UTC})'
            for a in actions
        ]
        return 'Pending actions:\n' + '\n'.join(lines)

    return f"Sorry, I don't know \"{command}\". Try /help."
