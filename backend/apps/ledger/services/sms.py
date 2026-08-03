import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class SMSBackend:
    def send(self, phone: str, message: str) -> dict:
        raise NotImplementedError


class ConsoleSMSBackend(SMSBackend):
    """Logs the SMS instead of sending it. Default backend for dev/testing so no paid gateway is required."""

    def send(self, phone: str, message: str) -> dict:
        logger.info("SMS to=%s message=%s", phone, message)
        return {"success": True, "provider": "console"}


def send_sms(phone: str, message: str) -> dict:
    backend_class = import_string(settings.SMS_BACKEND)
    backend = backend_class()

    try:
        return backend.send(phone, message)
    except Exception as exc:
        return {"success": False, "error": str(exc)}
