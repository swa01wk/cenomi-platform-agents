import uuid
import json
import shutil
from pathlib import Path
from typing import Dict, Optional, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from src.admin.routes import router as admin_router
from src.admin.tool_routes import router  as tool_router
from src.core.state import AppState
from src.supervisor.graph import build_supervisor_graph
from src.registry.store import AgentRegistryStore
from src.tools.registry import ToolRegistry

load_dotenv()

app = FastAPI(title="Agent Platform PoC (LangGraph Pattern A)")
app.include_router(admin_router)
app.include_router(tool_router)

SESSIONS: Dict[str, AppState] = {}
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
        "locked_fields": {},
        "ready_payload": None,
        "assistant_message": "Hi! What type of service request is this?",
        "submitted": None,
        "last_tool_events": []
    }

@app.post("/v1/session")
async def create_session():
    sid = uuid.uuid4().hex
    SESSIONS[sid] = default_state(sid)
    # Run one supervisor step to show choices
    state = await GRAPH.ainvoke(SESSIONS[sid])
    SESSIONS[sid] = state
    return {"session_id": sid, "assistant_message": state.get("assistant_message")}

class ChatIn(BaseModel):
    session_id: str
    message: str

class UpdateDraftIn(BaseModel):
    session_id: str
    agent_id: str
    field: str
    value: Any

async def store_upload(file: UploadFile) -> str:
    attachment_id = uuid.uuid4().hex
    original_name = file.filename or "upload"
    ext = Path(original_name).suffix
    stored_name = f"{attachment_id}{ext}"
    stored_path = UPLOAD_DIR / stored_name

    try:
        with stored_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()

    return str(stored_path)

@app.post("/v1/chat")
async def chat(
    request: Request,
    session_id: Optional[str] = Form(default=None),
    message: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    payload: Optional[ChatIn] = None
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        payload = ChatIn(**data)
    else:
        if session_id is None or message is None:
            raise HTTPException(status_code=400, detail="session_id and message are required")
        payload = ChatIn(session_id=session_id, message=message)

    sid = payload.session_id
    if sid not in SESSIONS:
        SESSIONS[sid] = default_state(sid)

    state = SESSIONS[sid]
    state["messages"].append({"role": "user", "content": payload.message})
    # Attachments are stored separately in state for this turn
    if file is not None:
        stored_path = await store_upload(file)
        state["turn_attachments"] = [stored_path]
    else:
        state["turn_attachments"] = []

    new_state = await GRAPH.ainvoke(state)

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

# @app.post("/v1/chat/stream")
# async def chat_stream(body: ChatIn):
#     """Streaming version of chat endpoint using Server-Sent Events (SSE)"""
#     sid = body.session_id
#     if sid not in SESSIONS:
#         SESSIONS[sid] = default_state(sid)

#     state = SESSIONS[sid]
#     state["messages"].append({"role": "user", "content": body.message})
#     state["turn_attachments"] = []

#     async def event_generator():
#         """Generate SSE events from LangGraph stream"""
#         final_state = None

#         # Stream events from the graph
#         async for event in GRAPH.astream(state):
#             # LangGraph streams events like {"node_name": state_update}
#             for node_name, node_state in event.items():
#                 # Send assistant message chunks if available
#                 if "assistant_message" in node_state:
#                     msg = node_state.get("assistant_message", "")
#                     if msg:
#                         yield f"data: {json.dumps({'type': 'message', 'content': msg})}\n\n"

#                 # Update final state
#                 final_state = node_state

#         # After streaming completes, send final state
#         if final_state:
#             assistant_msg = final_state.get("assistant_message", "")
#             final_state["messages"].append({"role": "assistant", "content": assistant_msg})
#             final_state["turn_attachments"] = []
#             SESSIONS[sid] = final_state

#             # Send complete state as final event
#             yield f"data: {json.dumps({'type': 'complete', 'state': {
#                 'phase': final_state.get('phase'),
#                 'active_agent_id': final_state.get('active_agent_id'),
#                 'drafts': final_state.get('drafts'),
#                 'stage_by_agent': final_state.get('stage_by_agent'),
#                 'ready_payload': final_state.get('ready_payload'),
#                 'submitted': final_state.get('submitted'),
#                 'last_tool_events': final_state.get('last_tool_events', []),
#             }})}\n\n"

#         yield "data: [DONE]\n\n"

#     return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/v1/draft/update")
async def update_draft(body: UpdateDraftIn):
    """Update a specific field in the draft from frontend"""
    sid = body.session_id
    if sid not in SESSIONS:
        return {"error": "Session not found"}, 404

    state = SESSIONS[sid]

    # Ensure drafts dict exists for the agent
    if "drafts" not in state:
        state["drafts"] = {}

    agent_id = body.agent_id
    if agent_id not in state["drafts"]:
        state["drafts"][agent_id] = {}

    # Update the field value
    state["drafts"][agent_id][body.field] = body.value

    # Optional: Run field validator if configured
    agents = await registry_store.alist_agents()
    agent_config = next((a for a in agents if a["agent_id"] == agent_id), None)

    validation_error = None
    if agent_config:
        # Find field spec
        field_spec = next((f for f in agent_config.get("fields", []) if f["key"] == body.field), None)
        if field_spec and field_spec.get("validator"):
            from src.tool_registry.prebuilt_tools import get_validator_by_name
            try:
                validator_name = field_spec["validator"]
                validator_tool = get_validator_by_name(validator_name)

                # Run validator
                if hasattr(validator_tool, 'args_schema') and validator_tool.args_schema:
                    result = validator_tool.invoke({body.field: body.value})
                else:
                    result = validator_tool.invoke(body.value)

                # Check if validation failed
                if isinstance(result, dict) and not result.get("valid", True):
                    validation_error = result.get("reason", "Validation failed")
                    # Don't store invalid value
                    del state["drafts"][agent_id][body.field]
            except Exception as e:
                validation_error = f"Validation error: {str(e)}"
                del state["drafts"][agent_id][body.field]

    # If validation passed, mark field as locked (manually edited)
    if not validation_error:
        if "locked_fields" not in state:
            state["locked_fields"] = {}
        if agent_id not in state["locked_fields"]:
            state["locked_fields"][agent_id] = []
        if body.field not in state["locked_fields"][agent_id]:
            state["locked_fields"][agent_id].append(body.field)

    SESSIONS[sid] = state

    if validation_error:
        return {
            "success": False,
            "error": validation_error,
            "drafts": state.get("drafts")
        }

    return {
        "success": True,
        "drafts": state.get("drafts"),
        "phase": state.get("phase"),
        "active_agent_id": state.get("active_agent_id")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)