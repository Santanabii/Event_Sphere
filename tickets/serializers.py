from rest_framework import serializers
from .models import Ticket, MpesaTransaction
from events.models import TicketTier


class TicketSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(
        source='tier.event.title',
        read_only=True
    )
    event_venue = serializers.CharField(
        source='tier.event.venue',
        read_only=True
    )
    event_date = serializers.DateTimeField(
        source='tier.event.date',
        read_only=True
    )
    tier_name = serializers.CharField(
        source='tier.name',
        read_only=True
    )
    owner_email = serializers.CharField(
        source='owner.email',
        read_only=True
    )

    class Meta:
        model = Ticket
        fields = [
            'id', 'qr_token', 'status',
            'purchase_price', 'issued_at',
            'event_title', 'event_venue',
            'event_date', 'tier_name',
            'owner_email'
        ]
        read_only_fields = [
            'qr_token', 'status',
            'purchase_price', 'issued_at'
        ]


class InitiatePurchaseSerializer(serializers.Serializer):
    tier_id = serializers.IntegerField()
    phone_number = serializers.CharField(max_length=15)

    def validate_tier_id(self, value):
        try:
            tier = TicketTier.objects.get(id=value)
        except TicketTier.DoesNotExist:
            raise serializers.ValidationError(
                "Ticket tier does not exist."
            )
        if not tier.is_available:
            raise serializers.ValidationError(
                "This ticket tier is not available."
            )
        return value

    def validate_phone_number(self, value):
        # Format phone number to 254XXXXXXXXX
        if value.startswith('0'):
            value = '254' + value[1:]
        elif value.startswith('+'):
            value = value[1:]
        if not value.startswith('254'):
            raise serializers.ValidationError(
                "Phone number must be a valid Kenyan number."
            )
        return value


class MpesaTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MpesaTransaction
        fields = [
            'id', 'phone_number', 'amount',
            'status', 'mpesa_receipt', 'created_at'
        ]
        read_only_fields = fields