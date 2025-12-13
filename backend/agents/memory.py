from __future__ import annotations

from langchain.memory import ConversationBufferMemory


class MemoryFactory:
    """Factory to build memory implementations for the agent."""

    @staticmethod
    def build_conversation_memory() -> ConversationBufferMemory:
        return ConversationBufferMemory(memory_key="chat_history", return_messages=True)
