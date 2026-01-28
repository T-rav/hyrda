"""Final report generation node for deep research workflow.

Generates comprehensive profile reports from accumulated research notes.
Includes Langfuse tracing for observability.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import boto3
from langchain_core.runnables import RunnableConfig
from shared.utils.agent_tracing import trace_agent_node

from .. import prompts
from ..configuration import ProfileConfiguration
from ..state import ProfileAgentState
from ..utils import (
    create_human_message,
    create_system_message,
    format_research_context,
    is_token_limit_exceeded,
    remove_up_to_last_ai_message,
)
from ..services.prompt_service import get_prompt_service

logger = logging.getLogger(__name__)


def upload_report_to_s3(report_content: str, company_name: str) -> Optional[str]:
    """Convert markdown to PDF and upload to MinIO/S3.

    Args:
        report_content: Full markdown report content
        company_name: Company name for filename

    Returns:
        Presigned URL to PDF or None if upload fails
    """
    try:
        # Use professional PDF generator (local copy)
        from ..pdf_utils.pdf_generator import markdown_to_pdf
        import re

        logger.info("Converting markdown to PDF...")

        # Strip LLM preambles (e.g., "Here is the revised report...")
        # Remove any text before the first markdown heading
        cleaned_content = re.sub(
            r'^.*?(?=^#\s)',  # Remove everything before first # heading
            '',
            report_content,
            flags=re.MULTILINE | re.DOTALL
        ).strip()

        # Strip metadata fields that LLM might add (Date:, Profile Type:, Focus Area:)
        # These appear as standalone lines before the first section content
        cleaned_content = re.sub(
            r'^(Date|Profile Type|Focus Area):\s*.*?$',
            '',
            cleaned_content,
            flags=re.MULTILINE
        )

        # Remove extra blank lines created by stripping
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content).strip()

        # Generate PDF with professional styling (no metadata clutter)
        pdf_buffer = markdown_to_pdf(
            markdown_content=cleaned_content,
            title=f"{company_name.title()} - Company Profile",  # Title case for consistency
            metadata={},  # No metadata header
            style="professional"
        )

        if not pdf_buffer:
            raise Exception("PDF generation failed")

        pdf_bytes = pdf_buffer.getvalue()

        # MinIO configuration
        s3_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        s3_access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        s3_secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        bucket_name = os.getenv("REPORTS_BUCKET", "profile-reports")

        # Create S3 client
        s3_client = boto3.client(
            "s3",
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
        )

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company_name = "".join(c if c.isalnum() else "_" for c in company_name)
        filename = f"profile_{safe_company_name}_{timestamp}.pdf"

        # Create bucket if it doesn't exist
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except:
            s3_client.create_bucket(Bucket=bucket_name)
            logger.info(f"Created bucket: {bucket_name}")

        # Upload PDF
        s3_client.put_object(
            Bucket=bucket_name,
            Key=filename,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )

        # Generate presigned URL (internal endpoint for bot)
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": filename},
            ExpiresIn=2592000,  # 30 days
        )

        logger.info(f"Uploaded PDF to S3: {filename} ({len(pdf_bytes)} bytes)")
        return url

    except Exception as e:
        logger.error(f"Failed to generate/upload PDF: {e}")
        return None


@trace_agent_node("final_report_generation")
async def final_report_generation(
    state: ProfileAgentState, config: RunnableConfig
) -> dict:
    """Generate final comprehensive profile report.

    Args:
        state: Current profile agent state with all research notes
        config: Runtime configuration

    Returns:
        Dict with final_report and executive_summary
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    notes = state.get("notes", [])
    profile_type = state.get("profile_type", "company")
    focus_area = state.get("focus_area", "")
    research_brief = state.get("research_brief", "")
    revision_count = state.get("revision_count", 0)
    revision_prompt = state.get("revision_prompt", "")

    if revision_count > 0:
        logger.info(
            f"Generating REVISED report (attempt {revision_count}) from {len(notes)} research notes"
        )
    else:
        logger.info(f"Generating final report from {len(notes)} research notes")

    if not notes:
        logger.warning("No research notes available for final report")
        return {"final_report": "No research findings available to generate report."}

    # Use LangChain with Gemini or OpenAI
    from config.settings import Settings

    settings = Settings()

    # Check if Gemini is enabled for final report generation
    llm = None
    if settings.gemini.enabled and settings.gemini.api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            logger.info(
                f"Using Gemini ({settings.gemini.model}) for final report generation"
            )
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini.model,
                google_api_key=settings.gemini.api_key,
                temperature=0.0,  # CRITICAL: 0.0 to prevent hallucination in relationship status
                max_output_tokens=configuration.final_report_model_max_tokens,
            )
        except ImportError:
            logger.warning(
                "langchain_google_genai not installed - falling back to OpenAI"
            )

    if llm is None:
        from langchain_openai import ChatOpenAI

        logger.info(f"Using OpenAI ({settings.llm.model}) for final report generation")
        llm = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            temperature=0.0,  # CRITICAL: 0.0 to prevent hallucination in relationship status
            max_completion_tokens=configuration.final_report_model_max_tokens,
        )

    # Format research context (async - uses LLM for source selection)
    notes_text = await format_research_context(research_brief, notes, profile_type)

    # Build final report prompt with focus area
    current_date = datetime.now().strftime("%B %d, %Y")

    # Build focus guidance for final report
    if focus_area:
        focus_guidance = f"""
**🎯 CRITICAL - USER'S SPECIFIC REQUEST**: The user specifically asked about "{focus_area}".

**Report Writing Strategy:**
1. **Front-load the focus**: Sections most relevant to {focus_area} should be LONGEST and MOST DETAILED
2. **Emphasize in Solutions section**: The "Solutions 8th Light Can Offer" section MUST heavily emphasize opportunities related to {focus_area}
3. **Connect throughout**: In EVERY section, look for connections to {focus_area} and make them explicit
4. **Executive Summary priority**: Ensure at least 1-2 of the 3 bullet points relate to {focus_area}
5. **Depth allocation**:
   - Sections directly about {focus_area}: Write 4-5 paragraphs each (maximum depth)
   - Related sections: Write 3-4 paragraphs (good depth)
   - Less relevant sections: Write 2-3 paragraphs (sufficient context)

**Example**: If focus is "AI needs", then:
- "Company Priorities" should extensively cover AI initiatives
- "Size of Teams" should deeply analyze AI/ML team structure
- "Solutions 8th Light Can Offer" should propose AI-specific consulting opportunities
- Other sections should still be comprehensive but briefer"""
    else:
        focus_guidance = ""

    # Use local prompts (not Langfuse)
    # Select prompt based on profile type
    if profile_type == "employee":
        # TODO: Add person_profile_final_report_prompt to prompts.py
        logger.warning("Employee/person profiles not yet migrated to local prompts - using fallback")
        prompt_template = """# Person Profile Report

You are generating a professional profile for a person.

Profile Type: {profile_type}
Focus Area: {focus_area}
{focus_guidance}

Research Notes:
{notes}

Date: {current_date}

Generate a comprehensive professional profile based on the research provided."""
    else:
        # Use local company profile prompt (from prompts.py)
        logger.info("Using local company_profile_final_report_prompt")
        prompt_template = prompts.company_profile_final_report_prompt

    system_prompt = prompt_template.format(
        profile_type=profile_type,
        focus_area=focus_area if focus_area else "None (general profile)",
        focus_guidance=focus_guidance,
        notes=notes_text,
        current_date=current_date,
    )

    # Try generation with retry on token limits
    max_attempts = 3

    # If this is a revision, add the revision prompt
    if revision_count > 0 and revision_prompt:
        logger.info(f"Using revision prompt: {revision_prompt[:100]}...")
        messages = [
            create_system_message(system_prompt),
            create_human_message(revision_prompt),
        ]
    else:
        messages = [
            create_system_message(system_prompt),
            create_human_message("Generate the comprehensive profile report now."),
        ]

    for attempt in range(max_attempts):
        try:
            # Use LangChain ChatOpenAI
            response = await llm.ainvoke(messages)
            final_report = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.info(f"Final report generated: {len(final_report)} characters")

            # Generate executive summary for Slack display
            logger.info("Generating executive summary from full report")

            try:
                # Build focus guidance for executive summary
                if focus_area:
                    summary_focus_guidance = f"""
**IMPORTANT**: The user specifically asked about "{focus_area}".
Ensure at least 1-2 of your 3 bullet points directly address {focus_area}."""
                else:
                    summary_focus_guidance = ""

                # Use local prompt for executive summary (not in Langfuse)
                summary_prompt = prompts.executive_summary_prompt.format(
                    full_report=final_report,
                    focus_area=focus_area if focus_area else "None (general profile)",
                    focus_guidance=summary_focus_guidance,
                )
                # Always use GPT-4o for executive summary (more reliable than Gemini)
                from langchain_openai import ChatOpenAI

                logger.info("Using GPT-4o for executive summary generation")
                summary_llm = ChatOpenAI(
                    model="gpt-4o",
                    api_key=settings.llm.api_key,
                    temperature=0.7,
                    max_completion_tokens=500,
                )
                summary_response = await summary_llm.ainvoke(
                    [create_human_message(summary_prompt)]
                )
                executive_summary = (
                    summary_response.content
                    if hasattr(summary_response, "content")
                    else str(summary_response)
                )

                # Validate that summary is not empty
                if not executive_summary or len(executive_summary.strip()) == 0:
                    raise ValueError("LLM returned empty executive summary")

                # Convert standard markdown to Slack markdown
                # Standard markdown: **bold** __italic__ → Slack: *bold* _italic_
                executive_summary = executive_summary.replace('**', '*').replace('__', '_')

                logger.info(
                    f"Executive summary generated: {len(executive_summary)} characters"
                )

                # Footer is already in the prompt, don't add it again

            except Exception as summary_error:
                logger.warning(f"Failed to generate executive summary: {summary_error}")
                # Fallback: use Slack-safe markdown
                executive_summary = (
                    "📊 *Executive Summary*\n\n"
                    "• Full detailed report attached as PDF\n\n"
                    "📎 _Unable to generate summary - see full report_\n\n\n"
                    "---\n\n"
                    "_💬 Ask me follow-up questions about this profile in this thread!_\n"
                    "_Or start your message with `profile [company name]` to profile another company._"
                )

            # Extract company name from query or report title
            query = state.get("query", "company")
            company_name = query.replace("profile ", "").strip() or "company"

            # Upload full report to S3 and get URL
            report_url = upload_report_to_s3(final_report, company_name)

            # Build standardized output for Slack integration
            # Use timestamp in filename for Slack attachment
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_company_name = "".join(c if c.isalnum() else "_" for c in company_name)
            slack_filename = f"profile_{safe_company_name}_{timestamp}.pdf"

            attachments = []
            if report_url:
                attachments.append({
                    "url": report_url,
                    "inject": True,  # Download and attach as Slack file
                    "type": "pdf",
                    "filename": slack_filename
                })

            return {
                "message": executive_summary,  # Slack-ready display text
                "attachments": attachments,  # URLs to process
                # Keep legacy fields for backward compatibility during transition
                "final_report": final_report,
                "executive_summary": executive_summary,
                # Enable follow-up mode after report generation
                "followup_mode": True,  # Allow conversational follow-ups
            }

        except Exception as e:
            if is_token_limit_exceeded(e, configuration.final_report_model):
                logger.warning(f"Token limit on final report attempt {attempt + 1}")
                messages = remove_up_to_last_ai_message(messages)
                continue

            logger.error(f"Final report error: {e}")
            break

    # Fallback: return notes summary
    fallback_report = (
        "# Profile Report (Partial)\n\n"
        "Unable to generate full report. Research findings:\n\n"
        + "\n\n".join(notes[:3])
    )

    # Try to upload fallback report too
    query = state.get("query", "company")
    company_name = query.replace("profile ", "").strip() or "company"
    report_url = upload_report_to_s3(fallback_report, company_name)

    fallback_summary = "📊 **Executive Summary**\n\n- Partial report generated\n\n---\n\n💬 *Ask follow-up questions in this thread!*"

    # Build standardized output with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_company_name = "".join(c if c.isalnum() else "_" for c in company_name)
    fallback_filename = f"profile_{safe_company_name}_{timestamp}_partial.pdf"

    attachments = []
    if report_url:
        attachments.append({
            "url": report_url,
            "inject": True,
            "type": "pdf",
            "filename": fallback_filename
        })

    return {
        "message": fallback_summary,
        "attachments": attachments,
        # Legacy fields
        "final_report": fallback_report,
        "executive_summary": fallback_summary,
        # Enable follow-up mode even for fallback reports
        "followup_mode": True,
    }
