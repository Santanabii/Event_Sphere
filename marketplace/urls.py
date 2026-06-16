from django.urls import path
from .views import (
    CreateListingView,
    ListingListView,
    MyListingsView,
    CancelListingView,
    PurchaseResaleTicketView
)

urlpatterns = [
    path('listings/', ListingListView.as_view(), name='listing-list'),
    path('listings/create/', CreateListingView.as_view(), name='create-listing'),
    path('listings/my/', MyListingsView.as_view(), name='my-listings'),
    path('listings/<int:pk>/cancel/', CancelListingView.as_view(), name='cancel-listing'),
    path('listings/<int:pk>/purchase/', PurchaseResaleTicketView.as_view(), name='purchase-resale'),
]