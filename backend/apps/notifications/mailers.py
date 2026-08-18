"""Email delivery for notifications — the in-app Notification row is always
created first (see services.create_notification); these just additionally
mail the shop owner so they don't have to have the app open to notice.
Uses the same EMAIL_BACKEND as apps.account.mailers (console by default)."""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_notification_email(notification):
    """Immediate, single-notification email — reserved for high-severity
    types (see services.CRITICAL_NOTIF_TYPES). Failure is logged, not
    raised: a broken mail provider must never break notification creation
    or the request that triggered it."""
    try:
        send_mail(
            subject=f"[Udharo Tracker] {notification.title}",
            message=notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.shop.owner.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send notification email for notification=%s", notification.id
        )


def send_daily_digest(shop, notifications):
    """One email per shop summarizing every notification still unread as of
    the daily digest run. Called by tasks.send_daily_digests."""
    lines = [
        f"- {n.title}: {n.message}" if n.message else f"- {n.title}"
        for n in notifications
    ]
    body = (
        f"You have {len(notifications)} unread notification(s) at {shop.name}:\n\n"
        + "\n".join(lines)
    )

    try:
        send_mail(
            subject=f"[Udharo Tracker] Daily summary — {len(notifications)} unread notification(s)",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[shop.owner.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send daily digest email for shop=%s", shop.id)
