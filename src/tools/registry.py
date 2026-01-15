"""
Tool Registry

This module provides the ToolRegistry class that loads tools from the
tool registry JSON file and provides a unified interface for tool resolution
and execution.

All tools are exposed as async callables that take a payload dict and return
a result dict.
"""

from typing import Any, Callable, Dict, Optional
import asyncio


class ToolRegistry:
    """Tool registry that loads tools from tools/registry/tool_registry.json"""

    def __init__(self):
        from src.tool_registry.manager import ToolRegistryManager

        self._registry_manager = ToolRegistryManager()
        self._resolved_cache: Dict[str, Callable] = {}
        self._name_to_id: Dict[str, str] = {}
        self._build_name_mapping()

    def _build_name_mapping(self):
        """Build a mapping from tool names to tool IDs."""
        all_tools = self._registry_manager.list_tools()
        for tool in all_tools:
            tool_name = tool.get("name")
            tool_id = tool.get("id")
            if tool_name and tool_id:
                self._name_to_id[tool_name] = tool_id

    def _resolve_tool_identifier(self, identifier: str) -> Optional[str]:
        """
        Resolve tool identifier to tool_id.

        Args:
            identifier: Either tool_id (e.g., "tool_abc123") or tool_name (e.g., "email_validator")

        Returns:
            tool_id if found, None otherwise
        """
        # Check if it's a tool_id pattern (starts with 'tool_')
        if identifier.startswith('tool_'):
            tool_data = self._registry_manager.get_tool(identifier)
            if tool_data:
                return identifier

        # Check if it's a tool name
        if identifier in self._name_to_id:
            return self._name_to_id[identifier]

        return None

    def has(self, identifier: str) -> bool:
        """Check if tool exists (by name or ID)."""
        return self._resolve_tool_identifier(identifier) is not None

    def get(self, identifier: str) -> Callable:
        """
        Get tool by name or ID, returning an async callable.

        Args:
            identifier: Either tool_id or tool_name

        Returns:
            Async callable that takes payload dict and returns result dict

        Raises:
            KeyError: If tool not found
        """
        tool_id = self._resolve_tool_identifier(identifier)

        if tool_id is None:
            raise KeyError(f"Unknown tool: {identifier}")

        # Check cache
        if tool_id in self._resolved_cache:
            return self._resolved_cache[tool_id]

        # Load from registry
        tool_data = self._registry_manager.get_tool(tool_id)
        if not tool_data:
            raise KeyError(f"Tool data not found for: {identifier}")

        # Create async wrapper based on tool type
        tool_type = tool_data.get("type")

        if tool_type == "prebuilt":
            async_tool = self._wrap_prebuilt_tool(tool_data)
        elif tool_type == "custom_function":
            async_tool = self._wrap_custom_function(tool_data)
        elif tool_type == "custom_api":
            async_tool = self._wrap_custom_api(tool_data)
        else:
            raise ValueError(f"Unsupported tool type: {tool_type}")

        # Cache and return
        self._resolved_cache[tool_id] = async_tool
        return async_tool

    def reload_registry(self):
        """Reload the tool registry (useful after tools are added/modified)."""
        from src.tool_registry.manager import ToolRegistryManager

        self._registry_manager = ToolRegistryManager()
        self._resolved_cache.clear()
        self._name_to_id.clear()
        self._build_name_mapping()

    def _wrap_prebuilt_tool(self, tool_data: Dict[str, Any]) -> Callable:
        """Wrap LangChain StructuredTool to async callable."""
        from src.tool_registry.prebuilt_tools import get_tool_by_id

        tool_id = tool_data["id"]
        structured_tool = get_tool_by_id(tool_id)

        async def async_wrapper(payload: Dict[str, Any]) -> Dict[str, Any]:
            input_schema = tool_data.get("input_schema", {})
            properties = input_schema.get("properties", {})

            # Build kwargs from payload based on tool's input schema
            kwargs = {k: payload.get(k) for k in properties.keys() if k in payload}

            # Run LangChain tool in executor (it's synchronous)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, structured_tool.invoke, kwargs)

            # Wrap result in dict if it's not already
            return result if isinstance(result, dict) else {"result": result}

        return async_wrapper

    def _wrap_custom_function(self, tool_data: Dict[str, Any]) -> Callable:
        """Wrap custom function to async callable."""
        function_name = tool_data.get("function")

        if not function_name:
            raise ValueError(f"Custom function tool missing 'function' field: {tool_data['id']}")

        from src.tool_registry.custom_functions import CUSTOM_FUNCTIONS

        if function_name not in CUSTOM_FUNCTIONS:
            raise KeyError(f"Custom function not found: {function_name}")

        func = CUSTOM_FUNCTIONS[function_name]

        # Return as-is if already async
        if asyncio.iscoroutinefunction(func):
            return func

        # Wrap synchronous function
        async def async_wrapper(payload: Dict[str, Any]) -> Dict[str, Any]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, payload)

        return async_wrapper

    def _wrap_custom_api(self, tool_data: Dict[str, Any]) -> Callable:
        """Wrap API tool to async callable with aiohttp."""
        import aiohttp

        api_url = tool_data.get("api_url")
        api_request_type = tool_data.get("api_request_type", "GET")
        custom_message = tool_data.get("custom_message", "")
        input_schema = tool_data.get("input_schema", {})
        properties = input_schema.get("properties", {})

        async def async_wrapper(payload: Dict[str, Any]) -> Dict[str, Any]:
            # Extract parameters from payload based on input schema
            params = {k: payload.get(k) for k in properties.keys() if k in payload}

            try:
                async with aiohttp.ClientSession() as session:
                    if api_request_type.upper() == "GET":
                        async with session.get(api_url, params=params, timeout=360) as resp:
                            data = await resp.json() if resp.content_type == 'application/json' else {}
                            return {
                                "status_code": resp.status,
                                "data": data,
                                "custom_message": custom_message
                            }
                    else:  # POST
                        async with session.post(api_url, json=params, timeout=360) as resp:
                            data = await resp.json() if resp.content_type == 'application/json' else {}
                            return {
                                "status_code": resp.status,
                                "data": data,
                                "custom_message": custom_message
                            }
            except Exception as e:
                return {
                    "status_code": 500,
                    "data": {"error": str(e)},
                    "custom_message": custom_message
                }

        return async_wrapper
