import base64
import logging
from datetime import datetime

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_access_token() -> str:
    url = f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=15,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    logger.debug("Daraja access token obtained successfully.")
    return token


def stk_push(phone_number: str, amount: int, account_reference: str, description: str) -> dict:
    timestamp    = datetime.now().strftime("%Y%m%d%H%M%S")
    raw_password = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    password     = base64.b64encode(raw_password.encode()).decode()

    access_token = get_access_token()

    url     = f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}"}

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password":          password,
        "Timestamp":         timestamp,
        "TransactionType":   "CustomerPayBillOnline",
        "Amount":            int(amount),
        "PartyA":            phone_number,
        "PartyB":            settings.MPESA_SHORTCODE,
        "PhoneNumber":       phone_number,
        "CallBackURL":       settings.MPESA_CALLBACK_URL,
        "AccountReference":  account_reference[:12],
        "TransactionDesc":   description[:13],
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    logger.info("STK Push sent | CheckoutRequestID: %s", data.get("CheckoutRequestID"))
    return data


def normalise_phone(raw: str) -> str:
    """
    Normalise a Kenyan phone number to the 254XXXXXXXXX format required by Daraja.

    Accepted input formats:
      - 07XXXXXXXX  (local format, Safaricom / Airtel)
      - 01XXXXXXXX  (local format, Airtel)
      - +2547XXXXXXXX
      - 2547XXXXXXXX
    """
    phone = raw.strip().replace(" ", "").replace("-", "")

    if phone.startswith("+"):
        phone = phone[1:]

    if phone.startswith("07") or phone.startswith("01"):
        phone = "254" + phone[1:]

    if not phone.startswith("254") or len(phone) != 12:
        raise ValueError(
            f"Invalid phone number '{raw}'. "
            "Expected formats: 07XXXXXXXX, +2547XXXXXXXX, or 2547XXXXXXXX"
        )

    return phone