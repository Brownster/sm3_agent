from __future__ import annotations

from typing import List

from langchain.agents import Tool

from backend.app.config import Settings
from backend.tools.mcp_client import MCPClient
from backend.utils.logger import get_logger


logger = get_logger(__name__)


def build_mcp_tools(settings: Settings) -> List[Tool]:
    """Create LangChain Tool definitions backed by MCP calls."""
    client = MCPClient(settings=settings)

    async def prometheus_tool(query: str) -> str:
        logger.info("Running Prometheus query", extra={"query": query})
        result = await client.query_prometheus(query)
        return str(result)

    async def loki_tool(query: str) -> str:
        logger.info("Running Loki query", extra={"query": query})
        result = await client.query_loki(query)
        return str(result)

    async def grafana_dashboard(uid: str) -> str:
        logger.info("Retrieving Grafana dashboard", extra={"uid": uid})
        result = await client.query_grafana_dashboard(uid)
        return str(result)

    return [
        Tool(
            name="prometheus_query",
            func=prometheus_tool,
            coroutine=prometheus_tool,
            description="Query Prometheus metrics using PromQL",
        ),
        Tool(
            name="loki_query",
            func=loki_tool,
            coroutine=loki_tool,
            description="Query Loki logs using LogQL",
        ),
        Tool(
            name="grafana_dashboard_lookup",
            func=grafana_dashboard,
            coroutine=grafana_dashboard,
            description="Fetch Grafana dashboard metadata by UID",
        ),
    ]
