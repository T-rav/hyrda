"""Tests for agent query detection and pattern matching."""

import re


class TestAgentDetection:
    """Test agent query detection with dynamic patterns."""

    def test_profile_agent_detection(self):
        """Test that 'profile costco' is detected as an agent query."""
        # Patterns that should be generated from agent service
        agent_patterns = [
            "^/profile",  # /profile
            "^profile\\s",  # profile <query>
            "^/-profile",  # /-profile (alias)
            "^-profile\\s",  # -profile <query>
        ]

        test_queries = [
            ("profile costco", True),
            ("profile tesla", True),
            ("/profile amazon", True),
            ("-profile microsoft", True),
            ("tell me about costco", False),
            ("what is the profile", False),
            ("costco profile", False),
        ]

        for query, should_match in test_queries:
            text_lower = query.lower().strip()
            is_agent_query = any(
                re.search(pattern, text_lower) for pattern in agent_patterns
            )
            assert is_agent_query == should_match, (
                f"Query '{query}' should {'match' if should_match else 'not match'} "
                f"agent patterns, but got {is_agent_query}"
            )

    def test_meddic_agent_detection(self):
        """Test that MEDDIC queries are detected."""
        agent_patterns = [
            "^/meddic",
            "^meddic\\s",
        ]

        test_queries = [
            ("meddic analysis for acme corp", True),
            ("/meddic help", True),
            ("run meddic", True),
            ("medicate the patient", False),
        ]

        for query, should_match in test_queries:
            text_lower = query.lower().strip()
            is_agent_query = any(
                re.search(pattern, text_lower) for pattern in agent_patterns
            )
            assert is_agent_query == should_match, (
                f"Query '{query}' should {'match' if should_match else 'not match'}"
            )

    def test_pattern_escaping(self):
        """Test that regex patterns are properly escaped."""
        # The pattern should use \\s not just \s in the string
        pattern = "^profile\\s"  # This is correct

        assert re.search(pattern, "profile costco"), "Should match 'profile costco'"
        assert re.search(pattern, "profile tesla"), "Should match 'profile tesla'"
        assert not re.search(pattern, "profiles"), "Should not match 'profiles'"
        assert not re.search(pattern, "profilecostco"), (
            "Should not match 'profilecostco'"
        )

    def test_case_insensitive_matching(self):
        """Test that agent detection is case-insensitive."""
        agent_patterns = ["^profile\\s"]

        test_queries = [
            "profile costco",
            "Profile Costco",
            "PROFILE COSTCO",
            "PrOfIlE CoStCo",
        ]

        for query in test_queries:
            text_lower = query.lower().strip()
            is_agent_query = any(
                re.search(pattern, text_lower) for pattern in agent_patterns
            )
            assert is_agent_query, f"Query '{query}' should match after lowercasing"
