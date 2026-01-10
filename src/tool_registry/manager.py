from typing import Dict, List, Any, Optional
import uuid

from store import ToolRegistryStore
from schemas import (
    ToolBase,
    PrebuiltTool,
    CustomAPITool,
    CustomFuntionTool
)

class ToolRegistryManager:
    def __init__(self, store: ToolRegistryStore):
        self.store = store
        self._registry = self.store.load()
        self._tools: Dict[str, Dict[str, Any]] = {
            tool["id"]: tool for tool in self._registry.get("tools", [])
        }
        
    def _persist(self) -> None:
        self.store.save({"tools": list(self._tools.values())})

    def _validate_tool(self, tool_data: Dict[str, Any]) -> ToolBase:
        tool_type = tool_data.get("type")
        if tool_type.lower() == "prebuilt":
            return PrebuiltTool(**tool_data)
        if tool_type.lower() == "custom_function":
            return CustomFuntionTool(**tool_data)
        if tool_type.lower() == "custom_api":
            return CustomAPITool(**tool_data)
        raise ValueError(f"Unsupported tool type: {tool_type}")
    
    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self._tools.values())

    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(tool_id)

    def add_tool(self, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = tool_data.get("name")
        if not tool_name:
            raise ValueError("Tool name is required")
        for existing_tool in self._tools.values():
            if existing_tool.get("name") == tool_name:
                raise ValueError(f"Tool with name '{tool_name}' already exists")
        tool_id = f"agent_{uuid.uuid4()}"
        tool_data["id"] = tool_id
        validated_tool = self._validate_tool(tool_data)
        self._tools[tool_id] = validated_tool.model_dump()
        self._persist()
        return self._tools[tool_id]

    def delete_tool(self, tool_id: str) -> bool:
        if tool_id not in self._tools:
            return False
        del self._tools[tool_id]
        self._persist()
        return True

if __name__ == "__main__":
    store = ToolRegistryStore()
    manager = ToolRegistryManager(store)

    # Add a prebuilt tool
    prebuilt_tool = {
        "type": "custom_api",
        "name": "Example Prebuilt Tool",
        "description": "A sample prebuilt tool for testing.",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "api_url": "https://api.example.com/data",
        "api_request_type": "GET"
    }
    manager.add_tool(prebuilt_tool)

    # List tools
    print(manager.list_tools())

    # Get a specific tool
    print(manager.get_tool("tool_1"))

    # Delete a tool
    manager.delete_tool("tool_1")
    print(manager.list_tools())