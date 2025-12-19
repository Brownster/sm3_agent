from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain.agents import Tool
from langchain.tools import StructuredTool

from backend.app.config import Settings
from backend.tools.mcp_client import MCPClient
from backend.tools.result_formatter import ToolResultFormatter
from backend.utils.logger import get_logger


logger = get_logger(__name__)
formatter = ToolResultFormatter()


def _extract_prometheus_uid(data: Any) -> str | None:
    """Find a Prometheus datasource UID from list_datasources result."""
    try:
        # Handle MCP TextContent objects - extract text and parse JSON
        if isinstance(data, list) and data and hasattr(data[0], 'text'):
            # Parse the JSON from the text content
            text = data[0].text
            parsed = json.loads(text) if isinstance(text, str) else text
            if isinstance(parsed, dict):
                data = parsed

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # common MCP shape might wrap in "datasources"
            if "datasources" in data and isinstance(data["datasources"], list):
                items = data["datasources"]
            elif "items" in data and isinstance(data["items"], list):
                items = data["items"]

        for item in items:
            if not isinstance(item, dict):
                continue
            ds_type = item.get("type") or item.get("datasource_type")
            if ds_type and "prometheus" in str(ds_type).lower():
                uid = item.get("uid") or item.get("id")
                if uid:
                    return uid
    except Exception:
        return None
    return None


async def build_mcp_tools(settings: Settings) -> List[Tool]:
    """
    Dynamically discover and create LangChain Tool definitions from MCP server.

    This connects to the Grafana MCP server and discovers all available tools,
    then wraps them as LangChain tools that the agent can use.
    """
    client = MCPClient(settings=settings)

    try:
        # Connect to MCP server
        await client.connect()
        logger.info("Connected to MCP server for tool discovery")

        # Discover all available tools from the MCP server
        tools_response = await client.session.list_tools()
        logger.info(f"Discovered {len(tools_response.tools)} tools from MCP server")

        langchain_tools = []

        for mcp_tool in tools_response.tools:
            # Create a closure that captures the tool name and client
            def make_tool_func(tool_name: str):
                async def tool_func(arguments: Any | None = None) -> str:
                    """
                    Execute an MCP tool with the given input.

                    Args:
                        arguments: dict, JSON string, plain string, or None containing tool arguments

                    Returns:
                        Formatted string result from the MCP tool
                    """
                    try:
                        # Normalize arguments
                        if arguments is None:
                            arguments_dict: Dict[str, Any] = {}
                        elif isinstance(arguments, dict):
                            arguments_dict = arguments
                        elif isinstance(arguments, str):
                            cleaned = arguments.strip()
                            if cleaned.startswith('{'):
                                arguments_dict = json.loads(cleaned)
                            elif cleaned:
                                arguments_dict = {"input": cleaned}
                            else:
                                arguments_dict = {}
                        else:
                            return "❌ Error: Unsupported argument type"

                        if "datasource_uid" in arguments_dict and "datasourceUid" not in arguments_dict:
                            arguments_dict["datasourceUid"] = arguments_dict.pop("datasource_uid")

                        # Auto-select Prometheus datasource if missing
                        if tool_name == "list_prometheus_metric_names" and "datasourceUid" not in arguments_dict:
                            ds_result = await client.invoke_tool("list_datasources", {})
                            prom_uid = _extract_prometheus_uid(ds_result)
                            if prom_uid:
                                arguments_dict["datasourceUid"] = prom_uid

                        logger.info(f"Invoking MCP tool: {tool_name}", extra={"arguments": arguments_dict})
                        result = await client.invoke_tool(tool_name, arguments_dict)

                        # Use structured formatter for better LLM comprehension
                        formatted_result = formatter.format(tool_name, result)

                        logger.debug(f"Tool {tool_name} completed", extra={
                            "result_length": len(formatted_result)
                        })

                        return formatted_result

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tool input as JSON: {e}")
                        return f"❌ Error: Invalid JSON input - {str(e)}"
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}", extra={"tool": tool_name})
                        return f"❌ Error executing {tool_name}: {str(e)}"

                return tool_func

            # Create the tool function with closure
            tool_func = make_tool_func(mcp_tool.name)

            # Build description with parameter info if available
            description = mcp_tool.description or f"Execute {mcp_tool.name}"
            if hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema:
                schema = mcp_tool.inputSchema
                if 'properties' in schema:
                    params = ', '.join(schema['properties'].keys())
                    description += f"\n\nParameters: {params}"
                if 'required' in schema:
                    required = ', '.join(schema['required'])
                    description += f"\n\nRequired: {required}"

            # Create LangChain Tool
            # Use coroutine parameter for async functions
            langchain_tools.append(StructuredTool.from_function(
                coroutine=tool_func,
                name=mcp_tool.name,
                description=description,
            ))

        logger.info(f"Successfully created {len(langchain_tools)} LangChain tools")
        return langchain_tools

    except Exception as e:
        logger.error(f"Failed to discover MCP tools: {e}")
        # Return empty list if discovery fails - agent will still work without tools
        return []
