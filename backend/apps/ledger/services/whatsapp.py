import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class WhatsAppBackend:
    def send(self, phone: str, message: str) -> dict:
        raise NotImplementedError


class ConsoleWhatsAppBackend(WhatsAppBackend):
    """Logs the message instead of sending it. Default backend for
    dev/testing so no WhatsApp Business API account is required."""

    def send(self, phone: str, message: str) -> dict:
        logger.info("WhatsApp to=%s message=%s", phone, message)
        return {"success": True, "provider": "console"}


def send_whatsapp(phone: str, message: str) -> dict:
    backend_class = import_string(settings.WHATSAPP_BACKEND)
    backend = backend_class()

    try:
        return backend.send(phone, message)
    except Exception as exc:
        return {"success": False, "error": str(exc)}
