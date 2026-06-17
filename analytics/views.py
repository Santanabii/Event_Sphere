import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from events.models import Event
from tickets.models import Ticket

logger = logging.getLogger(__name__)


class EventAnalyticsView(APIView):
    """REST endpoint — organiser fetches analytics for their event."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, event_id):
        try:
            event = Event.objects.get(
                id=event_id,
                organiser=request.user
            )
        except Event.DoesNotExist:
            return Response(
                {"error": "Event not found."},
                status=404
            )

        tiers = event.tiers.all()
        total_sold = sum(tier.quantity_sold for tier in tiers)
        total_capacity = sum(tier.quantity for tier in tiers)
        total_revenue = sum(
            tier.quantity_sold * tier.price for tier in tiers
        )
        checked_in = Ticket.objects.filter(
            tier__event=event,
            status='used'
        ).count()

        tier_breakdown = [
            {
                'name': tier.name,
                'price': float(tier.price),
                'quantity': tier.quantity,
                'sold': tier.quantity_sold,
                'remaining': tier.quantity_remaining,
                'revenue': float(tier.quantity_sold * tier.price)
            }
            for tier in tiers
        ]

        return Response({
            'event_id': event.id,
            'event_title': event.title,
            'total_sold': total_sold,
            'total_capacity': total_capacity,
            'total_revenue': float(total_revenue),
            'checked_in': checked_in,
            'checkin_rate': round(
                (checked_in / total_sold * 100) if total_sold > 0 else 0, 1
            ),
            'tier_breakdown': tier_breakdown
        })


def push_analytics_update(event_id):
    """
    Called after a ticket scan to push live update
    to all connected organiser dashboards.
    """
    try:
        channel_layer = get_channel_layer()
        event = Event.objects.get(id=event_id)
        tiers = event.tiers.all()

        total_sold = sum(tier.quantity_sold for tier in tiers)
        checked_in = Ticket.objects.filter(
            tier__event=event,
            status='used'
        ).count()

        data = {
            'event_id': event_id,
            'total_sold': total_sold,
            'checked_in': checked_in,
            'checkin_rate': round(
                (checked_in / total_sold * 100) if total_sold > 0 else 0, 1
            ),
            'total_revenue': float(sum(
                tier.quantity_sold * tier.price for tier in tiers
            ))
        }

        async_to_sync(channel_layer.group_send)(
            f'analytics_{event_id}',
            {
                'type': 'analytics_update',
                'data': data
            }
        )
    except Exception as e:
        logger.error("Analytics push failed: %s", e)