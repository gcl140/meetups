from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from events.calendarsync import send_call_reminder_email
from events.models import EventMembership, PlanningCall, ReminderLog

# Same daily-for-a-week cadence as send_action_deadlines.
DAYS_BEFORE = list(range(7, 0, -1))


def _window_display(days):
    return '1 day' if days == 1 else f'{days} days'


class Command(BaseCommand):
    help = 'Send daily planning-call reminder emails, starting 7 days out from the call.'

    def handle(self, *args, **options):
        now = timezone.now()
        tolerance = timedelta(minutes=max(1, settings.REMINDER_POLL_MINUTES))
        sent = 0

        upcoming_calls = PlanningCall.objects.filter(scheduled_at__gt=now).select_related('event')
        for call in upcoming_calls:
            for days in DAYS_BEFORE:
                target = call.scheduled_at - timedelta(days=days)
                if not (target <= now < target + tolerance):
                    continue
                label = f'{days}d'

                memberships = EventMembership.objects.filter(
                    event=call.event, rsvp_status=EventMembership.STATUS_GOING,
                ).select_related('user')
                for membership in memberships:
                    _, created = ReminderLog.objects.get_or_create(
                        user=membership.user, event=call.event, event_action=None, planning_call=call,
                        reminder_type=ReminderLog.TYPE_CALL_REMINDER, window_label=label,
                    )
                    if created:
                        send_call_reminder_email(call, membership.user, _window_display(days))
                        sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} call reminder email(s).'))
