from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .management.commands.send_event_reminders import Command as SendRemindersCommand
from .models import Attendance, Event, EventMembership, ReminderLog

User = get_user_model()


def make_user(email, password='testpass123'):
    return User.objects.create_user(email=email, username=email.split('@')[0], password=password)


class EventModelTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@example.com')

    def test_creating_event_via_view_makes_creator_a_going_admin(self):
        self.client.login(email='admin@example.com', password='testpass123')
        response = self.client.post(reverse('events:create'), {
            'title': 'Board Games Night',
            'description': 'Bring snacks',
            'visibility': Event.VISIBILITY_OPEN,
            'start_datetime': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
        })
        event = Event.objects.get(title='Board Games Night')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(event.admin, self.admin)
        membership = EventMembership.objects.get(event=event, user=self.admin)
        self.assertEqual(membership.rsvp_status, EventMembership.STATUS_GOING)

    def test_dashboard_shows_dummy_state_and_open_events_for_uninvited_user(self):
        Event.objects.create(
            title='Open Mic', admin=self.admin, visibility=Event.VISIBILITY_OPEN,
            start_datetime=timezone.now() + timedelta(days=1),
        )
        newbie = make_user('newbie@example.com')
        self.client.login(email='newbie@example.com', password='testpass123')
        response = self.client.get(reverse('events:dashboard'))
        self.assertFalse(response.context['has_any_events'])
        self.assertEqual(len(response.context['open_events']), 1)


class RsvpApiTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@example.com')
        self.event = Event.objects.create(
            title='Hike', admin=self.admin, visibility=Event.VISIBILITY_OPEN, capacity=1,
            start_datetime=timezone.now() + timedelta(days=2),
        )
        EventMembership.objects.create(event=self.event, user=self.admin, rsvp_status=EventMembership.STATUS_GOING)

    def test_join_full_event_is_rejected(self):
        member = make_user('member@example.com')
        self.client.login(email='member@example.com', password='testpass123')
        url = reverse('api-event-join', args=[self.event.slug])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)  # capacity=1 already full via admin

    def test_join_respects_capacity(self):
        self.event.capacity = 5
        self.event.save()
        member = make_user('member@example.com')
        self.client.login(email='member@example.com', password='testpass123')
        response = self.client.post(reverse('api-event-join', args=[self.event.slug]))
        self.assertEqual(response.status_code, 201)
        self.assertTrue(EventMembership.objects.filter(event=self.event, user=member).exists())

    def test_leave_event(self):
        member = make_user('member@example.com')
        EventMembership.objects.create(event=self.event, user=member, rsvp_status=EventMembership.STATUS_GOING)
        self.client.login(email='member@example.com', password='testpass123')
        response = self.client.post(reverse('api-event-leave', args=[self.event.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventMembership.objects.filter(event=self.event, user=member).exists())

    def test_admin_cannot_leave_own_event(self):
        self.client.login(email='admin@example.com', password='testpass123')
        response = self.client.post(reverse('api-event-leave', args=[self.event.slug]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(EventMembership.objects.filter(event=self.event, user=self.admin).exists())

    def test_admin_can_remove_member(self):
        member = make_user('member@example.com')
        EventMembership.objects.create(event=self.event, user=member, rsvp_status=EventMembership.STATUS_GOING)
        self.client.login(email='admin@example.com', password='testpass123')
        url = reverse('api-event-remove-member', args=[self.event.slug, member.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventMembership.objects.filter(event=self.event, user=member).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_non_admin_cannot_remove_member(self):
        member = make_user('member@example.com')
        other = make_user('other@example.com')
        EventMembership.objects.create(event=self.event, user=member, rsvp_status=EventMembership.STATUS_GOING)
        EventMembership.objects.create(event=self.event, user=other, rsvp_status=EventMembership.STATUS_GOING)
        self.client.login(email='other@example.com', password='testpass123')
        url = reverse('api-event-remove-member', args=[self.event.slug, member.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


class CalendarExportTests(TestCase):
    def test_export_ics_returns_valid_calendar(self):
        admin = make_user('admin@example.com')
        event = Event.objects.create(
            title='Retro', admin=admin, start_datetime=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse('events:export-ics', args=[event.slug]))
        self.assertEqual(response['Content-Type'], 'text/calendar')
        content = response.content.decode()
        self.assertIn('BEGIN:VEVENT', content)
        self.assertIn('SUMMARY:Retro', content)


class AttendanceApiTests(TestCase):
    def test_self_check_in(self):
        admin = make_user('admin@example.com')
        member = make_user('member@example.com')
        event = Event.objects.create(title='Cleanup', admin=admin, start_datetime=timezone.now() + timedelta(days=1))
        EventMembership.objects.create(event=event, user=member, rsvp_status=EventMembership.STATUS_GOING)

        self.client.login(email='member@example.com', password='testpass123')
        url = reverse('api-attendance-toggle', args=[event.slug, member.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        record = Attendance.objects.get(event=event, user=member)
        self.assertIsNotNone(record.checked_in_at)


class ReminderDedupTests(TestCase):
    def test_reminder_is_not_sent_twice_for_same_window(self):
        admin = make_user('admin@example.com')
        going_user = make_user('going@example.com')
        event = Event.objects.create(
            title='Standup', admin=admin,
            start_datetime=timezone.now() + timedelta(minutes=58),
        )
        EventMembership.objects.create(event=event, user=going_user, rsvp_status=EventMembership.STATUS_GOING)

        SendRemindersCommand().handle()
        SendRemindersCommand().handle()

        self.assertEqual(
            ReminderLog.objects.filter(user=going_user, event=event, window_label='1h').count(), 1,
        )
        self.assertEqual(len(mail.outbox), 1)


class EventUpdateNotificationTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@example.com')
        self.going_user = make_user('going@example.com')
        self.declined_user = make_user('declined@example.com')
        self.event = Event.objects.create(
            title='Original Title', description='Original description', admin=self.admin,
            location_name='Original Place', start_datetime=timezone.now() + timedelta(days=3),
        )
        EventMembership.objects.create(event=self.event, user=self.admin, rsvp_status=EventMembership.STATUS_GOING)
        EventMembership.objects.create(event=self.event, user=self.going_user, rsvp_status=EventMembership.STATUS_GOING)
        EventMembership.objects.create(
            event=self.event, user=self.declined_user, rsvp_status=EventMembership.STATUS_NOT_GOING,
        )

    def test_edit_notifies_going_members_but_not_admin_or_declined(self):
        self.client.login(email='admin@example.com', password='testpass123')
        new_start = (self.event.start_datetime + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
        response = self.client.post(reverse('events:edit', args=[self.event.slug]), {
            'title': 'New Title',
            'description': 'Original description',
            'visibility': Event.VISIBILITY_PRIVATE,
            'location_name': 'Original Place',
            'location_address': '',
            'start_datetime': new_start,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['going@example.com'])
        self.assertIn('New Title', mail.outbox[0].subject)

    def test_edit_with_no_tracked_changes_sends_no_email(self):
        self.client.login(email='admin@example.com', password='testpass123')
        response = self.client.post(reverse('events:edit', args=[self.event.slug]), {
            'title': self.event.title,
            'description': self.event.description,
            'visibility': Event.VISIBILITY_PRIVATE,
            'location_name': self.event.location_name,
            'location_address': '',
            'start_datetime': self.event.start_datetime.strftime('%Y-%m-%dT%H:%M'),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)


class EventEditModalTests(TestCase):
    def setUp(self):
        self.admin = make_user('modaladmin@example.com')
        self.event = Event.objects.create(
            title='Modal Test', admin=self.admin, start_datetime=timezone.now() + timedelta(days=3),
        )
        EventMembership.objects.create(event=self.event, user=self.admin, rsvp_status=EventMembership.STATUS_GOING)
        self.client.login(email='modaladmin@example.com', password='testpass123')

    def test_modal_get_returns_html_fragment_not_full_page(self):
        response = self.client.get(
            reverse('events:edit', args=[self.event.slug]), HTTP_X_REQUESTED_WITH='fetch',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
        content = response.content.decode()
        self.assertIn('data-modal-form', content)
        self.assertNotIn('<nav', content)  # no base.html chrome

    def test_modal_post_valid_returns_json_success(self):
        response = self.client.post(
            reverse('events:edit', args=[self.event.slug]),
            {
                'title': 'Modal Test Renamed', 'description': '', 'visibility': Event.VISIBILITY_PRIVATE,
                'location_name': '', 'location_address': '',
                'start_datetime': self.event.start_datetime.strftime('%Y-%m-%dT%H:%M'),
            },
            HTTP_X_REQUESTED_WITH='fetch',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('redirect_url', data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Modal Test Renamed')

    def test_modal_post_invalid_returns_json_with_errors_html(self):
        response = self.client.post(
            reverse('events:edit', args=[self.event.slug]),
            {'title': '', 'description': '', 'visibility': Event.VISIBILITY_PRIVATE},
            HTTP_X_REQUESTED_WITH='fetch',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('field-error', data['html'])

    def test_modal_non_admin_gets_json_403(self):
        make_user('modalother@example.com')
        self.client.login(email='modalother@example.com', password='testpass123')
        response = self.client.get(
            reverse('events:edit', args=[self.event.slug]), HTTP_X_REQUESTED_WITH='fetch',
        )
        self.assertEqual(response.status_code, 403)
