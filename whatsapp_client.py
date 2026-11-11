"""Thin wrapper around Meta's WhatsApp Cloud API.

You need a Meta developer app with the WhatsApp product added, a test
phone number (Meta gives you one for free during development), and a
permanent access token. None of that is required just to try the agent
logic, see simulate_chat.py for that, this file is only used once you're
ready to connect a real WhatsApp number.
"""

import hashlib
import hmac
import os

import requests

DEFAULT_GRAPH_API_VERSION = "v23.0"


def _api_url() -> str:
    version = os.getenv("WHATSAPP_GRAPH_API_VERSION") or DEFAULT_GRAPH_API_VERSION
    phone_number_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    return f"https://graph.facebook.com/{version}/{phone_number_id}/messages"


def send_whatsapp_message(to: str, text: str) -> dict:
    """Send a plain text WhatsApp message to a phone number (E.164 format,
    no leading +, e.g. '15551234567')."""
    token = os.environ["WHATSAPP_ACCESS_TOKEN"]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(_api_url(), json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()


def signature_is_valid(body: bytes, signature_header: str, app_secret: str) -> bool:
    """Check Meta's X-Hub-Signature-256 header against the raw request body."""
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


def extract_incoming_message(payload: dict) -> tuple[str, str, str] | None:
    """Pull (from_number, message_text, message_id) out of a WhatsApp
    webhook POST body.

    Returns None if the payload isn't a text message (e.g. it's a delivery
    status update, which WhatsApp also sends to the same webhook).
    """
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        messages = change.get("messages")
        if not messages:
            return None
        message = messages[0]
        if message.get("type") != "text":
            return None
        return message["from"], message["text"]["body"], message.get("id", "")
    except (KeyError, IndexError, TypeError):
        return None
