from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token


def _absolute_url(path):
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def send_verification_email(user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    verify_url = _absolute_url(reverse('accounts:verify-email', args=[uidb64, token]))

    context = {'user': user, 'verify_url': verify_url}
    text_body = render_to_string('emails/verify_email.txt', context)
    html_body = render_to_string('emails/verify_email.html', context)

    msg = EmailMultiAlternatives(
        subject='Verify your Meetups email', body=text_body, to=[user.email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=True)
