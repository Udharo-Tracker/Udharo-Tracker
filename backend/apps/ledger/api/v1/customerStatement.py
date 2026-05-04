from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Value, CharField, F
from itertools import chain

from apps.shops.models import Customer
from .models import UdharoEntry, Payment


class CustomerStatementView(APIView):
    def get(self, request, customer_id):
        # ---------------------------
        # 1. Get Customer + Shop
        # ---------------------------
        customer = Customer.objects.select_related("shop").get(id=customer_id)
        shop = customer.shop

        # ---------------------------
        # 2. Totals (DB-level, efficient)
        # ---------------------------
        total_udharo = (
            UdharoEntry.objects.filter(customer=customer)
            .aggregate(total=Sum("amount"))["total"] or 0
        )

        total_paid = (
            Payment.objects.filter(customer=customer)
            .aggregate(total=Sum("amount_paid"))["total"] or 0
        )

        outstanding_balance = total_udharo - total_paid

        # ---------------------------
        # 3. Normalize Transactions
        # ---------------------------
        udharo_qs = UdharoEntry.objects.filter(customer=customer).annotate(
            type=Value("udharo", output_field=CharField()),
            amount=F("amount"),
            date=F("created_at"),
        ).values("id", "type", "amount", "date", "note")

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
                "id": str(customer.id),
                "name": customer.name,
                "phone": getattr(customer, "phone", None),
            },
            "shop": {
                "id": str(shop.id),
                "name": shop.name,
            },
            "summary": {
                "total_udharo": total_udharo,
                "total_paid": total_paid,
                "outstanding_balance": outstanding_balance,
            },
            "transactions": transactions,
        }

        return Response(response)