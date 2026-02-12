"""HubSpot sync job for pulling closed deals with company tech stack data."""

import json
import logging
from typing import Any

import httpx

from jobs.base_job import BaseJob
from models.base import get_db_session
from models.oauth_credential import OAuthCredential
from services.encryption_service import get_encryption_service

logger = logging.getLogger(__name__)

HUBSPOT_API_BASE = "https://api.hubapi.com"


class HubSpotSyncJob(BaseJob):
    """
    Sync closed deals from HubSpot with associated company tech stack data.
    """

    JOB_NAME = "HubSpot Sync"
    JOB_DESCRIPTION = (
        "Sync closed deals from HubSpot including deal amount and "
        "associated company tech stack information."
    )
    REQUIRED_PARAMS = ["credential_id"]
    OPTIONAL_PARAMS = ["limit"]

    def _load_credentials(self, credential_id: str) -> str:
        """Load and decrypt HubSpot credentials from database."""
        with get_db_session() as session:
            credential = (
                session.query(OAuthCredential)
                .filter(OAuthCredential.credential_id == credential_id)
                .first()
            )

            if not credential:
                raise ValueError(f"Credential not found: {credential_id}")

            if credential.provider != "hubspot":
                raise ValueError(
                    f"Credential {credential_id} is not a HubSpot credential"
                )

            # Decrypt the token
            encryption_service = get_encryption_service()
            decrypted = encryption_service.decrypt(credential.encrypted_token)
            token_data = json.loads(decrypted)

            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError(f"No access_token found in credential {credential_id}")

            logger.info(f"Loaded HubSpot credentials: {credential.credential_name}")
            return access_token

    async def _execute_job(self) -> dict[str, Any]:
        """Execute HubSpot sync job."""
        self.validate_params()

        credential_id = self.params.get("credential_id")
        limit = self.params.get("limit", 100)

        logger.info("Starting HubSpot sync for closed deals")

        # Load credentials from database
        access_token = self._load_credentials(credential_id)

        # Use Bearer token auth
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch closed deals
            deals = await self._fetch_closed_deals(client, headers, limit)
            logger.info(f"Found {len(deals)} closed deals")

            # Enrich with company data
            enriched_deals = []
            for deal in deals:
                enriched = await self._enrich_deal_with_company(client, headers, deal)
                enriched_deals.append(enriched)
                logger.info(
                    f"Deal: {enriched['deal_name']} | "
                    f"Amount: ${enriched['amount']:,.2f} | "
                    f"Company: {enriched.get('company_name', 'N/A')}"
                )

        return {
            "status": "success",
            "records_processed": len(enriched_deals),
            "records_success": len(enriched_deals),
            "records_failed": 0,
            "deals": enriched_deals,
        }

    async def _fetch_closed_deals(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        limit: int,
    ) -> list[dict]:
        """Fetch closed won deals from HubSpot."""
        url = f"{HUBSPOT_API_BASE}/crm/v3/objects/deals"

        params = {
            "limit": min(limit, 100),
            "properties": "dealname,amount,closedate,dealstage,pipeline",
            "associations": "companies",
        }

        all_deals = []
        after = None

        while len(all_deals) < limit:
            if after:
                params["after"] = after

            response = await client.get(url, headers=headers, params=params)

            if response.status_code != 200:
                logger.error(
                    f"HubSpot API error: {response.status_code} - {response.text}"
                )
                raise Exception(f"HubSpot API error: {response.status_code}")

            data = response.json()
            results = data.get("results", [])

            # Filter for closed won deals
            for deal in results:
                props = deal.get("properties", {})
                stage = props.get("dealstage", "").lower()

                if "closedwon" in stage or "closed won" in stage:
                    all_deals.append(deal)

                if len(all_deals) >= limit:
                    break

            # Pagination
            paging = data.get("paging", {})
            next_link = paging.get("next", {})
            after = next_link.get("after")

            if not after or not results:
                break

        return all_deals[:limit]

    async def _enrich_deal_with_company(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        deal: dict,
    ) -> dict:
        """Enrich deal with associated company tech stack data."""
        props = deal.get("properties", {})

        enriched = {
            "deal_id": deal.get("id"),
            "deal_name": props.get("dealname", "Unknown"),
            "amount": float(props.get("amount") or 0),
            "close_date": props.get("closedate"),
            "deal_stage": props.get("dealstage"),
            "pipeline": props.get("pipeline"),
        }

        # Get associated company IDs
        associations = deal.get("associations", {})
        companies = associations.get("companies", {}).get("results", [])

        if companies:
            company_id = companies[0].get("id")
            company_data = await self._fetch_company(client, headers, company_id)

            if company_data:
                enriched["company_id"] = company_id
                enriched["company_name"] = company_data.get("name")
                enriched["company_domain"] = company_data.get("domain")
                enriched["industry"] = company_data.get("industry")
                enriched["tech_stack"] = company_data.get("tech_stack", [])
                enriched["num_employees"] = company_data.get("numberofemployees")

        return enriched

    async def _fetch_company(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        company_id: str,
    ) -> dict | None:
        """Fetch company details including tech stack."""
        url = f"{HUBSPOT_API_BASE}/crm/v3/objects/companies/{company_id}"

        params = {
            "properties": (
                "name,domain,industry,numberofemployees,annualrevenue,"
                "hs_analytics_source,description,"
                "technologies,tech_stack,builtwith_tech"
            ),
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code != 200:
                logger.warning(
                    f"Could not fetch company {company_id}: {response.status_code}"
                )
                return None

            data = response.json()
            props = data.get("properties", {})

            # Parse tech stack from various possible fields
            tech_stack = []
            for field in ["technologies", "tech_stack", "builtwith_tech"]:
                value = props.get(field)
                if value:
                    if isinstance(value, str):
                        tech_stack.extend(
                            [
                                t.strip()
                                for t in value.replace(";", ",").split(",")
                                if t.strip()
                            ]
                        )
                    elif isinstance(value, list):
                        tech_stack.extend(value)

            return {
                "name": props.get("name"),
                "domain": props.get("domain"),
                "industry": props.get("industry"),
                "numberofemployees": props.get("numberofemployees"),
                "annualrevenue": props.get("annualrevenue"),
                "description": props.get("description"),
                "tech_stack": list(set(tech_stack)),
            }

        except Exception as e:
            logger.error(f"Error fetching company {company_id}: {e}")
            return None
