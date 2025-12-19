"""
Result formatter for MCP tool outputs.

Provides intelligent formatting of tool results to make them more readable
and useful for the LLM agent.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List


class ToolResultFormatter:
    """Formats MCP tool results for better LLM comprehension."""

    @staticmethod
    def format(tool_name: str, result: Any) -> str:
        """
        Format a tool result based on the tool type and result structure.

        Args:
            tool_name: Name of the tool that produced this result
            result: Raw result from the MCP tool

        Returns:
            Formatted string suitable for LLM consumption
        """
        # Handle error responses
        if isinstance(result, dict) and "error" in result:
            return f"❌ Error: {result['error']}"

        # Route to specific formatters based on tool name
        if tool_name == "search_dashboards":
            return ToolResultFormatter._format_dashboard_search(result)
        if "prometheus" in tool_name.lower():
            return ToolResultFormatter._format_prometheus(result)
        elif "loki" in tool_name.lower():
            return ToolResultFormatter._format_loki(result)
        elif "dashboard" in tool_name.lower():
            return ToolResultFormatter._format_dashboard(result)
        elif "alert" in tool_name.lower():
            return ToolResultFormatter._format_alert(result)
        elif "datasource" in tool_name.lower():
            return ToolResultFormatter._format_datasource(result)
        elif "search" in tool_name.lower():
            return ToolResultFormatter._format_search(result)
        else:
            return ToolResultFormatter._format_generic(result)

    @staticmethod
    def _format_prometheus(result: Any) -> str:
        """Format Prometheus query results."""
        if not isinstance(result, (dict, list)):
            return str(result)

        # Handle list of content items from MCP (TextContent objects or dicts)
        if isinstance(result, list):
            formatted_parts = []
            for item in result:
                if hasattr(item, 'text'):
                    formatted_parts.append(item.text)
                elif isinstance(item, dict) and "text" in item:
                    formatted_parts.append(item["text"])
                else:
                    formatted_parts.append(str(item))
            return "\n".join(formatted_parts)

        # Handle dict results
        if "data" in result:
            data = result["data"]
            result_type = data.get("resultType", "unknown")

            if result_type == "matrix":
                return ToolResultFormatter._format_prometheus_matrix(data.get("result", []))
            elif result_type == "vector":
                return ToolResultFormatter._format_prometheus_vector(data.get("result", []))
            elif result_type == "scalar":
                return f"Scalar value: {data.get('result', 'N/A')}"

        return json.dumps(result, indent=2)

    @staticmethod
    def _format_prometheus_matrix(results: List[Dict]) -> str:
        """Format range query results."""
        if not results:
            return "No data found"

        output = []
        for idx, series in enumerate(results[:5], 1):  # Limit to 5 series
            metric = series.get("metric", {})
            values = series.get("values", [])

            metric_str = json.dumps(metric)
            output.append(f"\n📊 Series {idx}: {metric_str}")
            output.append(f"   Data points: {len(values)}")

            if values:
                # Show first and last values
                first_val = values[0]
                last_val = values[-1]
                output.append(f"   First: [{first_val[0]}] = {first_val[1]}")
                output.append(f"   Last:  [{last_val[0]}] = {last_val[1]}")

        if len(results) > 5:
            output.append(f"\n... and {len(results) - 5} more series")

        return "\n".join(output)

    @staticmethod
    def _format_prometheus_vector(results: List[Dict]) -> str:
        """Format instant query results."""
        if not results:
            return "No data found"

        output = ["📈 Instant Query Results:\n"]
        for series in results[:10]:  # Limit to 10 series
            metric = series.get("metric", {})
            value = series.get("value", [])

            metric_str = ", ".join(f"{k}={v}" for k, v in metric.items())
            if value and len(value) >= 2:
                output.append(f"  • {metric_str}: {value[1]}")

        if len(results) > 10:
            output.append(f"\n... and {len(results) - 10} more results")

        return "\n".join(output)

    @staticmethod
    def _format_loki(result: Any) -> str:
        """Format Loki log query results."""
        if not isinstance(result, (dict, list)):
            return str(result)

        # Handle list of content items from MCP (TextContent objects or dicts)
        if isinstance(result, list):
            formatted_parts = []
            for item in result:
                if hasattr(item, 'text'):
                    formatted_parts.append(item.text)
                elif isinstance(item, dict) and "text" in item:
                    formatted_parts.append(item["text"])
                else:
                    formatted_parts.append(str(item))
            return "\n".join(formatted_parts)

        # Handle dict results
        if "data" in result:
            data = result["data"]
            result_type = data.get("resultType", "unknown")
            results = data.get("result", [])

            if result_type == "streams":
                return ToolResultFormatter._format_loki_streams(results)
            elif result_type == "matrix" or result_type == "vector":
                return f"Loki metric query returned {len(results)} series"

        return json.dumps(result, indent=2)

    @staticmethod
    def _format_loki_streams(results: List[Dict]) -> str:
        """Format Loki log streams."""
        if not results:
            return "No logs found"

        output = ["📋 Log Entries:\n"]
        total_entries = 0

        for stream in results[:5]:  # Limit to 5 streams
            labels = stream.get("stream", {})
            values = stream.get("values", [])
            total_entries += len(values)

            label_str = ", ".join(f"{k}={v}" for k, v in labels.items())
            output.append(f"\nStream: {{{label_str}}}")

            # Show a few log lines
            for ts, line in values[:3]:
                # Truncate long lines
                display_line = line[:100] + "..." if len(line) > 100 else line
                output.append(f"  [{ts}] {display_line}")

            if len(values) > 3:
                output.append(f"  ... and {len(values) - 3} more log lines")

        output.append(f"\nTotal log entries: {total_entries}")

        if len(results) > 5:
            output.append(f"... and {len(results) - 5} more streams")

        return "\n".join(output)

    @staticmethod
    def _format_dashboard(result: Any) -> str:
        """Format dashboard results."""
        if not isinstance(result, (dict, list)):
            return str(result)

        # Handle list of content items from MCP (TextContent objects or dicts)
        if isinstance(result, list):
            formatted_parts = []
            for item in result:
                if hasattr(item, 'text'):
                    formatted_parts.append(item.text)
                elif isinstance(item, dict) and "text" in item:
                    formatted_parts.append(item["text"])
                else:
                    formatted_parts.append(str(item))
            return "\n".join(formatted_parts)

        # For dashboard dict, extract key info
        output = []
        if "dashboard" in result:
            dash = result["dashboard"]
            output.append(f"📊 Dashboard: {dash.get('title', 'Untitled')}")
            output.append(f"   UID: {dash.get('uid', 'N/A')}")
            output.append(f"   Panels: {len(dash.get('panels', []))}")

            if "tags" in dash:
                output.append(f"   Tags: {', '.join(dash['tags'])}")

        return "\n".join(output) if output else json.dumps(result, indent=2)

    @staticmethod
    def _format_dashboard_search(result: Any) -> str:
        """Format search_dashboards result into a concise list."""
        items: List[Dict[str, Any]] = []

        # Handle MCP TextContent objects
        if isinstance(result, list) and result and hasattr(result[0], 'text'):
            # Parse JSON from TextContent
            import json
            try:
                text = result[0].text
                parsed = json.loads(text) if isinstance(text, str) else text
                if isinstance(parsed, dict):
                    result = parsed
            except:
                pass

        if isinstance(result, list):
            items = result
        elif isinstance(result, dict):
            if "items" in result and isinstance(result["items"], list):
                items = result["items"]
            elif "dashboards" in result and isinstance(result["dashboards"], list):
                items = result["dashboards"]

        if not items:
            return "No dashboards found."

        lines = []
        for item in items[:25]:  # cap output
            if not isinstance(item, dict):
                continue
            title = item.get("title", "(untitled)")
            dtype = item.get("type", "dash")
            uid = item.get("uid", "")
            url = item.get("url") or item.get("uri") or ""
            folder = item.get("folderTitle") or item.get("folder") or ""
            parts = [title]
            if folder:
                parts.append(f"folder: {folder}")
            if uid:
                parts.append(f"uid: {uid}")
            if url:
                parts.append(f"url: {url}")
            lines.append(f"• {', '.join(parts)} [{dtype}]")

        if len(items) > 25:
            lines.append(f"... and {len(items) - 25} more")

        return "\n".join(lines)

    @staticmethod
    def _format_alert(result: Any) -> str:
        """Format alert results."""
        if not isinstance(result, (dict, list)):
            return str(result)

        # Handle list of content items from MCP (TextContent objects or dicts)
        if isinstance(result, list):
            # Check if it's a list of MCP content items (TextContent objects)
            if result and hasattr(result[0], 'text'):
                formatted_parts = []
                for item in result:
                    formatted_parts.append(item.text)
                return "\n".join(formatted_parts)
            # Check if it's a list of MCP content items (dicts)
            elif result and isinstance(result[0], dict) and "text" in result[0]:
                formatted_parts = []
                for item in result:
                    formatted_parts.append(item["text"])
                return "\n".join(formatted_parts)
            else:
                # List of alerts
                output = [f"🔔 Found {len(result)} alert(s):\n"]
                for alert in result[:10]:
                    if isinstance(alert, dict):
                        name = alert.get("name", alert.get("title", "Unknown"))
                        state = alert.get("state", "unknown")
                        output.append(f"  • {name}: {state}")

                if len(result) > 10:
                    output.append(f"\n... and {len(result) - 10} more alerts")

                return "\n".join(output)

        return json.dumps(result, indent=2)

    @staticmethod
    def _format_datasource(result: Any) -> str:
        """Format datasource results."""
        if not isinstance(result, (dict, list)):
            return str(result)

        # Handle list of content items from MCP (TextContent objects or dicts)
        if isinstance(result, list):
            # Check if it's MCP TextContent objects
            if result and hasattr(result[0], 'text'):
                formatted_parts = []
                for item in result:
                    formatted_parts.append(item.text)
                return "\n".join(formatted_parts)
            elif result and isinstance(result[0], dict) and "text" in result[0]:
                formatted_parts = []
                for item in result:
                    formatted_parts.append(item["text"])
                return "\n".join(formatted_parts)
            else:
                # List of datasources
                output = [f"💾 Found {len(result)} datasource(s):\n"]
                for ds in result:
                    if isinstance(ds, dict):
                        name = ds.get("name", "Unknown")
                        ds_type = ds.get("type", "unknown")
                        uid = ds.get("uid", "N/A")
                        output.append(f"  • {name} ({ds_type}) - UID: {uid}")

                return "\n".join(output)

        return json.dumps(result, indent=2)

    @staticmethod
    def _format_search(result: Any) -> str:
        """Format search results."""
        if not isinstance(result, (dict, list)):
            return str(result)

        # Handle list of content items from MCP (TextContent objects or dicts)
        if isinstance(result, list):
            if result and hasattr(result[0], 'text'):
                formatted_parts = []
                for item in result:
                    formatted_parts.append(item.text)
                return "\n".join(formatted_parts)
            elif result and isinstance(result[0], dict) and "text" in result[0]:
                formatted_parts = []
                for item in result:
                    formatted_parts.append(item["text"])
                return "\n".join(formatted_parts)
            else:
                # List of search results
                output = [f"🔍 Found {len(result)} result(s):\n"]
                for item in result[:10]:
                    if isinstance(item, dict):
                        title = item.get("title", "Untitled")
                        uid = item.get("uid", "N/A")
                        item_type = item.get("type", "unknown")
                        output.append(f"  • {title} ({item_type}) - UID: {uid}")

                if len(result) > 10:
                    output.append(f"\n... and {len(result) - 10} more results")

                return "\n".join(output)

        return json.dumps(result, indent=2)

    @staticmethod
    def _format_generic(result: Any) -> str:
        """Generic formatter for unknown result types."""
        if result is None:
            return "No result"

        # Handle list of content items from MCP (TextContent objects or dicts)
        if isinstance(result, list):
            if result and hasattr(result[0], 'text'):
                formatted_parts = []
                for item in result:
                    if hasattr(item, 'text'):
                        formatted_parts.append(item.text)
                    else:
                        formatted_parts.append(str(item))
                return "\n".join(formatted_parts)
            elif result and isinstance(result[0], dict) and "text" in result[0]:
                formatted_parts = []
                for item in result:
                    if isinstance(item, dict) and "text" in item:
                        formatted_parts.append(item["text"])
                    else:
                        formatted_parts.append(str(item))
                return "\n".join(formatted_parts)

        # Handle simple types
        if isinstance(result, (str, int, float, bool)):
            return str(result)

        # Handle complex types - format as JSON
        if isinstance(result, (dict, list)):
            json_str = json.dumps(result, indent=2)
            # Truncate if too long
            if len(json_str) > 2000:
                return json_str[:2000] + "\n\n... (truncated, result too large)"
            return json_str

        return str(result)
