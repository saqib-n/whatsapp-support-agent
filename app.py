"""FastAPI webhook server for the WhatsApp support agent.

This is what you'd actually deploy and point Meta's webhook at. For local
testing without a real WhatsApp Business setup, use simulate_chat.py
instead, it runs the exact same agent logic from the command line.

Run locally:
    uvicorn app:app --reload --port 8000

Then expose it with ngrok (or similar) and set that URL as the webhook in
your Meta developer app, with the /webhook path.
"""

import json
import logging
import os
from collections import deque

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request, Response

from agent.core import reply_to_message
from whatsapp_client import extract_incoming_message, send_whatsapp_message, signature_is_valid

load_dotenv()

logger = logging.getLogger("whatsapp-agent")
app = FastAPI(title="WhatsApp Support Agent")

# Meta retries a webhook it thinks failed, so remember recent message ids
# and don't answer the same message twice.
_recent_ids: deque[str] = deque(maxlen=1000)


@app.get("/webhook")
def verify_webhook(request: Request):
    """Meta calls this once when you set up the webhook, to confirm you
    control the endpoint."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge", "")

    expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    # Without a configured token nobody passes, otherwise a request with no
    # token at all would match an unset one.
    if expected_token and mode == "subscribe" and token == expected_token:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


def handle_message(from_number: str, text: str) -> None:
    """Runs after the webhook has already answered Meta, so a slow model
    call never makes Meta time out and resend the message."""
    try:
        reply_text = reply_to_message(phone_number=from_number, text=text)
        send_whatsapp_message(to=from_number, text=reply_text)
    except Exception:
        logger.exception("Failed to answer the WhatsApp message from %s", from_number)


@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Meta posts incoming messages here."""
    body = await request.body()

    app_secret = os.getenv("WHATSAPP_APP_SECRET")
    if app_secret:
        if not signature_is_valid(body, request.headers.get("X-Hub-Signature-256", ""), app_secret):
            return Response(content="Invalid signature", status_code=403)
    else:
        logger.warning("WHATSAPP_APP_SECRET is not set, accepting an unsigned webhook call.")

    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return Response(content="Invalid JSON", status_code=400)

    parsed = extract_incoming_message(payload)
    if parsed is None:
        # Not a text message (could be a status update, image, etc.), ignore it.
        return {"status": "ignored"}

    from_number, text, message_id = parsed
    if message_id and message_id in _recent_ids:
        return {"status": "duplicate"}
    if message_id:
        _recent_ids.append(message_id)

    background_tasks.add_task(handle_message, from_number, text)
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
