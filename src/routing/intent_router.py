import os
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

class RouteDecision(BaseModel):
    agent_id: Optional[str] = Field(default=None, description="Chosen agent_id from registry or null if unsure")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(default="")
    clarification_question: Optional[str] = Field(default=None)

def build_agents_context(agents: List[Dict[str, Any]]) -> str:
    lines = []
    for a in agents:
        lines.append(
            f"- agent_id={a['agent_id']}, name={a['name']}, service_type={a.get('service_type')}, "
            f"description={a.get('description','')}, keywords={a.get('keywords',[])}"
        )
    return "\n".join(lines)

def infer_intent(user_text: str, agents: List[Dict[str, Any]]) -> RouteDecision:
    llm = ChatOpenAI(model=MODEL_DEFAULT, temperature=0).with_structured_output(RouteDecision)

    ctx = build_agents_context(agents)
    sys = f"""
You are an intent router for a service-request chatbot.

You must choose the best agent_id from the registry when possible.
If the user's intent is ambiguous, do NOT guess; instead return agent_id=null and provide a short clarification_question.

Registry agents:
{ctx}

Rules:
- If user mentions leasing/rent/unit type/brand/company/property -> lead enquiry.
- If user mentions generic help/request/support/category/subcategory -> general enquiry.
- Confidence should reflect certainty (>=0.75 means you are confident).
- clarification_question must be one short, friendly question.
"""

    return llm.invoke([SystemMessage(content=sys), HumanMessage(content=user_text)])
