from django.urls import path
from .views import EventAnalyticsView

urlpatterns = [
    path('events/<int:event_id>/', EventAnalyticsView.as_view(), name='event-analytics'),
]