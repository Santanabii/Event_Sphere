from django.urls import path
from .views import (
    EventListCreateView,
    EventDetailView,
    TicketTierListCreateView,
    TicketTierDetailView
)

urlpatterns = [
    path('', EventListCreateView.as_view(), name='event-list-create'),
    path('<int:pk>/', EventDetailView.as_view(), name='event-detail'),
    path('<int:event_id>/tiers/', TicketTierListCreateView.as_view(), name='tier-list-create'),
    path('<int:event_id>/tiers/<int:pk>/', TicketTierDetailView.as_view(), name='tier-detail'),
]