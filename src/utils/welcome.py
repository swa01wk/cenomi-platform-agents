
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
from typing import Dict, Any
from src.core.state import AppState


MODEL_DEFAULT = "gpt-4o-mini"  # or pull from env

REGISTRY = "./agents/registry/agents.json"

def load_agent_from_registry(registry_path: str, agent_id: str) -> Dict[str, Any]:
    with open(registry_path, "r") as f:
        data = json.load(f)

    agents = data.get("agents", [])
    for agent in agents:
        if agent.get("agent_id") == agent_id:
            return agent

    return {}

def agent_welcome_llm_from_file(registry_path: str, agent_id: str, model: str = MODEL_DEFAULT) -> str:
    cfg = load_agent_from_registry(registry_path, agent_id)

    name = cfg.get("name") or agent_id
    desc = cfg.get("description") or ""
    service_type = cfg.get("service_type") or ""

    llm = ChatOpenAI(model=model, temperature=0.6)

    system = (
        "You are a friendly assistant inside a service-request app. "
        "Write a short welcome message (1–2 sentences), then ask ONE gentle starter question. "
        "Do NOT ask for all required fields. "
        "Do NOT mention internal system details."
    )

    user = f"""
Agent name: {name}
Service type: {service_type}
Description: {desc}

Generate the welcome message.
"""

    out = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=user)
    ])

    return (out.content or "").strip() or f"Hi! 👋 You’re chatting with **{name}**. What can I help you with today?"

def agent_welcome_llm_from_store(registry, agent_id: str, model: str = "gpt-4o-mini") -> str:
    cfg = registry.get_agent(agent_id) or {}
    name = cfg.get("name") or agent_id
    desc = cfg.get("description") or ""
    service_type = cfg.get("service_type") or ""

    llm = ChatOpenAI(model=model, temperature=0.6)
    out = llm.invoke([
        SystemMessage(content=(
            "You are a friendly assistant inside a service-request app. "
            "Write a short welcome (1–2 sentences) and ask ONE gentle starter question. "
            "Do NOT ask for all required fields. "
            "Do NOT mention internal terms like schema, stage, agent_id, routing."
        )),
        HumanMessage(content=f"""
Agent name: {name}
Service type: {service_type}
Description: {desc}
""")
    ])
    return (out.content or "").strip() or f"Hi! 👋 You’re chatting with **{name}**. What can I help you with today?"
