from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from ..models import User

class UserRegisterSerializers(serializers.ModelSerializer):
    password = serializers.CharField(
        validators=[validate_password],
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "profile_picture",
            "phone_number",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError("Passwords didn't match")
        return attrs


    def create(self, validated_data):
        validated_data.pop("confirm_password")
        return User.objects.create_user(**validated_data)
