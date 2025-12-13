from __future__ import annotations

from typing import List

from langchain.agents import AgentExecutor, AgentType, initialize_agent
from langchain.agents import Tool as LangChainTool
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

from backend.app.config import Settings
from backend.schemas.models import AgentResult
from backend.tools.tool_wrappers import build_mcp_tools
from backend.utils.prompts import SYSTEM_PROMPT


class AgentManager:
    """Orchestrates LLM calls, tools, and memory."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        self.llm = ChatOpenAI(model=settings.model, temperature=0.1, api_key=settings.openai_api_key)
        self.tools: List[LangChainTool] = build_mcp_tools(settings=settings)
        self.agent: AgentExecutor = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
            verbose=settings.enable_tracing,
            memory=self.memory,
            handle_parsing_errors=True,
            agent_kwargs={"system_message": SYSTEM_PROMPT},
        )

    async def run_chat(self, message: str, session_id: str | None) -> AgentResult:
        """Execute a chat turn and return the agent response."""
        response = await self.agent.arun(input=message, session_id=session_id)
        tool_calls = getattr(self.agent, "tool_calls", None) or []
        return AgentResult(message=response, tool_calls=tool_calls)
