import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from tickets.models import Ticket
from events.models import Event


class AnalyticsConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.event_id = self.scope['url_route']['kwargs']['event_id']
        self.group_name = f'analytics_{self.event_id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

        # Send current stats immediately on connect
        stats = await self.get_stats()
        await self.send(text_data=json.dumps(stats))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Client can request a refresh
        stats = await self.get_stats()
        await self.send(text_data=json.dumps(stats))

    async def analytics_update(self, event):
        # Receive update from group and forward to WebSocket client
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def get_stats(self):
        try:
            event = Event.objects.get(id=self.event_id)
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

            return {
                'event_id': self.event_id,
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

        except Event.DoesNotExist:
            return {'error': 'Event not found'}