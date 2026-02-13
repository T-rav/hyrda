"""HubSpot sync job for pulling closed deals with company tech stack data."""

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from jobs.base_job import BaseJob
from models.base import get_db_session
from models.oauth_credential import OAuthCredential
from services.encryption_service import get_encryption_service
from services.hubspot_deal_tracking_service import HubSpotDealTrackingService
from services.openai_embeddings import OpenAIEmbeddings
from services.qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

HUBSPOT_API_BASE = "https://api.hubapi.com"

# Deal properties to fetch from HubSpot
DEAL_PROPERTIES = [
    "dealname",
    "amount",
    "closedate",
    "dealstage",
    "pipeline",
    "hubspot_owner_id",
    "deal_currency_code",
    "hs_analytics_source",
    "dealtype",
    "hs_deal_stage_probability",
    # Custom fields (8th Light HubSpot configuration)
    "qualified_services",
    "practice_studio__cloned_",  # Practice/Studio field
    "deal_tech_stacks",  # Relevant Tech/Skills Required
    "tam",  # Client Service Lead
    "no_of_crafters_needed",  # Size of Team Needed
    # Metric.ai integration fields
    "metric_id",  # Metric Project ID
    "metric_link",  # Metric Project URL
]


class HubSpotSyncJob(BaseJob):
    """
    Sync closed deals from HubSpot with associated company tech stack data.

    Builds structured documents for each closed won deal and stores them
    in the vector database for RAG search.
    """

    JOB_NAME = "HubSpot Sync"
    JOB_DESCRIPTION = (
        "Sync closed deals from HubSpot including deal amount, owner, "
        "company tech stack, and ingest into vector database for search."
    )
    REQUIRED_PARAMS = ["credential_id"]
    OPTIONAL_PARAMS = ["limit", "skip_vector_ingestion"]

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
        """Execute HubSpot sync job with vector ingestion."""
        self.validate_params()

        credential_id = self.params.get("credential_id")
        limit = self.params.get("limit", 100)
        skip_vector = self.params.get("skip_vector_ingestion", False)

        logger.info("Starting HubSpot sync for closed deals")

        # Load credentials from database
        access_token = self._load_credentials(credential_id)

        # Use Bearer token auth
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Initialize tracking service and vector clients
        tracking_service = HubSpotDealTrackingService()

        qdrant_client = None
        embeddings = None
        if not skip_vector:
            embeddings = OpenAIEmbeddings()
            qdrant_client = QdrantClient()
            await qdrant_client.initialize()

        # Stats for reporting
        stats = {
            "processed": 0,
            "indexed": 0,
            "skipped_unchanged": 0,
            "failed": 0,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch closed deals
            deals = await self._fetch_closed_deals(client, headers, limit)
            logger.info(f"Found {len(deals)} closed deals")

            # Cache for owner lookups (same owner may be on multiple deals)
            owner_cache: dict[str, dict | None] = {}

            enriched_deals = []
            for deal in deals:
                try:
                    # Enrich with company and owner data
                    enriched = await self._enrich_deal_with_company(
                        client, headers, deal
                    )

                    # Fetch owner info (with caching)
                    owner_id = deal.get("properties", {}).get("hubspot_owner_id")
                    if owner_id:
                        if owner_id not in owner_cache:
                            owner_cache[owner_id] = await self._fetch_owner(
                                client, headers, owner_id
                            )
                        owner = owner_cache[owner_id]
                        if owner:
                            enriched["owner_name"] = (
                                f"{owner.get('firstName', '')} "
                                f"{owner.get('lastName', '')}".strip()
                            )
                            enriched["owner_email"] = owner.get("email")

                    # Add additional deal properties
                    props = deal.get("properties", {})
                    enriched["currency"] = props.get("deal_currency_code", "USD")
                    enriched["source"] = props.get("hs_analytics_source") or "Unknown"
                    enriched["qualified_services"] = (
                        props.get("qualified_services") or "Not specified"
                    )
                    enriched["practice_studio"] = (
                        props.get("practice_studio__cloned_") or "Not specified"
                    )

                    # Parse deal tech stacks (semicolon-separated)
                    deal_tech_raw = props.get("deal_tech_stacks") or ""
                    if deal_tech_raw:
                        enriched["deal_tech_stacks"] = [
                            t.strip() for t in deal_tech_raw.split(";") if t.strip()
                        ]
                    else:
                        enriched["deal_tech_stacks"] = []

                    # Fetch Client Service Lead (tam) user details
                    tam_id = props.get("tam")
                    if tam_id:
                        if tam_id not in owner_cache:
                            owner_cache[tam_id] = await self._fetch_owner(
                                client, headers, tam_id
                            )
                        tam_user = owner_cache[tam_id]
                        if tam_user:
                            enriched["client_service_lead"] = (
                                f"{tam_user.get('firstName', '')} "
                                f"{tam_user.get('lastName', '')}".strip()
                            )
                        else:
                            enriched["client_service_lead"] = "Not specified"
                    else:
                        enriched["client_service_lead"] = "Not specified"

                    enriched["team_size_needed"] = props.get("no_of_crafters_needed")
                    enriched["hubspot_updated_at"] = deal.get("updatedAt")

                    # Metric.ai integration fields (for linking to Metric projects)
                    enriched["metric_id"] = props.get("metric_id")
                    enriched["metric_link"] = props.get("metric_link")

                    enriched_deals.append(enriched)
                    stats["processed"] += 1

                    # Check if deal needs indexing
                    if not skip_vector:
                        needs_reindex, existing_uuid = (
                            tracking_service.check_deal_needs_reindex(
                                enriched["deal_id"], enriched
                            )
                        )

                        if not needs_reindex:
                            logger.debug(
                                f"Skipping unchanged deal: {enriched['deal_name']}"
                            )
                            stats["skipped_unchanged"] += 1
                            continue

                        # Build document and ingest
                        vector_uuid = (
                            existing_uuid
                            or tracking_service.generate_base_uuid(enriched["deal_id"])
                        )

                        doc = self._build_deal_document(enriched)

                        # Generate embedding and store
                        embedding = embeddings.embed_batch([doc["content"]])[0]

                        # Add deal_id to metadata for Qdrant ID generation
                        doc["metadata"]["deal_id"] = enriched["deal_id"]

                        await qdrant_client.upsert_with_namespace(
                            texts=[doc["content"]],
                            embeddings=[embedding],
                            metadata=[doc["metadata"]],
                            namespace="hubspot_deal",
                        )

                        # Record in tracking table
                        hubspot_updated = None
                        if enriched.get("hubspot_updated_at"):
                            with contextlib.suppress(ValueError, AttributeError):
                                hubspot_updated = datetime.fromisoformat(
                                    enriched["hubspot_updated_at"].replace(
                                        "Z", "+00:00"
                                    )
                                )

                        tracking_service.record_deal_ingestion(
                            hubspot_deal_id=enriched["deal_id"],
                            deal_name=enriched["deal_name"],
                            deal_data=enriched,
                            vector_uuid=vector_uuid,
                            document_content=doc["content"],
                            hubspot_updated_at=hubspot_updated,
                            status="success",
                            metadata={
                                "company_name": enriched.get("company_name"),
                                "amount": enriched.get("amount"),
                                "close_date": enriched.get("close_date"),
                            },
                            metric_id=enriched.get("metric_id"),
                        )

                        stats["indexed"] += 1
                        logger.info(
                            f"Indexed deal: {enriched['deal_name']} | "
                            f"Amount: {enriched.get('currency', 'USD')} "
                            f"{enriched['amount']:,.2f} | "
                            f"Company: {enriched.get('company_name', 'N/A')}"
                        )
                    else:
                        logger.info(
                            f"Deal: {enriched['deal_name']} | "
                            f"Amount: ${enriched['amount']:,.2f} | "
                            f"Company: {enriched.get('company_name', 'N/A')}"
                        )

                except Exception as e:
                    logger.error(f"Error processing deal {deal.get('id')}: {e}")
                    stats["failed"] += 1

        # Close Qdrant connection
        if qdrant_client:
            await qdrant_client.close()

        return {
            "status": "success",
            "records_processed": stats["processed"],
            "records_indexed": stats["indexed"],
            "records_skipped_unchanged": stats["skipped_unchanged"],
            "records_failed": stats["failed"],
            "deals": enriched_deals,
        }

    async def _fetch_won_stage_ids(
        self,
        client: httpx.AsyncClient,
        headers: dict,
    ) -> set[str]:
        """Fetch all 'Won' stage IDs from HubSpot pipelines."""
        url = f"{HUBSPOT_API_BASE}/crm/v3/pipelines/deals"

        try:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                logger.warning(
                    f"Could not fetch pipelines: {response.status_code}, "
                    "falling back to stage name matching"
                )
                return set()

            data = response.json()
            won_stage_ids = set()

            for pipeline in data.get("results", []):
                for stage in pipeline.get("stages", []):
                    metadata = stage.get("metadata", {})
                    label = stage.get("label", "").lower()
                    # Stage is "Won" if isClosed is true and label contains "won"
                    if metadata.get("isClosed") == "true" and "won" in label:
                        won_stage_ids.add(stage.get("id"))
                        logger.debug(
                            f"Found Won stage: {stage.get('label')} "
                            f"(id: {stage.get('id')}) in pipeline {pipeline.get('label')}"
                        )

            logger.info(f"Found {len(won_stage_ids)} 'Won' stages across all pipelines")
            return won_stage_ids

        except Exception as e:
            logger.error(f"Error fetching pipelines: {e}")
            return set()

    async def _fetch_closed_deals(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        limit: int,
    ) -> list[dict]:
        """Fetch closed won deals from HubSpot (2019 onwards)."""
        # First, get all "Won" stage IDs from pipelines
        won_stage_ids = await self._fetch_won_stage_ids(client, headers)

        if not won_stage_ids:
            logger.warning("No Won stage IDs found, cannot fetch deals")
            return []

        # Use search API to filter by stage and close date
        url = f"{HUBSPOT_API_BASE}/crm/v3/objects/deals/search"

        all_deals = []
        after = 0

        # Search for Won deals from each pipeline stage (2019 onwards)
        for stage_id in won_stage_ids:
            after = 0
            while len(all_deals) < limit:
                payload = {
                    "filterGroups": [
                        {
                            "filters": [
                                {
                                    "propertyName": "dealstage",
                                    "operator": "EQ",
                                    "value": stage_id,
                                },
                                {
                                    "propertyName": "closedate",
                                    "operator": "GTE",
                                    "value": "2019-01-01",
                                },
                            ]
                        }
                    ],
                    "sorts": [
                        {
                            "propertyName": "closedate",
                            "direction": "DESCENDING",
                        }
                    ],
                    "properties": DEAL_PROPERTIES,
                    "limit": min(limit - len(all_deals), 100),
                }

                if after:
                    payload["after"] = after

                response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(
                        f"HubSpot search API error: {response.status_code} - "
                        f"{response.text}"
                    )
                    break

                data = response.json()
                results = data.get("results", [])

                if not results:
                    break

                # Fetch company associations for each deal
                for deal in results:
                    deal_id = deal.get("id")
                    assoc_url = (
                        f"{HUBSPOT_API_BASE}/crm/v3/objects/deals/{deal_id}"
                        f"/associations/companies"
                    )
                    assoc_resp = await client.get(assoc_url, headers=headers)
                    if assoc_resp.status_code == 200:
                        assoc_data = assoc_resp.json()
                        deal["associations"] = {
                            "companies": {"results": assoc_data.get("results", [])}
                        }
                    else:
                        deal["associations"] = {}

                    all_deals.append(deal)

                    if len(all_deals) >= limit:
                        break

                # Pagination
                paging = data.get("paging", {})
                next_link = paging.get("next", {})
                after = next_link.get("after")

                if not after:
                    break

            if len(all_deals) >= limit:
                break

        logger.info(f"Found {len(all_deals)} Won deals from 2019 onwards")
        return all_deals[:limit]

    async def _fetch_owner(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        owner_id: str,
    ) -> dict | None:
        """Fetch deal owner details from HubSpot."""
        url = f"{HUBSPOT_API_BASE}/crm/v3/owners/{owner_id}"

        try:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning(
                    f"Could not fetch owner {owner_id}: {response.status_code}"
                )
                return None

            data = response.json()
            return {
                "firstName": data.get("firstName", ""),
                "lastName": data.get("lastName", ""),
                "email": data.get("email", ""),
            }

        except Exception as e:
            logger.error(f"Error fetching owner {owner_id}: {e}")
            return None

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

    def _build_deal_document(self, deal: dict[str, Any]) -> dict[str, Any]:
        """
        Build a structured document for vector storage.

        Args:
            deal: Enriched deal data

        Returns:
            Dictionary with 'content' (text for embedding) and 'metadata'
        """
        # Format tech stack (from company)
        company_tech_stack = ", ".join(deal.get("tech_stack", [])) or "Not specified"
        # Deal-specific tech requirements (now a list)
        deal_tech_list = deal.get("deal_tech_stacks", [])
        deal_tech = ", ".join(deal_tech_list) if deal_tech_list else "Not specified"

        # Get Metric integration fields
        metric_id = deal.get("metric_id") or "Not linked"
        metric_link = deal.get("metric_link") or "Not linked"

        # Build human-readable content for embedding
        content = f"""Client: {deal.get("company_name", "Unknown")}
Deal Owner: {deal.get("owner_name", "Not specified")}
Client Service Lead: {deal.get("client_service_lead", "Not specified")}
Company Tech Stack: {company_tech_stack}
Deal Tech Requirements: {deal_tech}
Currency: {deal.get("currency", "USD")}
Source: {deal.get("source", "Unknown")}
Qualified Services: {deal.get("qualified_services", "Not specified")}
Practice/Studio: {deal.get("practice_studio", "Not specified")}
Company Team Size: {deal.get("num_employees", "Unknown")}
Team Size Needed: {deal.get("team_size_needed") or "Not specified"}
Close Date: {deal.get("close_date", "Unknown")}
Deal ID: {deal.get("deal_id")}
Amount: {deal.get("currency", "USD")} {deal.get("amount", 0):,.2f}
Deal Name: {deal.get("deal_name", "Unknown")}
Industry: {deal.get("industry", "Not specified")}
Company Domain: {deal.get("company_domain", "Unknown")}
Metric Project ID: {metric_id}
Metric Link: {metric_link}"""

        # Build metadata for filtering and retrieval
        metadata = {
            "source": "hubspot",
            "type": "closed_deal",
            "deal_id": deal.get("deal_id"),
            "deal_name": deal.get("deal_name"),
            "client": deal.get("company_name"),
            "company_domain": deal.get("company_domain"),
            "amount": float(deal.get("amount") or 0),
            "currency": deal.get("currency", "USD"),
            "close_date": deal.get("close_date"),
            "deal_owner": deal.get("owner_name"),
            "owner_email": deal.get("owner_email"),
            "client_service_lead": deal.get("client_service_lead"),
            "tech_stack": deal.get("tech_stack", []),
            "deal_tech_stacks": deal.get("deal_tech_stacks"),
            "industry": deal.get("industry"),
            "company_team_size": deal.get("num_employees"),
            "team_size_needed": deal.get("team_size_needed"),
            "source_channel": deal.get("source"),
            "qualified_services": deal.get("qualified_services"),
            "practice_studio": deal.get("practice_studio"),
            "metric_id": deal.get("metric_id"),
            "metric_link": deal.get("metric_link"),
            "ingested_at": datetime.now(UTC).isoformat(),
        }

        return {"content": content, "metadata": metadata}
