"""Tools the WhatsApp support agent can call.

These read local JSON files so the whole project runs without a real store
backend. Swap get_order_status and search_faq for real API calls (Shopify,
WooCommerce, a helpdesk system) to point this at an actual store.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

from langchain_core.tools import tool

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(filename: str):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@tool
def check_order_status(order_id: str) -> str:
    """Look up an order by its ID (e.g. ORD-2001) and return its status,
    item, and estimated delivery date."""
    orders = _load("orders.json")
    order_id = order_id.strip().upper()

    if order_id not in orders:
        return f"No order found with ID {order_id}. Ask the customer to double check the ID."

    # Demo orders store dates relative to today so they never go stale.
    order = orders[order_id]
    placed = date.today() - timedelta(days=order["ordered_days_ago"])
    delivery = placed + timedelta(days=order["delivery_days"])
    return (
        f"Order {order_id}: {order['item']}, status is {order['status']}, "
        f"estimated delivery {delivery.isoformat()} (today is {date.today().isoformat()})."
    )


@tool
def search_faq(query: str) -> str:
    """Search the store's FAQ knowledge base for an answer to a general
    question about store hours, returns, shipping, or payment."""
    faqs = _load("faq.json")
    query_lower = query.lower()

    best_match = None
    best_score = 0
    for entry in faqs:
        score = sum(1 for kw in entry["keywords"] if kw in query_lower)
        if score > best_score:
            best_score = score
            best_match = entry

    if best_match is None or best_score == 0:
        return "No matching FAQ entry found. If you can't answer confidently, escalate to a human instead of guessing."

    return best_match["answer"]


@tool
def escalate_to_human(reason: str) -> str:
    """Escalate the conversation to a human support agent when the request
    is a complaint, involves a damaged or wrong item, or is something you
    can't confidently resolve yourself."""
    ticket_id = f"WA-{random.randint(10000, 99999)}"
    return f"Escalated to a human agent. Ticket {ticket_id} created, tell the customer someone will follow up shortly."


ALL_TOOLS = [check_order_status, search_faq, escalate_to_human]
