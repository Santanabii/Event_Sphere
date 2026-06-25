import logging
import uuid

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Listing, ResaleOrder, ResaleMpesaTransaction
from .serializers import (
    ListingSerializer,
    CreateListingSerializer,
    ResaleOrderSerializer,
    InitiateResalePurchaseSerializer
)
from tickets.models import Ticket
from django.conf import settings
from tickets.mpesa import stk_push

logger = logging.getLogger(__name__)


class CreateListingView(generics.CreateAPIView):
    """Ticket holder lists their ticket for resale."""
    serializer_class = CreateListingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        ticket = Ticket.objects.get(
            id=serializer.validated_data['ticket_id'],
            owner=self.request.user
        )
        expires_at = ticket.tier.event.date

        with transaction.atomic():
            ticket.status = 'listed'
            ticket.save()

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
            listing.ticket.status = 'active'
            listing.ticket.save()

            listing.status = 'cancelled'
            listing.save()

        return Response(
            {"message": "Listing cancelled successfully."},
            status=status.HTTP_200_OK
        )


class InitiateResalePurchaseView(APIView):
    """
    Buyer initiates payment for a resale ticket.
    Sends STK Push to their phone.
    """
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

        serializer = InitiateResalePurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = serializer.validated_data['phone_number']

        # Send STK Push
        try:
            mpesa_response = stk_push(
                phone_number=phone_number,
                amount=int(listing.asking_price),
                account_reference=f"EVSR{listing.id}",
                description=f"Resale ticket for {listing.ticket.tier.event.title}",
                callback_url=settings.MPESA_RESALE_CALLBACK_URL
            )
        except Exception as exc:
            logger.exception("Resale STK Push failed: %s", exc)
            return Response(
                {"error": "Could not reach M-Pesa. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY
            )

        if mpesa_response.get('ResponseCode') != '0':
            return Response(
                {"error": mpesa_response.get('ResponseDescription', 'Payment initiation failed.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create pending resale transaction
        ResaleMpesaTransaction.objects.create(
            listing=listing,
            buyer=request.user,
            phone_number=phone_number,
            amount=listing.asking_price,
            merchant_request_id=mpesa_response.get('MerchantRequestID', ''),
            checkout_request_id=mpesa_response.get('CheckoutRequestID', ''),
            status='pending'
        )

        return Response({
            "message": "Payment initiated. Enter your M-Pesa PIN on your phone.",
            "checkout_request_id": mpesa_response.get('CheckoutRequestID')
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class ResaleMpesaCallbackView(APIView):
    """
    M-Pesa calls this after resale payment completes.
    Transfers ticket ownership if payment succeeded.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        stk_callback        = request.data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = stk_callback.get('CheckoutRequestID', '')
        result_desc         = stk_callback.get('ResultDesc', '')

        # Normalise ResultCode — Daraja sends an integer but guard against
        # strings or a missing key so we never silently drop a successful payment.
        raw_code = stk_callback.get('ResultCode')
        if raw_code is None:
            logger.error("Resale callback missing ResultCode | CheckoutRequestID=%s", checkout_request_id)
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        try:
            result_code = int(raw_code)
        except (TypeError, ValueError):
            logger.error("Unparseable ResultCode '%s' | CheckoutRequestID=%s",
                         raw_code, checkout_request_id)
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        logger.info(
            "Resale Callback | CheckoutRequestID=%s | ResultCode=%s",
            checkout_request_id, result_code
        )

        try:
            resale_transaction = ResaleMpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id
            )
        except ResaleMpesaTransaction.DoesNotExist:
            logger.error("Unknown resale CheckoutRequestID: %s", checkout_request_id)
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        if result_code == 0:
            items = {
                item['Name']: item.get('Value')
                for item in stk_callback.get('CallbackMetadata', {}).get('Item', [])
            }
            receipt = str(items.get('MpesaReceiptNumber', ''))

            listing = resale_transaction.listing
            amount_paid = listing.asking_price
            platform_fee = amount_paid * 10 / 100
            seller_payout = amount_paid - platform_fee

            with transaction.atomic():
                # Update transaction
                resale_transaction.status = 'completed'
                resale_transaction.mpesa_receipt = receipt
                resale_transaction.save()

                # Generate new QR token
                new_token = uuid.uuid4()

                # Transfer ticket ownership
                ticket = listing.ticket
                ticket.owner = resale_transaction.buyer
                ticket.qr_token = new_token
                ticket.status = 'active'
                ticket.save()

                # Mark listing as sold
                listing.status = 'sold'
                listing.save()

                # Create resale order
                ResaleOrder.objects.create(
                    listing=listing,
                    buyer=resale_transaction.buyer,
                    amount_paid=amount_paid,
                    platform_fee=platform_fee,
                    seller_payout=seller_payout,
                    new_qr_token=new_token
                )

        elif result_code == 1032:
            resale_transaction.status = 'cancelled'
            resale_transaction.save()
            logger.info("Resale payment cancelled by user")

        else:
            resale_transaction.status = 'failed'
            resale_transaction.save()
            logger.warning(
                "Resale payment failed | ResultCode=%s | %s",
                result_code, result_desc
            )

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class ResalePaymentStatusView(APIView):
    """Frontend polls this to check if resale M-Pesa callback has arrived."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, checkout_request_id):
        try:
            tx = ResaleMpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id,
                buyer=request.user
            )

            response_data = {
                "status":  tx.status,
                "receipt": tx.mpesa_receipt,
            }

            # If completed, include the new ticket details
            if tx.status == 'completed':
                try:
                    resale_order = tx.listing.resale_order
                    ticket = tx.listing.ticket
                    response_data.update({
                        "new_qr_token":  str(resale_order.new_qr_token),
                        "amount_paid":   str(resale_order.amount_paid),
                        "platform_fee":  str(resale_order.platform_fee),
                        "seller_payout": str(resale_order.seller_payout),
                        "event_title":   ticket.tier.event.title,
                        "event_venue":   ticket.tier.event.venue,
                        "event_date":    ticket.tier.event.date,
                        "tier_name":     ticket.tier.name,
                        "ticket_id":     ticket.id,
                    })
                except Exception as e:
                    logger.error("Failed to attach resale order details: %s", e)

            return Response(response_data)

        except ResaleMpesaTransaction.DoesNotExist:
            return Response(
                {"error": "Transaction not found."},
                status=status.HTTP_404_NOT_FOUND
            )