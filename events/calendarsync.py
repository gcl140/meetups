"""Calendar (.ics) generation and reminder/deadline emails with an ICS
attachment, so recipients can add the event/deadline straight to their
calendar app from the email itself.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from icalendar import Calendar, Event as ICalEvent


def _absolute_url(path):
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def build_event_ics(event):
    cal = Calendar()
    cal.add('prodid', '-//Meetups//meetups.local//')
    cal.add('version', '2.0')

    vevent = ICalEvent()
    vevent.add('uid', f'event-{event.pk}@meetups.local')
    vevent.add('summary', event.title)
    vevent.add('dtstart', event.start_datetime)
    if event.end_datetime:
        vevent.add('dtend', event.end_datetime)
    if event.description:
        vevent.add('description', event.description)
    location = event.location_name or event.location_address
    if location:
        vevent.add('location', location)
    vevent.add('url', _absolute_url(event.get_absolute_url()))
    cal.add_component(vevent)
    return cal.to_ical()


def build_action_ics(action):
    cal = Calendar()
    cal.add('prodid', '-//Meetups//meetups.local//')
    cal.add('version', '2.0')

    vevent = ICalEvent()
    vevent.add('uid', f'action-{action.pk}@meetups.local')
    vevent.add('summary', f'{action.event.title}: {action.title}')
    vevent.add('dtstart', action.deadline)
    vevent.add('dtend', action.deadline)
    if action.description:
        vevent.add('description', action.description)
    vevent.add('url', _absolute_url(action.event.get_absolute_url()))
    cal.add_component(vevent)
    return cal.to_ical()


def _send_email_with_ics(*, to_email, subject, template_prefix, context, ics_bytes, ics_filename):
    text_body = render_to_string(f'emails/{template_prefix}.txt', context)
    html_body = render_to_string(f'emails/{template_prefix}.html', context)

    msg = EmailMultiAlternatives(subject=subject, body=text_body, to=[to_email])
    msg.attach_alternative(html_body, 'text/html')
    msg.attach(ics_filename, ics_bytes, 'text/calendar')
    msg.send(fail_silently=True)


def send_event_reminder_email(membership, window_label):
    event = membership.event
    user = membership.user
    ics_bytes = build_event_ics(event)
    context = {
        'user': user,
        'event': event,
        'window_label': window_label,
        'event_url': _absolute_url(event.get_absolute_url()),
    }
    _send_email_with_ics(
        to_email=user.email,
        subject=f'Reminder: {event.title} is coming up',
        template_prefix='event_reminder',
        context=context,
        ics_bytes=ics_bytes,
        ics_filename=f'{event.slug}.ics',
    )


def send_action_deadline_email(action, user, window_label):
    ics_bytes = build_action_ics(action)
    context = {
        'user': user,
        'action': action,
        'event': action.event,
        'window_label': window_label,
        'event_url': _absolute_url(action.event.get_absolute_url()),
    }
    _send_email_with_ics(
        to_email=user.email,
        subject=f'Action needed for {action.event.title}: {action.title}',
        template_prefix='action_deadline',
        context=context,
        ics_bytes=ics_bytes,
        ics_filename=f'{action.event.slug}-action-{action.pk}.ics',
    )


def send_invite_email(invitation_or_membership, *, is_new_account, token=None):
    """invitation_or_membership is either an Invitation (email has no
    account yet) or an EventMembership (email belongs to an existing
    user)."""
    event = invitation_or_membership.event
    if is_new_account:
        email = invitation_or_membership.email
        signup_url = _absolute_url(reverse('accounts:signup')) + f'?invite={token}'
        context = {'event': event, 'signup_url': signup_url, 'event_url': _absolute_url(event.get_absolute_url())}
        to_email = email
    else:
        user = invitation_or_membership.user
        context = {'event': event, 'user': user, 'event_url': _absolute_url(event.get_absolute_url())}
        to_email = user.email

    text_body = render_to_string('emails/invite.txt', context)
    html_body = render_to_string('emails/invite.html', context)
    msg = EmailMultiAlternatives(
        subject=f"You're invited: {event.title}", body=text_body, to=[to_email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.attach(f'{event.slug}.ics', build_event_ics(event), 'text/calendar')
    msg.send(fail_silently=True)


def send_removed_email(event, user):
    context = {'event': event, 'user': user}
    text_body = render_to_string('emails/removed.txt', context)
    html_body = render_to_string('emails/removed.html', context)
    msg = EmailMultiAlternatives(
        subject=f'You were removed from {event.title}', body=text_body, to=[user.email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=True)


# Fields worth telling attendees about when an admin edits an event, and
# how to describe a change to each one in plain English.
TRACKED_EVENT_FIELDS = [
    'title', 'description', 'cover_image', 'visibility', 'capacity',
    'location_name', 'location_address', 'start_datetime', 'end_datetime',
]


def snapshot_event_fields(event):
    """Call before saving an edit form, so there's a pre-save value to
    diff the freshly-saved instance against afterwards."""
    return {field: getattr(event, field) for field in TRACKED_EVENT_FIELDS}


def _format_datetime(value):
    return value.strftime('%a, %b %d %Y %H:%M') if value else 'not set'


def _truncate_to_minute(value):
    # The edit form's datetime-local inputs only carry minute precision,
    # so compare at that granularity or every resave of an unrelated field
    # would falsely report the start/end time as "changed".
    return value.replace(second=0, microsecond=0) if value else value


def describe_event_changes(before, event):
    changes = []

    if before['title'] != event.title:
        changes.append(f'Title changed to "{event.title}"')

    if before['description'] != event.description:
        changes.append('Description was updated')

    if before['cover_image'] != event.cover_image:
        changes.append('Cover image was updated')

    if before['visibility'] != event.visibility:
        changes.append(f'Visibility changed to {event.get_visibility_display()}')

    if before['capacity'] != event.capacity:
        changes.append(f'Capacity changed to {event.capacity if event.capacity else "unlimited"}')

    if before['location_name'] != event.location_name or before['location_address'] != event.location_address:
        location = event.location_name or event.location_address or 'not set'
        changes.append(f'Location changed to {location}')

    if _truncate_to_minute(before['start_datetime']) != _truncate_to_minute(event.start_datetime):
        changes.append(f'Start time changed to {_format_datetime(event.start_datetime)}')

    if _truncate_to_minute(before['end_datetime']) != _truncate_to_minute(event.end_datetime):
        changes.append(f'End time changed to {_format_datetime(event.end_datetime)}')

    return changes


def send_event_updated_email(event, changes, changed_by):
    """Emails everyone still engaged with the event (Going/Maybe/Invited --
    not people who already said Not going) a summary of what changed,
    with the refreshed .ics attached since dates/location may have moved."""
    from .models import EventMembership

    recipients = (
        EventMembership.objects.filter(event=event)
        .exclude(user=changed_by)
        .exclude(rsvp_status=EventMembership.STATUS_NOT_GOING)
        .select_related('user')
    )
    if not recipients:
        return

    ics_bytes = build_event_ics(event)
    event_url = _absolute_url(event.get_absolute_url())

    for membership in recipients:
        context = {
            'user': membership.user,
            'event': event,
            'changes': changes,
            'changed_by': changed_by,
            'event_url': event_url,
        }
        _send_email_with_ics(
            to_email=membership.user.email,
            subject=f'"{event.title}" was updated',
            template_prefix='event_updated',
            context=context,
            ics_bytes=ics_bytes,
            ics_filename=f'{event.slug}.ics',
        )
