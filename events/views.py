from rest_framework import generics, permissions
from .models import Event, TicketTier
from .serializers import EventSerializer, TicketTierSerializer
from .permissions import IsOrganiser, IsOrganiserOrReadOnly


class EventListCreateView(generics.ListCreateAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsOrganiserOrReadOnly]

    def get_queryset(self):
        # Public sees only published events
        # Organisers see their own events including drafts
        user = self.request.user
        if user.is_authenticated and user.role == 'organiser':
            return Event.objects.filter(organiser=user)
        return Event.objects.filter(status='published')

    def perform_create(self, serializer):
        # Automatically set the organiser to the logged in user
        serializer.save(organiser=self.request.user)


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsOrganiserOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role == 'organiser':
            return Event.objects.filter(organiser=user)
        return Event.objects.filter(status='published')


class TicketTierListCreateView(generics.ListCreateAPIView):
    serializer_class = TicketTierSerializer
    permission_classes = [IsOrganiser]

    def get_queryset(self):
        return TicketTier.objects.filter(
            event__organiser=self.request.user,
            event_id=self.kwargs['event_id']
        )

    def perform_create(self, serializer):
        event = Event.objects.get(
            id=self.kwargs['event_id'],
            organiser=self.request.user
        )
        serializer.save(event=event)


class TicketTierDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TicketTierSerializer
    permission_classes = [IsOrganiser]

    def get_queryset(self):
        return TicketTier.objects.filter(
            event__organiser=self.request.user,
            event_id=self.kwargs['event_id']
        )
