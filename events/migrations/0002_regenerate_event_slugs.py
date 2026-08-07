from django.db import migrations
from django.utils.text import slugify

from events.models import random_slug_suffix


def regenerate_slugs(apps, schema_editor):
    Event = apps.get_model('events', 'Event')
    for event in Event.objects.all():
        base_slug = slugify(' '.join(event.title.split()[:3]))[:100] or 'event'
        slug = f'{base_slug}-{random_slug_suffix()}'
        while Event.objects.filter(slug=slug).exclude(pk=event.pk).exists():
            slug = f'{base_slug}-{random_slug_suffix()}'
        event.slug = slug
        event.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(regenerate_slugs, migrations.RunPython.noop),
    ]
