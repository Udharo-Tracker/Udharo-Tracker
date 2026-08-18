from .mailers import send_notification_email
from .models import Notification

# Types worth interrupting the shop owner for immediately by email, rather
# than waiting for them to open the app or for the daily digest (see
# tasks.send_daily_digests) — both are money-at-risk signals.
CRITICAL_NOTIF_TYPES = {
    Notification.NotifType.CREDIT_RISK_RED,
    Notification.NotifType.CREDIT_LIMIT_EXCEEDED,
}


def create_notification(*, shop, notif_type, title, message="", customer=None):
    """Single entry point signal handlers use to record an activity. Kept as
    a plain function (rather than inlining `Notification.objects.create()`
    in every handler) so every notification is built the same way."""
    notification = Notification.objects.create(
        shop=shop,
        customer=customer,
        notif_type=notif_type,
        title=title,
        message=message,
    )

    if notif_type in CRITICAL_NOTIF_TYPES:
        send_notification_email(notification)

    return notification
