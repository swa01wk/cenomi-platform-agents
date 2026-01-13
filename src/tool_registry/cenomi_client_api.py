from pathlib import Path
from typing import Optional, List

import httpx


class CenomiAPIClient:
    """
    Centralized async client for Cenomi backend APIs.
    """

    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _post(
        self,
        endpoint: str,
        *,
        json: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
        headers: dict | None = None,
    ):
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=json,
                data=data,
                files=files,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    # ---------------------------------------------------------
    # 1. Document Upload
    # ---------------------------------------------------------
    async def upload_document(
        self,
        file_path: Path,
        file_extension: str,
        source: str,
        revised_version: Optional[str] = None,
        cenomi_contact_name: Optional[str] = None,
        cenomi_contact_role: Optional[str] = None,
    ):
        files = {
            "document": (file_path.name, file_path.open("rb")),
        }

        data = {
            "file_extension": file_extension,
            "source": source,
            "revised_version": revised_version or "",
            "cenomi_contact_name": cenomi_contact_name or "",
            "cenomi_contact_role": cenomi_contact_role or "",
        }

        return await self._post(
            endpoint="/v1/documents",
            data=data,
            files=files,
        )

    # ---------------------------------------------------------
    # 2. Fitout Submission
    # ---------------------------------------------------------
    async def submit_fitout_request(
        self,
        tenant_profile_id: Optional[int],
        lease_code: str,
        status: str,
        lease_id: Optional[int],
        title: str,
        comment: str,
    ):
        payload = {
            "tenant_profile_id": tenant_profile_id,
            "lease_code": lease_code,
            "status": status,
            "lease_id": lease_id,
            "title": title,
            "comment": comment,
        }

        return await self._post(
            endpoint="/v1/service-requests",
            json=payload,
        )

    # ---------------------------------------------------------
    # 3. Lead Enquiry
    # ---------------------------------------------------------
    async def create_lead_enquiry(
        self,
        name: str,
        email: str,
        phone: str,
        requested_min_area: Optional[int],
        requested_max_area: Optional[int],
        requested_rent_period: str,
        property_ids: List[int],
        phone_verified: Optional[bool],
    ):
        payload = {
            "name": name,
            "email": email,
            "phone": phone,
            "requested_min_area": requested_min_area,
            "requested_max_area": requested_max_area,
            "requested_rent_period": requested_rent_period,
            "property_ids": property_ids,
            "phone_verified": phone_verified,
        }

        return await self._post(
            endpoint="/v1/lead-enquiries",
            json=payload,
        )
