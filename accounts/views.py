from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from .forms import ProfileForm, SignUpForm


class MeetupsLoginView(LoginView):
    template_name = 'accounts/login.html'
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
            login(request, user)

            from events.models import Invitation
            accepted = Invitation.accept_all_for_email(user)
            if accepted:
                messages.success(
                    request,
                    f"Welcome! You've been added to {accepted} event(s) you were invited to."
                )
            else:
                messages.success(request, 'Welcome to Meetups!')
            return redirect('events:dashboard')
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


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
