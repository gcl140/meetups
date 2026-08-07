"""In-process job scheduler for reminder/deadline emails.

No Celery or Redis required: an APScheduler BackgroundScheduler runs inside
the same process as the web server and periodically invokes the
send_event_reminders / send_action_deadlines management commands. Dedup is
handled by ReminderLog (see models.py) so re-running on a timer is safe.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)

_scheduler = None


def _run_command(name):
    try:
        call_command(name)
    except Exception:
        logger.exception('Scheduled command %s failed', name)


def start():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)
    minutes = max(1, settings.REMINDER_POLL_MINUTES)
    _scheduler.add_job(
        lambda: _run_command('send_event_reminders'),
        'interval', minutes=minutes, id='send_event_reminders', next_run_time=None,
    )
    _scheduler.add_job(
        lambda: _run_command('send_action_deadlines'),
        'interval', minutes=minutes, id='send_action_deadlines', next_run_time=None,
    )
    _scheduler.add_job(
        lambda: _run_command('send_call_reminders'),
        'interval', minutes=minutes, id='send_call_reminders', next_run_time=None,
    )
    _scheduler.start()
    logger.info('Reminder scheduler started (every %s minute(s))', minutes)
    return _scheduler
