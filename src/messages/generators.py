"""
Message generation functions for conversational AI responses.

This module contains LLM-powered message generators that create
context-aware, friendly, and conversational messages throughout
the agent interaction flow.
"""

import os
import json
import asyncio
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# OpenAI rate limiting: max 5 concurrent LLM calls
OPENAI_SEMAPHORE = asyncio.Semaphore(5)


async def generate_greeting(session_context: Dict[str, Any]) -> str:
    """
    Generate a friendly, contextual greeting for the user.

    Args:
        session_context: Dictionary containing:
            - is_new_session (bool): Whether this is a new conversation
            - last_submission (Optional[str]): Timestamp of last submission
            - previous_intents (List[str]): List of previous agent IDs used

    Returns:
        Friendly greeting message as a string
    """
    async with OPENAI_SEMAPHORE:
        llm = ChatOpenAI(model=MODEL_DEFAULT, temperature=0.7)

        is_new = session_context.get("is_new_session", True)
        prev_intents = session_context.get("previous_intents", [])

        prompt = f"""Generate a warm, friendly greeting for a user contacting Cenomi Platform support.

SESSION CONTEXT:
- New session: {is_new}
- Previous interactions: {len(prev_intents)}

GUIDELINES:
- Be welcoming and professional
- Keep it brief (1-2 sentences)
- Vary the greeting slightly each time (don't always use the same phrase)
- If returning user, acknowledge it warmly ("Welcome back!")
- Sound natural and conversational

Generate only the greeting message, nothing else."""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()


async def generate_agent_acknowledgement(
    agent_config: Dict[str, Any],
    user_intent: str,
    confidence: float,
    conversation_history: List[Dict[str, str]]
) -> str:
    """
    Generate a friendly acknowledgement when routing to a specific agent.

    Args:
        agent_config: Full agent configuration from agents.json
        user_intent: Original user message expressing intent
        confidence: Confidence score (0.0-1.0) from intent classification
        conversation_history: Recent conversation context

    Returns:
        Acknowledgement message as a string
    """
    async with OPENAI_SEMAPHORE:
        llm = ChatOpenAI(model=agent_config.get("model", MODEL_DEFAULT), temperature=0.7)

        # Build context from recent history
        history_context = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in conversation_history[-4:]
        ]) if conversation_history else "First interaction"

        agent_name = agent_config.get("name", "Assistant")
        agent_description = agent_config.get("description", "")
        system_prompt = agent_config.get("system_prompt", "")

        # Get field metadata to include choices in prompts
        field_metadata = {f["key"]: f for f in agent_config.get("fields", [])}
        first_required_fields = []
        if agent_config.get("stages"):
            first_stage = agent_config["stages"][0]
            required_keys = first_stage.get("required_fields", [])[:3]  # First 3 fields
            for key in required_keys:
                field_def = field_metadata.get(key, {})
                field_info = {
                    "key": key,
                    "label": field_def.get("label", key)
                }
                if field_def.get("choices"):
                    field_info["choices"] = field_def["choices"]
                if field_def.get("hint"):
                    field_info["hint"] = field_def["hint"]
                first_required_fields.append(field_info)

        prompt = f"""You are a {agent_name} assistant.

YOUR ROLE/PURPOSE: {agent_description}

SYSTEM INSTRUCTIONS: {system_prompt}

USER'S REQUEST: "{user_intent}"

CONVERSATION HISTORY:
{history_context}

FIRST FIELDS YOU NEED TO COLLECT:
{json.dumps(first_required_fields, indent=2)}

CRITICAL INSTRUCTIONS:
1. **READ THE USER'S MESSAGE** - If they already provided some info (like their name, company, etc.), acknowledge it
2. If they're asking a question (like "what options are available?"), ANSWER IT
3. Then ask for what you need - start with the first few fields
4. Be conversational and natural - respond to what they actually said
5. If asking about a choice field, mention the available options

Examples of GOOD responses:
- User: "I want to lease a shop" → "Got it! What's your name and company?"
- User: "Hi, I'm John from ABC Corp, looking to lease" → "Perfect, John from ABC Corp. What type of unit interests you - Kiosk, Shop, Restaurant, Office, or Other?"
- User: "What unit types do you have?" → "We have Kiosk, Shop, Restaurant, Office, or Other. Which one are you interested in? Also, what's your name?"

AVOID robotic patterns:
- ❌ "I'd be happy to help you with that!"
- ❌ "Great! I can help you..."
- ❌ "To get started, I'll need..."
- ❌ Ignoring what they said and just asking for fields

Generate only the acknowledgement message (1-2 sentences):"""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()


async def generate_validation_message(
    agent_config: Dict[str, Any],
    issues: List[Dict[str, Any]],
    draft: Dict[str, Any],
    conversation_history: List[Dict[str, str]]
) -> str:
    """
    Generate a friendly message asking for missing/invalid information.

    Args:
        agent_config: Agent configuration
        issues: List of validation issues [{key, kind, message, label}]
        draft: Current draft state
        conversation_history: Recent messages for context

    Returns:
        Validation message as a string
    """
    async with OPENAI_SEMAPHORE:
        llm = ChatOpenAI(model=agent_config.get("model", MODEL_DEFAULT), temperature=0.7)

        # Group issues by kind
        missing = [i for i in issues if i.get("kind") == "missing"]
        invalid = [i for i in issues if i.get("kind") == "invalid"]

        # Build field metadata
        field_metadata = {f["key"]: f for f in agent_config.get("fields", [])}

        # Build context of what's already collected WITH VALUES (to prevent hallucination)
        collected_items = []
        for k, v in draft.items():
            if v in (None, "", []):
                continue
            field_def = field_metadata.get(k, {})
            label = field_def.get("label", k.replace("_", " ").title())
            # Truncate long values for readability
            if isinstance(v, str) and len(v) > 100:
                display_val = v[:100] + "..."
            elif isinstance(v, list):
                display_val = f"{len(v)} item(s)"
            elif isinstance(v, dict):
                display_val = "(object)"
            else:
                display_val = str(v)
            collected_items.append(f"- {label}: {display_val}")

        collected_summary = "\n".join(collected_items) if collected_items else "Nothing yet"

        agent_name = agent_config.get("name", "Assistant")
        agent_description = agent_config.get("description", "")
        system_prompt = agent_config.get("system_prompt", "")

        # Get last user message for context (FIX: use -1 for last message, not -2)
        last_message = conversation_history[-1]["content"] if len(conversation_history) >= 1 else "First interaction"

        missing_with_choices = []
        for issue in missing:
            key = issue.get("key")
            field_def = field_metadata.get(key, {})
            choices = field_def.get("choices")
            hint = field_def.get("hint")

            item = {
                "field": issue.get("label") or key,
                "description": issue.get("message", "")
            }
            if choices:
                item["available_options"] = choices
            if hint:
                item["hint"] = hint

            missing_with_choices.append(item)

        prompt = f"""You are collecting information for a {agent_name}.

YOUR ROLE/PURPOSE: {agent_description}

SYSTEM INSTRUCTIONS: {system_prompt}

WHAT YOU'VE ALREADY COLLECTED (field name: value):
{collected_summary}

WHAT YOU STILL NEED:

Missing information:
{json.dumps(missing_with_choices, indent=2)}

Invalid information:
{json.dumps([{"field": i.get("label") or i.get("key"), "issue": i.get("message", "")} for i in invalid], indent=2)}

USER'S LAST MESSAGE:
"{last_message}"

CRITICAL INSTRUCTIONS:
1. **READ THE USER'S MESSAGE CAREFULLY** - If they're asking a question, ANSWER IT FIRST
2. If they ask "what options do I have" or "what are the choices" for a field with available_options, LIST THOSE OPTIONS
3. Then naturally transition to asking for what you need
4. Be conversational and responsive - don't ignore what they said
5. If they provided some info, acknowledge it sometimes briefly before asking for more
6. Sound like a real person having a conversation, not a form-filling robot

Examples of GOOD responses:
- User asks "what unit types are there?" → "We have Kiosk, Shop, Restaurant, Office, or Other. Which one interests you?"
- User provides partial info → "Got it, Web-X. What type of unit are you looking for - Kiosk, Shop, Restaurant, Office, or Other?"
- User asks about budget → "The rent budget is how much you're willing to pay. What's your budget in SAR?"

AVOID being robotic:
- ❌ Don't ignore user questions
- ❌ Don't just list missing fields without context
- ❌ Don't use phrases like "To assist you better" or "Looking forward to your response"

Generate only the message:"""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()


async def generate_confirmation_message(
    agent_config: Dict[str, Any],
    payload: Dict[str, Any],
    conversation_history: List[Dict[str, str]]
) -> str:
    """
    Generate a friendly confirmation message showing what was collected.

    Args:
        agent_config: Agent configuration
        payload: Complete collected data
        conversation_history: Full conversation for context

    Returns:
        Confirmation message as a string
    """
    async with OPENAI_SEMAPHORE:
        llm = ChatOpenAI(model=agent_config.get("model", MODEL_DEFAULT), temperature=0.7)

        # Extract field metadata for better labels
        field_metadata = {f["key"]: f for f in agent_config.get("fields", [])}

        # Build human-readable summary
        summary_items = []
        for key, value in payload.items():
            if key in ["agent_id", "service_type"]:
                continue

            field_def = field_metadata.get(key, {})
            label = field_def.get("label", key.replace("_", " ").title())

            # Format value appropriately
            if isinstance(value, list):
                formatted_value = f"{len(value)} item(s)"
            elif isinstance(value, dict):
                formatted_value = str(value)
            else:
                formatted_value = str(value)

            summary_items.append(f"- {label}: {formatted_value}")

        summary_text = "\n".join(summary_items)
        agent_name = agent_config.get("name", "Assistant")
        turn_count = len(conversation_history)

        prompt = f"""You are completing a {agent_name} submission.

INFORMATION COLLECTED:
{summary_text}

CONVERSATION CONTEXT:
The user has been chatting with you for {turn_count} messages.

Generate a confirmation message that:
1. Thanks the user warmly
2. Presents a natural language summary (not a bullet list - be conversational!)
3. Asks them to confirm if everything looks correct
4. Mentions what happens next after confirmation
5. Sounds friendly and professional (2-4 sentences)

Example confirmation messages:
- "Perfect! Let me confirm - you're Ahmad from ABC Company, and you're interested in leasing a retail space. Your contact details are ahmad@abc.com and +966501234567. Does everything look correct? Once you confirm, I'll submit this to our leasing team."
- "Great! I have all your details: you're interested in opening a shop at our mall. Should I go ahead and submit this enquiry?"

Generate only the confirmation message:"""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()


async def generate_submission_success_message(
    agent_config: Dict[str, Any],
    submission_result: Dict[str, Any],
    conversation_history: List[Dict[str, str]]
) -> str:
    """
    Generate a friendly submission success message with next steps.

    Args:
        agent_config: Agent configuration
        submission_result: Result from submission tool (includes IDs, status, etc.)
        conversation_history: Full conversation for context

    Returns:
        Success message as a string
    """
    async with OPENAI_SEMAPHORE:
        llm = ChatOpenAI(model=agent_config.get("model", MODEL_DEFAULT), temperature=0.7)

        # Extract useful info from result
        lead_id = submission_result.get("lead_id") or submission_result.get("request_id")
        status = submission_result.get("status", "submitted")
        agent_name = agent_config.get("name", "Assistant")
        service_type = agent_config.get("service_type", "enquiry")

        prompt = f"""You are confirming a successful {agent_name} submission.

SUBMISSION DETAILS:
- Reference ID: {lead_id or "Generated"}
- Status: {status}
- Service Type: {service_type}

Generate a success message that:
1. Celebrates the completion warmly
2. Provides the reference ID if available
3. Explains next steps (what the user can expect)
4. Sounds professional but friendly (2-3 sentences)
5. Do NOT ask if they need anything else (that comes in a separate message)

Examples:
- "All set! Your enquiry has been submitted successfully (Reference: #{lead_id}). Our leasing team will review it and get back to you within 2 business days."
- "Perfect! Your submission is complete. You'll receive a confirmation email shortly, and our team will be in touch soon."

Generate only the success message:"""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()


async def generate_continue_prompt(
    last_agent_config: Optional[Dict[str, Any]],
    conversation_history: List[Dict[str, str]]
) -> str:
    """
    Generate a friendly prompt to continue helping after submission.

    Args:
        last_agent_config: Config of agent that just completed (can be None)
        conversation_history: Full conversation history

    Returns:
        Continuation prompt as a string
    """
    async with OPENAI_SEMAPHORE:
        llm = ChatOpenAI(model=MODEL_DEFAULT, temperature=0.7)

        agent_name = last_agent_config.get("name", "service") if last_agent_config else "service"

        prompt = f"""The user just completed a {agent_name} submission with Cenomi Platform.

Generate a brief, friendly message that:
1. Offers to help with something else
2. Varies the phrasing (not always "Do you need anything else?")
3. Is warm and inviting (1 sentence)

Examples:
- "Is there anything else I can help you with today?"
- "Happy to help with anything else you need!"
- "What else can I assist you with?"

Generate only the continuation prompt:"""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()


# Helper function to build message history for LLM context
def build_message_history(
    conversation_history: List[Dict[str, str]],
    max_turns: int = 6
) -> List[Any]:
    """
    Build LangChain message objects from conversation history.

    Args:
        conversation_history: List of message dicts with 'role' and 'content'
        max_turns: Maximum number of messages to include (default: 6 = 3 exchanges)

    Returns:
        List of LangChain message objects (HumanMessage, AIMessage)
    """
    messages = []

    # Take last N messages for context
    recent_history = conversation_history[-max_turns:] if conversation_history else []

    for msg in recent_history:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    return messages
