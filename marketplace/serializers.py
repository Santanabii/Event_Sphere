from rest_framework import serializers
from .models import Listing, ResaleOrder
from tickets.models import Ticket
from django.utils import timezone


class ListingSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(
        source='ticket.tier.event.title',
        read_only=True
    )
    event_date = serializers.DateTimeField(
        source='ticket.tier.event.date',
        read_only=True
    )
    event_venue = serializers.CharField(
        source='ticket.tier.event.venue',
        read_only=True
    )
    tier_name = serializers.CharField(
        source='ticket.tier.name',
        read_only=True
    )
    original_price = serializers.DecimalField(
        source='ticket.purchase_price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    seller_username = serializers.CharField(
        source='seller.username',
        read_only=True
    )

    class Meta:
        model = Listing
        fields = [
            'id', 'asking_price', 'status',
            'listed_at', 'expires_at',
            'event_title', 'event_date',
            'event_venue', 'tier_name',
            'original_price', 'seller_username'
        ]
        read_only_fields = [
            'status', 'listed_at',
            'seller_username'
        ]


class CreateListingSerializer(serializers.ModelSerializer):
    ticket_id = serializers.IntegerField()

    class Meta:
        model = Listing
        fields = ['ticket_id', 'asking_price']

    def validate_ticket_id(self, value):
        request = self.context['request']
        try:
            ticket = Ticket.objects.get(
                id=value,
                owner=request.user,
                status='active'
            )
        except Ticket.DoesNotExist:
            raise serializers.ValidationError(
                "Ticket not found or not eligible for resale."
            )
        return value

    def validate(self, data):
        request = self.context['request']
        ticket = Ticket.objects.get(
            id=data['ticket_id'],
            owner=request.user
        )
        event = ticket.tier.event

        # Check if resale is allowed
        if not event.resale_allowed:
            raise serializers.ValidationError(
                "Resale is not allowed for this event."
            )

        # Check price cap
        max_price = ticket.purchase_price * (event.resale_price_cap / 100)
        if data['asking_price'] > max_price:
            raise serializers.ValidationError(
                f"Asking price cannot exceed KES {max_price} "
                f"({event.resale_price_cap}% of face value)."
            )

        return data


class ResaleOrderSerializer(serializers.ModelSerializer):
    buyer_email = serializers.CharField(
        source='buyer.email',
        read_only=True
    )
    event_title = serializers.CharField(
        source='listing.ticket.tier.event.title',
        read_only=True
    )

    class Meta:
        model = ResaleOrder
        fields = [
            'id', 'amount_paid', 'platform_fee',
            'seller_payout', 'new_qr_token',
            'completed_at', 'buyer_email',
            'event_title'
        ]
        read_only_fields = fields