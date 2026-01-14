from pathlib import Path
from typing import Optional, List

import httpx

class CenomiAPIClient:
    """
    Centralized async client for Cenomi backend APIs.
    """

    def __init__(self, base_url: str = "http://20.224.157.137:8000", timeout: int = 60):
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

        # Debug: print the payload being sent
        if json:
            print(f"Sending to {url}:")
            print(f"Payload: {json}")

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
        service_category: str,
        sub_category: str,
        drawing_type_obj: dict,
        documents_ids: List[str],
        document_type_id: str,
        document_status_list: List[dict],
        title: str,
        comment: str,
        document_id_history: List[dict],
        tenant_profile_id: int,
        lease_code: str,
        status: str,
        lease_id: int,
        mall: str,
        brand_id: int,
        brand_name: str,
        brand: str,
        lease: str,
        lease_brand_mall: str,
        contract_id: int,
        property_id: int,
        company_name: str,
        file: str = "",
    ):
        """
        Submit a fitout request with all individual parameters.
        """
        payload = {
            "service_category": service_category,
            "sub_category": sub_category,
            "payload": {
                "drawing_type_obj": drawing_type_obj,
                "documents_ids": documents_ids,
                "document_type_id": document_type_id,
                "document_status_list": document_status_list,
                "comment": comment,
                "title": title,
                "document_id_history": document_id_history,
            },
            "file": file,
            "mall": mall,
            "mall_ar": "",
            "brand_id": brand_id,
            "brand_name": brand_name,
            "brand": brand,
            "lease": lease,
            "lease_brand_mall": lease_brand_mall,
            "contract_id": contract_id,
            "property_id": property_id,
            "company_name": company_name,
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
        first_name: str,
        last_name: str,
        company: str,
        email: str,
        brand_name: str,
        unit_type: str,
        country_code: str,
        phone: str,
        company_address: str,
        unique_property_id: int,
        requested_lease_period: str,
        requested_min_area: int,
        phone_verified: bool,
        country_code_landline: Optional[str] = None,
    ):
        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "company": company,
            "email": email,
            "brand_name": brand_name,
            "unit_type": unit_type,
            "country_code": country_code,
            "phone": phone,
            "country_code_landline": country_code_landline,
            "company_address": company_address,
            "unique_property_id": unique_property_id,
            "requested_lease_period": requested_lease_period,
            "requested_min_area": requested_min_area,
            "phone_verified": phone_verified,
        }

        return await self._post(
            endpoint="/v1/lead-enquiries",
            json=payload,
        )

if __name__ == "__main__":
    import asyncio
    import os
    from dotenv import load_dotenv

    load_dotenv()

    async def main():
        client = CenomiAPIClient()

        # Test fitout submission with individual arguments
        response = await client.submit_fitout_request(
            service_category="FIT_OUT_DRAWING",
            sub_category="ARCHITECTURAL_DRAWING",
            drawing_type_obj={
                "documentType": "ARCHITECTURAL_DRAWING",
                "documentTypeId": "FIT_ARCH_DRW",
                "document_category_en": "Architectural Drawings",
                "documents": [
                    {
                        "document_name_en": "Architectural Layout",
                        "documentTypeId": "FIT_ARCH_DRW_ARCH_LAYOUT",
                        "status": "uploaded",
                        "comment": None
                    }
                ],
                "srDetails": {}
            },
            documents_ids=["65556a63-ba39-4fa6-90fa-8ca902f4d166"],
            document_type_id="FIT_ARCH_DRW",
            document_status_list=[
                {
                    "document_name_en": "Architectural Layout",
                    "documentTypeId": "FIT_ARCH_DRW_ARCH_LAYOUT",
                    "status": "uploaded",
                    "comment": None
                }
            ],
            title="Request for Architectural Drawings",
            comment="Test service request with newly uploaded document",
            document_id_history=[
                {
                    "document_ids": ["65556a63-ba39-4fa6-90fa-8ca902f4d166"],
                    "docNames": [
                        {
                            "document_name_en": "Architectural Layout",
                            "documentTypeId": "FIT_ARCH_DRW_ARCH_LAYOUT",
                            "status": "uploaded",
                            "comment": None
                        }
                    ]
                }
            ],
            tenant_profile_id=2153,
            lease_code="t0108240",
            status="SUBMITTED",
            lease_id=96225,
            mall="Nakheel Mall",
            brand_id=44249,
            brand_name="Flormar Trap",
            brand="Flormar Trap",
            lease="t0108240",
            lease_brand_mall="t0108240-Flormar Trap-Nakheel Mall",
            contract_id=96225,
            property_id=47,
            company_name="2153",
            file=""
        )
        print("Fitout Submission Response:", response)

    asyncio.run(main())