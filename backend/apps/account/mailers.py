"""Outbound account emails. Both functions build a link into FRONTEND_URL
(this is an API-only backend — there's no page here for the user to land
on) and send via Django's configured EMAIL_BACKEND, which defaults to the
console backend (logs instead of sending) so no mail provider is needed for
local dev/testing — same approach as apps.ledger.services.sms."""

import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token

logger = logging.getLogger(__name__)


def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"

    send_mail(
        subject="Verify your Udharo Tracker account",
        message=(
            f"Hi {user.first_name or user.email},\n\n"
            f"Confirm your email to activate your account:\n{link}\n\n"
            f"If you didn't create this account, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    logger.info("Sent verification email to %s", user.email)


def send_password_reset_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

    send_mail(
        subject="Reset your Udharo Tracker password",
        message=(
            f"Hi {user.first_name or user.email},\n\n"
            f"Reset your password here:\n{link}\n\n"
            f"If you didn't request this, ignore this email — your password "
            f"won't change."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    logger.info("Sent password reset email to %s", user.email)
