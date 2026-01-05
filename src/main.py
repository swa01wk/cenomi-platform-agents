import uuid
from typing import Dict, Optional, List, Literal, Any
from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from src.admin.routes import router as admin_router
from src.core.state import AppState
from src.supervisor.graph import build_supervisor_graph
from src.registry.store import AgentRegistryStore
from src.tools.registry import ToolRegistry
from src.utils.message_format import parse_assistant_message
from src.utils.welcome import agent_welcome_llm_from_file, REGISTRY

load_dotenv()

app = FastAPI(title="Agent Platform PoC (LangGraph Pattern A)")
app.include_router(admin_router)

SESSIONS: Dict[str, AppState] = {}

registry_store = AgentRegistryStore()
toolreg = ToolRegistry()

# Supervisor graph is compiled once, but it reloads registry per turn.
GRAPH = build_supervisor_graph(registry_store, toolreg)

class SessionCreateRequest(BaseModel):
    active_agent_id: Optional[str] = Field(
        default=None,
        description="If provided, the conversation starts directly with this agent (skips intent routing).",
        examples=["lead_enquiry_agent", "general_enquiry_agent"],
    )

    mode: Optional[Literal["auto", "explicit"]] = Field(
        default="auto",
        description="auto = supervisor routes by intent. explicit = use active_agent_id (must be provided).",
    )

def default_state(session_id: str) -> AppState:
    return {
        "session_id": session_id,
        "messages": [],
        "phase": "supervisor",
        "active_agent_id": None,
        "needs_service_choice": True,
        "drafts": {},
        "stage_by_agent": {},
        "ready_payload": None,
        "assistant_message": "Hi! What type of service request is this?",
        "submitted": None,
        "last_tool_events": []
    }

@app.post("/v1/session")
def create_session(payload: SessionCreateRequest = Body(default=SessionCreateRequest())):
    sid = uuid.uuid4().hex
    state = default_state(sid)

    active_agent_id = payload.active_agent_id
    mode = payload.mode or "auto"

    if mode == "explicit" and not active_agent_id:
        raise HTTPException(status_code=400, detail="mode='explicit' requires active_agent_id")

    # ✅ Explicit agent selection: return welcome message directly (do NOT invoke graph yet)
    if active_agent_id:
        welcome_msg = agent_welcome_llm_from_file(REGISTRY, active_agent_id)

        state["active_agent_id"] = active_agent_id
        state["phase"] = "collecting"
        state["ready_payload"] = None
        state["submitted"] = None
        state["just_switched_agent"] = True
        state["assistant_message"] = welcome_msg

        SESSIONS[sid] = state

        formatted = parse_assistant_message(welcome_msg or "")
        return {
            "session_id": sid,
            "message": welcome_msg,            # ✅ plain string for UI
            "assistant_message": welcome_msg,  # ✅ plain string for backward compat
            "message_ui": formatted,           # ✅ structured blocks
            "active_agent_id": state.get("active_agent_id"),
            "phase": state.get("phase"),
        }

    # ✅ Auto mode: run supervisor once
    SESSIONS[sid] = state
    state = GRAPH.invoke(SESSIONS[sid])
    SESSIONS[sid] = state

    msg = state.get("assistant_message") or ""
    formatted = parse_assistant_message(msg)

    return {
        "session_id": sid,
        "message": msg,                 # ✅ plain string
        "assistant_message": msg,       # ✅ plain string
        "message_ui": formatted,        # ✅ structured blocks
        "active_agent_id": state.get("active_agent_id"),
        "phase": state.get("phase"),
    }

class ChatIn(BaseModel):
    session_id: str
    message: str
    attachments: Optional[List[str]] = Field(
        default=None,
        description="Optional list of uploaded file references"
    )
    active_agent_id: Optional[str] = None

@app.post("/v1/chat")
def chat(payload: ChatIn = Body(...)):
    sid = payload.session_id

    if sid not in SESSIONS:
        raise HTTPException(status_code=404, detail="session not found")

    state = SESSIONS[sid]

    # --- 1) Persist attachments into state (CRITICAL) ---
    attachments = payload.attachments or []
    if attachments and not isinstance(attachments, list):
        attachments = [attachments]
    state["attachments"] = attachments

    print("Attachments in state:", state.get("attachments"))

    # --- 2) Optional explicit agent override ---
    if payload.active_agent_id:
        state["active_agent_id"] = payload.active_agent_id
        state["phase"] = "collecting"
        state["ready_payload"] = None
        state["submitted"] = None
        state["just_switched_agent"] = True

    # --- 3) Append user message ---
    state.setdefault("messages", [])
    state["messages"].append({
        "role": "user",
        "content": payload.message.strip()
    })

    # --- 4) Run supervisor graph ---
    new_state = GRAPH.invoke(state)

    # --- 5) Save updated state ---
    SESSIONS[sid] = new_state

    assistant_msg = (new_state.get("assistant_message") or "").strip()
    formatted = parse_assistant_message(assistant_msg)

    # --- 6) Response ---
    return {
        "message": assistant_msg,
        "assistant_message": assistant_msg,
        "message_ui": formatted,

        "phase": new_state.get("phase"),
        "active_agent_id": new_state.get("active_agent_id"),

        "drafts": new_state.get("drafts", {}),
        "stage_by_agent": new_state.get("stage_by_agent", {}),
        "ready_payload": new_state.get("ready_payload"),
        "submitted": new_state.get("submitted"),
        "last_tool_events": new_state.get("last_tool_events", []),
    }