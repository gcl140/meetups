from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Reminders and invites are sent here.')

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        # Held inactive until the verification link is clicked -- see
        # accounts.emails.send_verification_email / accounts.views.verify_email.
        user = super().save(commit=False)
        user.is_active = False
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    """Stock AuthenticationForm can't tell "wrong password" apart from
    "correct password but not verified yet" -- ModelBackend already
    refuses to authenticate an inactive user, so by the time we get here
    that distinction is gone. Re-derive it so unverified users get a
    message that actually points at what to do next."""

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                unverified = User.objects.filter(email__iexact=email, is_active=False).first()
                if unverified and unverified.check_password(password):
                    raise forms.ValidationError(
                        "Please verify your email before logging in -- check your inbox for the link, "
                        "or request a new one below.",
                        code='inactive',
                    )
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone', 'avatar')


class AdminUserCreationForm(UserCreationForm):
    """Used by the Django admin's "add user" page. The stock
    UserCreationForm only knows about `username`; ours needs `email`
    instead since that's USERNAME_FIELD and username just mirrors it."""

    class Meta:
        model = User
        fields = ('email',)
