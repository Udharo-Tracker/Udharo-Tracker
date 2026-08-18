from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth, TruncDate
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes

import calendar

from ...models import UdharoEntry, Payment


@extend_schema(
    tags=["Monthly Reports"],
    parameters=[
        OpenApiParameter("year", int, description="Year (required)", required=True),
        OpenApiParameter(
            "month", int, description="Month 1-12 (optional — omit for yearly summary)"
        ),
    ],
    responses=OpenApiResponse(
        response=OpenApiTypes.OBJECT,
        description="Yearly summary (12 months) when `month` is omitted, or a daily breakdown when `month` is given.",
        examples=[
            OpenApiExample(
                "Yearly summary (no month param)",
                value={
                    "year": 2026,
                    "months": [
                        {
                            "month": 7,
                            "month_name": "July",
                            "total_udharo": 8000.0,
                            "total_payments": 5000.0,
                            "net": 3000.0,
                            "entry_count": 4,
                            "payment_count": 3,
                        }
                    ],
                    "yearly_totals": {
                        "total_udharo": 42000.0,
                        "total_payments": 26800.0,
                        "net": 15200.0,
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Month detail (month param given)",
                value={
                    "year": 2026,
                    "month": 7,
                    "month_name": "July",
                    "daily_breakdown": [
                        {
                            "date": "2026-07-15",
                            "total_udharo": 1500.0,
                            "total_payments": 500.0,
                            "net": 1000.0,
                            "entry_count": 1,
                            "payment_count": 1,
                        }
                    ],
                    "totals": {
                        "total_udharo": 8000.0,
                        "total_payments": 5000.0,
                        "net": 3000.0,
                    },
                },
                response_only=True,
            ),
        ],
    ),
)
class MonthlyReportView(APIView):
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

        if month is not None:
            try:
                month = int(month)
                if not 1 <= month <= 12:
                    raise ValueError
            except ValueError:
                raise ValidationError({"month": "Must be an integer between 1 and 12."})
            return Response(self._month_detail(request.user, year, month))

        return Response(self._year_summary(request.user, year))

    @staticmethod
    def _year_summary(user, year):
        udharo_by_month = (
            UdharoEntry.objects.filter(
                customer__shop__owner=user,
                created_at__year=year,
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total_udharo=Sum("items__amount"), entry_count=Count("id"))
        )

        payments_by_month = (
            Payment.objects.filter(
                customer__shop__owner=user,
                created_at__year=year,
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total_payments=Sum("amount_paid"), payment_count=Count("id"))
        )

        udharo_map = {
            r["month"].month: {
                "total_udharo": r["total_udharo"] or 0,
                "entry_count": r["entry_count"] or 0,
            }
            for r in udharo_by_month
        }
        payment_map = {
            r["month"].month: {
                "total_payments": r["total_payments"] or 0,
                "payment_count": r["payment_count"] or 0,
            }
            for r in payments_by_month
        }

        months = []
        total_udharo = total_payments = 0

        for m in range(1, 13):
            u = udharo_map.get(m, {"total_udharo": 0, "entry_count": 0})
            p = payment_map.get(m, {"total_payments": 0, "payment_count": 0})
            total_udharo += u["total_udharo"]
            total_payments += p["total_payments"]
            months.append(
                {
                    "month": m,
                    "month_name": calendar.month_name[m],
                    "total_udharo": u["total_udharo"],
                    "total_payments": p["total_payments"],
                    "net": u["total_udharo"] - p["total_payments"],
                    "entry_count": u["entry_count"],
                    "payment_count": p["payment_count"],
                }
            )

        return {
            "year": year,
            "months": months,
            "yearly_totals": {
                "total_udharo": total_udharo,
                "total_payments": total_payments,
                "net": total_udharo - total_payments,
            },
        }

    @staticmethod
    def _month_detail(user, year, month):
        udharo_by_day = (
            UdharoEntry.objects.filter(
                customer__shop__owner=user,
                created_at__year=year,
                created_at__month=month,
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total_udharo=Sum("items__amount"), entry_count=Count("id"))
        )

        payments_by_day = (
            Payment.objects.filter(
                customer__shop__owner=user,
                created_at__year=year,
                created_at__month=month,
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total_payments=Sum("amount_paid"), payment_count=Count("id"))
        )

        udharo_map = {
            r["day"]: {
                "total_udharo": r["total_udharo"] or 0,
                "entry_count": r["entry_count"] or 0,
            }
            for r in udharo_by_day
        }
        payment_map = {
            r["day"]: {
                "total_payments": r["total_payments"] or 0,
                "payment_count": r["payment_count"] or 0,
            }
            for r in payments_by_day
        }

        all_days = sorted(set(udharo_map) | set(payment_map))
        daily_breakdown = []
        total_udharo = total_payments = 0

        for day in all_days:
            u = udharo_map.get(day, {"total_udharo": 0, "entry_count": 0})
            p = payment_map.get(day, {"total_payments": 0, "payment_count": 0})
            total_udharo += u["total_udharo"]
            total_payments += p["total_payments"]
            daily_breakdown.append(
                {
                    "date": day.isoformat(),
                    "total_udharo": u["total_udharo"],
                    "total_payments": p["total_payments"],
                    "net": u["total_udharo"] - p["total_payments"],
                    "entry_count": u["entry_count"],
                    "payment_count": p["payment_count"],
                }
            )

        return {
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "daily_breakdown": daily_breakdown,
            "totals": {
                "total_udharo": total_udharo,
                "total_payments": total_payments,
                "net": total_udharo - total_payments,
            },
        }
