from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Conversation session identifier")


class ChatResponse(BaseModel):
    message: str
    tool_calls: List[Any] = Field(default_factory=list)


class AgentResult(BaseModel):
    message: str
    tool_calls: List[Any] = Field(default_factory=list)
