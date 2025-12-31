from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator

FieldType = Literal["string", "number", "boolean", "datetime", "array"]

class FieldSpec(BaseModel):
    key: str
    type: FieldType = "string"
    required: bool = True
    label: str
    hint: Optional[str] = None

    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    choices: Optional[List[str]] = None

class StageSpec(BaseModel):
    stage_id: str
    label: str
    required_fields: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    optional_tools: List[str] = Field(default_factory=list)

class AgentCreate(BaseModel):
    agent_id: str
    name: str
    description: str
    service_type: str
    keywords: List[str] = Field(default_factory=list)

    model: str = "gpt-4o-mini"
    system_prompt: Optional[str] = None

    fields: List[FieldSpec] = Field(default_factory=list)
    stages: List[StageSpec] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        if not v or " " in v:
            raise ValueError("agent_id must be non-empty and contain no spaces")
        return v

    @field_validator("fields")
    @classmethod
    def ensure_unique_keys(cls, fields: List[FieldSpec]) -> List[FieldSpec]:
        keys = [f.key for f in fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate field keys are not allowed")
        return fields

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    service_type: Optional[str] = None
    keywords: Optional[List[str]] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    fields: Optional[List[FieldSpec]] = None
    stages: Optional[List[StageSpec]] = None
    tools: Optional[List[str]] = None
