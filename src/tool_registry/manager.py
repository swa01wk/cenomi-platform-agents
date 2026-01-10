from typing import Dict, List, Any, Optional
import uuid

try:
    from src.tool_registry.store import ToolRegistryStore
    from src.tool_registry.schemas import (
        ToolBase,
        PrebuiltTool,
        CustomAPITool,
        CustomFuntionTool
    )
except ModuleNotFoundError:
    from store import ToolRegistryStore
    from schemas import (
        ToolBase,
        PrebuiltTool,
        CustomAPITool,
        CustomFuntionTool
    )

class ToolRegistryManager:
    def __init__(self, store: ToolRegistryStore = ToolRegistryStore()):
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

    def list_tools_by_type(self, tool_type: str) -> List[Dict[str, Any]]:
        """
        List tools filtered by type.
        
        Args:
            tool_type: Type of tools to filter by ('prebuilt', 'custom_function', 'custom_api')
        
        Returns:
            List of tools matching the specified type
        """
        return [
            tool for tool in self._tools.values()
            if tool.get("type", "").lower() == tool_type.lower()
        ]

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

    # Add different types of tools
    # prebuilt_tool = {
    #     "type": "prebuilt",
    #     "name": "Prebuilt Tool",
    #     "description": "A prebuilt tool.",
    #     "input_schema": {"type": "object", "properties": {}},
    #     "output_schema": {"type": "object", "properties": {}}
    # }
    
    # custom_api_tool = {
    #     "type": "custom_api",
    #     "name": "Custom API Tool",
    #     "description": "A custom API tool.",
    #     "input_schema": {"type": "object", "properties": {}},
    #     "output_schema": {"type": "object", "properties": {}},
    #     "api_url": "https://api.example.com/data",
    #     "api_request_type": "GET"
    # }
    
    # custom_function_tool = {
    #     "type": "custom_function",
    #     "name": "Custom Function Tool",
    #     "description": "A custom function tool.",
    #     "input_schema": {"type": "object", "properties": {}},
    #     "output_schema": {"type": "object", "properties": {}},
    #     "function": "my_custom_function"
    # }
    
    # manager.add_tool(prebuilt_tool)
    # manager.add_tool(custom_api_tool)
    # manager.add_tool(custom_function_tool)

    # Test list_tools_by_type
    # print("All tools:", len(manager.list_tools()))
    # print("Prebuilt tools:", len(manager.list_tools_by_type("prebuilt")))
    # print("Custom API tools:", len(manager.list_tools_by_type("custom_api")))
    # print("Custom Function tools:", len(manager.list_tools_by_type("custom_function")))
    
    # print("Prebuilt tools:", manager.list_tools_by_type("prebuilt"))