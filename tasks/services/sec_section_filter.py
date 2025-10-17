"""
SEC Section Filtering

Filters SEC filings to keep only sections relevant for sales intelligence and deep research.
Reduces storage by ~65% while preserving key business insights.
"""

import logging
import re

logger = logging.getLogger(__name__)


class SECSectionFilter:
    """Filter SEC filings to keep only sales-relevant sections."""

    # Sections to keep for each filing type
    KEEP_SECTIONS = {
        "10-K": [
            "business",
            "risk factors",
            "management's discussion and analysis",
            "md&a",
            "properties",
            "legal proceedings",
        ],
        # 10-Q and 8-K disabled - only ingesting 10-K annual reports
    }

    # Sections to always skip (get from XBRL instead)
    SKIP_SECTIONS = [
        "consolidated financial statements",
        "notes to consolidated financial statements",
        "financial statements",
        "exhibits",
        "signatures",
        "controls and procedures",
        "market for registrant's common equity",
        "selected financial data",
        "index to financial statements",
        "index to exhibits",
    ]

    @staticmethod
    def should_keep_section(section_title: str, filing_type: str) -> bool:
        """
        Determine if a section should be kept based on filing type.

        Args:
            section_title: Title of the section (e.g., "Item 1. Business")
            filing_type: Type of filing (10-K, 10-Q, 8-K)

        Returns:
            True if section should be kept, False if it should be filtered out
        """
        # Normalize section title for comparison
        normalized = section_title.lower().strip()

        # Remove common prefixes like "Item 1.", "Part I", etc.
        normalized = re.sub(r"^(item|part)\s+[ivx0-9]+\.?\s*", "", normalized)
        normalized = normalized.strip()

        # Check if section should always be skipped
        for skip_pattern in SECSectionFilter.SKIP_SECTIONS:
            if skip_pattern in normalized:
                logger.debug(f"Skipping section: {section_title} (financial data)")
                return False

        # Get keep patterns for this filing type
        keep_patterns = SECSectionFilter.KEEP_SECTIONS.get(filing_type, [])

        # 8-K: Keep everything
        if "ALL" in keep_patterns:
            return True

        # Check if section matches any keep pattern
        for pattern in keep_patterns:
            if pattern in normalized:
                logger.debug(f"Keeping section: {section_title}")
                return True

        logger.debug(f"Filtering out section: {section_title}")
        return False

    @staticmethod
    def filter_filing_content(
        content: str, filing_type: str, parse_sections: bool = True
    ) -> str:
        """
        Filter filing content to keep only relevant sections.

        Args:
            content: Raw filing text
            filing_type: Type of filing (currently only 10-K supported)
            parse_sections: If True, attempt to parse and filter sections.
                           If False, return full content

        Returns:
            Filtered content with only relevant sections
        """
        # Only 10-K is supported - 10-Q and 8-K are disabled
        if filing_type != "10-K":
            logger.info(
                f"{filing_type} filing not supported for filtering: Keeping full content ({len(content)} chars)"
            )
            return content

        # If parsing disabled, return full content
        if not parse_sections:
            logger.info(
                f"Section parsing disabled: Keeping full content ({len(content)} chars)"
            )
            return content

        # Try to parse sections
        sections = SECSectionFilter._parse_sections(content)

        if not sections:
            logger.warning(
                "Could not parse sections, keeping full content as fallback"
            )
            return content

        # Filter sections
        filtered_sections = []
        original_chars = len(content)

        for section_title, section_content in sections:
            if SECSectionFilter.should_keep_section(section_title, filing_type):
                filtered_sections.append((section_title, section_content))

        # Rebuild content from filtered sections
        if not filtered_sections:
            logger.warning("No sections matched filter, keeping full content")
            return content

        # Join filtered sections
        filtered_content = "\n\n".join(
            [f"{title}\n\n{content}" for title, content in filtered_sections]
        )

        filtered_chars = len(filtered_content)
        reduction_pct = (1 - filtered_chars / original_chars) * 100

        logger.info(
            f"Filtered {filing_type}: {original_chars:,} → {filtered_chars:,} chars "
            f"({reduction_pct:.1f}% reduction, kept {len(filtered_sections)}/{len(sections)} sections)"
        )

        return filtered_content

    @staticmethod
    def _parse_sections(content: str) -> list[tuple[str, str]]:
        """
        Parse SEC filing into sections.

        Looks for common section headers like:
        - "Item 1. Business"
        - "ITEM 1A. RISK FACTORS"
        - "Part I"

        Args:
            content: Raw filing text

        Returns:
            List of (section_title, section_content) tuples
        """
        # Pattern for SEC section headers
        # Matches: "Item 1.", "ITEM 1A.", "Part I", etc.
        section_pattern = re.compile(
            r"^(?:ITEM|Item|PART|Part)\s+[0-9]+[A-Z]?\.?\s+[^\n]+$",
            re.MULTILINE | re.IGNORECASE,
        )

        # Find all section headers
        matches = list(section_pattern.finditer(content))

        if not matches:
            logger.debug("No section headers found in filing")
            return []

        sections = []

        for i, match in enumerate(matches):
            section_title = match.group().strip()
            start_pos = match.end()

            # End position is start of next section, or end of content
            end_pos = matches[i + 1].start() if i < len(matches) - 1 else len(content)

            section_content = content[start_pos:end_pos].strip()

            sections.append((section_title, section_content))

        logger.debug(f"Parsed {len(sections)} sections from filing")
        return sections


def filter_sec_filing(content: str, filing_type: str) -> str:
    """
    Convenience function to filter SEC filing content.

    Args:
        content: Raw filing text
        filing_type: Type of filing (10-K, 10-Q, 8-K)

    Returns:
        Filtered content with only relevant sections

    Example:
        >>> content = download_10k()
        >>> filtered = filter_sec_filing(content, "10-K")
        >>> # Returns ~65% smaller content with key sections only
    """
    return SECSectionFilter.filter_filing_content(content, filing_type)
