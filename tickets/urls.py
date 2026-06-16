from django.urls import path
from .views import (
    InitiatePurchaseView,
    MpesaCallbackView,
    PaymentStatusView,
    MyTicketsView,
    TicketDetailView,
    ScanTicketView
)

urlpatterns = [
    path('purchase/',                          InitiatePurchaseView.as_view(), name='purchase'),
    path('mpesa/callback/',                    MpesaCallbackView.as_view(),   name='mpesa-callback'),
    path('status/<str:checkout_request_id>/',  PaymentStatusView.as_view(),   name='payment-status'),
    path('my-tickets/',                        MyTicketsView.as_view(),       name='my-tickets'),
    path('my-tickets/<int:pk>/',               TicketDetailView.as_view(),    name='ticket-detail'),
    path('scan/',                              ScanTicketView.as_view(),      name='scan-ticket'),
]