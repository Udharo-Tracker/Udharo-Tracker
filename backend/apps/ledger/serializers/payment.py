from rest_framework import serializers
from ..models import Payment, PaymentPhoto
from apps.shops.models import Customer
from apps.shops.serializers.customer import CustomerSerializer

MAX_PHOTOS_PER_PAYMENT = 5


class PaymentPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentPhoto
        fields = ["id", "image", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class PaymentSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), source="customer", write_only=True
    )
    photos = PaymentPhotoSerializer(many=True, read_only=True)
    # Write-only: pass one or more image files under this key (multipart
    # form field repeated, e.g. `photo_uploads` appended N times) to attach
    # photos in the same request that creates/edits the payment.
    photo_uploads = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        max_length=MAX_PHOTOS_PER_PAYMENT,
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "customer",
            "customer_id",
            "amount_paid",
            "payment_mode",
            "reference",
            "note",
            "transaction_date",
            "created_at",
            "photos",
            "photo_uploads",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        photo_uploads = attrs.get("photo_uploads", [])
        existing_count = self.instance.photos.count() if self.instance else 0
        if existing_count + len(photo_uploads) > MAX_PHOTOS_PER_PAYMENT:
            raise serializers.ValidationError(
                {
                    "photo_uploads": (
                        f"A payment can have at most {MAX_PHOTOS_PER_PAYMENT} photos "
                        f"({existing_count} already attached)."
                    )
                }
            )
        return attrs

    def create(self, validated_data):
        photos_data = validated_data.pop("photo_uploads", [])
        payment = Payment.objects.create(**validated_data)
        self._attach_photos(payment, photos_data)
        return payment

    def update(self, instance, validated_data):
        photos_data = validated_data.pop("photo_uploads", [])
        payment = super().update(instance, validated_data)
        self._attach_photos(payment, photos_data)
        return payment

    @staticmethod
    def _attach_photos(payment, photos_data):
        for image in photos_data:
            PaymentPhoto.objects.create(payment=payment, image=image)
