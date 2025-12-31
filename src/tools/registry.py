from typing import Any, Callable, Dict

from src.tools.lead_enquiry_tools import (
    verify_email_phone, verify_cr_number, create_lead_enquiry,
    upload_documents, validate_documents, final_submit_lead_enquiry
)
from src.tools.general_enquiry_tools import (
    save_draft_general_enquiry, submit_general_enquiry
)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "verify_email_phone": verify_email_phone,
            "verify_cr_number": verify_cr_number,
            "create_lead_enquiry": create_lead_enquiry,
            "upload_documents": upload_documents,
            "validate_documents": validate_documents,
            "final_submit_lead_enquiry": final_submit_lead_enquiry,

            "save_draft_general_enquiry": save_draft_general_enquiry,
            "submit_general_enquiry": submit_general_enquiry,
        }

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str):
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]
