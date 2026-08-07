"""Manual Google OAuth 2.0 authorization-code flow -- no allauth/social-auth
dependency, so it stays consistent with the rest of this project's
"plain Django, few moving parts" style. Google verifies the user's email
for us, so accounts created this way skip the is_active email-verification
gate that manual email/password signups go through (see accounts/views.py).

GOOGLE_OAUTH_CLIENT_ID/SECRET are blank until real credentials are added
to .env -- every entry point below checks for that and bounces back to
login with a message instead of erroring.
"""

import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect
from django.urls import reverse

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'

User = get_user_model()


def _is_configured():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def _redirect_uri(request):
    return settings.GOOGLE_OAUTH_REDIRECT_URI or request.build_absolute_uri(reverse('accounts:google-callback'))


def google_login(request):
    if not _is_configured():
        messages.error(request, 'Google sign-in is not configured yet.')
        return redirect('accounts:login')

    state = secrets.token_urlsafe(24)
    request.session['google_oauth_state'] = state
    params = {
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri': _redirect_uri(request),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account',
    }
    return redirect(f'{GOOGLE_AUTH_URL}?{urlencode(params)}')


def google_callback(request):
    if not _is_configured():
        messages.error(request, 'Google sign-in is not configured yet.')
        return redirect('accounts:login')

    if request.GET.get('error'):
        messages.error(request, 'Google sign-in was cancelled.')
        return redirect('accounts:login')

    state = request.GET.get('state')
    expected_state = request.session.pop('google_oauth_state', None)
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        messages.error(request, 'Google sign-in failed (invalid state). Please try again.')
        return redirect('accounts:login')

    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Google sign-in failed. Please try again.')
        return redirect('accounts:login')

    try:
        token_response = requests.post(GOOGLE_TOKEN_URL, data={
            'code': code,
            'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
            'redirect_uri': _redirect_uri(request),
            'grant_type': 'authorization_code',
        }, timeout=10)
        token_response.raise_for_status()
        access_token = token_response.json()['access_token']

        userinfo_response = requests.get(
            GOOGLE_USERINFO_URL, headers={'Authorization': f'Bearer {access_token}'}, timeout=10,
        )
        userinfo_response.raise_for_status()
        profile = userinfo_response.json()
    except (requests.RequestException, KeyError, ValueError):
        messages.error(request, "Couldn't reach Google. Please try again.")
        return redirect('accounts:login')

    email = (profile.get('email') or '').lower().strip()
    if not email or not profile.get('email_verified', True):
        messages.error(request, 'Your Google account has no verified email address.')
        return redirect('accounts:login')

    google_id = profile.get('sub', '')
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User(
            email=email,
            first_name=profile.get('given_name', ''),
            last_name=profile.get('family_name', ''),
            google_id=google_id or None,
            is_active=True,
        )
        user.set_unusable_password()
        user.save()
    else:
        update_fields = []
        if not user.is_active:
            user.is_active = True
            update_fields.append('is_active')
        if google_id and user.google_id != google_id:
            user.google_id = google_id
            update_fields.append('google_id')
        if update_fields:
            user.save(update_fields=update_fields)

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    from events.models import Invitation
    accepted = Invitation.accept_all_for_email(user)
    if accepted:
        messages.success(request, f"Welcome! You've been added to {accepted} event(s) you were invited to.")
    else:
        messages.success(request, f'Welcome, {user.display_name}!')
    return redirect('events:dashboard')
