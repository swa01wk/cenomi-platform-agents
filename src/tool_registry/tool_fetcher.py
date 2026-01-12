from typing import Dict, Any, List
import requests
from langchain_core.tools import StructuredTool
from pydantic import create_model
from prebuilt_tools import get_tool_by_id
from manager import ToolRegistryManager


def _prebuilt_placeholder(tool_data):
    return get_tool_by_id(tool_data.get("id"))


def _custom_function_placeholder(tool_data):
    def _run(*args, **kwargs):
        return {"message": "Custom function placeholder", "tool": tool_data.get("name")}
    return _run


def _custom_api_placeholder(tool_def: Dict[str, Any]) -> List:
    name = tool_def["name"]
    description = tool_def["description"]
    api_url = tool_def["api_url"]
    api_request_type = tool_def["api_request_type"]
    custom_message = tool_def.get("custom_message", "")
    input_schema = tool_def["input_schema"]
    
    fields = {}
    properties = input_schema.get("properties", {})
    
    for field_name, field_spec in properties.items():
        field_type_map = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool
        }
        field_type = field_type_map.get(field_spec.get("type"), str)
        fields[field_name] = (field_type, None)
    
    if not fields:
        fields = {"_placeholder": (str, None)}
    
    InputModel = create_model(f"{name}_Input", **fields)
    
    def execute_api_call(**kwargs) -> Dict[str, Any]:
        try:
            kwargs.pop("_placeholder", None)
            
            if api_request_type.upper() == "GET":
                resp = requests.get(api_url, params=kwargs, timeout=10)
            else:
                resp = requests.post(api_url, json=kwargs, timeout=10)
            
            return {
                "status_code": resp.status_code,
                "data": resp.json() if resp.content else {},
                "custom_message": custom_message
            }
        except Exception as e:
            return {
                "status_code": 500,
                "data": {"error": str(e)},
                "custom_message": custom_message
            }
    
    tool = StructuredTool.from_function(
        func=execute_api_call,
        name=name,
        description=description,
        args_schema=InputModel
    )
    
    return [tool]


def build_langchain_tools(tool_ids: List[str]) -> List[StructuredTool]:
    manager = ToolRegistryManager()
    langchain_tools: List[StructuredTool] = []

    for tool_id in tool_ids:
        tool_data = manager.get_tool(tool_id)
        if not tool_data:
            print("tool is missing")
            continue

        tool_type = tool_data.get("type")
        name = tool_data.get("name")
        description = tool_data.get("description")

        if tool_type == "prebuilt":
            tool = _prebuilt_placeholder(tool_data)
            langchain_tools.append(tool)

        elif tool_type == "custom_function":
            func = _custom_function_placeholder(tool_data)
            tool = StructuredTool.from_function(
                func=func,
                name=name,
                description=description
            )
            langchain_tools.append(tool)

        elif tool_type == "custom_api":
            tools = _custom_api_placeholder(tool_data)
            langchain_tools.extend(tools)

    return langchain_tools

if __name__ == "__main__":
    tool_ids = [
    "tool_517087cd-4f45-4dfb-835d-ec908086baa4",
    "tool_9b2d94e3-1c6e-4f59-91a1-61e1cc0a6db1",
    "tool_c78a0e62-b6c1-49cf-9e5b-33f2cde54a77",
    "tool_2aee9e7a-7d67-4f13-9f91-bd7bb91e84fd",
    "tool_fe925649-e6ec-4002-8d7f-7374d07ffa7d",
    "tool_54da582b-e8e6-4f98-ab19-bfaf0a5965b6"
]
    tools = build_langchain_tools(tool_ids)
    for tool in tools:
        print(f"Loaded tool: {tool.name} - {tool.description}")
