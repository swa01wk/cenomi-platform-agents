import os
import re
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from pydantic import Field, create_model
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.func import entrypoint, task
from langgraph.checkpoint.memory import InMemorySaver

from src.messages.generators import generate_validation_message, generate_confirmation_message
from src.tool_registry.prebuilt_tools import get_validator_by_name
MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# OpenAI rate limiting: max 5 concurrent LLM calls to prevent quota exhaustion
OPENAI_SEMAPHORE = asyncio.Semaphore(5)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{10,15}$")


# -----------------------------
# Helpers: schema + stages
# -----------------------------
def compute_stage(cfg: Dict[str, Any], current_stage: Optional[str]) -> str:
    stages = cfg.get("stages") or []
    if not stages:
        return "DEFAULT"
    if current_stage:
        return current_stage
    return stages[0]["stage_id"]


def next_stage(cfg: Dict[str, Any], current_stage: str) -> Optional[str]:
    stages = cfg.get("stages") or []
    if not stages:
        return None
    ids = [s["stage_id"] for s in stages]
    if current_stage not in ids:
        return ids[0]
    i = ids.index(current_stage)
    return ids[i + 1] if i + 1 < len(ids) else None


def stage_spec(cfg: Dict[str, Any], stage_id: str) -> Dict[str, Any]:
    for s in (cfg.get("stages") or []):
        if s["stage_id"] == stage_id:
            return s
    return {"stage_id": "DEFAULT", "label": "Fill Form", "required_fields": [], "required_tools": [], "optional_tools": []}


def field_specs(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {f["key"]: f for f in (cfg.get("fields") or [])}


def guess_array_field_key(cfg: Dict[str, Any], stage_required: List[str]) -> Optional[str]:
    by_key = field_specs(cfg)
    # prefer required array fields
    for k in stage_required:
        f = by_key.get(k)
        if f and f.get("type") == "array":
            return k
    # common fallbacks
    for k in ("documents", "attachments"):
        f = by_key.get(k)
        if f and f.get("type") == "array":
            return k
    return None


# -----------------------------
# Conversational prompting (generated, not stored)
# -----------------------------
def friendly_label(cfg: dict, key: str) -> str:
    for f in (cfg.get("fields") or []):
        if f["key"] == key:
            label = (f.get("label") or key).strip()
            hint = f.get("hint")
            if hint:
                return f"{label} ({hint})"
            return label
    return key


def bucket_key(key: str) -> str:
    if key in ("first_name", "last_name"):
        return "identity"
    if key in ("email", "phone", "contact"):
        return "contact"
    if key in ("company_name", "cr_number"):
        return "company"
    if key in ("brand_name", "brand_name_ar"):
        return "brand"
    if key in ("unit_type", "area", "rent", "lease_period"):
        return "property_prefs"
    if key in ("unique_property_id",):
        return "property"
    if key in ("documents", "attachments"):
        return "docs"
    return "other"


def choose_issue_bundle(issues: List[Dict[str, Any]], max_items: int = 4) -> List[Dict[str, Any]]:
    """Pick 2–4 issues that belong together for one prompt."""
    if not issues:
        return []

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for it in issues:
        b = bucket_key(it["key"])
        groups.setdefault(b, []).append(it)

    priority = ["identity", "contact", "company", "brand", "property_prefs", "property", "docs", "other"]
    for b in priority:
        if b in groups:
            bundle = groups[b][:max_items]
            if len(bundle) < max_items:
                for b2 in priority:
                    if b2 == b or b2 not in groups:
                        continue
                    for it in groups[b2]:
                        if len(bundle) >= max_items:
                            break
                        bundle.append(it)
            return bundle

    return issues[:max_items]


async def ask_for_issues(cfg: dict, issues: List[Dict[str, Any]], stage_id: str, draft: Dict[str, Any]) -> str:
    """
    Make the prompt feel human while still asking for specific missing/invalid fields.
    """
    missing = [i for i in issues if i["kind"] == "missing"]
    invalid = [i for i in issues if i["kind"] == "invalid"]

    missing_labels = [friendly_label(cfg, i["key"]) for i in missing]
    invalid_lines = [f"{friendly_label(cfg, i['key'])}: {i['message']}" for i in invalid]

    system = (
        "You are a friendly service assistant chatting with a tenant. "
        "Be natural, short, and helpful. Ask for multiple missing items in one message. "
        "Don't mention internal terms like 'stage' or 'schema'. "
        "Don't show JSON. Use 1-2 short paragraphs. "
        "If documents are missing, ask them to upload/attach files."
    )

    user = f"""
We are collecting details for: {cfg.get('name')} ({cfg.get('service_type')}).
Current draft (what we already have): {draft}

Missing fields: {missing_labels}
Invalid fields: {invalid_lines}

Write the next assistant message. It must:
- acknowledge what we already captured (briefly),
- ask for the missing/invalid items (as a bundle),
- invite the user to answer in one message (but allow partial),
- sound natural.
"""
    return await llm_phrase(cfg.get("model"), system, user)

async def summarize_draft_naturally(cfg: dict, payload: dict) -> str:
    # remove noisy keys
    filtered = {k: v for k, v in payload.items() if k not in ("agent_id",)}
    system = (
        "You are a friendly assistant. Summarize a service request clearly and naturally. "
        "Use a short heading + bullets. Keep it concise. "
        "End by asking if the user wants to submit, using natural language."
    )
    user = f"""
Service type: {filtered.get('service_type')}
Data: {filtered}
"""
    return await llm_phrase(cfg.get("model"), system, user)

# -----------------------------
# Validation (the key change)
# -----------------------------
def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, list) and len(v) == 0:
        return True
    return False


def validate_draft(cfg: Dict[str, Any], stage_id: str, draft: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns issues list: [{key, kind, message}]
    - checks missing required fields for the stage
    - checks constraints for any present fields:
        - min_length, max_length, pattern, choices
        - basic email/phone validation where patterns exist or keys imply it
    """
    issues: List[Dict[str, Any]] = []

    spec_by_key = field_specs(cfg)
    st = stage_spec(cfg, stage_id)
    required_fields = st.get("required_fields") or []

    # 1) missing required
    for k in required_fields:
        if _is_empty(draft.get(k)):
            issues.append({
                "key": k,
                "kind": "missing",
                "message": "Required",
                "label": friendly_label(cfg, k)
            })

    # 2) invalid constraints (only if value present)
    for k, f in spec_by_key.items():
        if _is_empty(draft.get(k)):
            continue
        v = draft.get(k)

        # type sanity (lightweight)
        t = f.get("type", "string")
        if t == "number":
            try:
                # normalize numeric strings to float
                if isinstance(v, str):
                    v2 = float(v.strip())
                    draft[k] = v2
                    v = v2
                else:
                    float(v)
            except Exception:
                issues.append({
                    "key": k,
                    "kind": "invalid",
                    "message": "Please provide a number.",
                    "label": friendly_label(cfg, k)
                })
                continue

        if t == "array":
            if not isinstance(v, list):
                issues.append({
                    "key": k,
                    "kind": "invalid",
                    "message": "Please upload/attach files (can be multiple).",
                    "label": friendly_label(cfg, k)
                })
                continue

        # string constraints
        if isinstance(v, str):
            min_len = f.get("min_length")
            max_len = f.get("max_length")
            pattern = f.get("pattern")
            choices = f.get("choices")

            if min_len is not None and len(v.strip()) < int(min_len):
                issues.append({
                    "key": k,
                    "kind": "invalid",
                    "message": f"Too short (min {min_len} characters).",
                    "label": friendly_label(cfg, k)
                })
            if max_len is not None and len(v.strip()) > int(max_len):
                issues.append({
                    "key": k,
                    "kind": "invalid",
                    "message": f"Too long (max {max_len} characters).",
                    "label": friendly_label(cfg, k)
                })
            if choices:
                # Case-insensitive choice matching
                v_lower = v.strip().lower()
                choices_map = {c.lower(): c for c in choices}
                if v_lower not in choices_map:
                    issues.append({
                        "key": k,
                        "kind": "invalid",
                        "message": f"Choose one of: {', '.join(choices)}.",
                        "label": friendly_label(cfg, k)
                    })
                else:
                    # Normalize to correct case from choices
                    draft[k] = choices_map[v_lower]
            if pattern:
                try:
                    if not re.match(pattern, v.strip()):
                        # give friendlier hints for common fields
                        if k == "email":
                            issues.append({
                                "key": k,
                                "kind": "invalid",
                                "message": "That doesn't look like a valid email.",
                                "label": friendly_label(cfg, k)
                            })
                        elif k == "phone":
                            issues.append({
                                "key": k,
                                "kind": "invalid",
                                "message": "That doesn't look like a valid phone number.",
                                "label": friendly_label(cfg, k)
                            })
                        else:
                            issues.append({
                                "key": k,
                                "kind": "invalid",
                                "message": "Format looks invalid.",
                                "label": friendly_label(cfg, k)
                            })
                except re.error:
                    # ignore broken regex in config
                    pass

        # extra defaults if no pattern given but key implies it
        if k == "email" and isinstance(v, str) and not EMAIL_RE.match(v.strip()):
            # only add if not already flagged
            if not any(i["key"] == k and i["kind"] == "invalid" for i in issues):
                issues.append({
                    "key": k,
                    "kind": "invalid",
                    "message": "That doesn't look like a valid email.",
                    "label": friendly_label(cfg, k)
                })

        if k == "phone" and isinstance(v, str) and not PHONE_RE.match(v.strip()):
            if not any(i["key"] == k and i["kind"] == "invalid" for i in issues):
                issues.append({
                    "key": k,
                    "kind": "invalid",
                    "message": "Please include country code if possible (10–15 digits).",
                    "label": friendly_label(cfg, k)
                })
    return issues

async def llm_phrase(model: str, system: str, user: str) -> str:
    llm = ChatOpenAI(model=model or MODEL_DEFAULT, temperature=0.6)
    async with OPENAI_SEMAPHORE:
        out = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return (out.content or "").strip()

# -----------------------------
# Extraction (make it permissive)
# -----------------------------
def build_extraction_model(cfg: Dict[str, Any]):
    """
    Permissive extraction model for structured output:
    - all fields Optional
    - arrays are typed (List[str]) so OpenAI response_format schema is valid
    """
    fields = cfg.get("fields", []) or []
    annotations = {}

    for f in fields:
        key = f["key"]
        ftype = f.get("type", "string")

        if ftype == "integer":
            py_t = Optional[int]
        elif ftype == "number":
            py_t = Optional[float]
        elif ftype == "boolean":
            py_t = Optional[bool]
        elif ftype == "array":
            # IMPORTANT: give items a concrete type
            py_t = Optional[List[str]]
        elif ftype == "object":
            py_t = Optional[Dict[str, Any]]
        else:
            py_t = Optional[str]

        annotations[key] = (py_t, Field(default=None))

    return create_model(f"{cfg['agent_id']}_Extract", **annotations)  # type: ignore


@task
async def extract_fields(
    cfg: Dict[str, Any],
    user_text: str,
    draft: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    ExtractionModel = build_extraction_model(cfg)
    llm = ChatOpenAI(model=cfg.get("model") or MODEL_DEFAULT, temperature=0).with_structured_output(ExtractionModel)

    # Build field descriptions with hints
    field_descriptions = []
    for f in (cfg.get("fields") or []):
        key = f["key"]
        label = f.get("label", key)
        hint = f.get("hint")
        ftype = f.get("type", "string")
        choices = f.get("choices")

        desc = f"{key} ({label})"
        if hint:
            desc += f" - {hint}"
        if choices:
            desc += f" - must be one of: {', '.join(choices)}"
        if ftype == "integer":
            desc += " - must be an integer (whole number)"
        elif ftype == "number":
            desc += " - must be a number (can include decimals)"
        elif ftype == "boolean":
            desc += " - must be true or false"
        elif ftype == "object":
            desc += " - must be a JSON object/dictionary"
        elif ftype == "array":
            desc += " - must be a list/array"

        field_descriptions.append(desc)

    # Build context-aware system prompt
    turn_count = len(conversation_history) if conversation_history else 0
    collected_fields = [k for k, v in draft.items() if v not in (None, "", [])]

    sys = (
        (cfg.get("system_prompt") or "You are a helpful assistant collecting details conversationally.") + "\n\n"
        "FIELD DEFINITIONS:\n" + "\n".join(f"- {fd}" for fd in field_descriptions) + "\n\n"
        "Rules:\n"
        "- Greet only using name, not company name, brand name or last name.\n"
        "- Don't get confused between first name and last name.\n"
        "- User may provide one, a few, or all fields in one message.\n"
        "- Extract as many fields as you can.\n"
        "- If not present, return null.\n"
        "- Do not invent.\n"
        "- Pay attention to field types (string vs number) and hints.\n"
        "- For choice fields, normalize to exact match from allowed values (case-insensitive).\n"
        "- Reference previous conversation context when relevant.\n"
        "- Handle corrections gracefully (e.g., 'Actually, I meant...').\n"
        f"Current draft: {draft}\n"
        f"Conversation turn: {turn_count}\n"
        f"Already collected: {', '.join(collected_fields) if collected_fields else 'Nothing yet'}\n"
    )

    # Build message chain with history
    from langchain_core.messages import AIMessage
    messages = [SystemMessage(content=sys)]

    # Add recent conversation history for context (last 6 messages = 3 exchanges)
    if conversation_history:
        for msg in conversation_history[-6:]:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg.get("content", "")))

    # Add current user message if not already in history
    if not conversation_history or conversation_history[-1].get("content") != user_text:
        messages.append(HumanMessage(content=user_text))

    async with OPENAI_SEMAPHORE:
        out = await llm.ainvoke(messages)

    # Post-process: normalize choice field values (case-insensitive)
    extracted = out.model_dump()
    spec_by_key = field_specs(cfg)
    for k, v in extracted.items():
        if v is None or not isinstance(v, str):
            continue

        field_spec = spec_by_key.get(k)
        if not field_spec:
            continue

        choices = field_spec.get("choices")
        if choices:
            # Case-insensitive matching
            v_lower = v.strip().lower()
            choices_map = {c.lower(): c for c in choices}
            if v_lower in choices_map:
                extracted[k] = choices_map[v_lower]

    return extracted


# -----------------------------
# Tool execution
# -----------------------------
def should_run_optional_tool(tool_name: str, draft: Dict[str, Any]) -> bool:
    if tool_name == "verify_cr_number" and not draft.get("cr_number"):
        return False
    return True


checkpointer = InMemorySaver()


@entrypoint(checkpointer=checkpointer)
async def run_subagent(inputs: dict) -> dict:
    """
    Generic subagent runner (Pattern A).
    inputs = {
      "agent_cfg": dict,
      "user_text": str,
      "draft": dict,
      "current_stage": str|None,
      "attachments": [str],
      "conversation_history": List[Dict[str, str]],
      "tool_runner": callable(tool_name, payload)->result
    }
    """
    cfg: Dict[str, Any] = inputs["agent_cfg"]
    user_text: str = inputs.get("user_text", "")
    draft: Dict[str, Any] = dict(inputs.get("draft", {}))
    current_stage: Optional[str] = inputs.get("current_stage")
    attachments: List[str] = inputs.get("attachments") or []
    conversation_history: List[Dict[str, str]] = inputs.get("conversation_history", [])
    tool_runner = inputs["tool_runner"]

    stage_id = compute_stage(cfg, current_stage)
    st = stage_spec(cfg, stage_id)
    required_fields = st.get("required_fields") or []

    tool_events: List[Dict[str, Any]] = []

    # 0) Attachments merge into the appropriate array field
    if attachments:
        # Check if there's a file_path field in the schema (for single file validation)
        spec_by_key = field_specs(cfg)
        if "file_path" in spec_by_key and attachments:
            # If file_path field exists, populate it with the first attachment
            draft["file_path"] = attachments[0]
        
        # Also add to array field if one exists (for multiple documents)
        array_key = guess_array_field_key(cfg, required_fields)
        if array_key:
            existing = draft.get(array_key) or []
            if not isinstance(existing, list):
                existing = [str(existing)]
            for a in attachments:
                if a not in existing:
                    existing.append(a)
            draft[array_key] = existing

    # 0.5) Validate file_path if it exists and has a validator (even without user text)
    validation_issues: List[Dict[str, Any]] = []
    
    if draft.get("file_path"):
        spec_by_key = field_specs(cfg)
        field_spec = spec_by_key.get("file_path")
        if field_spec and field_spec.get("validator") == "file_prompt_validator":
            try:
                validator_tool = get_validator_by_name("file_prompt_validator")
                prompt = field_spec.get("prompt")
                print("Invoking file_prompt_validator with:", draft.get("file_path"), "the prompt being used is:", prompt)
                result = validator_tool.invoke({"pdf_path": draft.get("file_path"), "prompt": prompt})
                
                # Check verdict based on score
                if result.score < 50:
                    verdict = f"The document provided has scored {result.score} which is below the acceptable threshold of 50. Please provide a clearer document."
                    print(verdict)
                    # Add to validation issues and remove the path from draft
                    validation_issues.append({
                        "key": "file_path",
                        "kind": "invalid",
                        "message": verdict,
                        "label": friendly_label(cfg, "file_path")
                    })
                    # Remove file_path from draft since it failed validation
                    draft.pop("file_path", None)
                else:
                    verdict = f"The document has been successfully validated with a score of {result.score}."
                    print(verdict)
            except Exception as e:
                validation_issues.append({
                    "key": "file_path",
                    "kind": "invalid",
                    "message": f"Validation error: {str(e)}",
                    "label": friendly_label(cfg, "file_path")
                })
                # Remove file_path from draft on error
                draft.pop("file_path", None)

    # 1) Extract whatever user provided; merge into draft
    
    if user_text.strip():
        extracted = await extract_fields(cfg, user_text, draft, conversation_history)
        spec_by_key = field_specs(cfg)
        
        for k, v in extracted.items():
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            
            # Check if field has a validator
            field_spec = spec_by_key.get(k)
            if field_spec and field_spec.get("validator"):
                validator_name = field_spec["validator"]
                try:
                    if validator_name == "field_prompt_validator":
                        validator_tool = get_validator_by_name(validator_name)
                        prompt = field_spec.get("prompt")
                        result = validator_tool.invoke({"field": v, "prompt": prompt})
                    elif validator_name == "file_prompt_validator" and extracted.get("file_path"):
                        validator_tool = get_validator_by_name(validator_name)
                        prompt = field_spec.get("prompt")
                        print("Invoking file_prompt_validator with:", extracted.get("file_path"), "the prompt being used is:", prompt, "tool being used:", validator_tool)
                        result = validator_tool.invoke({"pdf_path": extracted.get("file_path"), "prompt": prompt})
                        
                        # Check verdict based on score
                        if result.score < 50:
                            verdict = f"The document provided has scored {result.score} which is below the acceptable threshold of 50. Please provide a clearer document."
                            print(verdict)
                            # Add to validation issues and skip storing the path
                            validation_issues.append({
                                "key": k,
                                "kind": "invalid",
                                "message": verdict,
                                "label": friendly_label(cfg, k)
                            })
                            continue
                        else:
                            verdict = f"The document has been successfully validated with a score of {result.score}."
                            print(verdict)
                    else:   
                        # For standard validators (email, phone, url, etc.)
                        validator_tool = get_validator_by_name(validator_name)
                        
                        # Check if tool has args_schema (phone, url) or takes direct value (email)
                        if hasattr(validator_tool, 'args_schema') and validator_tool.args_schema:
                            # Has schema - pass as dict with the field key
                            result = validator_tool.invoke({k: v})
                        else:
                            # No schema - pass value directly
                            result = validator_tool.invoke(v)
                    
                    # If validation fails, add to issues and skip storing
                    if isinstance(result, dict) and not result.get("valid", True):
                        reason = result.get("reason", "Validation failed")
                        validation_issues.append({
                            "key": k,
                            "kind": "invalid",
                            "message": reason,
                            "label": friendly_label(cfg, k)
                        })
                        continue

                    # If phone validation passed, set phone_verified to True
                    if k == "phone" and validator_name == "phone_validator":
                        draft["phone_verified"] = True

                except Exception as e:
                    validation_issues.append({
                        "key": k,
                        "kind": "invalid",
                        "message": f"Validation error: {str(e)}",
                        "label": friendly_label(cfg, k)
                    })
                    continue

            draft[k] = v

    # 1.5) If inline validation found issues, ask user to correct them
    if validation_issues:
        # Humanize validation errors
        error_details = "\n".join([f"- {issue['label']}: {issue['message']}" for issue in validation_issues])
        system = (
            "You are a friendly assistant helping a user fix validation errors. "
            "Be conversational, polite, and brief. "
            "Explain what needs to be corrected without being technical. "
            "Keep it to 1-2 sentences."
        )
        user_prompt = f"The user provided some information but these fields have issues:\n{error_details}\n\nWrite a friendly message asking them to correct these."
        q = await llm_phrase(cfg.get("model"), system, user_prompt)
        return {
            "status": "needs_user_input",
            "question": q,
            "draft": draft,
            "stage_id": stage_id,
            "tool_events": tool_events,
        }

    # 2) Validate draft (missing + invalid)
    issues_all = validate_draft(cfg, stage_id, draft)
    if issues_all:
        # bundle 2–4 issues for one natural question
        bundle = choose_issue_bundle(issues_all, max_items=4)
        q = await generate_validation_message(cfg, bundle, draft, conversation_history)
        return {
            "status": "needs_user_input",
            "question": q,
            "draft": draft,
            "stage_id": stage_id,
            "tool_events": tool_events,
        }

    # 3) Stage valid -> run required tools
    for tool_name in (st.get("required_tools") or []):
        result = await tool_runner(tool_name, {"agent_id": cfg["agent_id"], "service_type": cfg.get("service_type"), **draft})
        tool_events.append({"tool": tool_name, "result": result})
        if isinstance(result, dict):
            for k in ("lead_id", "request_id", "draft_id", "status"):
                if k in result and result[k]:
                    draft[k] = result[k]

    # Optional tools
    for tool_name in (st.get("optional_tools") or []):
        if not should_run_optional_tool(tool_name, draft):
            continue
        result = await tool_runner(tool_name, {"agent_id": cfg["agent_id"], "service_type": cfg.get("service_type"), **draft})
        tool_events.append({"tool": tool_name, "result": result})

    # 4) Move to next stage
    nxt = next_stage(cfg, stage_id)
    if nxt:
        nxt_issues = validate_draft(cfg, nxt, draft)
        if nxt_issues:
            bundle = choose_issue_bundle(nxt_issues, max_items=4)
            next_q = await generate_validation_message(cfg, bundle, draft, conversation_history)
            q = f"Great — I've captured the initial details. Next I need a bit more:\n{next_q}"
            return {
                "status": "needs_user_input",
                "question": q,
                "draft": draft,
                "stage_id": nxt,
                "tool_events": tool_events,
            }
        return {
            "status": "needs_user_input",
            "question": f"Great — moving to the next step (**{nxt}**). What would you like to add?",
            "draft": draft,
            "stage_id": nxt,
            "tool_events": tool_events,
        }

    # 5) Ready payload
    payload = {"agent_id": cfg["agent_id"], "service_type": cfg.get("service_type"), **draft}

    # Include submission_tools from stage so submit node knows what to execute
    submission_tools = st.get("submission_tools") or []
    payload["submission_tools"] = submission_tools

    natural_preview = await generate_confirmation_message(cfg, payload, conversation_history)
    return {
        "status": "ready",
        "payload": payload,
        "draft": draft,
        "stage_id": stage_id,
        "tool_events": tool_events,
        "natural_preview": natural_preview,
    }
