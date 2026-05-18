from rest_framework import serializers
from ..models import CreditScore

class CreditScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model= CreditScore
        fields = ['id',
        'customer',
        'calculated_at',
        'score',
        'validators',
        'risk_level']
        read_ony_fields = ['score', 'calculated_at', 'risk_level']
    
    