from rest_framework import serializers

from ..models import User


class UserProfileSerializers(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "profile_picture",
            "phone_number",
            "preferred_charity",
            "is_anonymous_donor",
            "is_active",
            "is_insurance_agent",
            "created_at",
            "updated_at",
            "preferred_charity_id",
        ]
        read_only_fields = ["is_active"]
