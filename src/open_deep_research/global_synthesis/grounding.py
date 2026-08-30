"""Concurrent Model B execution and deterministic Grounding materialization."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from open_deep_research.domain_models import (
    ClaimGroundingRecord,
    ClaimRecord,
    EvidenceRef,
    GroundingStatus,
)
from open_deep_research.global_synthesis.projection import GroundingEvidenceAdmission
from open_deep_research.global_synthesis.types import (
    AssessedGroundingReceipt,
    ClaimEvidenceVerdict,
    ClaimGroundingDraft,
    GlobalSynthesisLimits,
    UnassessedGroundingReceipt,
    _invoke_structured_once,
    _invoke_with_host_retry,
    _serialized_model_chars,
    _StructuredValidationError,
)
from open_deep_research.prompts import GROUNDING_JUDGE_PROMPT

_MODEL_B_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class GroundingWorkerOutcome:
    """One Claim's isolated grounding record, receipt, and execution facts."""

    record: ClaimGroundingRecord
    receipt: AssessedGroundingReceipt | UnassessedGroundingReceipt
    degradation_observed: bool
    error: str | None = None


def _strict_unassessed(claim_id: str, *, error: str | None = None) -> GroundingWorkerOutcome:
    """Materialize UNASSESSED without inventing attempted or evaluated Evidence."""
    return GroundingWorkerOutcome(
        record=ClaimGroundingRecord(
            claim_id=claim_id,
            evaluated_evidence_refs=[],
            supporting_evidence_refs=[],
            contradicting_evidence_refs=[],
            status=GroundingStatus.UNASSESSED,
            reason=None,
        ),
        receipt=UnassessedGroundingReceipt(claim_id=claim_id),
        degradation_observed=True,
        error=error,
    )


def _canonical_filtered_order(
    evaluated: Sequence[EvidenceRef], selected: Sequence[EvidenceRef]
) -> list[EvidenceRef]:
    selected_coordinates = {(ref.task_id, ref.evidence_id) for ref in selected}
    return [
        ref
        for ref in evaluated
        if (ref.task_id, ref.evidence_id) in selected_coordinates
    ]


def _validate_and_materialize_grounding(
    draft: ClaimGroundingDraft,
    *,
    claim: ClaimRecord,
    evaluated_evidence_refs: Sequence[EvidenceRef],
    limits: GlobalSynthesisLimits,
) -> GroundingWorkerOutcome:
    """Validate Judge authority and apply the exact frozen five-state mapping."""
    if _serialized_model_chars(draft) > limits.max_grounding_draft_serialized_chars:
        raise _StructuredValidationError("Grounding draft exceeds serialized capacity")
    if len(draft.reason) > limits.max_grounding_reason_chars:
        raise _StructuredValidationError("Grounding reason exceeds capacity")
    if any(ord(character) < 32 and character not in "\n\t" for character in draft.reason):
        raise _StructuredValidationError("Grounding reason contains control characters")

    supporting = draft.supporting_evidence_refs
    contradicting = draft.contradicting_evidence_refs
    supporting_coordinates = [(ref.task_id, ref.evidence_id) for ref in supporting]
    contradicting_coordinates = [
        (ref.task_id, ref.evidence_id) for ref in contradicting
    ]
    evaluated_coordinates = {
        (ref.task_id, ref.evidence_id) for ref in evaluated_evidence_refs
    }
    if len(supporting_coordinates) != len(set(supporting_coordinates)):
        raise _StructuredValidationError("Supporting EvidenceRefs must be unique")
    if len(contradicting_coordinates) != len(set(contradicting_coordinates)):
        raise _StructuredValidationError("Contradicting EvidenceRefs must be unique")
    if not set(supporting_coordinates) <= evaluated_coordinates:
        raise _StructuredValidationError("Supporting EvidenceRefs exceed Judge input")
    if not set(contradicting_coordinates) <= evaluated_coordinates:
        raise _StructuredValidationError("Contradicting EvidenceRefs exceed Judge input")
    if set(supporting_coordinates) & set(contradicting_coordinates):
        raise _StructuredValidationError("Grounding material Evidence roles must be disjoint")
    if list(supporting) != _canonical_filtered_order(
        evaluated_evidence_refs, supporting
    ):
        raise _StructuredValidationError("Supporting EvidenceRefs are out of order")
    if list(contradicting) != _canonical_filtered_order(
        evaluated_evidence_refs, contradicting
    ):
        raise _StructuredValidationError("Contradicting EvidenceRefs are out of order")

    if draft.verdict is ClaimEvidenceVerdict.SUPPORTED:
        if not supporting:
            raise _StructuredValidationError("SUPPORTED requires supporting Evidence")
        status = (
            GroundingStatus.SUPPORTED_WITH_CONFLICT
            if contradicting
            else GroundingStatus.SUPPORTED
        )
    elif draft.verdict is ClaimEvidenceVerdict.CONTRADICTED:
        if not contradicting:
            raise _StructuredValidationError(
                "CONTRADICTED requires contradicting Evidence"
            )
        status = GroundingStatus.CONTRADICTED
    else:
        status = GroundingStatus.INSUFFICIENT

    record = ClaimGroundingRecord(
        claim_id=claim.claim_id,
        evaluated_evidence_refs=list(evaluated_evidence_refs),
        supporting_evidence_refs=supporting,
        contradicting_evidence_refs=contradicting,
        status=status,
        reason=draft.reason,
    )
    return GroundingWorkerOutcome(
        record=record,
        receipt=AssessedGroundingReceipt(
            claim_id=claim.claim_id,
            validated_verdict=draft.verdict,
            evaluated_evidence_refs=tuple(evaluated_evidence_refs),
            expected_status=status,
        ),
        degradation_observed=False,
    )


async def _invoke_grounding_judge(
    invoke: Callable[[list[HumanMessage]], Awaitable[object]],
    *,
    admission: GroundingEvidenceAdmission,
    max_retries: int,
    limits: GlobalSynthesisLimits,
    sleep: Callable[[float], Awaitable[None]],
) -> GroundingWorkerOutcome:
    """Invoke and validate one Claim Judge under the shared Host retry policy."""
    evaluated = [view.evidence_ref for view in admission.evidence]
    projection = {
        "claim": admission.claim.model_dump(mode="json"),
        "evidence": [view.model_dump(mode="json") for view in admission.evidence],
    }
    request = [
        HumanMessage(
            content=GROUNDING_JUDGE_PROMPT.format(
                projection=json.dumps(
                    projection,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        )
    ]

    async def invoke_once() -> object:
        return await _invoke_structured_once(
            invoke, request, timeout_seconds=_MODEL_B_TIMEOUT_SECONDS
        )

    def validate(response: object) -> GroundingWorkerOutcome:
        draft = ClaimGroundingDraft.model_validate(response)
        return _validate_and_materialize_grounding(
            draft,
            claim=admission.claim,
            evaluated_evidence_refs=evaluated,
            limits=limits,
        )

    return await _invoke_with_host_retry(
        invoke_once,
        validate,
        max_retries=max_retries,
        sleep=sleep,
    )


async def _judge_claim_safe(
    invoke: Callable[[list[HumanMessage]], Awaitable[object]],
    *,
    admission: GroundingEvidenceAdmission,
    semaphore: asyncio.Semaphore,
    max_retries: int,
    limits: GlobalSynthesisLimits,
    sleep: Callable[[float], Awaitable[None]],
) -> GroundingWorkerOutcome:
    """Isolate ordinary Claim-local Judge failure while propagating cancellation."""
    if admission.skip_model_b:
        return _strict_unassessed(admission.claim.claim_id)
    try:
        async with semaphore:
            return await _invoke_grounding_judge(
                invoke,
                admission=admission,
                max_retries=max_retries,
                limits=limits,
                sleep=sleep,
            )
    except Exception as error:
        return _strict_unassessed(
            admission.claim.claim_id,
            error=f"{type(error).__name__}: {error}",
        )


async def _judge_claims(
    invoke: Callable[[list[HumanMessage]], Awaitable[object]],
    *,
    admissions: Sequence[GroundingEvidenceAdmission],
    max_concurrency: int,
    max_retries: int,
    limits: GlobalSynthesisLimits,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> tuple[GroundingWorkerOutcome, ...]:
    """Judge Claims concurrently while retaining canonical input ordering."""
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be positive")
    semaphore = asyncio.Semaphore(max_concurrency)
    outcomes = await asyncio.gather(
        *(
            _judge_claim_safe(
                invoke,
                admission=admission,
                semaphore=semaphore,
                max_retries=max_retries,
                limits=limits,
                sleep=sleep,
            )
            for admission in admissions
        )
    )
    return tuple(outcomes)
