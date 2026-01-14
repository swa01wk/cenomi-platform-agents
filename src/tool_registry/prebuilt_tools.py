from langchain_core.tools import StructuredTool
from pydantic import BaseModel, EmailStr, HttpUrl, Field
from langchain_openai import ChatOpenAI
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict
import re
import uuid
import json

load_dotenv()
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
        return {"valid": True}
    else:
        return {"valid": False}

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
    return {"valid": False}

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
    url: str = Field(..., description="URL to validate")

def validate_url(url: str) -> Dict:
    try:
        # Try to validate as HttpUrl
        from pydantic import HttpUrl, ValidationError
        
        # Create a temporary model to validate
        class TempModel(BaseModel):
            test_url: HttpUrl
        
        TempModel(test_url=url)
        return {"valid": True}
    except:
        return {"valid": False}

url_validator_tool = StructuredTool.from_function(
    name="url_validator",
    description="Validate URL format",
    func=validate_url,
    args_schema=URLValidatorInput,
)

# =========================================================
# 6 field prompt Validator Tool
# =========================================================
class FieldPromptInput(BaseModel):
    field: str = Field(..., description="The field value to validate")
    prompt: str = Field(..., description="Description of the expected data type/format (e.g., 'email address', 'phone number', 'date in YYYY-MM-DD format')")

class ValidationResult(BaseModel):
    valid: bool = Field(..., description="Whether the field matches the expected format")

def field_prompt_validator_func(field: str, prompt: str) -> Dict:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    validation_prompt = f"""You are a data validation expert. Analyze whether the given field value matches the expected data type or format.

    Field Value: "{field}"
    Expected Format/Type: {prompt}

    Evaluate:
    1. Does the field value match the expected format/type?
    2. Provide a validation score from 0 to 100 (0 = completely invalid, 100 = perfectly valid)
    3. Explain your reasoning

    Respond ONLY with valid JSON in this exact format (no markdown, no code blocks):
    {{"valid": true, "score": 100, "reason": "explanation here"}}"""

    try:
        response = llm.invoke(validation_prompt)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r'```(?:json)?\n?', '', content)
            content = content.strip()
        
        # Parse JSON
        result = json.loads(content)
        
        return {
            "valid": result.get("valid", False),
        }
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"Response content: {response.content}")
        return {
            "valid": False,
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "valid": False,
        }

field_prompt_validator = StructuredTool.from_function(
    name="field_prompt_validator",
    description="Validates whether a field value matches the data type or format specified in the prompt. Takes a field value and a description of the expected format, returns validation score and reasoning.",
    func=field_prompt_validator_func,
    args_schema=FieldPromptInput,
)

# =========================================================
# 7 file prompt Validator Tool
# =========================================================
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from openai import OpenAI
from typing import Dict

client = OpenAI()

class FilePromptInput(BaseModel):
    pdf_path: str = Field(..., description="Path to the PDF document")
    prompt: str = Field(..., description="Prompt to analyze the PDF")

class ValidationResult(BaseModel):
    score: int = Field(..., description="A validation score from 0 to 100")

def file_prompt_validator_func(pdf_path: str, prompt: str) -> ValidationResult:
    
    # Upload the file first
    with open(pdf_path, "rb") as file:
        uploaded_file = client.files.create(
            file=file,
            purpose="user_data"
        )
    
    # Use beta.chat.completions.parse for structured output
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"You are a PDF validation agent. Prompt: {prompt}"},
                    {"type": "file", "file": {"file_id": uploaded_file.id}},
                ]
            }
        ],
        response_format=ValidationResult
    )
    
    print(f"the file_prompt_validator tool response: {response.choices[0].message.parsed}")
    return response.choices[0].message.parsed

file_prompt_validator = StructuredTool.from_function(
    name="file_prompt_validator",
    description="Analyzes a PDF docuement based on a given prompt and returns a validation score.",
    func=file_prompt_validator_func,
    args_schema= FilePromptInput,
)

# =========================================================
# 7 file prompt Validator Tool
# =========================================================
import requests
from typing import Optional

def upload_document(
    file_path: str,
    file_extension: str,
    request_id: str,
    pms_id: str,
    pms_tenant_id: str,
    pms_customer_id: str,
    document_type_id: str,
    process_type_id: str,
    source: str,
    revised_version: str,
    cenomi_contact_name: str,
    cenomi_contact_role: str,
    uri: str = "http://20.224.157.137:8000/v1/documents",
) -> dict:
    print(f"upload documents invoked")
    # Prepare the files for upload
    with open(file_path, 'rb') as f:
        files = {
            'document': (file_path.split('\\')[-1], f, 'application/pdf')
        }
        
        # Prepare the form data
        data = {
            'file_extension': file_extension,
            'request_id': request_id,
            'pms_id': pms_id,
            'pms_tenant_id': pms_tenant_id,
            'pms_customer_id': pms_customer_id,
            'document_type_id': document_type_id,
            'process_type_id': process_type_id,
            'source': source,
            'revised_version': revised_version,
            'cenomi_contact_name': cenomi_contact_name,
            'cenomi_contact_role': cenomi_contact_role
        }
        
        # Make the POST request
        try:
            response = requests.post(uri, files=files, data=data)
            response.raise_for_status()
            print(f"Document uploaded successfully.{response}")
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "error": str(e),
                "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            }
            
upload_document_tool = StructuredTool.from_function(
    name="upload_document",
    description="Uploads a document to the specified URI with associated metadata.",
    func=upload_document,
)
# =========================================================
# 🧠 TOOL REGISTRY (tool_id → tool)
# =========================================================

TOOL_REGISTRY = {
    "tool_517087cd-4f45-4dfb-835d-ec908086baa4": email_validator_tool,
    "tool_9b2d94e3-1c6e-4f59-91a1-61e1cc0a6db1": phone_validator_tool,
    "tool_validate_phone": phone_validator_tool,
    "tool_c78a0e62-b6c1-49cf-9e5b-33f2cde54a77": password_strength_tool,
    "tool_2aee9e7a-7d67-4f13-9f91-bd7bb91e84fd": url_validator_tool,
    "tool_8f4e2d3a-5c6b-4e2f-9f1a-123456789abc": file_prompt_validator,
    "tool_9a7b6c5d-4e3f-2a1b-0c9d-8e7f6a5b4c3d": field_prompt_validator,
    "tool_dfafafad-adfa-adfa-adfa-dfadfadfadfa": upload_document_tool,
}
# =========================================================
# 🔎 Fetch Tool by ID
# =========================================================
def get_tool_by_id(tool_id: str) -> StructuredTool:
    if tool_id not in TOOL_REGISTRY:
        raise ValueError(f"Tool with id '{tool_id}' not found")
    return TOOL_REGISTRY[tool_id]

def get_validator_by_name(tool_name: str) -> StructuredTool:
    for tool in TOOL_REGISTRY.values():
        if tool.name == tool_name:
            return tool
    raise ValueError(f"Tool with name '{tool_name}' not found")

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
    
if __name__ == "__main__":
     print(url_validator_tool.invoke({"url": "h://www.google.com"}))