from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token

User = get_user_model()


class SignupVerificationTests(TestCase):
    def test_signup_creates_inactive_user_and_sends_verification_email(self):
        response = self.client.post(reverse('accounts:signup'), {
            'email': 'new@example.com', 'first_name': 'New', 'last_name': 'User',
            'password1': 'super-secret-99', 'password2': 'super-secret-99',
        })
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email='new@example.com')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify', mail.outbox[0].subject)

    def test_inactive_user_cannot_log_in_before_verifying(self):
        User.objects.create_user(email='unverified@example.com', password='testpass123', is_active=False)
        response = self.client.post(reverse('accounts:login'), {
            'username': 'unverified@example.com', 'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('verify your email', response.context['form'].errors['__all__'][0])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_verify_email_link_activates_and_logs_in(self):
        user = User.objects.create_user(email='pending@example.com', password='testpass123', is_active=False)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)

        response = self.client.get(reverse('accounts:verify-email', args=[uidb64, token]))
        self.assertRedirects(response, reverse('events:dashboard'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # session should now be authenticated as this user
        resp2 = self.client.get(reverse('events:dashboard'))
        self.assertEqual(resp2.wsgi_request.user, user)

    def test_verify_email_rejects_invalid_token(self):
        user = User.objects.create_user(email='badtoken@example.com', password='testpass123', is_active=False)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

        response = self.client.get(reverse('accounts:verify-email', args=[uidb64, 'not-a-real-token']))
        self.assertRedirects(response, reverse('accounts:resend-verification'))
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_verification_token_is_single_use(self):
        user = User.objects.create_user(email='reuse@example.com', password='testpass123', is_active=False)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)

        self.client.get(reverse('accounts:verify-email', args=[uidb64, token]))
        self.client.logout()
        second_response = self.client.get(reverse('accounts:verify-email', args=[uidb64, token]))
        self.assertRedirects(second_response, reverse('accounts:login'))

    def test_resend_verification_does_not_leak_account_existence(self):
        response_known = self.client.post(reverse('accounts:resend-verification'), {'email': 'nobody@example.com'})
        response_unknown = self.client.post(reverse('accounts:resend-verification'), {'email': 'also-nobody@example.com'})
        self.assertEqual(response_known.status_code, response_unknown.status_code)

    def test_invitation_only_accepted_after_verification(self):
        from events.models import Event, Invitation

        admin = User.objects.create_user(email='admin@example.com', password='testpass123')
        event = Event.objects.create(title='Retreat', admin=admin, start_datetime=timezone.now() + timedelta(days=5))
        Invitation.objects.create(event=event, email='invitee@example.com', invited_by=admin)

        self.client.post(reverse('accounts:signup'), {
            'email': 'invitee@example.com', 'first_name': 'Invitee', 'last_name': '',
            'password1': 'super-secret-99', 'password2': 'super-secret-99',
        })
        user = User.objects.get(email='invitee@example.com')
        from events.models import EventMembership
        self.assertFalse(EventMembership.objects.filter(event=event, user=user).exists())

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        self.client.get(reverse('accounts:verify-email', args=[uidb64, token]))
        self.assertTrue(EventMembership.objects.filter(event=event, user=user).exists())


class GoogleOAuthTests(TestCase):
    def test_login_page_hides_google_button_when_not_configured(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertNotContains(response, 'Continue with Google')

    def test_google_login_redirects_to_login_when_not_configured(self):
        response = self.client.get(reverse('accounts:google-login'))
        self.assertRedirects(response, reverse('accounts:login'))

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='test-id', GOOGLE_OAUTH_CLIENT_SECRET='test-secret')
    def test_login_page_shows_google_button_when_configured(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertContains(response, 'Continue with Google')

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='test-id', GOOGLE_OAUTH_CLIENT_SECRET='test-secret')
    def test_google_login_redirects_to_google_with_state(self):
        response = self.client.get(reverse('accounts:google-login'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts.google.com', response.url)
        self.assertIn('google_oauth_state', self.client.session)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='test-id', GOOGLE_OAUTH_CLIENT_SECRET='test-secret')
    def test_callback_rejects_mismatched_state(self):
        session = self.client.session
        session['google_oauth_state'] = 'expected-state'
        session.save()
        response = self.client.get(reverse('accounts:google-callback'), {'state': 'wrong-state', 'code': 'abc'})
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertFalse(User.objects.filter(email='googleuser@example.com').exists())

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='test-id', GOOGLE_OAUTH_CLIENT_SECRET='test-secret')
    @patch('accounts.google_oauth.requests')
    def test_callback_creates_active_verified_user(self, mock_requests):
        session = self.client.session
        session['google_oauth_state'] = 'state123'
        session.save()

        mock_requests.post.return_value = Mock(json=lambda: {'access_token': 'tok'}, raise_for_status=lambda: None)
        mock_requests.get.return_value = Mock(
            json=lambda: {
                'email': 'googleuser@example.com', 'email_verified': True,
                'given_name': 'Google', 'family_name': 'User', 'sub': 'g-12345',
            },
            raise_for_status=lambda: None,
        )

        response = self.client.get(reverse('accounts:google-callback'), {'state': 'state123', 'code': 'abc'})
        self.assertRedirects(response, reverse('events:dashboard'))

        user = User.objects.get(email='googleuser@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(user.google_id, 'g-12345')
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='test-id', GOOGLE_OAUTH_CLIENT_SECRET='test-secret')
    @patch('accounts.google_oauth.requests')
    def test_callback_activates_existing_unverified_user(self, mock_requests):
        User.objects.create_user(email='wasunverified@example.com', password='testpass123', is_active=False)
        session = self.client.session
        session['google_oauth_state'] = 'state123'
        session.save()

        mock_requests.post.return_value = Mock(json=lambda: {'access_token': 'tok'}, raise_for_status=lambda: None)
        mock_requests.get.return_value = Mock(
            json=lambda: {'email': 'wasunverified@example.com', 'email_verified': True, 'sub': 'g-999'},
            raise_for_status=lambda: None,
        )

        self.client.get(reverse('accounts:google-callback'), {'state': 'state123', 'code': 'abc'})
        user = User.objects.get(email='wasunverified@example.com')
        self.assertTrue(user.is_active)
