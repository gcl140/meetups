from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from events.calendarsync import send_event_reminder_email
from events.models import Event, EventMembership, ReminderLog

REMINDER_WINDOWS = [
    (timedelta(hours=24), '24h'),
    (timedelta(hours=1), '1h'),
]


class Command(BaseCommand):
    help = 'Send upcoming-event reminder emails (with an .ics attachment) to members who are Going.'

    def handle(self, *args, **options):
        now = timezone.now()
        tolerance = timedelta(minutes=max(1, settings.REMINDER_POLL_MINUTES))
        sent = 0

        upcoming_events = Event.objects.filter(start_datetime__gt=now)
        for event in upcoming_events:
            for window, label in REMINDER_WINDOWS:
                target = event.start_datetime - window
                if not (target <= now < target + tolerance):
                    continue

                memberships = EventMembership.objects.filter(
                    event=event, rsvp_status=EventMembership.STATUS_GOING,
                ).select_related('user')
                for membership in memberships:
                    _, created = ReminderLog.objects.get_or_create(
                        user=membership.user, event=event, event_action=None,
                        reminder_type=ReminderLog.TYPE_EVENT_UPCOMING, window_label=label,
                    )
                    if created:
                        send_event_reminder_email(membership, label)
                        sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} event reminder email(s).'))
