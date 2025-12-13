from __future__ import annotations

from typing import Any, Dict

from modelcontextprotocol.client import Client
from modelcontextprotocol.client.streamable_http import streamablehttp_client

from backend.app.config import Settings
from backend.utils.logger import get_logger


logger = get_logger(__name__)


class MCPClient:
    """Lightweight MCP client wrapper for Grafana MCP server."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = Client(app_name="grafana-mcp-chat")

    async def connect(self) -> None:
        """Establish a connection to the MCP server."""
        transport = streamablehttp_client(url=self.settings.mcp_server_url)
        await self.client.connect(transport)
        logger.info("Connected to MCP server", extra={"url": self.settings.mcp_server_url})

    async def invoke_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Invoke an MCP tool by name with arguments."""
        if not self.client.connected:
            await self.connect()
        response = await self.client.call_tool(name=name, arguments=arguments)
        return response.content if response else {}

    async def query_prometheus(self, query: str) -> Any:
        return await self.invoke_tool("prometheus_query", {"query": query})

    async def query_loki(self, query: str) -> Any:
        return await self.invoke_tool("loki_query", {"query": query})

    async def query_grafana_dashboard(self, uid: str) -> Any:
        return await self.invoke_tool("grafana_dashboard", {"uid": uid})
