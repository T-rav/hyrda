"""
Tests for Agent Processes handler.

Tests agent process definitions and triggering.
"""

from unittest.mock import Mock, patch

import pytest

from bot.handlers.agent_processes import AGENT_PROCESSES, trigger_agent_process


class TestAgentProcesses:
    """Test cases for agent process definitions"""

    def test_agent_processes_structure(self):
        """Test that AGENT_PROCESSES has expected structure"""
        assert isinstance(AGENT_PROCESSES, dict)
        assert len(AGENT_PROCESSES) > 0

        for name, config in AGENT_PROCESSES.items():
            assert isinstance(name, str)
            assert isinstance(config, dict)
            assert 'description' in config
            assert 'command' in config
            assert 'keywords' in config
            assert isinstance(config['keywords'], list)

    def test_agent_process_keywords(self):
        """Test that agent processes have meaningful keywords"""
        for _name, config in AGENT_PROCESSES.items():
            keywords = config['keywords']
            assert len(keywords) > 0
            assert all(isinstance(keyword, str) for keyword in keywords)
            assert all(len(keyword.strip()) > 0 for keyword in keywords)

    @pytest.mark.asyncio
    async def test_trigger_agent_process_found(self):
        """Test triggering existing agent process"""
        # Mock a process that matches
        test_message = "run data ingestion process"

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            result = await trigger_agent_process(test_message)

            # Should find and trigger a matching process
            assert result is not None
            assert "started" in result.lower()

    @pytest.mark.asyncio
    async def test_trigger_agent_process_not_found(self):
        """Test triggering non-existent agent process"""
        test_message = "this message matches no agent process keywords"

        result = await trigger_agent_process(test_message)

        # Should return None when no process matches
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_agent_process_keyword_matching(self):
        """Test keyword matching logic"""
        # Test various keyword matching scenarios
        test_cases = [
            ("ingest documents", True),  # Should match ingestion process
            ("data ingestion", True),    # Should match ingestion process
            ("random message", False),   # Should not match anything
            ("help with processing", False),  # Too generic
        ]

        for message, should_match in test_cases:
            with patch('subprocess.Popen'):
                result = await trigger_agent_process(message)

                if should_match:
                    assert result is not None
                else:
                    assert result is None

    def test_all_processes_have_valid_commands(self):
        """Test that all agent processes have valid command structures"""
        for _name, config in AGENT_PROCESSES.items():
            command = config['command']
            assert isinstance(command, list)
            assert len(command) > 0
            assert all(isinstance(cmd_part, str) for cmd_part in command)

    def test_process_descriptions_are_meaningful(self):
        """Test that process descriptions are meaningful"""
        for _name, config in AGENT_PROCESSES.items():
            description = config['description']
            assert isinstance(description, str)
            assert len(description.strip()) > 10  # Should be descriptive
            assert not description.isspace()

    def test_no_duplicate_process_names(self):
        """Test that there are no duplicate process names"""
        names = list(AGENT_PROCESSES.keys())
        assert len(names) == len(set(names))

    def test_keyword_coverage(self):
        """Test that keywords provide good coverage for expected use cases"""
        all_keywords = []
        for config in AGENT_PROCESSES.values():
            all_keywords.extend(config['keywords'])

        # Should have decent coverage of common terms
        common_terms = ['ingest', 'process', 'data', 'documents']
        found_terms = [term for term in common_terms if any(term in keyword.lower() for keyword in all_keywords)]

        assert len(found_terms) > 0  # Should match at least some common terms
