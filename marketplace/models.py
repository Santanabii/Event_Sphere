from django.db import models
from django.conf import settings
from tickets.models import Ticket
import uuid


class Listing(models.Model):

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        SOLD = 'sold', 'Sold'
        CANCELLED = 'cancelled', 'Cancelled'

    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name='listing'
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='listings'
    )
    asking_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )
    listed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.seller.email} - {self.ticket.tier.event.title} - {self.asking_price}"

    class Meta:
        ordering = ['-listed_at']


class ResaleOrder(models.Model):
    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name='resale_order'
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='resale_purchases'
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    seller_payout = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    new_qr_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.buyer.email} bought from {self.listing.seller.email}"


class ResaleMpesaTransaction(models.Model):

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='mpesa_transactions'
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='resale_transactions'
    )
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone_number} - {self.amount} - {self.status}"