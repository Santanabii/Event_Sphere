import logging

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from events.models import TicketTier
from .models import Ticket, MpesaTransaction
from .serializers import TicketSerializer, InitiatePurchaseSerializer
from .mpesa import stk_push, normalise_phone
from .utils import send_ticket_email

logger = logging.getLogger(__name__)


class InitiatePurchaseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InitiatePurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tier_id      = serializer.validated_data['tier_id']
        phone_number = serializer.validated_data['phone_number']

        # Use the validated tier stored on the serializer — no second DB hit
        tier = serializer._tier

        # Normalise & strictly validate the phone number before hitting Daraja
        try:
            phone_number = normalise_phone(phone_number)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            mpesa_response = stk_push(
                phone_number      = phone_number,
                amount            = int(tier.price),
                account_reference = f"EVS{tier.event.id}",
                description       = "EVS Ticket"
            )
        except Exception as exc:
            logger.exception("STK Push failed: %s", exc)
            return Response(
                {"error": "Could not reach M-Pesa. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY
            )

        if mpesa_response.get('ResponseCode') != '0':
            return Response(
                {"error": mpesa_response.get('ResponseDescription', 'Payment initiation failed.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        MpesaTransaction.objects.create(
            phone_number        = phone_number,
            amount              = tier.price,
            merchant_request_id = mpesa_response.get('MerchantRequestID', ''),
            checkout_request_id = mpesa_response['CheckoutRequestID'],
            tier                = tier,
            owner               = request.user,
            status              = MpesaTransaction.Status.PENDING
        )

        return Response({
            "message":             "Payment prompt sent. Enter your M-Pesa PIN.",
            "checkout_request_id": mpesa_response['CheckoutRequestID']
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        stk_callback        = request.data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = stk_callback.get('CheckoutRequestID', '')
        result_desc         = stk_callback.get('ResultDesc', '')

        # Normalise ResultCode — Daraja sends an integer but guard against
        # strings or a missing key so we never silently drop a successful payment.
        raw_code = stk_callback.get('ResultCode')
        if raw_code is None:
            logger.error("Callback missing ResultCode | CheckoutRequestID=%s", checkout_request_id)
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        try:
            result_code = int(raw_code)
        except (TypeError, ValueError):
            logger.error("Unparseable ResultCode '%s' | CheckoutRequestID=%s",
                         raw_code, checkout_request_id)
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        logger.info("Callback | CheckoutRequestID=%s | ResultCode=%s",
                    checkout_request_id, result_code)

        try:
            mpesa_tx = MpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id
            )
        except MpesaTransaction.DoesNotExist:
            logger.error("Unknown CheckoutRequestID: %s", checkout_request_id)
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        if result_code == 0:
            items = {
                item['Name']: item.get('Value')
                for item in stk_callback.get('CallbackMetadata', {}).get('Item', [])
            }
            receipt = str(items.get('MpesaReceiptNumber', ''))

            with transaction.atomic():
                # Lock the tier row to prevent overselling when two callbacks
                # arrive simultaneously for the last available ticket.
                tier = TicketTier.objects.select_for_update().get(pk=mpesa_tx.tier_id)

                if not tier.is_available:
                    mpesa_tx.status      = MpesaTransaction.Status.FAILED
                    mpesa_tx.result_desc = "Ticket tier sold out."
                    mpesa_tx.save()
                    logger.warning("Tier %s sold out at callback time | Tx=%s", tier.pk, mpesa_tx.pk)
                    return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

                ticket = Ticket.objects.create(
                    owner          = mpesa_tx.owner,
                    tier           = tier,
                    purchase_price = tier.price,
                    status         = Ticket.Status.ACTIVE
                )

                # Single consolidated save for the transaction
                mpesa_tx.status        = MpesaTransaction.Status.COMPLETED
                mpesa_tx.mpesa_receipt = receipt
                mpesa_tx.result_desc   = result_desc
                mpesa_tx.ticket        = ticket
                mpesa_tx.save()

                tier.quantity_sold += 1
                tier.save()

            try:
                send_ticket_email(ticket)
            except Exception as e:
                logger.error("Email failed for ticket %s: %s", ticket.id, e)

        elif result_code == 1032:
            mpesa_tx.status      = MpesaTransaction.Status.CANCELLED
            mpesa_tx.result_desc = result_desc
            mpesa_tx.save()
            logger.info("Payment cancelled by user | Tx=%s", mpesa_tx.pk)

        else:
            mpesa_tx.status      = MpesaTransaction.Status.FAILED
            mpesa_tx.result_desc = result_desc
            mpesa_tx.save()
            logger.warning("Payment failed | ResultCode=%s | %s", result_code, result_desc)

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class PaymentStatusView(APIView):
    """Frontend polls this to check if M-Pesa callback has arrived."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, checkout_request_id):
        try:
            tx = MpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id,
                owner=request.user
            )
            return Response({
                "status":  tx.status,
                "receipt": tx.mpesa_receipt,
                "desc":    tx.result_desc,
            })
        except MpesaTransaction.DoesNotExist:
            return Response(
                {"error": "Transaction not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class MyTicketsView(generics.ListAPIView):
    serializer_class   = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Ticket.objects.filter(owner=self.request.user)


class TicketDetailView(generics.RetrieveAPIView):
    serializer_class   = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Ticket.objects.filter(owner=self.request.user)


class ScanTicketView(APIView):
    """Staff-only endpoint: scans a QR token and marks the ticket as used."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Restrict to staff / admin users only
        if not request.user.is_staff:
            return Response(
                {"error": "You do not have permission to scan tickets."},
                status=status.HTTP_403_FORBIDDEN
            )

        qr_token = request.data.get('qr_token')
        if not qr_token:
            return Response(
                {"error": "QR token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ticket = Ticket.objects.get(qr_token=qr_token)
        except Ticket.DoesNotExist:
            return Response(
                {"result": "invalid", "message": "Ticket not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if ticket.status == Ticket.Status.USED:
            return Response({
                "result":  "used",
                "message": "This ticket has already been used.",
                "owner":   ticket.owner.email
            })

        if ticket.status != Ticket.Status.ACTIVE:
            return Response({
                "result":  "invalid",
                "message": f"Ticket status is '{ticket.status}' and cannot be admitted."
            }, status=status.HTTP_400_BAD_REQUEST)

        ticket.status = Ticket.Status.USED
        ticket.save()

        # Push live update to organiser dashboard — imported lazily so a missing
        # analytics app does not break the entire tickets module on startup.
        try:
            from analytics.views import push_analytics_update
            push_analytics_update(ticket.tier.event.id)
        except Exception as e:
            logger.error("Analytics update failed: %s", e)

        return Response({
            "result":  "valid",
            "message": "Ticket is valid. Entry granted!",
            "owner":   ticket.owner.email,
            "tier":    ticket.tier.name,
            "event":   ticket.tier.event.title
        })