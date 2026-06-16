from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from .models import Listing, ResaleOrder
from .serializers import (
    ListingSerializer,
    CreateListingSerializer,
    ResaleOrderSerializer
)
from tickets.models import Ticket
import uuid


class CreateListingView(generics.CreateAPIView):
    """Ticket holder lists their ticket for resale."""
    serializer_class = CreateListingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        ticket = Ticket.objects.get(
            id=serializer.validated_data['ticket_id'],
            owner=self.request.user
        )
        # Set expiry to event date
        expires_at = ticket.tier.event.date

        with transaction.atomic():
            # Mark ticket as listed
            ticket.status = 'listed'
            ticket.save()

            # Create listing
            serializer.save(
                seller=self.request.user,
                ticket=ticket,
                expires_at=expires_at
            )


class ListingListView(generics.ListAPIView):
    """Browse all open resale listings."""
    serializer_class = ListingSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Listing.objects.filter(
            status='open',
            expires_at__gt=timezone.now()
        )


class MyListingsView(generics.ListAPIView):
    """Seller views their own listings."""
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Listing.objects.filter(seller=self.request.user)


class CancelListingView(APIView):
    """Seller cancels their listing."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            listing = Listing.objects.get(
                id=pk,
                seller=request.user,
                status='open'
            )
        except Listing.DoesNotExist:
            return Response(
                {"error": "Listing not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            # Return ticket to active
            listing.ticket.status = 'active'
            listing.ticket.save()

            # Cancel listing
            listing.status = 'cancelled'
            listing.save()

        return Response(
            {"message": "Listing cancelled successfully."},
            status=status.HTTP_200_OK
        )


class PurchaseResaleTicketView(APIView):
    """Buyer purchases a resale ticket."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            listing = Listing.objects.get(
                id=pk,
                status='open'
            )
        except Listing.DoesNotExist:
            return Response(
                {"error": "Listing not found or no longer available."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Can't buy your own listing
        if listing.seller == request.user:
            return Response(
                {"error": "You cannot buy your own listing."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check listing hasn't expired
        if listing.expires_at < timezone.now():
            return Response(
                {"error": "This listing has expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate fees
        amount_paid = listing.asking_price
        platform_fee = amount_paid * 10 / 100  # 10% platform fee
        seller_payout = amount_paid - platform_fee

        with transaction.atomic():
            # Generate new QR token for buyer
            new_token = uuid.uuid4()

            # Transfer ticket ownership
            ticket = listing.ticket
            ticket.owner = request.user
            ticket.qr_token = new_token
            ticket.status = 'active'
            ticket.save()

            # Mark listing as sold
            listing.status = 'sold'
            listing.save()

            # Create resale order
            resale_order = ResaleOrder.objects.create(
                listing=listing,
                buyer=request.user,
                amount_paid=amount_paid,
                platform_fee=platform_fee,
                seller_payout=seller_payout,
                new_qr_token=new_token
            )

        return Response(
            ResaleOrderSerializer(resale_order).data,
            status=status.HTTP_201_CREATED
        )