"""FastAPI server for the WhatsApp support agent.

Two things live here:

  /          a chat screen in the browser, to try the agent without any
             WhatsApp account (it calls /api/chat)
  /webhook   the real endpoint you point Meta's WhatsApp webhook at

Run locally (opens the chat screen in your browser):
    python app.py

For the real WhatsApp number, expose port 8000 with ngrok (or similar) and
set that URL plus /webhook as the callback in your Meta developer app.
"""

import json
import logging
import os
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from agent.core import reply_to_message, run_turn
from agent.llm import DEFAULT_MODEL
from whatsapp_client import extract_incoming_message, send_whatsapp_message, signature_is_valid

load_dotenv()

logger = logging.getLogger("whatsapp-agent")
app = FastAPI(title="WhatsApp Support Agent")

WEB_DIR = Path(__file__).resolve().parent / "web"


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)


@app.get("/", include_in_schema=False)
def chat_screen():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/info")
def info():
    return {"model": os.getenv("LLM_MODEL") or DEFAULT_MODEL}


@app.post("/api/chat")
def chat(request: ChatRequest):
    """One customer message in, the agent's reply and the tools it used out.

    The session id plays the part of the customer's phone number, so each
    browser tab gets its own conversation memory.
    """
    started = time.perf_counter()
    try:
        turn = run_turn(phone_number=f"web-{request.session_id}", text=request.text.strip())
    except Exception as exc:
        logger.exception("The agent failed to answer a chat message")
        detail = str(exc).splitlines()[0][:200] if str(exc) else ""
        return JSONResponse(status_code=502, content={"error": f"The agent could not answer ({type(exc).__name__}: {detail}). Check the server log, your API key and your quota."})
    return {**turn, "seconds": round(time.perf_counter() - started, 1)}

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


if __name__ == "__main__":
    import threading
    import webbrowser

    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=port)
