"""State definitions for Lead Qualifier agent."""

from typing import Any, Literal

from typing_extensions import TypedDict


class CompanyData(TypedDict, total=False):
    """Company-level input fields."""

    company_name: str
    company_domain: str
    industry: str
    company_size: str  # size band
    location: str
    region: str


class ContactData(TypedDict, total=False):
    """Contact-level input fields."""

    contact_name: str
    job_title: str
    seniority: str  # IC, Manager, Director, VP, C-level
    department: str  # Engineering, Product, Data, Leadership
    lifecycle_stage: str
    lead_source: str
    original_source: str
    hubspot_lead_score: float


class QualifierInput(TypedDict, total=False):
    """Input data structure for the qualifier agent."""

    company: CompanyData
    contact: ContactData
    sequence_identifier: str  # Optional: only if from outbound sequence


class QualifierOutput(TypedDict, total=False):
    """Output data structure from the qualifier agent."""

    # AI Scoring
    qualification_score: int  # 0-100
    fit_tier: Literal["High", "Medium", "Low"]

    # Recommendations
    recommended_solution: list[str]  # List of applicable service categories
    similar_client_example: list[str]  # 1-2 past project references

    # Seller-Facing Summary
    qualification_summary: str  # Short narrative explaining fit

    # Optional Strategic Insights
    primary_initiative: str  # e.g., Data modernization, AI adoption
    risk_flags: list[str]  # e.g., early-stage, unclear owner


class QualifierState(TypedDict):
    """State for the Lead Qualifier agent workflow."""

    # Input
    query: str  # User query or trigger context
    company: CompanyData
    contact: ContactData
    sequence_identifier: str | None

    # Intermediate analysis
    solution_fit_score: int  # 0-40
    solution_fit_reasoning: str
    strategic_fit_score: int  # 0-25
    strategic_fit_reasoning: str
    historical_similarity_score: int  # 0-25
    historical_similarity_reasoning: str

    # Internal knowledge base results
    similar_clients: list[dict[str, Any]]
    similar_projects: list[dict[str, Any]]

    # Output
    qualification_score: int  # 0-100
    fit_tier: Literal["High", "Medium", "Low"]
    recommended_solution: list[str]
    similar_client_example: list[str]
    qualification_summary: str
    primary_initiative: str
    risk_flags: list[str]

    # Metadata
    error: str | None
