from __future__ import annotations

from typing import Any, Dict, List, Optional
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from backend.app.config import Settings
from backend.tools.cache import get_cache
from backend.utils.logger import get_logger


logger = get_logger(__name__)


class MCPClient:
    """
    MCP client wrapper for Grafana MCP server with proper lifecycle management.

    Uses AsyncExitStack to properly manage async context managers.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._connection_attempts = 0
        self._max_retries = 3

    async def __aenter__(self) -> MCPClient:
        """Async context manager entry - establishes connection."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures proper cleanup."""
        await self.disconnect()

    async def connect(self) -> None:
        """
        Establish a connection to the MCP server with retry logic.

        Raises:
            Exception: If connection fails after max retries
        """
        if self.session is not None:
            logger.debug("Already connected to MCP server")
            return

        last_error = None
        while self._connection_attempts < self._max_retries:
            try:
                logger.info(
                    f"Connecting to MCP server (attempt {self._connection_attempts + 1}/{self._max_retries})",
                    extra={"url": self.settings.mcp_server_url}
                )

                # Use AsyncExitStack to properly manage context managers
                self._exit_stack = AsyncExitStack()
                await self._exit_stack.__aenter__()

                # Enter transport context
                read, write, _ = await self._exit_stack.enter_async_context(
                    streamablehttp_client(url=self.settings.mcp_server_url)
                )

                # Enter session context
                self.session = await self._exit_stack.enter_async_context(
                    ClientSession(read, write)
                )

                # Initialize session
                await self.session.initialize()

                logger.info("Successfully connected to MCP server", extra={"url": self.settings.mcp_server_url})
                self._connection_attempts = 0
                return

            except Exception as e:
                last_error = e
                self._connection_attempts += 1
                logger.error(
                    f"Failed to connect to MCP server: {e}",
                    extra={
                        "url": self.settings.mcp_server_url,
                        "attempt": self._connection_attempts,
                        "max_retries": self._max_retries
                    }
                )

                # Clean up exit stack on error
                if self._exit_stack:
                    try:
                        await self._exit_stack.__aexit__(None, None, None)
                    except:
                        pass
                    self._exit_stack = None
                    self.session = None

                if self._connection_attempts >= self._max_retries:
                    raise Exception(
                        f"Failed to connect to MCP server after {self._max_retries} attempts: {last_error}"
                    ) from last_error

    async def disconnect(self) -> None:
        """Gracefully disconnect from the MCP server."""
        try:
            if self._exit_stack is not None:
                logger.info("Disconnecting from MCP server")
                await self._exit_stack.__aexit__(None, None, None)
                self._exit_stack = None
                self.session = None
                self._connection_attempts = 0
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")

    async def ensure_connected(self) -> None:
        """Ensure connection is established, reconnect if needed."""
        if self.session is None:
            logger.warning("Connection lost, attempting to reconnect")
            await self.connect()

    async def invoke_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """
        Invoke an MCP tool by name with arguments (with caching).

        Args:
            name: Tool name to invoke
            arguments: Dictionary of arguments for the tool

        Returns:
            Tool execution result (may be from cache)

        Raises:
            Exception: If tool invocation fails
        """
        cache = get_cache()

        # Try to get from cache first
        cached_result = cache.get(name, arguments)
        if cached_result is not None:
            logger.info(f"Cache hit for tool: {name}")
            return cached_result

        try:
            await self.ensure_connected()

            logger.debug(f"Invoking tool: {name}", extra={"arguments": arguments})
            response = await self.session.call_tool(name=name, arguments=arguments)

            if response and hasattr(response, 'content'):
                result = response.content

                # Store in cache
                cache.set(name, arguments, result)

                return result
            else:
                logger.warning(f"Tool {name} returned no content")
                return {"error": f"No response from tool {name}"}

        except Exception as e:
            logger.error(
                f"Tool invocation failed: {e}",
                extra={"tool": name, "arguments": arguments}
            )
            raise Exception(f"Failed to invoke tool '{name}': {str(e)}") from e

    def invalidate_cache(self, tool_name: str, arguments: Dict[str, Any] = None):
        """
        Invalidate cache for a specific tool.

        Useful after write operations (update_dashboard, etc.)

        Args:
            tool_name: Name of the tool to invalidate
            arguments: Specific arguments to invalidate, or None for all
        """
        cache = get_cache()
        cache.invalidate(tool_name, arguments)
        logger.info(f"Invalidated cache for: {tool_name}")
