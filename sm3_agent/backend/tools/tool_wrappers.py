from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain.agents import Tool

from backend.app.config import Settings
from backend.tools.mcp_client import MCPClient
from backend.tools.result_formatter import ToolResultFormatter
from backend.utils.logger import get_logger


logger = get_logger(__name__)
formatter = ToolResultFormatter()


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
                async def tool_func(tool_input: str) -> str:
                    """
                    Execute an MCP tool with the given input.

                    Args:
                        tool_input: JSON string or plain string containing tool arguments

                    Returns:
                        Formatted string result from the MCP tool
                    """
                    try:
                        # Parse input as JSON if possible, otherwise treat as single string argument
                        if tool_input.strip().startswith('{'):
                            arguments = json.loads(tool_input)
                        else:
                            # For simple tools with single string argument
                            arguments = {"input": tool_input}

                        logger.info(f"Invoking MCP tool: {tool_name}", extra={"arguments": arguments})
                        result = await client.invoke_tool(tool_name, arguments)

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
            langchain_tools.append(Tool(
                name=mcp_tool.name,
                func=tool_func,
                coroutine=tool_func,
                description=description
            ))

        logger.info(f"Successfully created {len(langchain_tools)} LangChain tools")
        return langchain_tools

    except Exception as e:
        logger.error(f"Failed to discover MCP tools: {e}")
        # Return empty list if discovery fails - agent will still work without tools
        return []
