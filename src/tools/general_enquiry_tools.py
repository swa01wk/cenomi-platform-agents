from typing import Dict, Any
import uuid
import asyncio

async def save_draft_general_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Simulate async I/O (database write)
    await asyncio.sleep(0.1)
    return {"ok": True, "draft_id": f"DRAFT-{uuid.uuid4().hex[:8].upper()}", "status": "DRAFT"}

async def submit_general_enquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Simulate async I/O (database write/submission)
    await asyncio.sleep(0.1)
    return {"ok": True, "request_id": f"REQ-{uuid.uuid4().hex[:8].upper()}", "status": "SUBMITTED"}
