from rest_framework import serializers
from ..models import CreditScore

class CreditScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model= CreditScore
        fields = ['id',
        'customer',
        'calculated_at',
        'score',
        'risk_level']
        read_only_fields = ['score', 'calculated_at', 'risk_level']
    
    