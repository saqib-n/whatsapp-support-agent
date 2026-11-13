"""The support agent itself.

Built with LangChain's prebuilt create_agent, which gives us a tool calling
loop (think, call a tool, read the result, decide if it needs another tool
or is ready to answer) without hand rolling the graph. Each WhatsApp phone
number gets its own conversation thread via the checkpointer, so the agent
remembers context like an order ID mentioned two messages ago.
"""

from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from agent.llm import get_llm
from agent.tools import ALL_TOOLS

SYSTEM_PROMPT = """You are a WhatsApp support assistant for an online store.

Keep replies short, the way a real support agent would text on WhatsApp,
not a formal email. A sentence or two is usually enough. Plain text only,
no emojis and no markdown.

Use check_order_status when the customer mentions an order or asks where
something is. Use search_faq for general questions about store hours,
returns, shipping, or payment. Use escalate_to_human for complaints,
damaged items, or anything you're not confident answering yourself.

If the customer hasn't given an order ID but you need one, just ask for it,
don't guess.
"""

_checkpointer = MemorySaver()
_graph = None


def get_agent(model: str | None = None):
    global _graph
    if _graph is None:
        _graph = create_agent(
            get_llm(model),
            tools=ALL_TOOLS,
            system_prompt=SYSTEM_PROMPT,
            checkpointer=_checkpointer,
        )
    return _graph


def run_turn(phone_number: str, text: str) -> dict:
    """Run the agent for one incoming message.

    Returns the reply text plus every tool the agent called on the way, in
    order, as {"name", "args", "result"} dicts. The web demo shows those
    steps next to the chat so you can see why the agent said what it said.

    phone_number is used as the thread_id, so each customer's conversation
    history is kept separate.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": phone_number}}
    result = agent.invoke({"messages": [{"role": "user", "content": text}]}, config=config)
    messages = result["messages"]

    # The thread holds the whole conversation, so only look at the messages
    # this turn added: everything after the last customer message.
    start = max(i for i, m in enumerate(messages) if m.type == "human") + 1
    tool_steps = []
    for message in messages[start:]:
        for call in getattr(message, "tool_calls", None) or []:
            tool_steps.append({"id": call.get("id"), "name": call["name"], "args": call.get("args", {}), "result": None})
        if message.type == "tool":
            for step in tool_steps:
                if step["id"] == message.tool_call_id:
                    step["result"] = message.text
    for step in tool_steps:
        step.pop("id")

    return {"reply": messages[-1].text, "tools": tool_steps}


def reply_to_message(phone_number: str, text: str) -> str:
    """Run the agent for one incoming message and return just the reply text."""
    return run_turn(phone_number, text)["reply"]
