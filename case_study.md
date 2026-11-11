# WhatsApp Support Agent

## Portfolio entry

An AI support agent for WhatsApp that checks real order data, answers from the store's FAQ, and escalates complaints and damaged-item reports to a person instead of trying to resolve them. Built on LangGraph's tool-calling agent with three tools and conversation memory keyed to each customer's phone number. Connects to Meta's WhatsApp Cloud API through a FastAPI webhook, and ships with a terminal simulator that runs the identical agent code so the logic can be demoed without a Meta developer account.

**Stack:** Python, LangGraph, LangChain, FastAPI, WhatsApp Cloud API

---

## Why WhatsApp specifically

For a lot of small businesses, WhatsApp is where customers already are. They're not going to a support portal, they're messaging the number on the shop's Instagram page. Which means the support burden lands in a personal-feeling channel with no ticketing, no history, and one person trying to answer "where's my order" forty times a day between other work.

## Three tools and one that matters most

The agent picks between checking an order, searching the FAQ, and escalating to a human.

The escalation tool is the one that makes this usable. Without it the agent tries to handle a damaged-item complaint, which it has no authority to resolve, and produces something apologetic and useless. With it, the agent recognises the shape of the message, opens a ticket, and tells the customer a person is coming. That's a better outcome than any answer it could have generated.

## Tone was a real problem

First version wrote like a support email. Formal greeting, full paragraphs, sign-off. In WhatsApp that reads as a bot immediately, because no human texts like that.

Fixing it was a system prompt change, keep it to a sentence or two, write like a person texting. Small thing, but it's the difference between a customer engaging and a customer asking for a human straight away.

## Two entry points, one agent

Setting up WhatsApp Business API takes a Meta developer account, an app, a test number and a verify token. That's a lot of friction before you can find out whether the agent is any good.

So there are two ways in. `simulate_chat.py` runs the agent from a terminal. `app.py` is the FastAPI webhook for real WhatsApp traffic. Both call the same `reply_to_message` function, nothing is duplicated, so the simulator is a genuine test of the thing that runs in production rather than a separate demo path that might drift.

For client work that also means I can show the agent working in a call before anyone touches Meta's developer console.

## Rough edges

Escalation produces a ticket number but there's no interface for a human to actually take over the conversation, which is the obvious next build.

Also missing: WhatsApp message templates, required if the business wants to message a customer first rather than only replying, and retry handling on the Graph API call, since a dropped request currently loses a reply silently.

## My part

Tool design and escalation logic, the LangGraph agent, and the WhatsApp Cloud API integration end to end including the webhook verification handshake.
