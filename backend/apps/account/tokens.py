from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Same one-time-use pattern as Django's password-reset token, but salted
    differently so a verification link can't double as a password-reset
    token (or vice versa) and stays valid only until it's used.

    Hashing on user.is_active means the token stops validating the moment
    verify_email() flips is_active to True — the same link can't be replayed.
    """

    key_salt = "apps.account.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email}{user.is_active}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()
