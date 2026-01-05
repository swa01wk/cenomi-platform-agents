from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END

from src.core.state import AppState
from src.core.utils import last_user_text, YES_RE
from src.routing.router import route_by_keywords, parse_choice
from src.subagent.runner import run_subagent
from src.registry.store import AgentRegistryStore
from src.tools.registry import ToolRegistry
from src.routing.intent_router import infer_intent
from src.utils.welcome import agent_welcome_llm_from_store, REGISTRY

import re

YES_RE = re.compile(r"^\s*(yes|y|submit|confirm|go ahead|okay submit)\b", re.I)
NO_RE = re.compile(r"^\s*(no|nope|not now|don'?t submit|change|edit|wait)\b", re.I)


def looks_like_new_intent(text: str) -> bool:
    # Lightweight heuristic to trigger re-routing even in confirm mode
    t = (text or "").lower()
    keywords = [
        "lead",
        "leasing",
        "lease",
        "rent",
        "unit",
        "kiosk",
        "shop",
        "brand",
        "property",
        "cr number",
        "company",
        "quotation",
        "complaint",
        "refund",
        "booking",
    ]
    return any(k in t for k in keywords)


def format_choices(agents: List[Dict[str, Any]]) -> str:
    lines = ["What type of service request is this? Choose one:"]
    for i, a in enumerate(agents, start=1):
        lines.append(f"{i}) {a['name']} — {a.get('description','')}")
    lines.append("Reply with number or name.")
    return "\n".join(lines)


def tool_runner(toolreg: ToolRegistry, state: AppState):
    def _run(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        tool = toolreg.get(tool_name)
        return tool(payload)

    return _run


def node_supervisor(state: AppState, registry: AgentRegistryStore) -> AppState:
    state.setdefault("messages", [])
    state.setdefault("drafts", {})
    state.setdefault("stage_by_agent", {})
    state.setdefault("last_tool_events", [])
    msg = last_user_text(state.get("messages", [])) or ""

    # ✅ clear one-time skip flag unless re-set below
    state.pop("skip_subagent_once", None)

    # 0) Confirm phase: unlockable + re-route capable
    if state.get("phase") == "confirm":
        if YES_RE.match(msg):
            state["assistant_message"] = "Alright — submitting it now."
            return state

        if NO_RE.match(msg) or looks_like_new_intent(msg):
            agents = registry.list_agents() or []
            if agents:
                decision = infer_intent(msg, agents)
                if (
                    decision.agent_id
                    and decision.confidence >= 0.70
                    and decision.agent_id != state.get("active_agent_id")
                ):
                    state["active_agent_id"] = decision.agent_id
                    state["phase"] = "collecting"
                    state["ready_payload"] = None
                    state["submitted"] = None
                    state["just_switched_agent"] = True

                    # ✅ show welcome first, don’t call subagent this same invoke
                    state["skip_subagent_once"] = True
                    state["assistant_message"] = agent_welcome_llm_from_store(registry, decision.agent_id)
                    return state

            state["phase"] = "collecting"
            state["ready_payload"] = None
            state["assistant_message"] = "Sure — tell me what you want to change, and I’ll update it."
            return state

        state["assistant_message"] = "Do you want me to submit this, or update something?"
        return state

    # 1) Explicit agent mode: if active_agent_id is already set, skip routing
    if state.get("active_agent_id"):
        agents = registry.list_agents() or []
        if agents and msg:
            decision = infer_intent(msg, agents)
            if decision.agent_id and decision.confidence >= 0.80 and decision.agent_id != state["active_agent_id"]:
                state["active_agent_id"] = decision.agent_id
                state["phase"] = "collecting"
                state["ready_payload"] = None
                state["just_switched_agent"] = True

                # ✅ show welcome first, don’t call subagent this same invoke
                state["skip_subagent_once"] = True
                state["assistant_message"] = agent_welcome_llm_from_store(registry, decision.agent_id)
                return state

        state["phase"] = "collecting"
        state["assistant_message"] = ""
        return state

    # 2) No active agent -> route by intent
    agents = registry.list_agents() or []
    if not agents:
        state["assistant_message"] = "No service agents are configured yet. An admin needs to create them first."
        state["phase"] = "supervisor"
        return state

    if not msg:
        state["assistant_message"] = "Hi! Tell me what you need help with, and I’ll create the request."
        state["phase"] = "supervisor"
        return state

    decision = infer_intent(msg, agents)
    if (not decision.agent_id) or decision.confidence < 0.75:
        state["assistant_message"] = decision.clarification_question or (
            "Quick question — is this about leasing/property (lead enquiry) or a general support request?"
        )
        state["phase"] = "supervisor"
        return state

    # ✅ selected agent -> show welcome first
    state["active_agent_id"] = decision.agent_id
    state["phase"] = "collecting"
    state["ready_payload"] = None
    state["just_switched_agent"] = True

    # ✅ show welcome first, don’t call subagent this same invoke
    state["skip_subagent_once"] = True
    state["assistant_message"] = agent_welcome_llm_from_store(registry, decision.agent_id)
    return state

def node_call_subagent(state: AppState, registry: AgentRegistryStore, toolreg: ToolRegistry) -> AppState:
    state.setdefault("messages", [])
    state.setdefault("drafts", {})
    state.setdefault("stage_by_agent", {})
    state.setdefault("last_tool_events", [])

    agent_id = state.get("active_agent_id")
    if not agent_id:
        state["phase"] = "supervisor"
        state["assistant_message"] = "Tell me what you need help with."
        return state

    cfg = registry.get_agent(agent_id)
    if not cfg:
        state["active_agent_id"] = None
        state["phase"] = "supervisor"
        state["assistant_message"] = "That service is no longer available. Tell me what you need help with."
        return state

    user_text = last_user_text(state.get("messages", [])) or ""
    attachments = state.get("attachments", []) or []

    draft = state["drafts"].get(agent_id, {}) or {}
    current_stage = state["stage_by_agent"].get(agent_id)

    # Tool runner adapter
    def tool_runner(name: str, payload: dict):
        fn = toolreg.get(name)
        if not fn:
            raise ValueError(f"Tool not found: {name}")
        return fn(payload)


    result = run_subagent.invoke({
        "agent_cfg": cfg,
        "user_text": user_text,
        "draft": draft,
        "current_stage": current_stage,
        "attachments": attachments,
        "tool_runner": tool_runner,
        "just_switched_agent": state.get("just_switched_agent", False),
    })

    # Clear after first use
    state.pop("just_switched_agent", None)

    # persist state
    state["drafts"][agent_id] = result.get("draft", draft)
    state["stage_by_agent"][agent_id] = result.get("stage_id", current_stage)
    state["last_tool_events"] = result.get("tool_events", []) or []

    if result.get("status") == "needs_user_input":
        state["phase"] = "collecting"
        state["assistant_message"] = result.get("question", "")
        state["ready_payload"] = None
        return state

    if result.get("status") == "ready":
        state["ready_payload"] = result.get("payload")
        state["phase"] = "confirm"
        preview = result.get("natural_preview")
        if preview:
            state["assistant_message"] = preview + "\n\nSay **submit** to send it, or tell me what to change."
        else:
            state["assistant_message"] = "Here’s what I’ve got. Want me to submit it, or change anything?"
        return state

    state["phase"] = "collecting"
    state["assistant_message"] = "Tell me a bit more so I can proceed."
    return state


def node_submit(state: AppState, toolreg: ToolRegistry) -> AppState:
    msg = last_user_text(state.get("messages", []))
    if state.get("phase") != "confirm" or not YES_RE.match(msg or ""):
        state["assistant_message"] = "Not submitted."
        return state

    payload = state.get("ready_payload") or {}
    # Use a generic submit tool based on service_type if you want.
    # For PoC: if service_type == general_enquiry -> submit_general_enquiry else final_submit_lead_enquiry already ran.
    service_type = payload.get("service_type")

    if service_type == "general_enquiry":
        tool = toolreg.get("submit_general_enquiry")
        submitted = tool(payload)
    else:
        # Lead enquiry final submit tool already runs in stage tools; return its status + lead_id
        submitted = {
            "ok": True,
            "status": payload.get("status", "SUBMITTED"),
            "lead_id": payload.get("lead_id"),
        }

    state["submitted"] = submitted
    state["phase"] = "done"
    if submitted.get("request_id"):
        state["assistant_message"] = (
            f"✅ Submitted! Request id: **{submitted['request_id']}**"
        )
    else:
        state["assistant_message"] = (
            f"✅ Submitted! Status: **{submitted.get('status','SUBMITTED')}**"
        )
    return state


def build_supervisor_graph(registry: AgentRegistryStore, toolreg: ToolRegistry):
    g = StateGraph(AppState)
    g.add_node("supervisor", lambda s: node_supervisor(s, registry))
    g.add_node("call_subagent", lambda s: node_call_subagent(s, registry, toolreg))
    g.add_node("submit", lambda s: node_submit(s, toolreg))
    g.set_entry_point("supervisor")

    def after_supervisor(state: AppState):
        msg = last_user_text(state.get("messages", []))

        if state.get("phase") == "confirm" and YES_RE.match(msg or ""):
            return "submit"

        # ✅ If supervisor just routed/switched and wants to show welcome first, don't call subagent yet
        if state.get("skip_subagent_once"):
            return END

        if state.get("phase") == "collecting" and state.get("active_agent_id"):
            return "call_subagent"

        return END


    g.add_conditional_edges(
        "supervisor",
        after_supervisor,
        {"call_subagent": "call_subagent", "submit": "submit", END: END},
    )

    g.add_edge("call_subagent", END)
    g.add_edge("submit", END)
    return g.compile()

