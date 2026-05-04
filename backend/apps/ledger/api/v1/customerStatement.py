from rest_framework.views import APIView
from rest_framework.response import Response
from itertools import chain
from django.db.models import Value, CharField, F
from rest_framework.permissions import IsAuthenticated


from ...models import UdharoEntry, Payment

class CustomerStatementView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, customer_id):
        udharo_qs = UdharoEntry.objects.filter(customer_id=customer_id).annotate(
        type=Value("udharo", output_field=CharField()),
        amount=F("amount"),
        date=F("created_at"),
        ).values("id", "type", "amount", "date", "note")

        payment_qs = Payment.objects.filter(customer_id=customer_id).annotate(
        type=Value("payment", output_field=CharField()),
        amount=F("amount_paid"),
        date=F("created_at"),
        ).values("id", "type", "amount", "date", "note")

        combined = sorted(
            chain(udharo_qs, payment_qs),
            key=lambda x: x["date"]
        )

        balance = 0
        result = []

        for item in combined:
            if item["type"] == "udharo":
                balance += item["amount_value"]
            else:
                balance -= item["amount_value"]

            item["balance"] = balance
            result.append(item)

        return Response(result)