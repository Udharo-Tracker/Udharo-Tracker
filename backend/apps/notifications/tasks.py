from celery import shared_task

from apps.shops.models import Shop

from .mailers import send_daily_digest
from .models import Notification


@shared_task
def send_daily_digests():
    """Runs once daily (see CELERY_BEAT_SCHEDULE) — one email per shop that
    has unread notifications, summarizing all of them. Immediate email for
    the high-severity types happens separately at creation time (see
    services.create_notification); this catches everything else so a shop
    owner who never opens the app still hears about it eventually."""
    shop_ids = (
        Notification.objects.filter(is_read=False)
        .values_list("shop_id", flat=True)
        .distinct()
    )

    sent = 0
    for shop in Shop.objects.filter(id__in=shop_ids).select_related("owner"):
        notifications = list(
            Notification.objects.filter(shop=shop, is_read=False).order_by(
                "-created_at"
            )
        )
        if not notifications:
            continue
        send_daily_digest(shop, notifications)
        sent += 1

    return {"shops_emailed": sent}
