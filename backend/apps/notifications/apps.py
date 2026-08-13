from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"

    def ready(self):
        from . import signals  # noqa: F401 — connects the post_save receivers
