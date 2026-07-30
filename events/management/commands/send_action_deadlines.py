from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from events.calendarsync import send_action_deadline_email
from events.models import EventAction, EventMembership, ReminderLog

REMINDER_WINDOWS = [
    (timedelta(hours=24), '24h'),
    (timedelta(hours=1), '1h'),
]


class Command(BaseCommand):
    help = "Send action-deadline emails (with an .ics attachment) for before/after event actions."

    def handle(self, *args, **options):
        now = timezone.now()
        tolerance = timedelta(minutes=max(1, settings.REMINDER_POLL_MINUTES))
        sent = 0

        upcoming_actions = EventAction.objects.filter(deadline__gt=now).select_related('event')
        for action in upcoming_actions:
            for window, label in REMINDER_WINDOWS:
                target = action.deadline - window
                if not (target <= now < target + tolerance):
                    continue

                memberships = EventMembership.objects.filter(
                    event=action.event, rsvp_status=EventMembership.STATUS_GOING,
                ).select_related('user')
                for membership in memberships:
                    _, created = ReminderLog.objects.get_or_create(
                        user=membership.user, event=action.event, event_action=action,
                        reminder_type=ReminderLog.TYPE_ACTION_DEADLINE, window_label=label,
                    )
                    if created:
                        send_action_deadline_email(action, membership.user, label)
                        sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} action deadline email(s).'))
