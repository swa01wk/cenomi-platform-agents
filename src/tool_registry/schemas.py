from typing import Dict, Any, Literal, Optional
from pydantic import BaseModel, Field

class Metadata(BaseModel):
    created_by: Literal["system", "user"]
    created_at: str


class ToolBase(BaseModel):
    id: str = Field(..., description="Unique tool identifier")
    type: Literal["prebuilt", "custom_api"]
    name: str = Field(..., description="Tool name exposed to the LLM")
    description: str = Field(..., description="Used by LLM for tool selection")

    input_schema: Dict[str, Any] = Field(
        ..., description="JSON Schema defining tool input"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object"}
    )
    metadata: Metadata


class PrebuiltTool(ToolBase):
    type: Literal["prebuilt"]


class CustomAPITool(ToolBase):
    type: Literal["custom_api"]
    custom_message: Optional[str] = Field(
            None,
            description="Guides LLM to extract specific fields from API response"
        )
    api_url: str = Field(..., description="Target API endpoint")
    api_request_type: Literal["GET", "POST"] = Field(
        ..., description="HTTP method"
    )
