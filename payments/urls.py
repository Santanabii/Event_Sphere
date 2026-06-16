from django.urls import path
from .views import initiate_stk_push, mpesa_callback

urlpatterns = [
    path('pay/', initiate_stk_push, name='mpesa_pay'),
    path('callback/', mpesa_callback, name='mpesa_callback'),
]