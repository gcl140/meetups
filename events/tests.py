from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .management.commands.send_action_deadlines import Command as SendActionDeadlinesCommand
from .management.commands.send_call_reminders import Command as SendCallRemindersCommand
from .management.commands.send_event_reminders import Command as SendRemindersCommand
from .models import (
    ActionCompletion, Attendance, CallRsvp, Event, EventAction, EventMembership, PlanningCall,
    ReminderLog,
)
from .richtext import sanitize_rich_text

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

    def test_slug_uses_first_three_words_plus_random_suffix(self):
        event = Event.objects.create(
            title='This Title Has Way More Than Three Words In It',
            admin=self.admin, start_datetime=timezone.now() + timedelta(days=1),
        )
        prefix, suffix = event.slug.rsplit('-', 1)
        self.assertEqual(prefix, 'this-title-has')
        self.assertEqual(len(suffix), 6)
        self.assertTrue(suffix.isalnum())

    def test_slug_is_stable_across_resaves(self):
        event = Event.objects.create(
            title='Stable Slug Test', admin=self.admin, start_datetime=timezone.now() + timedelta(days=1),
        )
        original_slug = event.slug
        event.description = 'updated'
        event.save()
        self.assertEqual(event.slug, original_slug)

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

    def test_end_before_start_is_rejected(self):
        self.client.login(email='admin@example.com', password='testpass123')
        start = timezone.now() + timedelta(days=5)
        response = self.client.post(reverse('events:create'), {
            'title': 'Backwards Event',
            'visibility': Event.VISIBILITY_PRIVATE,
            'start_datetime': start.strftime('%Y-%m-%dT%H:%M'),
            'end_datetime': (start - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('End time must be after the start time.', response.context['form'].errors['end_datetime'])
        self.assertFalse(Event.objects.filter(title='Backwards Event').exists())


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


class RichTextSanitizationTests(TestCase):
    def test_allowed_formatting_survives(self):
        html = '<p>Bring <strong>snacks</strong> and <em>drinks</em>, <s>maybe</s> definitely.</p>'
        self.assertEqual(sanitize_rich_text(html), html)

    def test_links_keep_only_href(self):
        html = '<p><a href="https://example.com" onclick="alert(1)" style="color:red">link</a></p>'
        cleaned = sanitize_rich_text(html)
        self.assertIn('href="https://example.com"', cleaned)
        self.assertNotIn('onclick', cleaned)
        self.assertNotIn('style', cleaned)

    def test_script_tags_and_javascript_urls_are_stripped(self):
        html = '<p>hi</p><script>alert(1)</script><a href="javascript:alert(1)">click</a>'
        cleaned = sanitize_rich_text(html)
        self.assertNotIn('<script>', cleaned)
        self.assertNotIn('alert(1)', cleaned)  # script content dropped entirely, not just unwrapped
        self.assertNotIn('javascript:', cleaned)
        self.assertNotIn('href', cleaned)  # the javascript: href itself got stripped

    def test_disallowed_tags_are_stripped_but_text_kept(self):
        html = '<div class="evil"><h1>Big title</h1><img src=x onerror=alert(1)></div>'
        cleaned = sanitize_rich_text(html)
        self.assertNotIn('<div', cleaned)
        self.assertNotIn('<h1', cleaned)
        self.assertNotIn('<img', cleaned)
        self.assertIn('Big title', cleaned)

    def test_visually_empty_quill_output_normalizes_to_blank(self):
        self.assertEqual(sanitize_rich_text('<p><br></p>'), '')
        self.assertEqual(sanitize_rich_text(''), '')
        self.assertEqual(sanitize_rich_text(None), '')

    def test_event_create_sanitizes_description_end_to_end(self):
        admin = make_user('richtext@example.com')
        self.client.login(email='richtext@example.com', password='testpass123')
        response = self.client.post(reverse('events:create'), {
            'title': 'Rich Text Event',
            'description': '<p>Safe <strong>bold</strong> text</p><script>alert(1)</script>',
            'visibility': Event.VISIBILITY_PRIVATE,
            'start_datetime': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
        })
        self.assertEqual(response.status_code, 302)
        event = Event.objects.get(title='Rich Text Event')
        self.assertNotIn('<script>', event.description)
        self.assertIn('<strong>bold</strong>', event.description)


class EventActionCompletionTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@example.com')
        self.member = make_user('member@example.com')
        self.event = Event.objects.create(
            title='Cabin Trip', admin=self.admin, start_datetime=timezone.now() + timedelta(days=5),
        )
        EventMembership.objects.create(event=self.event, user=self.admin, rsvp_status=EventMembership.STATUS_GOING)
        EventMembership.objects.create(event=self.event, user=self.member, rsvp_status=EventMembership.STATUS_GOING)
        self.action = EventAction.objects.create(
            event=self.event, title='Book cabin', deadline=timezone.now() + timedelta(days=2),
        )

    def test_regular_member_can_mark_complete(self):
        self.client.login(email='member@example.com', password='testpass123')
        response = self.client.post(reverse('api-action-complete', args=[self.action.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['my_is_completed'])
        self.assertTrue(ActionCompletion.objects.filter(action=self.action, user=self.member).exists())

    def test_toggle_twice_marks_incomplete_again(self):
        self.client.login(email='admin@example.com', password='testpass123')
        url = reverse('api-action-complete', args=[self.action.id])
        self.client.post(url)
        response = self.client.post(url)
        data = response.json()
        self.assertFalse(data['my_is_completed'])
        self.assertFalse(ActionCompletion.objects.filter(action=self.action, user=self.admin).exists())

    def test_non_member_cannot_mark_complete(self):
        make_user('outsider@example.com')
        self.client.login(email='outsider@example.com', password='testpass123')
        response = self.client.post(reverse('api-action-complete', args=[self.action.id]))
        self.assertEqual(response.status_code, 403)

    def test_one_members_completion_does_not_complete_it_for_others(self):
        # The bug this whole model exists to fix: completion used to be a
        # single shared flag, so one person checking a task off marked it
        # done for every other attendee too. It has to be independent.
        self.client.login(email='member@example.com', password='testpass123')
        self.client.post(reverse('api-action-complete', args=[self.action.id]))

        self.client.login(email='admin@example.com', password='testpass123')
        response = self.client.get(reverse('api-event-actions', args=[self.event.slug]))
        admin_view = next(a for a in response.json() if a['id'] == self.action.id)
        self.assertFalse(admin_view['my_is_completed'])
        self.assertEqual(admin_view['completed_by_names'], [str(self.member)])

        response = self.client.get(reverse('events:detail', args=[self.event.slug]))
        content = response.content.decode()
        self.assertIn('Done by: ' + str(self.member), content)
        self.assertIn('<i class="fa-solid fa-check"></i> Complete', content)  # admin's own button, still unchecked

    def test_is_past_due_is_based_on_deadline_only(self):
        # Completion no longer affects is_past_due -- that's purely "has
        # the deadline passed", with "did *I* finish it" tracked separately.
        overdue = EventAction.objects.create(
            event=self.event, title='Overdue thing', deadline=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(overdue.is_past_due)
        ActionCompletion.objects.create(action=overdue, user=self.member)
        self.assertTrue(overdue.is_past_due)


class ActionDeadlineDailyReminderTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@example.com')
        self.going = make_user('going@example.com')
        self.event = Event.objects.create(title='Cleanup Day', admin=self.admin, start_datetime=timezone.now() + timedelta(days=10))
        EventMembership.objects.create(event=self.event, user=self.going, rsvp_status=EventMembership.STATUS_GOING)

    def test_reminder_fires_seven_days_before_deadline(self):
        EventAction.objects.create(
            event=self.event, title='Reserve grill', deadline=timezone.now() + timedelta(days=7) - timedelta(minutes=1),
        )
        SendActionDeadlinesCommand().handle()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ReminderLog.objects.filter(window_label='7d', reminder_type=ReminderLog.TYPE_ACTION_DEADLINE).count(), 1)

    def test_reminder_does_not_fire_outside_daily_windows(self):
        EventAction.objects.create(
            event=self.event, title='Random task', deadline=timezone.now() + timedelta(days=3, hours=12),
        )
        SendActionDeadlinesCommand().handle()
        self.assertEqual(len(mail.outbox), 0)

    def test_member_who_completed_it_is_skipped(self):
        action = EventAction.objects.create(
            event=self.event, title='Already done', deadline=timezone.now() + timedelta(days=1) - timedelta(minutes=1),
        )
        ActionCompletion.objects.create(action=action, user=self.going)
        SendActionDeadlinesCommand().handle()
        self.assertEqual(len(mail.outbox), 0)

    def test_member_who_has_not_completed_it_still_gets_reminded(self):
        # Companion to the skip test above -- one member's completion must
        # not silence the reminder for everyone else going to the event.
        action = EventAction.objects.create(
            event=self.event, title='Half done', deadline=timezone.now() + timedelta(days=1) - timedelta(minutes=1),
        )
        other_going = make_user('other-going@example.com')
        EventMembership.objects.create(event=self.event, user=other_going, rsvp_status=EventMembership.STATUS_GOING)
        ActionCompletion.objects.create(action=action, user=self.going)

        SendActionDeadlinesCommand().handle()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [other_going.email])

    def test_reminder_is_not_sent_twice_for_same_day(self):
        EventAction.objects.create(
            event=self.event, title='Buy snacks', deadline=timezone.now() + timedelta(days=2) - timedelta(minutes=1),
        )
        SendActionDeadlinesCommand().handle()
        SendActionDeadlinesCommand().handle()
        self.assertEqual(len(mail.outbox), 1)


class CallReminderDailyTests(TestCase):
    def test_reminder_fires_seven_days_before_call(self):
        admin = make_user('admin@example.com')
        going = make_user('going@example.com')
        event = Event.objects.create(title='Reunion', admin=admin, start_datetime=timezone.now() + timedelta(days=20))
        EventMembership.objects.create(event=event, user=going, rsvp_status=EventMembership.STATUS_GOING)
        PlanningCall.objects.create(
            event=event, title='Kickoff call', scheduled_at=timezone.now() + timedelta(days=7) - timedelta(minutes=1),
            created_by=admin,
        )
        SendCallRemindersCommand().handle()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Kickoff call', mail.outbox[0].subject)


class NewActionAndCallNotificationTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@example.com')
        self.member = make_user('member@example.com')
        self.event = Event.objects.create(title='Ski Trip', admin=self.admin, start_datetime=timezone.now() + timedelta(days=15))
        EventMembership.objects.create(event=self.event, user=self.admin, rsvp_status=EventMembership.STATUS_GOING)
        EventMembership.objects.create(event=self.event, user=self.member, rsvp_status=EventMembership.STATUS_GOING)
        self.client.login(email='admin@example.com', password='testpass123')

    def test_creating_action_notifies_members(self):
        response = self.client.post(reverse('api-event-actions', args=[self.event.slug]), {
            'title': 'Buy lift tickets', 'action_type': EventAction.TYPE_BEFORE,
            'deadline': (timezone.now() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        })
        self.assertEqual(response.status_code, 201)
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertIn('Buy lift tickets', mail.outbox[0].subject)

    def test_creating_call_notifies_members_but_not_creator(self):
        response = self.client.post(reverse('api-event-calls', args=[self.event.slug]), {
            'title': 'Planning sync', 'scheduled_at': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['member@example.com'])


class CallRsvpTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@example.com')
        self.member = make_user('member@example.com')
        self.event = Event.objects.create(title='Board Game Night', admin=self.admin, start_datetime=timezone.now() + timedelta(days=8))
        EventMembership.objects.create(event=self.event, user=self.admin, rsvp_status=EventMembership.STATUS_GOING)
        EventMembership.objects.create(event=self.event, user=self.member, rsvp_status=EventMembership.STATUS_GOING)
        self.call = PlanningCall.objects.create(
            event=self.event, title='Prep call', scheduled_at=timezone.now() + timedelta(days=4), created_by=self.admin,
        )

    def test_member_can_rsvp_attending(self):
        self.client.login(email='member@example.com', password='testpass123')
        response = self.client.post(
            reverse('api-call-rsvp', args=[self.call.id]), {'will_attend': True}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['my_will_attend'])
        self.assertTrue(CallRsvp.objects.get(call=self.call, user=self.member).will_attend)

    def test_rsvp_toggling_updates_existing_row_instead_of_duplicating(self):
        self.client.login(email='member@example.com', password='testpass123')
        url = reverse('api-call-rsvp', args=[self.call.id])
        self.client.post(url, {'will_attend': True}, content_type='application/json')
        self.client.post(url, {'will_attend': False}, content_type='application/json')
        self.assertEqual(CallRsvp.objects.filter(call=self.call, user=self.member).count(), 1)
        self.assertFalse(CallRsvp.objects.get(call=self.call, user=self.member).will_attend)

    def test_call_ics_export_includes_link_and_description(self):
        self.call.description = 'Bring snack ideas'
        self.call.call_link = 'https://meet.example.com/xyz'
        self.call.save()
        response = self.client.get(reverse('events:export-call-ics', args=[self.event.slug, self.call.id]))
        self.assertEqual(response['Content-Type'], 'text/calendar')
        content = response.content.decode()
        self.assertIn('Bring snack ideas', content)
        self.assertIn('https://meet.example.com/xyz', content)

    def test_admin_notified_when_member_rsvps_attending(self):
        self.client.login(email='member@example.com', password='testpass123')
        self.client.post(
            reverse('api-call-rsvp', args=[self.call.id]), {'will_attend': True}, content_type='application/json',
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@example.com'])
        self.assertIn('attending', mail.outbox[0].subject)

    def test_admin_not_notified_for_cant_make_it(self):
        self.client.login(email='member@example.com', password='testpass123')
        self.client.post(
            reverse('api-call-rsvp', args=[self.call.id]), {'will_attend': False}, content_type='application/json',
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_not_notified_when_rsvping_to_own_call(self):
        self.client.login(email='admin@example.com', password='testpass123')
        self.client.post(
            reverse('api-call-rsvp', args=[self.call.id]), {'will_attend': True}, content_type='application/json',
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_notified_only_once_for_repeated_yes(self):
        self.client.login(email='member@example.com', password='testpass123')
        url = reverse('api-call-rsvp', args=[self.call.id])
        self.client.post(url, {'will_attend': True}, content_type='application/json')
        self.client.post(url, {'will_attend': True}, content_type='application/json')
        self.assertEqual(len(mail.outbox), 1)

    def test_attendees_list_only_includes_those_attending(self):
        self.client.login(email='member@example.com', password='testpass123')
        response = self.client.post(
            reverse('api-call-rsvp', args=[self.call.id]), {'will_attend': True}, content_type='application/json',
        )
        self.assertEqual(response.json()['attendees'], [str(self.member)])

        other = make_user('skip@example.com')
        EventMembership.objects.create(event=self.event, user=other, rsvp_status=EventMembership.STATUS_GOING)
        self.client.login(email='skip@example.com', password='testpass123')
        response = self.client.post(
            reverse('api-call-rsvp', args=[self.call.id]), {'will_attend': False}, content_type='application/json',
        )
        self.assertEqual(response.json()['attendees'], [str(self.member)])

    def test_event_page_lists_attendees_and_past_due_badges(self):
        CallRsvp.objects.create(call=self.call, user=self.member, will_attend=True)
        overdue_action = EventAction.objects.create(
            event=self.event, title='Overdue thing', deadline=timezone.now() - timedelta(hours=1),
        )
        past_call = PlanningCall.objects.create(
            event=self.event, title='Missed call', scheduled_at=timezone.now() - timedelta(hours=1),
            created_by=self.admin,
        )

        self.client.login(email='admin@example.com', password='testpass123')
        response = self.client.get(reverse('events:detail', args=[self.event.slug]))
        content = response.content.decode()
        self.assertIn(str(self.member), content)
        self.assertIn('Overdue', content)
        self.assertIn('Ended', content)


class PlanningCallSchedulingTests(TestCase):
    """UX for a call that's already ended: RSVP buttons stop making sense
    once a call is over, so the page swaps them for a note instead -- but
    keeps them while the call is still ongoing (has an end time in the
    future). Also covers the "no past times" guard on creating a call and
    the new expected-duration field these UX decisions depend on."""

    def setUp(self):
        self.admin = make_user('admin@example.com')
        self.member = make_user('member@example.com')
        self.event = Event.objects.create(title='Board Game Night', admin=self.admin, start_datetime=timezone.now() + timedelta(days=8))
        EventMembership.objects.create(event=self.event, user=self.admin, rsvp_status=EventMembership.STATUS_GOING)
        EventMembership.objects.create(event=self.event, user=self.member, rsvp_status=EventMembership.STATUS_GOING)
        self.client.login(email='admin@example.com', password='testpass123')

    def test_cannot_create_call_scheduled_in_the_past(self):
        response = self.client.post(reverse('api-event-calls', args=[self.event.slug]), {
            'title': 'Too late', 'scheduled_at': (timezone.now() - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('scheduled_at', response.json())
        self.assertFalse(PlanningCall.objects.filter(title='Too late').exists())

    def test_cannot_set_end_time_before_start_time(self):
        start = timezone.now() + timedelta(days=1)
        response = self.client.post(reverse('api-event-calls', args=[self.event.slug]), {
            'title': 'Backwards', 'scheduled_at': start.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'ends_at': (start - timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('ends_at', response.json())

    def test_creating_call_with_end_time_reports_duration(self):
        start = timezone.now() + timedelta(days=1)
        response = self.client.post(reverse('api-event-calls', args=[self.event.slug]), {
            'title': 'Sync', 'scheduled_at': start.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'ends_at': (start + timedelta(minutes=45)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['duration_minutes'], 45)

    def test_ongoing_call_shows_rsvp_buttons_and_live_badge(self):
        call = PlanningCall.objects.create(
            event=self.event, title='In progress', created_by=self.admin,
            scheduled_at=timezone.now() - timedelta(minutes=10),
            ends_at=timezone.now() + timedelta(minutes=20),
        )
        self.assertTrue(call.is_ongoing)
        self.assertFalse(call.is_past_due)

        response = self.client.get(reverse('events:detail', args=[self.event.slug]))
        content = response.content.decode()
        self.assertIn('Happening now', content)
        self.assertIn("I'll attend", content)

    def test_ended_call_hides_rsvp_buttons(self):
        call = PlanningCall.objects.create(
            event=self.event, title='Wrapped up', created_by=self.admin,
            scheduled_at=timezone.now() - timedelta(hours=2),
            ends_at=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(call.is_past_due)
        self.assertFalse(call.is_ongoing)

        response = self.client.get(reverse('events:detail', args=[self.event.slug]))
        content = response.content.decode()
        self.assertIn('This call has ended', content)
        self.assertNotIn(f'data-call-rsvp="{call.id}"', content)
