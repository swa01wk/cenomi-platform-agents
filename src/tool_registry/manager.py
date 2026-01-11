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
    
    def modify_tool(self, tool_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing_tool = self._tools.get(tool_id)
        if not existing_tool:
            return None

        # Protected fields
        protected_fields = {"id", "type", "metadata"}

        # Apply allowed updates
        for key, value in updates.items():
            if key not in protected_fields:
                existing_tool[key] = value

        # Re-validate the updated tool
        validated_tool = self._validate_tool(existing_tool)

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

    # --- CREATE TOOLS ---
    prebuilt = manager.add_tool({
    "type": "prebuilt",
    "name": "web_search",
    "description": "Search tool",
    "input_schema": {
        "properties": {}
        }
    })

    custom_function = manager.add_tool({
        "type": "custom_function",
        "name": "discount_calc",
        "description": "Discount calculator",
        "input_schema": {
            "properties": {
                "original_price": {
                    "type": "number",
                    "description": "Original price of the item"
                },
                "discount_percentage": {
                    "type": "number",
                    "description": "Discount percentage to apply"
                }
            }
        },
        "function": "calc_discount"
    })

    custom_api = manager.add_tool({
        "type": "custom_api",
        "name": "order_fetch",
        "description": "Fetch orders",
        "input_schema": {
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "ID of the order to fetch"
                },
                "user_id": {
                    "type": "string",
                    "description": "ID of the user"
                }
            }
        },
        "api_url": "https://api.example.com/orders",
        "api_request_type": "GET"
    })

    # # --- MODIFY TOOLS ---

    # manager.modify_tool(
    #     prebuilt["id"],
    #     {"description": "Updated prebuilt search tool"}
    # )

    # manager.modify_tool(
    #     custom_function["id"],
    #     {
    #         "description": "Updated discount calculator",
    #         "function": "updated_discount_fn"
    #     }
    # )

    # manager.modify_tool(
    #     custom_api["id"],
    #     {
    #         "description": "Updated order fetcher",
    #         "custom_message": "Extract order_id and price"
    #     }
    # )


    # # --- VERIFY ---

    # assert manager.get_tool(prebuilt["id"])["description"] == "Updated prebuilt search tool"
    # assert manager.get_tool(custom_function["id"])["function"] == "updated_discount_fn"
    # assert manager.get_tool(custom_api["id"])["custom_message"] == "Extract order_id and price"

    # print("✅ MODIFY TOOL TEST PASSED FOR ALL TOOL TYPES")

    # Test list_tools_by_type
    # print("All tools:", len(manager.list_tools()))
    # print("Prebuilt tools:", len(manager.list_tools_by_type("prebuilt")))
    # print("Custom API tools:", len(manager.list_tools_by_type("custom_api")))
    # print("Custom Function tools:", len(manager.list_tools_by_type("custom_function")))
    
    # print("Prebuilt tools:", manager.list_tools_by_type("prebuilt"))