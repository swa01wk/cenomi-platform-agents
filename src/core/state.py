from typing import Any, Dict, List, Optional, TypedDict, Literal

Phase = Literal["supervisor", "collecting", "confirm", "done"]

class AppState(TypedDict, total=False):
    session_id: str
    messages: List[Dict[str, str]]

    phase: Phase
    active_agent_id: Optional[str]
    needs_service_choice: bool

    drafts: Dict[str, Dict[str, Any]]          # draft per agent_id
    stage_by_agent: Dict[str, str]             # stage per agent_id (multi-stage)

    ready_payload: Optional[Dict[str, Any]]
    assistant_message: str
    submitted: Optional[Dict[str, Any]]

    # ✅ used for better greeting when switching agents or explicitly setting agent
    just_switched_agent: bool

    # ✅ optional: indicates user explicitly selected agent (vs supervisor routing)
    explicit_agent_selected: bool
    skip_subagent_once: bool

    # per-turn attachments
    turn_attachments: List[str]

    # debug / observability
    last_tool_events: List[Dict[str, Any]]

    # optional: prevent some fields from being edited once confirmed
    locked_fields: Dict[str, List[str]]
