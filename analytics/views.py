import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from events.models import Event
from tickets.models import Ticket

logger = logging.getLogger(__name__)


def _build_stats(event):
    """
    Single source of truth for the analytics payload shape — used by both
    the initial REST fetch (EventAnalyticsView) and every live WebSocket
    push (push_analytics_update), so the two can never drift out of sync
    again like they had (push_analytics_update was previously missing
    event_title, total_capacity, and tier_breakdown, which broke the
    frontend the moment a live update replaced the initial full payload).
    """
    tiers = event.tiers.all()
    total_sold = sum(tier.quantity_sold for tier in tiers)
    total_capacity = sum(tier.quantity for tier in tiers)
    total_revenue = sum(tier.quantity_sold * tier.price for tier in tiers)
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

    return {
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
    }


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

        return Response(_build_stats(event))


def push_analytics_update(event_id):
    """
    Called after a ticket scan to push live update
    to all connected organiser dashboards.
    """
    try:
        channel_layer = get_channel_layer()
        event = Event.objects.get(id=event_id)
        data = _build_stats(event)

        async_to_sync(channel_layer.group_send)(
            f'analytics_{event_id}',
            {
                'type': 'analytics_update',
                'data': data
            }
        )
    except Exception as e:
        logger.error("Analytics push failed: %s", e)