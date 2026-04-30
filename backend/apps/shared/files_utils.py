import os
import re
import uuid

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class FileSizeValidator:
    def __init__(self, max_size):
        self.max_size = max_size

    def __call__(self, value):
        if value.size > self.max_size:
            raise ValidationError(
                f"File size must be less than {self.size_to_human_readable(self.max_size)}"
            )

    @staticmethod
    def size_to_human_readable(size_in_bytes):
        for x in ["bytes", "KB", "MB", "GB", "TB"]:
            if size_in_bytes < 1024.0:
                return "%3.1f %s" % (size_in_bytes, x)
            size_in_bytes /= 1024.0


def file_upload_path(instance, filename):
    if hasattr(instance, "tenant") and instance.tenant:
        _, file_extension = os.path.splitext(filename)
        return f"t_{instance.tenant.id}/{instance._meta.model_name}/{uuid.uuid4()}{file_extension}"
    else:
        _, file_extension = os.path.splitext(filename)
        return f"shared/{instance._meta.model_name}/{uuid.uuid4()}{file_extension}"


def validate_phone(value):
    # remove spaces and dashes
    value = re.sub(r"[\s\-]", "", value)

    # Nepal pattern
    pattern = r"^(?:\+977|977)?9[6-8]\d{8}$"

    if not re.fullmatch(pattern, value):
        raise ValidationError("Enter a valid Nepali phone number")