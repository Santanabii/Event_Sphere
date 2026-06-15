from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django_daraja.mpesa.core import MpesaClient
import json

def initiate_stk_push(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')          # Must be 2547xxxxxxxx
        amount = int(request.POST.get('amount', 1))
        order_id = request.POST.get('order_id', 'ORDER001')

        cl = MpesaClient()
        callback_url = 'https://your-ngrok-url.ngrok.io/mpesa/callback/'  # Update

        response = cl.stk_push(
            phone_number=phone,
            amount=amount,
            account_reference=order_id,
            transaction_desc="Ticket Purchase",
            callback_url=callback_url
        )

        # Save initial transaction
        # MpesaTransaction.objects.create(...)  # You can add this later

        return JsonResponse(response)

    return render(request, 'payments/payment_form.html')  # We'll create this next
