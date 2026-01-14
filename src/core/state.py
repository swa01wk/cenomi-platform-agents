from typing import Any, Dict, List, Optional, TypedDict, Literal

Phase = Literal["supervisor", "collecting", "confirm", "done"]

class AppState(TypedDict, total=False):
    session_id: str
    messages: List[Dict[str, str]]

    phase: Phase
    active_agent_id: Optional[str]
    needs_service_choice: bool

    drafts: Dict[str, Dict[str, Any]]          # draft per agent_id
    stage_by_agent: Dict[str, str]             # current stage per agent_id (multi-stage)
    locked_fields: Dict[str, List[str]]        # fields manually edited by user per agent_id

    ready_payload: Optional[Dict[str, Any]]
    assistant_message: str
    submitted: Optional[Dict[str, Any]]

    # for passing attachments per turn
    turn_attachments: List[str]

    # debug/observability
    last_tool_events: List[Dict[str, Any]]
