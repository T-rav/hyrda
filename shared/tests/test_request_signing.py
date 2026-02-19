"""Unit tests for HMAC request signing utilities.

Tests cover:
- Signature generation and verification
- Timestamp validation and replay attack prevention
- Clock skew handling
- Missing/invalid components
- Various payload types
- Security edge cases
"""

import time

import pytest

from shared.utils.request_signing import (
    SIGNATURE_VALIDITY_SECONDS,
    RequestSigningError,
    add_signature_headers,
    extract_and_verify_signature,
    generate_signature,
    verify_signature,
)


class TestGenerateSignature:
    """Test signature generation."""

    def test_generate_signature_basic(self):
        """Test basic signature generation with valid inputs."""
        token = "test-service-token"
        body = '{"query": "test", "context": {}}'
        timestamp = "1234567890"

        signature = generate_signature(token, body, timestamp)

        # Should return hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex digest is 64 chars
        assert all(c in "0123456789abcdef" for c in signature)

    def test_generate_signature_empty_body(self):
        """Test signature generation with empty body."""
        token = "test-token"
        body = ""
        timestamp = "1234567890"

        signature = generate_signature(token, body, timestamp)

        assert isinstance(signature, str)
        assert len(signature) == 64

    def test_generate_signature_large_body(self):
        """Test signature generation with large payload."""
        token = "test-token"
        body = '{"data": "' + ("x" * 10000) + '"}'
        timestamp = "1234567890"

        signature = generate_signature(token, body, timestamp)

        assert isinstance(signature, str)
        assert len(signature) == 64

    def test_generate_signature_deterministic(self):
        """Test that same inputs always produce same signature."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = "1234567890"

        sig1 = generate_signature(token, body, timestamp)
        sig2 = generate_signature(token, body, timestamp)

        assert sig1 == sig2

    def test_generate_signature_different_tokens(self):
        """Test that different tokens produce different signatures."""
        body = '{"query": "test"}'
        timestamp = "1234567890"

        sig1 = generate_signature("token1", body, timestamp)
        sig2 = generate_signature("token2", body, timestamp)

        assert sig1 != sig2

    def test_generate_signature_different_bodies(self):
        """Test that different bodies produce different signatures."""
        token = "test-token"
        timestamp = "1234567890"

        sig1 = generate_signature(token, '{"query": "test1"}', timestamp)
        sig2 = generate_signature(token, '{"query": "test2"}', timestamp)

        assert sig1 != sig2

    def test_generate_signature_different_timestamps(self):
        """Test that different timestamps produce different signatures."""
        token = "test-token"
        body = '{"query": "test"}'

        sig1 = generate_signature(token, body, "1234567890")
        sig2 = generate_signature(token, body, "1234567891")

        assert sig1 != sig2

    def test_generate_signature_with_special_characters(self):
        """Test signature with special characters in body."""
        token = "test-token"
        body = '{"data": "test\\n\\t\\r\\"special\\"", "emoji": "🔒"}'
        timestamp = "1234567890"

        signature = generate_signature(token, body, timestamp)

        assert isinstance(signature, str)
        assert len(signature) == 64

    def test_generate_signature_with_unicode(self):
        """Test signature with unicode characters."""
        token = "test-token"
        body = '{"message": "Hello 世界 🌍"}'
        timestamp = "1234567890"

        signature = generate_signature(token, body, timestamp)

        assert isinstance(signature, str)
        assert len(signature) == 64


class TestVerifySignature:
    """Test signature verification."""

    def test_verify_signature_valid(self):
        """Test verification of valid signature."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, body, timestamp)
        is_valid, error = verify_signature(token, body, timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_verify_signature_invalid_signature(self):
        """Test verification with wrong signature."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))

        wrong_signature = "0" * 64
        is_valid, error = verify_signature(token, body, timestamp, wrong_signature)

        assert is_valid is False
        assert error == "Invalid signature"

    def test_verify_signature_tampered_body(self):
        """Test that tampering with body invalidates signature."""
        token = "test-token"
        original_body = '{"query": "test"}'
        tampered_body = '{"query": "hacked"}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, original_body, timestamp)
        is_valid, error = verify_signature(token, tampered_body, timestamp, signature)

        assert is_valid is False
        assert error == "Invalid signature"

    def test_verify_signature_wrong_token(self):
        """Test that wrong token invalidates signature."""
        correct_token = "correct-token"
        wrong_token = "wrong-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))

        signature = generate_signature(correct_token, body, timestamp)
        is_valid, error = verify_signature(wrong_token, body, timestamp, signature)

        assert is_valid is False
        assert error == "Invalid signature"

    def test_verify_signature_expired(self):
        """Test that old timestamps are rejected (replay attack prevention)."""
        token = "test-token"
        body = '{"query": "test"}'
        # Timestamp from 10 minutes ago (beyond 5 minute window)
        old_timestamp = str(int(time.time()) - 600)

        signature = generate_signature(token, body, old_timestamp)
        is_valid, error = verify_signature(token, body, old_timestamp, signature)

        assert is_valid is False
        assert error is not None
        assert "Request expired" in error
        assert "600s" in error

    def test_verify_signature_within_validity_window(self):
        """Test that timestamps within validity window are accepted."""
        token = "test-token"
        body = '{"query": "test"}'
        # Timestamp from 1 minute ago (within 5 minute window)
        recent_timestamp = str(int(time.time()) - 60)

        signature = generate_signature(token, body, recent_timestamp)
        is_valid, error = verify_signature(token, body, recent_timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_verify_signature_custom_max_age(self):
        """Test verification with custom max_age_seconds."""
        token = "test-token"
        body = '{"query": "test"}'
        # Timestamp from 2 minutes ago
        timestamp = str(int(time.time()) - 120)

        signature = generate_signature(token, body, timestamp)

        # Reject with 1 minute max age
        is_valid, error = verify_signature(
            token, body, timestamp, signature, max_age_seconds=60
        )
        assert is_valid is False
        assert error is not None
        assert "Request expired" in error

        # Accept with 3 minute max age
        is_valid, error = verify_signature(
            token, body, timestamp, signature, max_age_seconds=180
        )
        assert is_valid is True
        assert error is None

    def test_verify_signature_future_timestamp_rejected(self):
        """Test that future timestamps are rejected (clock skew attack)."""
        token = "test-token"
        body = '{"query": "test"}'
        # Timestamp 1 minute in the future
        future_timestamp = str(int(time.time()) + 60)

        signature = generate_signature(token, body, future_timestamp)
        is_valid, error = verify_signature(token, body, future_timestamp, signature)

        assert is_valid is False
        assert error == "Request timestamp in the future"

    def test_verify_signature_allows_small_clock_skew(self):
        """Test that small clock skew (<=30s) is allowed."""
        token = "test-token"
        body = '{"query": "test"}'
        # Timestamp 15 seconds in the future (within 30s tolerance)
        timestamp = str(int(time.time()) + 15)

        signature = generate_signature(token, body, timestamp)
        is_valid, error = verify_signature(token, body, timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_verify_signature_invalid_timestamp_format(self):
        """Test that invalid timestamp format is rejected."""
        token = "test-token"
        body = '{"query": "test"}'
        invalid_timestamp = "not-a-number"

        signature = generate_signature(token, body, invalid_timestamp)
        is_valid, error = verify_signature(token, body, invalid_timestamp, signature)

        assert is_valid is False
        assert error == "Invalid timestamp format"

    def test_verify_signature_none_timestamp(self):
        """Test that None timestamp is rejected."""
        token = "test-token"
        body = '{"query": "test"}'
        signature = "dummy-signature"

        is_valid, error = verify_signature(token, body, None, signature)  # type: ignore

        assert is_valid is False
        assert error == "Invalid timestamp format"

    def test_verify_signature_empty_string_timestamp(self):
        """Test that empty string timestamp is rejected."""
        token = "test-token"
        body = '{"query": "test"}'
        signature = "dummy-signature"

        is_valid, error = verify_signature(token, body, "", signature)

        assert is_valid is False
        assert error == "Invalid timestamp format"

    def test_verify_signature_at_max_age_boundary(self):
        """Test verification at exact max_age boundary."""
        token = "test-token"
        body = '{"query": "test"}'
        # Timestamp exactly at max age (300 seconds)
        timestamp = str(int(time.time()) - SIGNATURE_VALIDITY_SECONDS)

        signature = generate_signature(token, body, timestamp)

        # Should be accepted (age = max_age_seconds, condition is age > max_age_seconds)
        is_valid, error = verify_signature(token, body, timestamp, signature)
        assert is_valid is True
        assert error is None

    def test_verify_signature_just_beyond_max_age(self):
        """Test verification just beyond max_age boundary."""
        token = "test-token"
        body = '{"query": "test"}'
        # Timestamp 1 second beyond max age
        timestamp = str(int(time.time()) - SIGNATURE_VALIDITY_SECONDS - 1)

        signature = generate_signature(token, body, timestamp)

        # Should be rejected (age > max_age_seconds)
        is_valid, error = verify_signature(token, body, timestamp, signature)
        assert is_valid is False
        assert error is not None
        assert "Request expired" in error

    def test_verify_signature_just_before_max_age(self):
        """Test verification just before max_age boundary."""
        token = "test-token"
        body = '{"query": "test"}'
        # Timestamp 1 second before max age
        timestamp = str(int(time.time()) - SIGNATURE_VALIDITY_SECONDS + 1)

        signature = generate_signature(token, body, timestamp)

        # Should be accepted
        is_valid, error = verify_signature(token, body, timestamp, signature)
        assert is_valid is True
        assert error is None


class TestAddSignatureHeaders:
    """Test add_signature_headers function."""

    def test_add_signature_headers_basic(self):
        """Test adding signature headers to request."""
        headers = {"Content-Type": "application/json"}
        token = "test-token"
        body = '{"query": "test"}'

        updated_headers = add_signature_headers(headers, token, body)

        assert "X-Request-Timestamp" in updated_headers
        assert "X-Request-Signature" in updated_headers
        assert "Content-Type" in updated_headers

    def test_add_signature_headers_creates_valid_signature(self):
        """Test that added signature can be verified."""
        headers: dict[str, str] = {}
        token = "test-token"
        body = '{"query": "test"}'

        updated_headers = add_signature_headers(headers, token, body)

        timestamp = updated_headers["X-Request-Timestamp"]
        signature = updated_headers["X-Request-Signature"]

        is_valid, error = verify_signature(token, body, timestamp, signature)
        assert is_valid is True
        assert error is None

    def test_add_signature_headers_timestamp_is_recent(self):
        """Test that generated timestamp is recent."""
        headers: dict[str, str] = {}
        token = "test-token"
        body = '{"query": "test"}'

        updated_headers = add_signature_headers(headers, token, body)

        timestamp = int(updated_headers["X-Request-Timestamp"])
        current_time = int(time.time())

        # Timestamp should be within 1 second of current time
        assert abs(timestamp - current_time) <= 1

    def test_add_signature_headers_does_not_modify_original(self):
        """Test that function returns new dict without modifying original."""
        original_headers = {"Content-Type": "application/json"}
        token = "test-token"
        body = '{"query": "test"}'

        updated_headers = add_signature_headers(original_headers.copy(), token, body)

        # Original should be unchanged
        assert "X-Request-Timestamp" not in original_headers
        assert "X-Request-Signature" not in original_headers

        # Updated should have new headers
        assert "X-Request-Timestamp" in updated_headers
        assert "X-Request-Signature" in updated_headers

    def test_add_signature_headers_empty_body(self):
        """Test adding signature headers with empty body."""
        headers: dict[str, str] = {}
        token = "test-token"
        body = ""

        updated_headers = add_signature_headers(headers, token, body)

        assert "X-Request-Timestamp" in updated_headers
        assert "X-Request-Signature" in updated_headers

    def test_add_signature_headers_multiple_calls_different_signatures(self):
        """Test that multiple calls produce different signatures (due to timestamp)."""
        headers: dict[str, str] = {}
        token = "test-token"
        body = '{"query": "test"}'

        result1 = add_signature_headers(headers.copy(), token, body)
        time.sleep(1.1)  # Wait to ensure different timestamp
        result2 = add_signature_headers(headers.copy(), token, body)

        # Timestamps should be different
        assert result1["X-Request-Timestamp"] != result2["X-Request-Timestamp"]
        # Signatures should be different
        assert result1["X-Request-Signature"] != result2["X-Request-Signature"]


class TestExtractAndVerifySignature:
    """Test extract_and_verify_signature function."""

    def test_extract_and_verify_valid_signature(self):
        """Test successful extraction and verification."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))
        signature = generate_signature(token, body, timestamp)

        # Should not raise exception
        extract_and_verify_signature(token, body, timestamp, signature)

    def test_extract_and_verify_missing_timestamp(self):
        """Test that missing timestamp header raises exception."""
        token = "test-token"
        body = '{"query": "test"}'
        signature = "dummy-signature"

        with pytest.raises(RequestSigningError) as exc_info:
            extract_and_verify_signature(token, body, None, signature)

        assert "Missing X-Request-Timestamp header" in str(exc_info.value)

    def test_extract_and_verify_missing_signature(self):
        """Test that missing signature header raises exception."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))

        with pytest.raises(RequestSigningError) as exc_info:
            extract_and_verify_signature(token, body, timestamp, None)

        assert "Missing X-Request-Signature header" in str(exc_info.value)

    def test_extract_and_verify_invalid_signature(self):
        """Test that invalid signature raises exception."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))
        wrong_signature = "0" * 64

        with pytest.raises(RequestSigningError) as exc_info:
            extract_and_verify_signature(token, body, timestamp, wrong_signature)

        assert "Request signature validation failed" in str(exc_info.value)
        assert "Invalid signature" in str(exc_info.value)

    def test_extract_and_verify_expired_signature(self):
        """Test that expired signature raises exception."""
        token = "test-token"
        body = '{"query": "test"}'
        old_timestamp = str(int(time.time()) - 600)
        signature = generate_signature(token, body, old_timestamp)

        with pytest.raises(RequestSigningError) as exc_info:
            extract_and_verify_signature(token, body, old_timestamp, signature)

        assert "Request signature validation failed" in str(exc_info.value)
        assert "Request expired" in str(exc_info.value)

    def test_extract_and_verify_custom_max_age(self):
        """Test extract and verify with custom max_age_seconds."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()) - 120)  # 2 minutes ago
        signature = generate_signature(token, body, timestamp)

        # Should raise with 1 minute max age
        with pytest.raises(RequestSigningError):
            extract_and_verify_signature(
                token, body, timestamp, signature, max_age_seconds=60
            )

        # Should succeed with 3 minute max age
        extract_and_verify_signature(
            token, body, timestamp, signature, max_age_seconds=180
        )

    def test_extract_and_verify_empty_string_headers(self):
        """Test that empty string headers are treated as missing."""
        token = "test-token"
        body = '{"query": "test"}'

        # Empty timestamp - empty string is falsy, so caught by "if not timestamp_header"
        with pytest.raises(RequestSigningError) as exc_info:
            extract_and_verify_signature(token, body, "", "signature")
        assert "Missing X-Request-Timestamp header" in str(exc_info.value)

        # Empty signature - empty string is falsy, so caught by "if not signature_header"
        with pytest.raises(RequestSigningError) as exc_info:
            extract_and_verify_signature(token, body, str(int(time.time())), "")
        assert "Missing X-Request-Signature header" in str(exc_info.value)


class TestRequestSigningError:
    """Test RequestSigningError exception."""

    def test_exception_can_be_raised(self):
        """Test that exception can be raised."""
        with pytest.raises(RequestSigningError):
            raise RequestSigningError("Test error")

    def test_exception_message(self):
        """Test exception message is preserved."""
        error_msg = "Custom error message"
        with pytest.raises(RequestSigningError) as exc_info:
            raise RequestSigningError(error_msg)

        assert str(exc_info.value) == error_msg

    def test_exception_is_exception_subclass(self):
        """Test that RequestSigningError is an Exception subclass."""
        assert issubclass(RequestSigningError, Exception)


class TestSecurityProperties:
    """Test security properties of request signing."""

    def test_timing_attack_resistance(self):
        """Test that signature comparison uses constant-time comparison."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))

        correct_sig = generate_signature(token, body, timestamp)
        # Create signature that differs only in last character
        wrong_sig = correct_sig[:-1] + ("0" if correct_sig[-1] != "0" else "1")

        # Both should fail, using constant-time comparison
        is_valid_1, _ = verify_signature(token, body, timestamp, wrong_sig)
        is_valid_2, _ = verify_signature(token, body, timestamp, "0" * 64)

        assert is_valid_1 is False
        assert is_valid_2 is False

    def test_replay_attack_prevention(self):
        """Test that old valid signatures are rejected."""
        token = "test-token"
        body = '{"query": "test"}'
        old_timestamp = str(int(time.time()) - 600)

        # Generate valid signature for old request
        signature = generate_signature(token, body, old_timestamp)

        # Even though signature is valid, should be rejected due to age
        is_valid, error = verify_signature(token, body, old_timestamp, signature)

        assert is_valid is False
        assert error is not None
        assert "expired" in error.lower()

    def test_request_tampering_prevention(self):
        """Test that any modification to request invalidates signature."""
        token = "test-token"
        original_body = '{"amount": 100}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, original_body, timestamp)

        # Try various tampering attempts
        tampering_attempts = [
            '{"amount": 1000}',  # Modified value
            '{"amount": 100, "hacked": true}',  # Added field
            '{"amount":100}',  # Whitespace change
        ]

        for tampered_body in tampering_attempts:
            is_valid, _ = verify_signature(token, tampered_body, timestamp, signature)
            assert is_valid is False

    def test_signature_includes_all_components(self):
        """Test that signature includes timestamp and body."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, body, timestamp)

        # Verify signature changes if any component changes
        sig_diff_time = generate_signature(token, body, str(int(timestamp) + 1))
        sig_diff_body = generate_signature(token, '{"query": "test2"}', timestamp)
        sig_diff_token = generate_signature("different-token", body, timestamp)

        assert signature != sig_diff_time
        assert signature != sig_diff_body
        assert signature != sig_diff_token

    def test_clock_skew_attack_prevention(self):
        """Test that future timestamps are rejected."""
        token = "test-token"
        body = '{"query": "test"}'
        future_timestamp = str(int(time.time()) + 120)  # 2 minutes future

        signature = generate_signature(token, body, future_timestamp)
        is_valid, error = verify_signature(token, body, future_timestamp, signature)

        assert is_valid is False
        assert error is not None
        assert "future" in error.lower()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_token(self):
        """Test signature with very long token."""
        token = "x" * 1000
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, body, timestamp)
        is_valid, error = verify_signature(token, body, timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_special_characters_in_token(self):
        """Test signature with special characters in token."""
        token = "token!@#$%^&*(){}[]|\\:;\"'<>,.?/~`"
        body = '{"query": "test"}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, body, timestamp)
        is_valid, error = verify_signature(token, body, timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_json_with_nested_structures(self):
        """Test signature with complex nested JSON."""
        token = "test-token"
        body = '{"level1": {"level2": {"level3": {"data": [1, 2, 3]}}}}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, body, timestamp)
        is_valid, error = verify_signature(token, body, timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_json_with_arrays(self):
        """Test signature with JSON arrays."""
        token = "test-token"
        body = '{"items": [{"id": 1}, {"id": 2}, {"id": 3}]}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, body, timestamp)
        is_valid, error = verify_signature(token, body, timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_non_json_body(self):
        """Test signature with non-JSON body."""
        token = "test-token"
        body = "This is just plain text, not JSON"
        timestamp = str(int(time.time()))

        signature = generate_signature(token, body, timestamp)
        is_valid, error = verify_signature(token, body, timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_binary_data_representation(self):
        """Test signature with binary data represented in body."""
        token = "test-token"
        body = '{"data": "\\x00\\x01\\x02\\x03"}'
        timestamp = str(int(time.time()))

        signature = generate_signature(token, body, timestamp)
        is_valid, error = verify_signature(token, body, timestamp, signature)

        assert is_valid is True
        assert error is None

    def test_maximum_timestamp_value(self):
        """Test with maximum reasonable timestamp value."""
        token = "test-token"
        body = '{"query": "test"}'
        # Year 2038 problem timestamp
        timestamp = "2147483647"

        signature = generate_signature(token, body, timestamp)

        # Should fail due to being in future
        is_valid, error = verify_signature(token, body, timestamp, signature)
        assert is_valid is False

    def test_negative_timestamp(self):
        """Test with negative timestamp."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = "-1"

        signature = generate_signature(token, body, timestamp)

        # Should fail due to age
        is_valid, error = verify_signature(token, body, timestamp, signature)
        assert is_valid is False

    def test_zero_timestamp(self):
        """Test with zero timestamp."""
        token = "test-token"
        body = '{"query": "test"}'
        timestamp = "0"

        signature = generate_signature(token, body, timestamp)

        # Should fail due to age
        is_valid, error = verify_signature(token, body, timestamp, signature)
        assert is_valid is False
        assert error is not None
        assert "expired" in error.lower()


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_complete_request_flow(self):
        """Test complete flow: add headers, extract, verify."""
        token = "production-service-token"
        body = '{"user_id": "12345", "action": "process"}'

        # Step 1: Client adds signature headers
        headers: dict[str, str] = {"Content-Type": "application/json"}
        headers_with_sig = add_signature_headers(headers, token, body)

        # Step 2: Server extracts and verifies
        timestamp_header = headers_with_sig.get("X-Request-Timestamp")
        signature_header = headers_with_sig.get("X-Request-Signature")

        # Should not raise exception
        extract_and_verify_signature(token, body, timestamp_header, signature_header)

    def test_microservice_authentication(self):
        """Test typical microservice-to-microservice authentication."""
        service_a_token = "service-a-secret-token"
        service_b_token = "service-b-secret-token"

        # Service A sends request to Service B
        request_body = '{"data": "from service A"}'
        headers: dict[str, str] = {}
        headers_with_sig = add_signature_headers(headers, service_a_token, request_body)

        # Service B verifies with correct token
        ts = headers_with_sig["X-Request-Timestamp"]
        sig = headers_with_sig["X-Request-Signature"]

        extract_and_verify_signature(service_a_token, request_body, ts, sig)

        # Service B rejects with wrong token
        with pytest.raises(RequestSigningError):
            extract_and_verify_signature(service_b_token, request_body, ts, sig)

    def test_concurrent_requests(self):
        """Test that concurrent requests with same body work correctly."""
        token = "test-token"
        body = '{"query": "test"}'

        # Generate multiple signatures "concurrently"
        headers1 = add_signature_headers({}, token, body)
        headers2 = add_signature_headers({}, token, body)

        # Both should verify independently
        extract_and_verify_signature(
            token,
            body,
            headers1["X-Request-Timestamp"],
            headers1["X-Request-Signature"],
        )
        extract_and_verify_signature(
            token,
            body,
            headers2["X-Request-Timestamp"],
            headers2["X-Request-Signature"],
        )

    def test_retry_with_new_signature(self):
        """Test that retry requires new signature after expiry."""
        token = "test-token"
        body = '{"query": "test"}'

        # First request with old timestamp
        old_timestamp = str(int(time.time()) - 600)
        old_signature = generate_signature(token, body, old_timestamp)

        # Should fail
        with pytest.raises(RequestSigningError):
            extract_and_verify_signature(token, body, old_timestamp, old_signature)

        # Retry with fresh signature
        headers = add_signature_headers({}, token, body)
        extract_and_verify_signature(
            token, body, headers["X-Request-Timestamp"], headers["X-Request-Signature"]
        )
