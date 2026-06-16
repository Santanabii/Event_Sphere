from django.db import models
from django.conf import settings
from events.models import TicketTier
import uuid


class Ticket(models.Model):

    class Status(models.TextChoices):
        ACTIVE      = 'active',      'Active'
        LISTED      = 'listed',      'Listed for Resale'
        TRANSFERRED = 'transferred', 'Transferred'
        USED        = 'used',        'Used'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    tier = models.ForeignKey(
        TicketTier,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    qr_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.qr_token} - {self.owner.email}"

    class Meta:
        ordering = ['-issued_at']


class MpesaTransaction(models.Model):

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED    = 'failed',    'Failed'
        CANCELLED = 'cancelled', 'Cancelled'  # ← added

    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name='mpesa_transaction',
        null=True,
        blank=True
    )
    phone_number        = models.CharField(max_length=15)
    amount              = models.DecimalField(max_digits=10, decimal_places=2)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt       = models.CharField(max_length=100, blank=True)
    result_desc         = models.TextField(blank=True)   # ← added
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    tier = models.ForeignKey(
        TicketTier,
        on_delete=models.CASCADE,
        related_name='transactions',
        null=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions',
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone_number} - {self.amount} - {self.status}"

    class Meta:
        ordering = ['-created_at']