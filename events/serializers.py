from rest_framework import serializers
from .models import Event, TicketTier
from django.utils import timezone


class TicketTierSerializer(serializers.ModelSerializer):
    quantity_remaining = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = TicketTier
        fields = [
            'id', 'name', 'price', 'quantity',
            'quantity_sold', 'quantity_remaining',
            'is_available', 'sale_start', 'sale_end'
        ]
        read_only_fields = ['quantity_sold']

    def validate(self, data):
        if data['sale_start'] >= data['sale_end']:
            raise serializers.ValidationError(
                "Sale end date must be after sale start date."
            )
        return data


class EventSerializer(serializers.ModelSerializer):
    tiers = TicketTierSerializer(many=True, read_only=True)
    organiser_name = serializers.CharField(
        source='organiser.username',
        read_only=True
    )

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description', 'venue', 'date',
            'banner_image', 'status', 'resale_allowed',
            'resale_price_cap', 'organiser_name',
            'tiers', 'created_at', 'updated_at'
        ]
        read_only_fields = ['organiser_name', 'created_at', 'updated_at']

    def validate_date(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Event date must be in the future."
            )
        return value