from pathlib import Path
import asyncio
# from cenomi_api_client import CenomiAPIClient

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
            if response.status_code >= 400:
                print(f"Error response: {response.text}")
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
        comment: str
    ):
        payload = {
            "tenant_profile_id": tenant_profile_id,
            "lease_code": lease_code,
            "status": status,
            "lease_id": lease_id,
            "title": title,
            "comment": comment
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
        payload = {"first_name":"Kishan","last_name":"Sah","company":"Kishan Company","email":"kishansah1234@gmail.com","brand_name":"Kishan Brand","unit_type":"store","country_code":"+966","phone":"123456789987","country_code_landline":"+966", "company_address":"Kishan Address", "unique_property_id":12,"requested_lease_period":"1_year","requested_min_area":12500,"phone_verified":True}
    #     payload={
    #   "first_name": "Ram",
    #   "last_name": "Shyam",
    #   "email": "ram@gmail.com",
    #   "phone": "9876543210",
    #   "phone_verified": True,
    #   "brand_name": "webx",
    #   "company": "webxx",
    #   "unit_type": "store",
    #   "unique_property_id": 12,
    #   "country_code": "+966",
    #   "country_code_landline": "+966",
    #   "company_address": "delhi",
    #   "requested_lease_period": "1_year",
    #   "requested_min_area": 2300234

    # }
        return await self._post(
            endpoint="/v1/lead-enquiries",
            json=payload,
        )


async def main():
    client = CenomiAPIClient(base_url="http://20.224.157.137:8000")

    # Document upload
    # try:
    #     result = await client.upload_document(
    #         file_path=Path("sample.pdf"),
    #         file_extension="pdf",
    #         source="tenant",
    #         cenomi_contact_name="John Doe",
    #         cenomi_contact_role="Leasing Manager",
    #     )
    #     print("✓ Document upload successful!")
    #     print(f"Response: {result}\n")
    # except Exception as e:
    #     print(f"✗ Document upload failed: {e}\n")

    # Fitout request
    # try:
    #     result = await client.submit_fitout_request(
    #         tenant_profile_id=None,
    #         lease_code="123",
    #         status="DRAFT",
    #         lease_id=None,
    #         title="Fitout Approval",
    #         comment="Initial submission",
    #     )
    #     print("✓ Fitout request successful!")
    #     print(f"Response: {result}\n")
    # except Exception as e:
    #     print(f"✗ Fitout request failed: {e}\n")

    # Lead enquiry
    try:
        result = await client.create_lead_enquiry(
            name="Jane Doe",
            email="jane@example.com",
            phone="+971500000000",
            requested_min_area=100,
            requested_max_area=250,
            requested_rent_period="yearly",
            property_ids=[],
            phone_verified=None,
        )
        print("✓ Lead enquiry successful!")
        print(f"Response: {result}\n")
    except Exception as e:
        print(f"✗ Lead enquiry failed: {e}\n")


asyncio.run(main())
