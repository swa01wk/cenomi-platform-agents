"""
Custom Functions Registry

This module serves as a central registry for all custom function tools.
Functions can be synchronous or asynchronous and should follow the signature:
    func(payload: Dict[str, Any]) -> Dict[str, Any]

All functions registered here can be used as custom_function type tools
in the tool registry.
"""

from typing import Dict, Any, Callable, List
import uuid
import asyncio
import os

try:
    from src.tool_registry.cenomi_client_api import CenomiAPIClient
except ImportError:
    from cenomi_client_api import CenomiAPIClient

# Cenomi API base URL
CENOMI_API_BASE_URL = os.getenv("CENOMI_API_BASE_URL", "http://20.224.157.137:8000")


# ============================================================================
# LEAD ENQUIRY TOOLS
# ============================================================================

async def verify_email_phone(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Verify email and phone number through OTP verification."""
    # Simulate async I/O (email/OTP verification API call)
    await asyncio.sleep(0.1)
    # In real: OTP/email verification, etc.
    return {"ok": True, "verified": True}


async def verify_cr_number(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Verify CR (Commercial Registration) number."""
    cr = payload.get("cr_number")
    if not cr:
        return {"ok": True, "skipped": True}
    # Simulate async I/O (external CR verification service)
    await asyncio.sleep(0.1)
    # Real: external CR verification
    return {"ok": True, "cr_verified": True}


async def create_lead_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create lead enquiry via Cenomi API."""
    try:
        client = CenomiAPIClient(base_url=CENOMI_API_BASE_URL)

        # Call the API with the required fields from payload
        result = await client.create_lead_enquiry(
            first_name=payload.get("first_name"),
            last_name=payload.get("last_name"),
            company=payload.get("company"),
            email=payload.get("email"),
            brand_name=payload.get("brand_name"),
            unit_type=payload.get("unit_type"),
            country_code=payload.get("country_code"),
            phone=payload.get("phone"),
            company_address=payload.get("company_address"),
            unique_property_id=payload.get("unique_property_id"),
            requested_lease_period=payload.get("requested_lease_period"),
            requested_min_area=payload.get("requested_min_area"),
            phone_verified=payload.get("phone_verified"),
            country_code_landline=payload.get("country_code_landline"),
        )
        # print(f"{result=}")
        # Expected response: {'success': True, 'data': {'lead_enquiry_id': '...', 'lead_enquiry_number': ..., 'lead_enquiry_code': '...'}}
        if result.get("success"):
            data = result.get("data", {})
            return {
                "ok": True,
                "lead_id": data.get("lead_enquiry_id"),
                "lead_enquiry_code": data.get("lead_enquiry_code"),
                "lead_enquiry_number": data.get("lead_enquiry_number"),
                "status": "NEW_ENQUIRY"
            }
        else:
            return {
                "ok": False,
                "error": result.get("message", "Unknown error"),
                "status": "ERROR"
            }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "status": "ERROR"
        }


async def upload_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Upload documents to storage."""
    # Simulate async I/O (S3 upload)
    await asyncio.sleep(0.1)
    # In real: store docs in S3; here docs are already references
    docs: List[str] = payload.get("documents") or []
    return {"ok": True, "uploaded": docs}


async def validate_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate uploaded documents."""
    # Simulate async I/O (document validation service)
    await asyncio.sleep(0.1)
    docs: List[str] = payload.get("documents") or []
    if not docs:
        return {"ok": False, "error": "No documents found"}
    # Real: doc validation rules
    return {"ok": True, "validated": True, "count": len(docs)}


async def final_submit_lead_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Final submission of lead enquiry."""
    # Simulate async I/O (database update)
    await asyncio.sleep(0.1)
    # Real: status SUBMITTED
    return {"ok": True, "status": "SUBMITTED"}


# ============================================================================
# FITOUT SUBMISSION TOOLS
# ============================================================================

async def submit_fitout_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Submit fitout architectural drawing request via Cenomi API."""
    try:
        client = CenomiAPIClient(base_url=CENOMI_API_BASE_URL)

        # Parse drawing_type_obj from string to dict if needed
        drawing_type_obj = payload.get("drawing_type_obj")
        if isinstance(drawing_type_obj, str):
            import json
            drawing_type_obj = json.loads(drawing_type_obj)

        # Build document_status_list from drawing_type_obj documents
        document_status_list = drawing_type_obj.get("documents", [])

        # Get document_ids (could be string or list)
        documents_ids = payload.get("documents_ids", [])
        if isinstance(documents_ids, str):
            documents_ids = [documents_ids]

        # Build document_id_history
        document_id_history = [{
            "document_ids": documents_ids,
            "docNames": document_status_list
        }]

        # Construct lease_brand_mall
        lease_code = payload.get("lease_code", "")
        brand_name = payload.get("brand_name", "")
        mall = payload.get("mall", "")
        lease_brand_mall = f"{lease_code}-{brand_name}-{mall}"

        result = await client.submit_fitout_request(
            service_category=payload.get("service_category"),
            sub_category=payload.get("sub_category"),
            drawing_type_obj=drawing_type_obj,
            documents_ids=documents_ids,
            document_type_id=payload.get("document_type_id"),
            document_status_list=document_status_list,
            title=payload.get("title", "Request for Architectural Drawings"),
            comment=payload.get("comment", ""),
            document_id_history=document_id_history,
            tenant_profile_id=int(payload.get("tenant_profile_id", 0)),
            lease_code=lease_code,
            status=payload.get("status", "SUBMITTED"),
            lease_id=int(payload.get("lease_id", 0)),
            mall=mall,
            brand_id=int(payload.get("brand_id", 0)),
            brand_name=brand_name,
            brand=brand_name,
            lease=lease_code,
            lease_brand_mall=lease_brand_mall,
            contract_id=int(payload.get("contract_id", 0)),
            property_id=int(payload.get("property_id", 0)),
            company_name=str(payload.get("tenant_profile_id", "")),
            file=""
        )

        if result.get("success"):
            data = result.get("data", {})
            return {
                "ok": True,
                "request_id": data.get("service_request_id"),
                "status": "SUBMITTED"
            }
        else:
            return {
                "ok": False,
                "error": result.get("message", "Unknown error"),
                "status": "ERROR"
            }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "status": "ERROR"
        }


# ============================================================================
# GENERAL ENQUIRY TOOLS
# ============================================================================

async def save_draft_general_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Save draft of general enquiry."""
    # Simulate async I/O (database write)
    await asyncio.sleep(0.1)
    return {
        "ok": True,
        "draft_id": f"DRAFT-{uuid.uuid4().hex[:8].upper()}",
        "status": "DRAFT"
    }

async def submit_general_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Submit general enquiry."""
    # Simulate async I/O (database write/submission)
    await asyncio.sleep(0.1)
    return {
        "ok": True,
        "request_id": f"REQ-{uuid.uuid4().hex[:8].upper()}",
        "status": "SUBMITTED"
    }

# ============================================================================
# CUSTOM FUNCTIONS REGISTRY
# ============================================================================

# Central registry mapping function_name -> callable
# The function_name must match the "function" field in the tool definition JSON
CUSTOM_FUNCTIONS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    # Lead enquiry tools
    "verify_email_phone": verify_email_phone,
    "verify_cr_number": verify_cr_number,
    "create_lead_enquiry": create_lead_enquiry,
    "upload_documents": upload_documents,
    "validate_documents": validate_documents,
    "final_submit_lead_enquiry": final_submit_lead_enquiry,

    # Fitout submission tools
    "submit_fitout_request": submit_fitout_request,

    # General enquiry tools
    "save_draft_general_enquiry": save_draft_general_enquiry,
    "submit_general_enquiry": submit_general_enquiry,
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def register_custom_function(name: str, func: Callable) -> None:
    """
    Register a new custom function dynamically.

    Args:
        name: Function name to register
        func: Callable that takes Dict[str, Any] and returns Dict[str, Any]
    """
    CUSTOM_FUNCTIONS[name] = func


def list_custom_functions() -> list:
    """List all registered custom function names."""
    return list(CUSTOM_FUNCTIONS.keys())


def get_custom_function(name: str) -> Callable:
    """
    Get a custom function by name.

    Args:
        name: Function name

    Returns:
        The function callable

    Raises:
        KeyError: If function name not found
    """
    if name not in CUSTOM_FUNCTIONS:
        raise KeyError(f"Custom function not found: {name}")
    return CUSTOM_FUNCTIONS[name]

if __name__ == "__main__":
    response = asyncio.run(upload_documents(
        {
        "file_path": r"C:\github_work\cenomi-platform-agents\test_doc.pdf",
        "file_extension": "pdf",
        "request_id": "test-request-123",
        "pms_id": "96225",
        "pms_tenant_id": "t0108240",
        "pms_customer_id": "customer-code",
        "document_type_id": "FIT_ARCH_DRW",
        "process_type_id": "2000",
        "source": "tenant_central",
        "revised_version": "no",
        "cenomi_contact_name": "Test Contact",
        "cenomi_contact_role": "Test Role"
    }
    ))
    
    print(response)