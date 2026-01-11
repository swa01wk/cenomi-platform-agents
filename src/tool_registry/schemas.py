from typing import Dict, Any, Literal, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, computed_field

class Metadata(BaseModel):
    created_at: str

class ToolBase(BaseModel):
    id: str = Field(..., description="Unique tool identifier")
    type: Literal["prebuilt", "custom_function", "custom_api"] = Field(
        ..., description="Type of the tool"
    )
    name: str = Field(..., description="Tool name exposed to the LLM")
    description: str = Field(..., description="Used by LLM for tool selection")
    input_schema: Dict[str, Any] = Field(
        description="JSON Schema defining tool input"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object"}
    )

    @computed_field
    @property
    def metadata(self) -> Metadata:
        return Metadata(
            created_at=datetime.now(timezone.utc).isoformat()
        )

class PrebuiltTool(ToolBase):
    type: Literal["prebuilt"]

class CustomFuntionTool(ToolBase):
    type: Literal["custom_function"]
    function: Optional[str]

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