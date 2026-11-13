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


def reply_to_message(phone_number: str, text: str) -> str:
    """Run the agent for one incoming message and return the reply text.

    phone_number is used as the thread_id, so each customer's conversation
    history is kept separate.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": phone_number}}
    result = agent.invoke({"messages": [{"role": "user", "content": text}]}, config=config)
    return result["messages"][-1].text
