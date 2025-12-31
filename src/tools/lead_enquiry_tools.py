from typing import Dict, Any, List
import uuid

def verify_email_phone(payload: Dict[str, Any]) -> Dict[str, Any]:
    # In real: OTP/email verification, etc.
    return {"ok": True, "verified": True}

def verify_cr_number(payload: Dict[str, Any]) -> Dict[str, Any]:
    cr = payload.get("cr_number")
    if not cr:
        return {"ok": True, "skipped": True}
    # Real: external CR verification
    return {"ok": True, "cr_verified": True}

def create_lead_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Real: write to DB with status NEW_ENQUIRY
    return {"ok": True, "lead_id": f"LEAD-{uuid.uuid4().hex[:8].upper()}", "status": "NEW_ENQUIRY"}

def upload_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    # In real: store docs in S3; here docs are already references
    docs: List[str] = payload.get("documents") or []
    return {"ok": True, "uploaded": docs}

def validate_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    docs: List[str] = payload.get("documents") or []
    if not docs:
        return {"ok": False, "error": "No documents found"}
    # Real: doc validation rules
    return {"ok": True, "validated": True, "count": len(docs)}

def final_submit_lead_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Real: status SUBMITTED
    return {"ok": True, "status": "SUBMITTED"}
