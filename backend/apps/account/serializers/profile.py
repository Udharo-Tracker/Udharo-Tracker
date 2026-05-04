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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "email", "created_at", "updated_at"]
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["full_name"] = f"{instance.first_name} {instance.last_name}"
        return data
