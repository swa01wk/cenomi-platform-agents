import uuid
from typing import Dict, Optional, List
from fastapi import FastAPI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from src.admin.routes import router as admin_router
from src.core.state import AppState
from src.supervisor.graph import build_supervisor_graph
from src.registry.store import AgentRegistryStore
from src.tools.registry import ToolRegistry

load_dotenv()

app = FastAPI(title="Agent Platform PoC (LangGraph Pattern A)")
app.include_router(admin_router)

SESSIONS: Dict[str, AppState] = {}

registry_store = AgentRegistryStore()
toolreg = ToolRegistry()

# Supervisor graph is compiled once, but it reloads registry per turn.
GRAPH = build_supervisor_graph(registry_store, toolreg)

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
def create_session():
    sid = uuid.uuid4().hex
    SESSIONS[sid] = default_state(sid)
    # Run one supervisor step to show choices
    state = GRAPH.invoke(SESSIONS[sid])
    SESSIONS[sid] = state
    return {"session_id": sid, "assistant_message": state.get("assistant_message")}

class ChatIn(BaseModel):
    session_id: str
    message: str
    attachments: Optional[List[str]] = Field(default=None, description="Optional list of uploaded file references")

@app.post("/v1/chat")
def chat(body: ChatIn):
    sid = body.session_id
    if sid not in SESSIONS:
        SESSIONS[sid] = default_state(sid)

    state = SESSIONS[sid]
    state["messages"].append({"role": "user", "content": body.message})
    # Attachments are stored separately in state for this turn
    state["turn_attachments"] = body.attachments or []

    new_state = GRAPH.invoke(state)

    assistant_msg = new_state.get("assistant_message", "")
    new_state["messages"].append({"role": "assistant", "content": assistant_msg})

    # clear turn attachments after processing
    new_state["turn_attachments"] = []
    SESSIONS[sid] = new_state

    return {
        "assistant_message": assistant_msg,
        "phase": new_state.get("phase"),
        "active_agent_id": new_state.get("active_agent_id"),
        "drafts": new_state.get("drafts"),
        "stage_by_agent": new_state.get("stage_by_agent"),
        "ready_payload": new_state.get("ready_payload"),
        "submitted": new_state.get("submitted"),
        "last_tool_events": new_state.get("last_tool_events", []),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)