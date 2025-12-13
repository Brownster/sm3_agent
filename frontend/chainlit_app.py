import chainlit as cl

from backend.app.config import get_settings
from backend.agents.agent_manager import AgentManager


settings = get_settings()
agent_manager = AgentManager(settings=settings)


@cl.on_chat_start
async def start():
    await cl.Message(content="Connected to Grafana MCP assistant. How can I help?").send()


@cl.on_message
async def handle_message(message: cl.Message):
    session_id = cl.user_session.get("session_id")
    if session_id is None:
        session_id = message.id
        cl.user_session.set("session_id", session_id)

    result = await agent_manager.run_chat(message.content, session_id=session_id)
    await cl.Message(content=result.message).send()
