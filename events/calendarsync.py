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
