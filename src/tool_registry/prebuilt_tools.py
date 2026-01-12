from langchain_core.tools import StructuredTool
from pydantic import BaseModel, EmailStr, HttpUrl, Field
from typing import Dict
import re
import uuid

# =========================================================
# 🔧 Utility: Generate Tool ID
# =========================================================

def generate_tool_id() -> str:
    return f"tool_{uuid.uuid4()}"


# =========================================================
# 1️⃣ Email Validator Tool
# =========================================================
def validate_email(email: str) -> Dict:
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_pattern, email):
        return {"valid": True, "reason": "Email format is correct"}
    else:
        return {"valid": False, "reason": "Email format is not correct"}

email_validator_tool = StructuredTool.from_function(
    name="email_validator",
    description="Validate whether an email address is valid and non-disposable",
    func=validate_email,
)


# =========================================================
# 2️⃣ Phone Number Validator (India)
# =========================================================

class PhoneValidatorInput(BaseModel):
    phone: str = Field(..., description="Indian phone number")

def validate_phone(phone: str) -> Dict:
    if re.match(r"^[6-9]\d{9}$", phone):
        return {"valid": True}
    return {"valid": False, "reason": "Invalid Indian phone number"}

phone_validator_tool = StructuredTool.from_function(
    name="phone_validator",
    description="Validate Indian phone numbers",
    func=validate_phone,
    args_schema=PhoneValidatorInput,
)


# =========================================================
# 3️⃣ Password Strength Checker
# =========================================================

class PasswordStrengthInput(BaseModel):
    password: str = Field(..., description="Password to evaluate")

def check_password_strength(password: str) -> Dict:
    rules = {
        "length": len(password) >= 8,
        "uppercase": bool(re.search(r"[A-Z]", password)),
        "lowercase": bool(re.search(r"[a-z]", password)),
        "digit": bool(re.search(r"\d", password)),
        "special_char": bool(re.search(r"[!@#$%^&*]", password)),
    }

    score = sum(rules.values())

    return {
        "strength_score": score,
        "strong": score >= 4,
        "rules": rules
    }

password_strength_tool = StructuredTool.from_function(
    name="password_strength_checker",
    description="Evaluate password strength",
    func=check_password_strength,
    args_schema=PasswordStrengthInput,
)


# =========================================================
# 5️⃣ URL Validator Tool
# =========================================================

class URLValidatorInput(BaseModel):
    url: HttpUrl = Field(..., description="URL to validate")

def validate_url(url: HttpUrl) -> Dict:
    return {"valid": True, "url": str(url)}

url_validator_tool = StructuredTool.from_function(
    name="url_validator",
    description="Validate URL format",
    func=validate_url,
    args_schema=URLValidatorInput,
)

# =========================================================
# 🧠 TOOL REGISTRY (tool_id → tool)
# =========================================================

TOOL_REGISTRY = {
    "tool_517087cd-4f45-4dfb-835d-ec908086baa4": email_validator_tool,
    "tool_9b2d94e3-1c6e-4f59-91a1-61e1cc0a6db1": phone_validator_tool,
    "tool_c78a0e62-b6c1-49cf-9e5b-33f2cde54a77": password_strength_tool,
    "tool_2aee9e7a-7d67-4f13-9f91-bd7bb91e84fd": url_validator_tool,
}
# =========================================================
# 🔎 Fetch Tool by ID
# =========================================================
def get_tool_by_id(tool_id: str) -> StructuredTool:
    if tool_id not in TOOL_REGISTRY:
        raise ValueError(f"Tool with id '{tool_id}' not found")
    return TOOL_REGISTRY[tool_id]

# =========================================================
# 📤 Export tool metadata (for JSON/db storage)
# =========================================================

def export_tool_metadata():
    return [
        {
            "tool_id": tool.tool_id,
            "name": tool.name,
            "description": tool.description,
        }
        for tool in TOOL_REGISTRY.values()
    ]