from django.urls import path
from .views import (
    CreateListingView,
    ListingListView,
    MyListingsView,
    CancelListingView,
    InitiateResalePurchaseView,
    ResaleMpesaCallbackView,
    ResalePaymentStatusView
)

urlpatterns = [
    path('listings/', ListingListView.as_view(), name='listing-list'),
    path('listings/create/', CreateListingView.as_view(), name='create-listing'),
    path('listings/my/', MyListingsView.as_view(), name='my-listings'),
    path('listings/<int:pk>/cancel/', CancelListingView.as_view(), name='cancel-listing'),
    path('listings/<int:pk>/purchase/', InitiateResalePurchaseView.as_view(), name='purchase-resale'),
    path('mpesa/callback/', ResaleMpesaCallbackView.as_view(), name='resale-mpesa-callback'),
    path('payment-status/<str:checkout_request_id>/', ResalePaymentStatusView.as_view(), name='resale-payment-status'),
]