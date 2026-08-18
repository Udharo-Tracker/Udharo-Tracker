from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from apps.shared.pdf_utils import render_pdf_response

from .monthlyReport import MonthlyReportView

_TABLE_HEAD = ["Period", "Udharo", "Payments", "Net", "Entries", "Payment count"]


@extend_schema(
    tags=["Monthly Reports"],
    parameters=[
        OpenApiParameter("year", int, description="Year (required)", required=True),
        OpenApiParameter(
            "month", int, description="Month 1-12 (optional — omit for yearly summary)"
        ),
    ],
    responses=OpenApiResponse(response=OpenApiTypes.BINARY),
    description=(
        "Downloads a PDF of the same data as GET /ledger/monthly-report/ — "
        "a yearly summary when `month` is omitted, or a daily breakdown "
        "for that month otherwise."
    ),
)
class MonthlyReportPDFView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        year = request.query_params.get("year")
        month = request.query_params.get("month")

        if not year:
            raise ValidationError({"year": "This parameter is required."})
        try:
            year = int(year)
        except ValueError:
            raise ValidationError({"year": "Must be a valid integer."})

        shop = request.user.shop

        if month is not None:
            try:
                month = int(month)
                if not 1 <= month <= 12:
                    raise ValueError
            except ValueError:
                raise ValidationError({"month": "Must be an integer between 1 and 12."})
            data = MonthlyReportView._month_detail(request.user, year, month)
            return self._render_month(shop, data)

        data = MonthlyReportView._year_summary(request.user, year)
        return self._render_year(shop, data)

    def _render_year(self, shop, data):
        table_rows = [
            [
                m["month_name"],
                f"Rs.{m['total_udharo']}",
                f"Rs.{m['total_payments']}",
                f"Rs.{m['net']}",
                m["entry_count"],
                m["payment_count"],
            ]
            for m in data["months"]
        ]
        totals = data["yearly_totals"]
        return render_pdf_response(
            filename=f"monthly-report-{data['year']}.pdf",
            title=f"Yearly Report — {data['year']}",
            meta_lines=[shop.name],
            table_head=_TABLE_HEAD,
            table_rows=table_rows,
            summary_lines=[
                ("Total Udharo", f"Rs.{totals['total_udharo']}"),
                ("Total Payments", f"Rs.{totals['total_payments']}"),
                ("Net", f"Rs.{totals['net']}"),
            ],
        )

    def _render_month(self, shop, data):
        table_rows = [
            [
                d["date"],
                f"Rs.{d['total_udharo']}",
                f"Rs.{d['total_payments']}",
                f"Rs.{d['net']}",
                d["entry_count"],
                d["payment_count"],
            ]
            for d in data["daily_breakdown"]
        ]
        totals = data["totals"]
        return render_pdf_response(
            filename=f"monthly-report-{data['year']}-{data['month']:02d}.pdf",
            title=f"Monthly Report — {data['month_name']} {data['year']}",
            meta_lines=[shop.name],
            table_head=_TABLE_HEAD,
            table_rows=table_rows,
            summary_lines=[
                ("Total Udharo", f"Rs.{totals['total_udharo']}"),
                ("Total Payments", f"Rs.{totals['total_payments']}"),
                ("Net", f"Rs.{totals['net']}"),
            ],
        )
