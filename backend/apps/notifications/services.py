from .models import Notification


def create_notification(*, shop, notif_type, title, message="", customer=None):
    """Single entry point signal handlers use to record an activity. Kept as
    a plain function (rather than inlining `Notification.objects.create()`
    in every handler) so every notification is built the same way."""
    return Notification.objects.create(
        shop=shop,
        customer=customer,
        notif_type=notif_type,
        title=title,
        message=message,
    )
