"""Tests for escalation_gate.py."""

from __future__ import annotations

from escalation_gate import should_escalate_debug


def test_no_escalation_when_confident_and_low_risk() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk="low",
        high_risk_files_touched=False,
    )
    assert decision.escalate is False
    assert decision.reasons == []


def test_escalation_on_low_confidence() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.2,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk="low",
        high_risk_files_touched=False,
    )
    assert decision.escalate is True
    assert "low_confidence" in decision.reasons


def test_escalation_on_parse_failure() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.8,
        confidence_threshold=0.7,
        parse_failed=True,
        retry_count=0,
        max_subskill_attempts=1,
        risk="medium",
        high_risk_files_touched=False,
    )
    assert decision.escalate is True
    assert "precheck_parse_failed" in decision.reasons


def test_no_escalation_when_gate_disabled() -> None:
    decision = should_escalate_debug(
        enabled=False,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk="low",
        high_risk_files_touched=False,
    )
    assert decision.escalate is False
    assert decision.reasons == ["disabled"]


def test_disabled_gate_ignores_triggering_signals() -> None:
    decision = should_escalate_debug(
        enabled=False,
        confidence=0.2,
        confidence_threshold=0.7,
        parse_failed=True,
        retry_count=5,
        max_subskill_attempts=3,
        risk="critical",
        high_risk_files_touched=True,
    )
    assert decision.escalate is False
    assert decision.reasons == ["disabled"]


def test_escalation_on_high_risk() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk="high",
        high_risk_files_touched=False,
    )
    assert decision.escalate is True
    assert decision.reasons == ["risk_high"]


def test_escalation_on_critical_risk() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk="critical",
        high_risk_files_touched=False,
    )
    assert decision.escalate is True
    assert decision.reasons == ["risk_critical"]


def test_escalation_on_high_risk_files_touched() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk="low",
        high_risk_files_touched=True,
    )
    assert decision.escalate is True
    assert decision.reasons == ["high_risk_files"]


def test_escalation_on_retries_exhausted_at_max() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=3,
        max_subskill_attempts=3,
        risk="low",
        high_risk_files_touched=False,
    )
    assert decision.escalate is True
    assert decision.reasons == ["subskill_retries_exhausted"]


def test_escalation_on_retries_exhausted_above_max() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=5,
        max_subskill_attempts=3,
        risk="low",
        high_risk_files_touched=False,
    )
    assert decision.escalate is True
    assert decision.reasons == ["subskill_retries_exhausted"]


def test_no_escalation_when_retries_below_max() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=2,
        max_subskill_attempts=3,
        risk="low",
        high_risk_files_touched=False,
    )
    assert decision.escalate is False
    assert decision.reasons == []


def test_multi_reason_escalation() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.3,
        confidence_threshold=0.7,
        parse_failed=True,
        retry_count=5,
        max_subskill_attempts=3,
        risk="critical",
        high_risk_files_touched=True,
    )
    assert decision.escalate is True
    assert "precheck_parse_failed" in decision.reasons
    assert "low_confidence" in decision.reasons
    assert "risk_critical" in decision.reasons
    assert "high_risk_files" in decision.reasons
    assert "subskill_retries_exhausted" in decision.reasons
    assert len(decision.reasons) == 5


def test_risk_normalization_whitespace_and_case() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk=" High ",
        high_risk_files_touched=False,
    )
    assert decision.escalate is True
    assert decision.reasons == ["risk_high"]


def test_no_escalation_on_medium_risk() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.9,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk="medium",
        high_risk_files_touched=False,
    )
    assert decision.escalate is False
    assert decision.reasons == []


def test_no_escalation_at_exact_confidence_threshold() -> None:
    decision = should_escalate_debug(
        enabled=True,
        confidence=0.7,
        confidence_threshold=0.7,
        parse_failed=False,
        retry_count=0,
        max_subskill_attempts=1,
        risk="low",
        high_risk_files_touched=False,
    )
    assert decision.escalate is False
    assert decision.reasons == []
