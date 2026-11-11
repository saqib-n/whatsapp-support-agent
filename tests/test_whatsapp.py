import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import app as webhook
from agent.tools import check_order_status, search_faq
from whatsapp_client import extract_incoming_message


def text_payload(message_id="wamid.1", text="where is ORD-2001?"):
    return {"entry": [{"changes": [{"value": {"messages": [
        {"from": "15551234567", "id": message_id, "type": "text", "text": {"body": text}}
    ]}}]}]}


def test_tools():
    assert "Out for Delivery" in check_order_status.invoke({"order_id": "ord-2001"})
    assert "No order found" in check_order_status.invoke({"order_id": "ORD-9"})
    assert "Monday to Saturday" in search_faq.invoke({"query": "what are your hours"})


def test_payload_parsing():
    assert extract_incoming_message(text_payload()) == ("15551234567", "where is ORD-2001?", "wamid.1")
    status_update = {"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]}
    assert extract_incoming_message(status_update) is None


def test_verify_handshake(monkeypatch):
    client = TestClient(webhook.app)
    params = {"hub.mode": "subscribe", "hub.challenge": "42"}
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)
    assert client.get("/webhook", params=params).status_code == 403
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "secret-token")
    ok = client.get("/webhook", params={**params, "hub.verify_token": "secret-token"})
    assert (ok.status_code, ok.text) == (200, "42")


def test_signature_and_duplicates(monkeypatch):
    handled = []
    monkeypatch.setattr(webhook, "handle_message", lambda number, text: handled.append(text))
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    webhook._recent_ids.clear()
    client = TestClient(webhook.app)

    body = json.dumps(text_payload()).encode()
    assert client.post("/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=wrong"}).status_code == 403

    signature = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}
    assert client.post("/webhook", content=body, headers=headers).json() == {"status": "ok"}
    assert client.post("/webhook", content=body, headers=headers).json() == {"status": "duplicate"}
    assert handled == ["where is ORD-2001?"]
