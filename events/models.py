from django.db import models
from django.conf import settings
import cloudinary.models


class Event(models.Model):

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        CLOSED = 'closed', 'Closed'

    organiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='events'
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    venue = models.CharField(max_length=255)
    date = models.DateTimeField()
    banner_image = cloudinary.models.CloudinaryField(
        'image',
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    resale_allowed = models.BooleanField(default=True)
    resale_price_cap = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=150.00,
        help_text='Maximum resale price as a percentage of face value'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class TicketTier(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='tiers'
    )
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    quantity_sold = models.PositiveIntegerField(default=0)
    sale_start = models.DateTimeField()
    sale_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.event.title}"

    @property
    def quantity_remaining(self):
        return self.quantity - self.quantity_sold

    @property
    def is_available(self):
        from django.utils import timezone
        now = timezone.now()
        return (
            self.quantity_remaining > 0 and
            self.sale_start <= now <= self.sale_end
        )

    class Meta:
        ordering = ['price']