from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END

from src.core.state import AppState
from src.core.utils import last_user_text, YES_RE
from src.routing.router import route_by_keywords, parse_choice
from src.subagent.runner import run_subagent
from src.registry.store import AgentRegistryStore
from src.tools.registry import ToolRegistry
from src.routing.intent_router import infer_intent
from src.messages.generators import (
    generate_greeting,
    generate_agent_acknowledgement,
    generate_continue_prompt,
    generate_submission_success_message
)

import re

YES_RE = re.compile(r"^\s*(yes|y|submit|confirm|go ahead|okay submit)\b", re.I)
NO_RE = re.compile(r"^\s*(no|nope|not now|don'?t submit|change|edit|wait)\b", re.I)

def looks_like_new_intent(text: str) -> bool:
    # Lightweight heuristic to trigger re-routing even in confirm mode
    t = (text or "").lower()
    keywords = [
        "lead", "leasing", "lease", "rent", "unit", "kiosk", "shop", "brand",
        "property", "cr number", "company", "quotation", "complaint", "refund", "booking"
    ]
    return any(k in t for k in keywords)


def format_choices(agents: List[Dict[str, Any]]) -> str:
    lines = ["What type of service request is this? Choose one:"]
    for i, a in enumerate(agents, start=1):
        lines.append(f"{i}) {a['name']} — {a.get('description','')}")
    lines.append("Reply with number or name.")
    return "\n".join(lines)

def tool_runner(toolreg: ToolRegistry, state: AppState):
    """Synchronous tool runner (deprecated - kept for backwards compatibility)"""
    def _run(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        tool = toolreg.get(tool_name)
        return tool(payload)
    return _run

def atool_runner_factory(toolreg: ToolRegistry, state: AppState):
    """Async tool runner factory for Phase 4+"""
    async def _run(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        tool = toolreg.get(tool_name)
        return await tool(payload)
    return _run

async def node_supervisor(state: AppState, registry: AgentRegistryStore) -> AppState:
    msg = last_user_text(state.get("messages", []))
    agents = await registry.alist_agents()

    if not agents:
        state["assistant_message"] = "No service agents are configured yet. An admin needs to create them first."
        state["phase"] = "supervisor"
        return state

    # If already done
    if state.get("phase") == "done":
        state["assistant_message"] = "That request is already submitted. If you want, tell me what you want to do next."
        return state

    # Confirm phase: handled by conditional edge (submit)
    if state.get("phase") == "confirm":
        msg = last_user_text(state.get("messages", [])) or ""

        # 1) If user confirms submit
        if YES_RE.search(msg):
            state["assistant_message"] = "Alright — submitting it now."
            # Let conditional edge take it to submit node
            return state

        # 2) If user says no / wants changes / indicates new intent:
        # Try re-route FIRST if it looks like intent changed
        if NO_RE.search(msg) or looks_like_new_intent(msg):
            agents = await registry.alist_agents()
            conversation_history = state.get("messages", [])
            decision = await infer_intent(msg, agents, conversation_history)

            # If router confidently picks a different agent -> switch
            if decision.agent_id and decision.confidence >= 0.70 and decision.agent_id != state.get("active_agent_id"):
                state["active_agent_id"] = decision.agent_id
                state["phase"] = "collecting"
                state["ready_payload"] = None  # unlock
                # keep drafts dict, but we'll now operate on the new agent's draft
                chosen_name = next((a["name"] for a in agents if a["agent_id"] == decision.agent_id), decision.agent_id)
                state["assistant_message"] = f"Got it — let's switch to **{chosen_name}**. Tell me what you need, and I'll collect the details."
                return state

            # Otherwise treat as edits to the SAME request and continue collecting
            state["phase"] = "collecting"
            state["ready_payload"] = None  # unlock so subagent can update
            state["assistant_message"] = "No worries — tell me what you want to change (you can write it naturally), and I'll update the request."
            return state

        # 3) Anything else in confirm: don't loop the same robotic message
        state["assistant_message"] = "Do you want me to submit this, or update something?"
        return state


    # If we already locked an agent, continue
    if state.get("active_agent_id"):
        msg = last_user_text(state.get("messages", [])) or ""
        agents = await registry.alist_agents()
        conversation_history = state.get("messages", [])

        # allow mid-stream reroute if message strongly indicates different intent
        decision = await infer_intent(msg, agents, conversation_history)
        if decision.agent_id and decision.confidence >= 0.80 and decision.agent_id != state.get("active_agent_id"):
            state["active_agent_id"] = decision.agent_id
            state["phase"] = "collecting"
            state["ready_payload"] = None
            chosen_name = next((a["name"] for a in agents if a["agent_id"] == decision.agent_id), decision.agent_id)
            state["assistant_message"] = f"Got it — switching to **{chosen_name}**."
            return state

        state["phase"] = "collecting"
        # Don't say "continuing" every time — it feels botty
        state["assistant_message"] = ""
        return state


    # First turn or not routed yet: infer intent
    if not msg.strip():
        greeting = await generate_greeting({"is_new_session": True})
        state["assistant_message"] = greeting
        state["phase"] = "supervisor"
        return state

    conversation_history = state.get("messages", [])
    decision = await infer_intent(msg, agents, conversation_history)

    # If unsure -> ask one clarifying question
    if (not decision.agent_id) or decision.confidence < 0.75:
        q = decision.clarification_question or "Quick question — is this about leasing a property, or a general enquiry/support request?"
        state["assistant_message"] = q
        state["phase"] = "supervisor"
        return state

    # Route to chosen subagent
    state["active_agent_id"] = decision.agent_id
    state["phase"] = "collecting"

    # Natural acknowledgment using LLM-generated message
    chosen_agent = next((a for a in agents if a["agent_id"] == decision.agent_id), None)
    if chosen_agent:
        acknowledgement = await generate_agent_acknowledgement(
            chosen_agent,
            msg,
            decision.confidence,
            conversation_history
        )
        state["assistant_message"] = acknowledgement
    else:
        chosen_name = decision.agent_id
        state["assistant_message"] = f"Got it — I'll help you with **{chosen_name}**. Let's get a few details."
    return state

async def node_call_subagent(state: AppState, registry: AgentRegistryStore, toolreg: ToolRegistry) -> AppState:
    agents = await registry.alist_agents()
    agent_id = state.get("active_agent_id")
    cfg = next((a for a in agents if a["agent_id"] == agent_id), None)
    if not cfg:
        state["needs_service_choice"] = True
        state["active_agent_id"] = None
        state["assistant_message"] = format_choices(agents)
        return state

    drafts = state.get("drafts", {})
    draft = dict(drafts.get(agent_id, {}))

    stage_map = state.get("stage_by_agent", {})
    current_stage = stage_map.get(agent_id)

    msg = last_user_text(state.get("messages", []))
    attachments = state.get("turn_attachments", []) or []
    conversation_history = state.get("messages", [])

    result = await run_subagent.ainvoke({
        "agent_cfg": cfg,
        "user_text": msg,
        "draft": draft,
        "current_stage": current_stage,
        "attachments": attachments,
        "conversation_history": conversation_history,
        "tool_runner": atool_runner_factory(toolreg, state),
    })

    drafts[agent_id] = result.get("draft", draft)
    state["drafts"] = drafts

    stage_map[agent_id] = result.get("stage_id") or (current_stage or "")
    state["stage_by_agent"] = stage_map

    # store tool events for debugging
    state["last_tool_events"] = result.get("tool_events", [])

    if result["status"] == "needs_user_input":
        state["phase"] = "collecting"
        state["assistant_message"] = result["question"]
        return state

    # ready -> show final form
    payload = result["payload"]
    state["ready_payload"] = payload
    state["phase"] = "confirm"

    preview = result.get("natural_preview")
    if preview:
        state["assistant_message"] = preview + "\n\nIf you'd like, say **submit** to send it — or tell me what you want to change."
    else:
        state["assistant_message"] = "I've put this together. Want me to submit it, or change anything?"
    return state

async def node_submit(state: AppState, registry: AgentRegistryStore, toolreg: ToolRegistry) -> AppState:
    msg = last_user_text(state.get("messages", []))
    if state.get("phase") != "confirm" or not YES_RE.match(msg or ""):
        state["assistant_message"] = "Not submitted."
        return state

    payload = state.get("ready_payload") or {}

    # Execute submission_tools generically (tools that run only after user confirms)
    submission_tools = payload.get("submission_tools") or []

    if not submission_tools:
        state["assistant_message"] = "No submission tool configured for this agent."
        return state

    submitted = {"ok": True, "status": "SUBMITTED"}

    for tool_name in submission_tools:
        tool = toolreg.get(tool_name)
        if tool:
            result = await tool(payload)
            # Merge results (like lead_id, request_id, status) into submitted dict
            if isinstance(result, dict):
                submitted.update(result)

    state["submitted"] = submitted

    # Check if submission was successful
    if not submitted.get("ok", True):
        # Submission failed - show error message
        error_message = submitted.get("error", "Some error occurred, reach out to our team using their contact or email")
        state["assistant_message"] = f"Some error occurred, reach out to our team using their contact or email"
        state["phase"] = "done"

        # Reset for new enquiry
        state["active_agent_id"] = None
        state["phase"] = "supervisor"
        return state

    state["phase"] = "done"

    # Get agent config for personalized success message
    active_agent_id = state.get("active_agent_id")
    agents = await registry.alist_agents()
    agent_config = next((a for a in agents if a["agent_id"] == active_agent_id), None)
    conversation_history = state.get("messages", [])

    if agent_config:
        success_message = await generate_submission_success_message(
            agent_config,
            submitted,
            conversation_history
        )
        # Add continue prompt
        continue_message = await generate_continue_prompt(agent_config, conversation_history)
        state["assistant_message"] = f"{success_message}\n\n{continue_message}"
    else:
        # Fallback if no agent config
        if submitted.get("request_id"):
            state["assistant_message"] = f"✅ Submitted! Request id: **{submitted['request_id']}**"
        else:
            state["assistant_message"] = f"✅ Submitted! Status: **{submitted.get('status','SUBMITTED')}**"

    # Reset for new enquiry (reinitiation)
    state["active_agent_id"] = None
    state["phase"] = "supervisor"

    return state

def build_supervisor_graph(registry: AgentRegistryStore, toolreg: ToolRegistry):
    g = StateGraph(AppState)

    # LangGraph requires async nodes to be defined as coroutine functions
    async def supervisor_node(s: AppState):
        return await node_supervisor(s, registry)

    async def call_subagent_node(s: AppState):
        return await node_call_subagent(s, registry, toolreg)

    async def submit_node(s: AppState):
        return await node_submit(s, registry, toolreg)

    g.add_node("supervisor", supervisor_node)
    g.add_node("call_subagent", call_subagent_node)
    g.add_node("submit", submit_node)
    g.set_entry_point("supervisor")

    # Conditional edges remain sync
    def after_supervisor(state: AppState):
        msg = last_user_text(state.get("messages", []))
        if state.get("phase") == "confirm" and YES_RE.match(msg or ""):
            return "submit"
        if state.get("phase") == "collecting" and state.get("active_agent_id"):
            return "call_subagent"
        return END

    g.add_conditional_edges("supervisor", after_supervisor, {
        "call_subagent": "call_subagent",
        "submit": "submit",
        END: END
    })

    g.add_edge("call_subagent", END)
    g.add_edge("submit", END)
    return g.compile()
