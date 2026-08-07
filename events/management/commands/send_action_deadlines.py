from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from events.calendarsync import send_action_deadline_email
from events.models import ActionCompletion, EventAction, EventMembership, ReminderLog

# Daily cadence instead of fixed 24h/1h windows: one reminder a day for the
# week leading up to the deadline, so a task doesn't fall off people's
# radar until the night before.
DAYS_BEFORE = list(range(7, 0, -1))


def _window_display(days):
    return '1 day' if days == 1 else f'{days} days'


class Command(BaseCommand):
    help = "Send daily action-deadline reminder emails for before/after event tasks, starting 7 days out."

    def handle(self, *args, **options):
        now = timezone.now()
        tolerance = timedelta(minutes=max(1, settings.REMINDER_POLL_MINUTES))
        sent = 0

        upcoming_actions = EventAction.objects.filter(deadline__gt=now).select_related('event')
        for action in upcoming_actions:
            for days in DAYS_BEFORE:
                target = action.deadline - timedelta(days=days)
                if not (target <= now < target + tolerance):
                    continue
                label = f'{days}d'

                # Completion is per-person now -- someone who's already done
                # their part doesn't need nagging just because others haven't.
                completed_user_ids = set(
                    ActionCompletion.objects.filter(action=action).values_list('user_id', flat=True)
                )
                memberships = EventMembership.objects.filter(
                    event=action.event, rsvp_status=EventMembership.STATUS_GOING,
                ).exclude(user_id__in=completed_user_ids).select_related('user')
                for membership in memberships:
                    _, created = ReminderLog.objects.get_or_create(
                        user=membership.user, event=action.event, event_action=action, planning_call=None,
                        reminder_type=ReminderLog.TYPE_ACTION_DEADLINE, window_label=label,
                    )
                    if created:
                        send_action_deadline_email(action, membership.user, _window_display(days))
                        sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} action deadline reminder email(s).'))
