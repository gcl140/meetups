from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from .emails import send_verification_email
from .forms import EmailAuthenticationForm, ProfileForm, SignUpForm
from .tokens import email_verification_token

User = get_user_model()


class MeetupsLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = EmailAuthenticationForm
    redirect_authenticated_user = True


class MeetupsLogoutView(LogoutView):
    next_page = 'accounts:login'


def signup(request):
    if request.user.is_authenticated:
        return redirect('events:dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_verification_email(user)
            # Pending invites for this email are accepted once verification
            # proves the signup actually owns the address -- not before,
            # so signing up with someone else's email can't grab their
            # invites while the account sits unverified.
            return render(request, 'accounts/verify_sent.html', {'email': user.email})
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and user.is_active:
        messages.info(request, 'That account is already verified -- log in below.')
        return redirect('accounts:login')

    if user is not None and email_verification_token.check_token(user, token):
        user.is_active = True
        user.save(update_fields=['is_active'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        from events.models import Invitation
        accepted = Invitation.accept_all_for_email(user)
        if accepted:
            messages.success(request, f"Email verified! You've been added to {accepted} event(s) you were invited to.")
        else:
            messages.success(request, 'Email verified. Welcome to Meetups!')
        return redirect('events:dashboard')

    messages.error(request, 'That verification link is invalid or has expired.')
    return redirect('accounts:resend-verification')


def resend_verification(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=False).first()
        if user:
            send_verification_email(user)
        # Same message either way -- otherwise this becomes an
        # account-existence oracle for any email address typed in.
        messages.success(request, "If that email needs verifying, we've sent a fresh link.")
        return redirect('accounts:login')

    return render(request, 'accounts/resend_verification.html')


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def user_profile(request, pk):
    from events.models import Event, EventMembership

    profile_user = get_object_or_404(User, pk=pk, is_active=True)
    is_self = profile_user.pk == request.user.pk

    common_events = None
    if not is_self:
        # Both sides have to have actually said "going" -- an invite either
        # of them ignored or declined isn't a real shared event.
        my_going_event_ids = EventMembership.objects.filter(
            user=request.user, rsvp_status=EventMembership.STATUS_GOING,
        ).values_list('event_id', flat=True)
        common_events = (
            Event.objects.filter(id__in=my_going_event_ids)
            .filter(membership__user=profile_user, membership__rsvp_status=EventMembership.STATUS_GOING)
            .distinct()
            .order_by('-start_datetime')
        )

    return render(request, 'accounts/user_profile.html', {
        'profile_user': profile_user,
        'is_self': is_self,
        'common_events': common_events,
    })
