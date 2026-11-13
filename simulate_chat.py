"""Test the agent from the terminal, no WhatsApp account needed.

This runs the exact same agent logic that app.py uses for real WhatsApp
messages, just with your keyboard standing in for WhatsApp. Useful for
building and demoing the agent before setting up a Meta developer account.

Run:
    python simulate_chat.py

Try:
    Hey, where's my order ORD-2001?
    what are your store hours
    my order arrived broken, I want a refund
"""

import sys

from dotenv import load_dotenv

from agent.core import reply_to_message

load_dotenv()


def main():
    # Windows terminals default to a code page that can't print every
    # character a model might send back, so switch to UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    fake_phone_number = "923001234567"
    print("WhatsApp Support Agent (simulated chat), type 'exit' to quit\n")

    while True:
        user_input = input("Customer: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        reply = reply_to_message(phone_number=fake_phone_number, text=user_input)
        print(f"Agent: {reply}\n")


if __name__ == "__main__":
    main()
