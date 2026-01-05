from typing import Dict, Any
import uuid


def save_draft_general_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "draft_id": f"DRAFT-{uuid.uuid4().hex[:8].upper()}",
        "status": "DRAFT",
    }


def submit_general_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "request_id": f"REQ-{uuid.uuid4().hex[:8].upper()}",
        "status": "SUBMITTED",
    }
