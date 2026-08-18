from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.shops.models import Customer
from apps.shared.pdf_utils import render_pdf_response

from ...models import Transaction
from ...tasks.services import build_balance_after_map, get_balance_breakdown


@extend_schema(
    tags=["Customers"],
    parameters=[
        OpenApiParameter(
            "customer_id", OpenApiTypes.UUID, location=OpenApiParameter.PATH
        )
    ],
    responses={200: OpenApiTypes.BINARY},
    description="Downloads a PDF statement of this customer's full transaction history.",
)
class CustomerStatementPDFView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        if customer.shop.owner != request.user:
            raise PermissionDenied()

        shop = customer.shop
        # Same voided-row exclusion as build_balance_after_map below, and in
        # the same order, so each row's printed balance lines up with the
        # row itself.
        transactions = (
            Transaction.objects.filter(customer=customer)
            .exclude(udharo_entry__is_voided=True)
            .exclude(payment__is_voided=True)
            .order_by("transaction_date", "created_at")
        )
        balance_after_map = build_balance_after_map(customer.id)

        table_rows = []
        for txn in transactions:
            is_payment = txn.txn_type == Transaction.TxnType.PAYMENT
            table_rows.append(
                [
                    txn.transaction_date.strftime("%Y-%m-%d"),
                    txn.txn_number,
                    txn.get_txn_type_display(),
                    "" if is_payment else f"Rs.{txn.amount}",
                    f"Rs.{txn.amount}" if is_payment else "",
                    f"Rs.{balance_after_map.get(txn.id, 0)}",
                ]
            )

        breakdown = get_balance_breakdown(customer)

        meta_lines = [shop.name]
        if shop.address:
            meta_lines.append(shop.address)
        if shop.phone:
            meta_lines.append(f"Phone: {shop.phone}")
        meta_lines.append(
            f"Statement for: {customer.name}"
            + (f" ({customer.phone})" if customer.phone else "")
        )

        safe_name = "".join(c if c.isalnum() else "-" for c in customer.name).strip("-")
        return render_pdf_response(
            filename=f"statement-{safe_name or customer.id}.pdf",
            title="Customer Statement",
            meta_lines=meta_lines,
            table_head=["Date", "Txn #", "Type", "Debit", "Credit", "Balance"],
            table_rows=table_rows,
            summary_lines=[
                ("Total Udharo", f"Rs.{breakdown['total_udharo']}"),
                ("Total Paid", f"Rs.{breakdown['total_paid']}"),
                ("Outstanding Balance", f"Rs.{breakdown['outstanding_balance']}"),
            ],
        )
