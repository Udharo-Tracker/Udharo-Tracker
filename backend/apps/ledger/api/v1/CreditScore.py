from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema


from apps.shops.models import Customer
from ...models import CreditScore
from ...serializers.CreditScore import CreditScoreSerializer

@extend_schema(
    tags=["Customers"],
)
class CustomerCreditScoreView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()
        
        latest = CreditScore.objects.filter(
            customer=customer
        ).order_by('-calculated_at').first()


        if not latest:
            return Response({"message": "No score calculated yet"}, status=404)
        
        serializer = CreditScoreSerializer(latest)
        return Response(serializer.data)
    

@extend_schema(tags=["Customers"])
class CustomerCreditScoreHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id= customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()
        
        scores = CreditScore.objects.filter(
            customer=customer
        ).order_by('-calculated_at')


        serializer = CreditScoreSerializer(scores, many=True)
        return Response(serializer.data)