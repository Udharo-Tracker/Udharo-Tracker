from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Value, CharField, F
from itertools import chain
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes


from apps.shops.models import Customer
from ...models import UdharoEntry, Payment
from ...serializers.udharoEntry import UdharoEntrySerializer


@extend_schema(
    tags=["Customer Statement"],
    responses=OpenApiResponse(
        response=OpenApiTypes.OBJECT,
        description="Customer profile, running totals, full udharo entries, and a merged/sorted transaction ledger with running balance.",
        examples=[
            OpenApiExample(
                "Example response",
                value={
                    "customer": {
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "name": "Ram Sharma",
                        "phone": "+9779812345678",
                    },
                    "summary": {
                        "total_udharo": 5000.0,
                        "total_paid": 2000.0,
                        "outstanding_balance": 3000.0,
                    },
                    "udharo_entries": [],
                    "transactions": [
                        {
                            "id": "6f9619ff-8b86-d011-b42d-00c04fc964ff",
                            "type": "udharo",
                            "amount": 2000.0,
                            "note": "Rice and oil",
                            "date": "2026-07-01T09:15:00+05:45",
                            "balance": 2000.0,
                        },
                        {
                            "id": "9b2e1a4c-1234-4a3b-8c9d-abcdef123456",
                            "type": "payment",
                            "amount": 500.0,
                            "note": "Partial payment",
                            "date": "2026-07-10T18:00:00+05:45",
                            "balance": 1500.0,
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    ),
)
class CustomerStatementView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        # ---------------------------
        # 1. Get Customer + Shop
        # ---------------------------
        customer = get_object_or_404(
        Customer.objects.select_related("shop__owner"), 
        id=customer_id
        )

        if customer.shop.owner != request.user:
            raise PermissionDenied("You do not have access to this customer.")

        udharo_entries = UdharoEntry.objects.prefetch_related(
        'items'
        ).filter(customer=customer)

        # ---------------------------
        # 2. Totals (DB-level, efficient)
        # ---------------------------
        total_udharo = (
            UdharoEntry.objects.filter(customer=customer)
            .aggregate(total=Sum("items__amount"))["total"] or 0
        )

        total_paid = (
            Payment.objects.filter(customer=customer)
            .aggregate(total=Sum("amount_paid"))["total"] or 0
        )

        outstanding_balance = total_udharo - total_paid

        # ---------------------------
        # 3. Normalize Transactions
        # ---------------------------
        # UdharoEntry — remove the redundant amount annotation
        udharo_qs = UdharoEntry.objects.filter(customer=customer).annotate(
            type=Value("udharo", output_field=CharField()),
            date=F("created_at"),
            amount=Sum("items__amount"),
        ).values("id", "type", "amount", "date", "note")

        # Payment — keep the rename, it's correct
        payment_qs = Payment.objects.filter(customer=customer).annotate(
            type=Value("payment", output_field=CharField()),
            amount=F("amount_paid"),
            date=F("created_at"),
        ).values("id", "type", "amount", "date", "note")

        # ---------------------------
        # 4. Merge + Sort
        # ---------------------------
        combined = sorted(
            chain(udharo_qs, payment_qs),
            key=lambda x: (x["date"], x["id"])  # stable ordering
        )

        # ---------------------------
        # 5. Running Balance
        # ---------------------------
        balance = 0
        transactions = []

        for item in combined:
            if item["type"] == "udharo":
                balance += item["amount"]
            else:
                balance -= item["amount"]

            transactions.append({
                "id": item["id"],
                "type": item["type"],
                "amount": item["amount"],
                "note": item["note"],
                "date": item["date"],
                "balance": balance,
            })

        # ---------------------------
        # 6. Final Response
        # ---------------------------
        response = {
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "phone": getattr(customer, "phone", None),
            },
            "summary": {
                "total_udharo": total_udharo,
                "total_paid": total_paid,
                "outstanding_balance": outstanding_balance,
            },
            "udharo_entries": UdharoEntrySerializer(udharo_entries, many=True).data,
            "transactions": transactions,
        }

        return Response(response)