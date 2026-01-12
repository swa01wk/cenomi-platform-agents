from fastapi import APIRouter, HTTPException
from typing import List

from src.tool_registry.manager import ToolRegistryManager
from src.tool_registry.schemas import (
    PrebuiltTool,
    CustomFuntionTool,
    CustomAPITool,
)

router = APIRouter(prefix="/v1", tags=["Tool Registry PoC"])
tool_manager = ToolRegistryManager()

@router.post("/custom-function", response_model=CustomFuntionTool)
def create_custom_function_tool(tool: CustomFuntionTool):
    try:
        return tool_manager.add_tool(tool.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/custom-function", response_model=List[CustomFuntionTool])
def list_custom_function_tools():
    return tool_manager.list_tools_by_type("custom_function")

@router.post("/custom-api", response_model=CustomAPITool)
def create_custom_api_tool(tool: CustomAPITool):
    try:
        return tool_manager.add_tool(tool.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/custom-api", response_model=List[CustomAPITool])
def list_custom_api_tools():
    return tool_manager.list_tools_by_type("custom_api")

@router.get("/", response_model=List[object])
def list_all_tools():
    return tool_manager.list_tools()

@router.get("/{tool_id}")
def get_tool(tool_id: str):
    tool = tool_manager.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool

@router.put("/{tool_id}")
def modify_tool(tool_id: str, updates: dict):
    updated_tool = tool_manager.modify_tool(tool_id, updates)

    if not updated_tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    return updated_tool

@router.delete("/{tool_id}")
def delete_tool(tool_id: str):
    """
    Delete a tool by ID.
    """
    deleted = tool_manager.delete_tool(tool_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Tool not found")

    return {
        "status": "deleted",
        "tool_id": tool_id
    }
