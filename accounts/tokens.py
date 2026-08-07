from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Same signed-token trick Django uses for password resets, applied to
    signup verification links instead. Folding `is_active` into the hash
    means the token stops validating the moment it's used once (verifying
    flips is_active True -> the old link's hash no longer matches)."""

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.is_active}{timestamp}{user.email}'


email_verification_token = EmailVerificationTokenGenerator()
