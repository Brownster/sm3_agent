from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from backend.app.config import get_settings
from backend.agents.agent_manager import AgentManager
from backend.agents.proactive import create_default_targets, get_proactive_monitor
from backend.api.monitoring import router as monitoring_router
from backend.api.alerts import router as alerts_router
from backend.schemas.models import ChatRequest, ChatResponse
from backend.telemetry.metrics import (
    chat_requests_total,
    chat_duration_seconds,
    active_sessions,
    get_metrics,
    get_content_type,
    set_agent_info,
    update_cache_metrics,
    update_monitoring_metrics
)
from backend.tools.cache import get_cache
from backend.tools.mcp_client import MCPClient
from backend.utils.logger import get_logger
import json
import asyncio
import time


settings = get_settings()
logger = get_logger(__name__)
agent_manager = AgentManager(settings=settings)

# Store MCP client in app state
mcp_client_instance = None

app = FastAPI(
    title="Grafana MCP Chat API",
    version="0.2.0",
    description="Chat agent for Grafana observability with proactive monitoring and anomaly detection"
)

# Configure CORS with settings from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "OPTIONS", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(monitoring_router)
app.include_router(alerts_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize agent and proactive monitoring on startup."""
    logger.info("Starting Grafana MCP Chat API v0.2.0")
    logger.info(f"CORS origins: {settings.cors_origins}")
    logger.info(f"MCP server URL: {settings.mcp_server_url}")

    # Set agent info for Prometheus
    set_agent_info(
        version="0.2.0",
        model=settings.model,
        mcp_server=settings.mcp_server_url
    )

    # Initialize agent
    await agent_manager.initialize()
    logger.info("Agent initialized successfully")

    # Initialize proactive monitoring (but don't start it yet)
    try:
        mcp_client = MCPClient(settings=settings)
        await mcp_client.connect()

        proactive_monitor = get_proactive_monitor(mcp_client)

        # Add default monitoring targets (optional - can be configured via API)
        default_targets = create_default_targets()
        for target in default_targets:
            # Disable by default - user can enable via API
            target.enabled = False
            proactive_monitor.add_target(target)

        logger.info(f"Proactive monitoring initialized with {len(default_targets)} default targets")
        logger.info("Use POST /monitoring/start to begin proactive monitoring")

    except Exception as e:
        logger.warning(f"Proactive monitoring initialization failed: {e}")
        logger.warning("Proactive monitoring will not be available")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """
    Handle chat requests from the UI.

    Args:
        payload: Chat request with message and optional session_id

    Returns:
        ChatResponse with agent's message, tool calls, and suggestions
    """
    session_id = payload.session_id or "default"
    start_time = time.time()
    status = "success"

    try:
        logger.info("Processing chat request", extra={"session_id": session_id})
        active_sessions.inc()

        result = await agent_manager.run_chat(message=payload.message, session_id=session_id)

        return ChatResponse(
            message=result.message,
            tool_calls=result.tool_calls,
            suggestions=result.suggestions
        )
    except Exception as e:
        status = "error"
        logger.error(f"Chat request failed: {e}", exc_info=True)
        raise
    finally:
        duration = time.time() - start_time
        chat_requests_total.labels(session_id=session_id, status=status).inc()
        chat_duration_seconds.labels(session_id=session_id).observe(duration)
        active_sessions.dec()


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest):
    """
    Handle streaming chat requests with Server-Sent Events.

    Args:
        payload: Chat request with message and optional session_id

    Returns:
        StreamingResponse with SSE events
    """
    logger.info("Processing streaming chat request", extra={"session_id": payload.session_id})

    async def event_generator():
        """Generate SSE events for streaming response."""
        try:
            # Send initial event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Processing your request...'})}\n\n"
            await asyncio.sleep(0.1)  # Small delay for client to connect

            # Stream the agent response
            async for chunk in agent_manager.run_chat_stream(
                message=payload.message,
                session_id=payload.session_id
            ):
                if chunk["type"] == "token":
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk["type"] == "tool":
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk["type"] == "error":
                    yield f"data: {json.dumps(chunk)}\n\n"
                    break
                elif chunk["type"] == "complete":
                    yield f"data: {json.dumps(chunk)}\n\n"
                    break

                await asyncio.sleep(0.01)  # Small delay to prevent overwhelming client

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        # Send completion event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "grafana-mcp-chat"}


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Exposes metrics for monitoring agent performance, usage, and health.
    """
    # Update cache metrics
    cache = get_cache()
    update_cache_metrics(cache.get_stats())

    # Update monitoring metrics if available
    try:
        monitor = get_proactive_monitor()
        update_monitoring_metrics(monitor.get_monitoring_status())
    except:
        pass  # Monitoring might not be initialized

    return Response(content=get_metrics(), media_type=get_content_type())


@app.get("/cache/stats")
async def cache_stats() -> dict:
    """
    Get cache statistics.

    Returns:
        Cache performance metrics including hit rate, size, etc.
    """
    cache = get_cache()
    return cache.get_stats()


@app.post("/cache/clear")
async def clear_cache() -> dict:
    """
    Clear all cache entries.

    Returns:
        Confirmation message
    """
    cache = get_cache()
    stats_before = cache.get_stats()
    cache.clear()

    logger.info("Cache cleared via API")
    return {
        "status": "cleared",
        "entries_removed": stats_before["size"]
    }
