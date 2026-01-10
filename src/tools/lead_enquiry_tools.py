from typing import Dict, Any, List
import uuid
import asyncio

async def verify_email_phone(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Simulate async I/O (email/OTP verification API call)
    await asyncio.sleep(0.1)
    # In real: OTP/email verification, etc.
    return {"ok": True, "verified": True}

async def verify_cr_number(payload: Dict[str, Any]) -> Dict[str, Any]:
    cr = payload.get("cr_number")
    if not cr:
        return {"ok": True, "skipped": True}
    # Simulate async I/O (external CR verification service)
    await asyncio.sleep(0.1)
    # Real: external CR verification
    return {"ok": True, "cr_verified": True}

async def create_lead_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Simulate async I/O (database write)
    await asyncio.sleep(0.1)
    # Real: write to DB with status NEW_ENQUIRY
    return {"ok": True, "lead_id": f"LEAD-{uuid.uuid4().hex[:8].upper()}", "status": "NEW_ENQUIRY"}

async def upload_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Simulate async I/O (S3 upload)
    await asyncio.sleep(0.1)
    # In real: store docs in S3; here docs are already references
    docs: List[str] = payload.get("documents") or []
    return {"ok": True, "uploaded": docs}

async def validate_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Simulate async I/O (document validation service)
    await asyncio.sleep(0.1)
    docs: List[str] = payload.get("documents") or []
    if not docs:
        return {"ok": False, "error": "No documents found"}
    # Real: doc validation rules
    return {"ok": True, "validated": True, "count": len(docs)}

async def final_submit_lead_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Simulate async I/O (database update)
    await asyncio.sleep(0.1)
    # Real: status SUBMITTED
    return {"ok": True, "status": "SUBMITTED"}
