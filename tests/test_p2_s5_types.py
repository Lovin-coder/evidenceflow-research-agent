"""Focused tests for P2-S5 process-local types and retry ownership."""

import asyncio
from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from open_deep_research.global_synthesis.types import (
    ClaimDraftBatch,
    ClaimMaterializationReceipt,
    GlobalSynthesisLimits,
    GlobalSynthesisStage,
    ReportParagraphDraft,
    ReportSectionDraft,
    ShadowReportDraft,
    _invoke_structured_once,
    _invoke_with_host_retry,
    _StructuredValidationError,
    _validate_claim_draft_batch,
    _validate_shadow_report_draft,
)


def test_limits_match_frozen_values_and_capacity_relationship() -> None:
    limits = GlobalSynthesisLimits()

    assert limits.max_findings_total == 40
    assert limits.max_section_title_chars == 300
    assert limits.max_shadow_report_chars == 30_000
    assert limits.max_citations >= limits.max_claims * limits.max_evidence_refs_per_claim
    with pytest.raises(ValueError, match="max_citations"):
        GlobalSynthesisLimits(max_citations=479)


def test_receipts_and_limits_are_immutable() -> None:
    receipt = ClaimMaterializationReceipt(0, b"{}", "claim:1")

    with pytest.raises(FrozenInstanceError):
        setattr(receipt, "expected_claim_id", "claim:2")
    with pytest.raises(FrozenInstanceError):
        setattr(GlobalSynthesisLimits(), "max_claims", 1)


def test_stage_values_are_stable_issue_strings() -> None:
    assert GlobalSynthesisStage.INPUT_PROJECTION.value == "input_projection"
    assert GlobalSynthesisStage.RENDERER_VALIDATION.value == "renderer_validation"


def _draft_with_title(title: str) -> ShadowReportDraft:
    return ShadowReportDraft(
        sections=[
            ReportSectionDraft(
                title=title,
                paragraphs=[ReportParagraphDraft(text="Body", claim_ids=["claim:1"])],
            )
        ]
    )


def test_renderer_aggregate_validates_limit_minus_one_limit_and_limit_plus_one() -> None:
    limits = GlobalSynthesisLimits()

    assert _validate_shadow_report_draft(
        _draft_with_title("x" * (limits.max_section_title_chars - 1)), limits
    )
    assert _validate_shadow_report_draft(
        _draft_with_title("x" * limits.max_section_title_chars), limits
    )
    with pytest.raises(_StructuredValidationError, match="section title"):
        _validate_shadow_report_draft(
            _draft_with_title("x" * (limits.max_section_title_chars + 1)), limits
        )


def test_claim_batch_aggregate_rejects_item_overflow() -> None:
    limits = GlobalSynthesisLimits(max_claim_drafts_returned=0)
    assert _validate_claim_draft_batch(ClaimDraftBatch(claims=[]), limits)


@pytest.mark.asyncio
async def test_single_attempt_sends_exactly_one_request() -> None:
    calls = 0

    async def invoke(value: str) -> str:
        nonlocal calls
        calls += 1
        return value.upper()

    assert await _invoke_structured_once(invoke, "ok", timeout_seconds=1) == "OK"
    assert calls == 1


@pytest.mark.asyncio
async def test_validation_failures_retry_immediately_without_sleep() -> None:
    attempts = 0
    sleeps: list[float] = []

    async def invoke_once() -> int:
        nonlocal attempts
        attempts += 1
        return attempts

    def validate(value: int) -> int:
        if value < 3:
            raise _StructuredValidationError("invalid")
        return value

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    assert await _invoke_with_host_retry(
        invoke_once, validate, max_retries=3, sleep=sleep
    ) == 3
    assert attempts == 3
    assert sleeps == []


@pytest.mark.asyncio
async def test_transient_failures_use_capped_deterministic_backoff() -> None:
    attempts = 0
    sleeps: list[float] = []

    async def invoke_once() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 5:
            raise TimeoutError("transient")
        return "ok"

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    assert await _invoke_with_host_retry(
        invoke_once, lambda value: value, max_retries=4, sleep=sleep
    ) == "ok"
    assert attempts == 5
    assert sleeps == [0.5, 1.0, 2.0, 2.0]


@pytest.mark.asyncio
async def test_request_count_is_bounded_and_cancellation_propagates() -> None:
    calls = 0

    async def fail() -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider")

    with pytest.raises(RuntimeError, match="provider"):
        await _invoke_with_host_retry(fail, lambda value: value, max_retries=2)
    assert calls == 3

    async def cancel() -> str:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _invoke_with_host_retry(cancel, lambda value: value, max_retries=3)


def test_internal_models_remain_strict() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        ClaimDraftBatch.model_validate({"claims": [], "unexpected": True})
