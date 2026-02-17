"""HubSpot relationship check skill."""

from dataclasses import dataclass
from typing import Any

from ..base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .clients import CompanyInfo, get_hubspot


@dataclass
class RelationshipData:
    """Relationship check result data."""

    company_name: str
    found_in_hubspot: bool
    company_info: CompanyInfo | None = None
    can_pursue: bool = True
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_name": self.company_name,
            "found_in_hubspot": self.found_in_hubspot,
            "can_pursue": self.can_pursue,
            "skip_reason": self.skip_reason,
            "company_info": {
                "company_id": self.company_info.company_id,
                "name": self.company_info.name,
                "domain": self.company_info.domain,
                "industry": self.company_info.industry,
                "employees": self.company_info.employees,
                "lifecycle_stage": self.company_info.lifecycle_stage,
                "is_customer": self.company_info.is_customer,
                "has_active_deal": self.company_info.has_active_deal,
                "deal_count": self.company_info.deal_count,
            }
            if self.company_info
            else None,
        }


class CheckRelationshipSkill(BaseSkill):
    """Check HubSpot for existing relationship with a company.

    This skill checks if a company is already in HubSpot and
    determines if we can pursue them as a prospect.

    Returns:
        - found_in_hubspot: Whether company exists in HubSpot
        - can_pursue: Whether we should pursue (not a customer/active deal)
        - company_info: Full HubSpot data if found
    """

    name = "check_relationship"
    description = "Check HubSpot for existing relationship with a company"
    version = "1.0.0"

    def __init__(self, context: SkillContext | None = None):
        super().__init__(context)
        self.hubspot = get_hubspot()

    async def execute(self, company_name: str) -> SkillResult[RelationshipData]:
        """Check relationship with company.

        Args:
            company_name: Company to check

        Returns:
            SkillResult with relationship data
        """
        self._step("check_hubspot")

        # Check cache first
        cache_key = f"hubspot:{company_name.lower()}"
        cached = self.context.get_cached(cache_key)
        if cached:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=cached,
                message=f"Found cached relationship data for {company_name}",
                steps_completed=["cache_hit"],
            )

        # Not configured - assume can pursue
        if not self.hubspot.is_configured:
            data = RelationshipData(
                company_name=company_name,
                found_in_hubspot=False,
                can_pursue=True,
            )
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"HubSpot not configured - assuming {company_name} is new",
                steps_completed=["hubspot_not_configured"],
            )

        # Search HubSpot
        company_info = await self.hubspot.check_company(company_name)

        if not company_info:
            # Not found - can pursue
            data = RelationshipData(
                company_name=company_name,
                found_in_hubspot=False,
                can_pursue=True,
            )
            self.context.set_cached(cache_key, data)
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"✅ {company_name} not in HubSpot - NET NEW prospect",
                steps_completed=["hubspot_search", "not_found"],
            )

        # Found - check if we can pursue
        can_pursue = not company_info.is_customer and not company_info.has_active_deal
        skip_reason = None

        if company_info.is_customer:
            skip_reason = "Already a customer"
        elif company_info.has_active_deal:
            skip_reason = "Has active deal"

        data = RelationshipData(
            company_name=company_name,
            found_in_hubspot=True,
            company_info=company_info,
            can_pursue=can_pursue,
            skip_reason=skip_reason,
        )
        self.context.set_cached(cache_key, data)

        if can_pursue:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"✅ {company_name} in HubSpot but can pursue (stage: {company_info.lifecycle_stage})",
                steps_completed=["hubspot_search", "found", "can_pursue"],
            )
        else:
            return SkillResult(
                status=SkillStatus.SKIPPED,
                data=data,
                message=f"⏭️ Skip {company_name}: {skip_reason}",
                steps_completed=["hubspot_search", "found", "skip"],
            )
