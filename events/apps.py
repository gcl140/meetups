import os

from django.apps import AppConfig
from django.conf import settings


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'

    def ready(self):
        # Avoid starting the scheduler twice under the dev autoreloader,
        # and never during migrate/makemigrations/test management commands.
        if not settings.RUN_SCHEDULER:
            return
        if os.environ.get('RUN_MAIN') != 'true' and not os.environ.get('MEETUPS_FORCE_SCHEDULER'):
            return
        import sys
        if any(cmd in sys.argv for cmd in ('migrate', 'makemigrations', 'test', 'collectstatic', 'shell')):
            return

        from . import scheduler
        scheduler.start()
