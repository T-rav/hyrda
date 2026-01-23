"""
Regression tests for conversation tracking double-counting bug.

This test suite prevents the bug where conversation_turn observations
were being created twice per user message (once in llm_service.py and
once in message_handlers.py), causing lifetime stats to be inflated.
"""


class TestConversationTrackingDocumentation:
    """
    Documentation tests to prevent regression of double-counting bug.

    These tests document the expected behavior and serve as a contract.
    """

    def test_conversation_tracking_architecture(self):
        """
        Document the correct conversation tracking architecture.

        SINGLE SOURCE OF TRUTH: Only message_handlers.py should call trace_conversation()

        WRONG (causes double-counting):
        - llm_service.py calls trace_conversation() → 1 observation
        - message_handlers.py calls trace_conversation() → 1 observation
        = 2 observations per user message ❌

        CORRECT (single source):
        - llm_service.py does NOT call trace_conversation()
        - message_handlers.py calls trace_conversation() → 1 observation
        = 1 observation per user message ✅

        This ensures:
        - Lifetime stats show accurate user message counts
        - Average messages per thread is not inflated
        - Each user message creates exactly ONE conversation_turn observation
        """
        # Verify llm_service.py does not have trace_conversation calls
        # Read the source file directly to avoid mocking issues
        from pathlib import Path

        llm_service_path = Path(__file__).parent.parent / "services" / "llm_service.py"
        assert llm_service_path.exists(), f"Could not find {llm_service_path}"

        source = llm_service_path.read_text()

        # Check for actual function calls, ignoring comments
        # Remove comments and check for the pattern
        lines = source.split("\n")
        code_lines = [line for line in lines if not line.strip().startswith("#")]
        code_without_comments = "\n".join(code_lines)

        # This assertion will fail if trace_conversation is added back to llm_service as a function call
        # (Comments explaining the architecture are fine)
        assert ".trace_conversation(" not in code_without_comments, (
            "llm_service.py should NOT call .trace_conversation() - this causes double-counting!"
        )

    def test_message_handlers_are_tracking_source(self):
        """
        Document that message_handlers.py is the single source of truth for tracking.

        The following handlers in message_handlers.py should call trace_conversation:
        - handle_message() - for normal user messages (via _send_llm_response helper)
        - handle_agent_command() - for agent commands
        - agent process handlers - for process-specific commands
        """
        import inspect

        from handlers import message_handlers

        # Check that handle_message calls _send_llm_response (which contains trace_conversation)
        handle_message_source = inspect.getsource(message_handlers.handle_message)
        assert "_send_llm_response" in handle_message_source, (
            "message_handlers.handle_message() should call _send_llm_response()"
        )

        # Verify _send_llm_response helper contains trace_conversation call
        helper_source = inspect.getsource(message_handlers._send_llm_response)
        assert "trace_conversation" in helper_source, (
            "message_handlers._send_llm_response() should call trace_conversation()"
        )

    def test_langfuse_lifetime_stats_query(self):
        """
        Document the Langfuse query that counts conversation_turn observations.

        The lifetime stats query in langfuse_service.get_lifetime_stats() filters
        observations by name="conversation_turn". This count represents the total
        number of user messages.

        If each message creates 2 observations, the count will be doubled.
        """
        import inspect

        from services.langfuse_service import LangfuseService

        source = inspect.getsource(LangfuseService.get_lifetime_stats)

        # Verify the query filters by conversation_turn
        assert (
            'name": "conversation_turn"' in source or '"conversation_turn"' in source
        ), "Lifetime stats should query conversation_turn observations"
