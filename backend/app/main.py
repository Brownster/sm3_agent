from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import get_settings
from backend.agents.agent_manager import AgentManager
from backend.schemas.models import ChatRequest, ChatResponse
from backend.utils.logger import get_logger


settings = get_settings()
logger = get_logger(__name__)
agent_manager = AgentManager(settings=settings)

app = FastAPI(title="Grafana MCP Chat API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """Handle chat requests from the UI."""
    logger.info("Processing chat request", extra={"session_id": payload.session_id})
    result = await agent_manager.run_chat(message=payload.message, session_id=payload.session_id)
    return ChatResponse(message=result.message, tool_calls=result.tool_calls)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
