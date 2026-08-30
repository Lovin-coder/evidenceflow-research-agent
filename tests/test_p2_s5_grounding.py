"""Focused tests for P2-S5 Evidence admission and five-state Grounding."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from test_p2_s5_projection import _result

from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.domain_models import (
    ClaimMateriality,
    ClaimRecord,
    EvidenceRef,
    FindingRef,
    GroundingStatus,
)
from open_deep_research.global_synthesis.grounding import (
    _judge_claims,
    _strict_unassessed,
    _validate_and_materialize_grounding,
)
from open_deep_research.global_synthesis.projection import (
    TaskQualifiedResolver,
    build_grounding_evidence_admission,
)
from open_deep_research.global_synthesis.types import (
    AssessedGroundingReceipt,
    ClaimEvidenceVerdict,
    ClaimGroundingDraft,
    GlobalSynthesisLimits,
    _StructuredValidationError,
)


def _claim(claim_id: str = "claim-1") -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        text="Treatment improves outcomes.",
        materiality=ClaimMateriality.HIGH,
        finding_refs=[FindingRef(task_id="task-1", finding_id="shared-finding")],
        scope="Adults",
        qualifiers=["At twelve weeks"],
    )


def _admission(tmp_path, *, limits=None, claim_id="claim-1"):
    result = _result("task-1")
    resolver = TaskQualifiedResolver(
        [result], LocalFileArtifactStore(tmp_path, "grounding-run")
    )
    return build_grounding_evidence_admission(
        claim=_claim(claim_id),
        resolver=resolver,
        limits=limits or GlobalSynthesisLimits(),
    )


def _draft(
    verdict: ClaimEvidenceVerdict,
    *,
    supporting: list[EvidenceRef] | None = None,
    contradicting: list[EvidenceRef] | None = None,
) -> ClaimGroundingDraft:
    return ClaimGroundingDraft(
        verdict=verdict,
        supporting_evidence_refs=supporting or [],
        contradicting_evidence_refs=contradicting or [],
        reason="Bounded semantic assessment.",
    )


def test_evidence_universe_uses_exact_excerpt_and_whitelisted_metadata(tmp_path) -> None:
    admission = _admission(tmp_path)

    assert len(admission.evidence) == 1
    view = admission.evidence[0]
    assert view.evidence_ref == EvidenceRef(
        task_id="task-1", evidence_id="shared-evidence"
    )
    assert view.excerpt == "Exact evidence excerpt."
    payload = view.model_dump(mode="json")
    assert "artifact_ref" not in payload
    assert "raw_content" not in payload
    assert admission.skip_model_b is False


def test_judge_admission_is_a_whole_canonical_prefix(tmp_path) -> None:
    admission = _admission(
        tmp_path,
        limits=replace(GlobalSynthesisLimits(), max_judge_evidence_chars=1),
    )

    assert admission.evidence == ()
    assert admission.skip_model_b is True
    assert admission.omitted_evidence_count == 1
    assert admission.degradation_observed is True


@pytest.mark.parametrize(
    ("verdict", "has_support", "has_conflict", "expected"),
    [
        (ClaimEvidenceVerdict.SUPPORTED, True, False, GroundingStatus.SUPPORTED),
        (
            ClaimEvidenceVerdict.SUPPORTED,
            True,
            True,
            GroundingStatus.SUPPORTED_WITH_CONFLICT,
        ),
        (
            ClaimEvidenceVerdict.INSUFFICIENT,
            False,
            False,
            GroundingStatus.INSUFFICIENT,
        ),
        (
            ClaimEvidenceVerdict.CONTRADICTED,
            False,
            True,
            GroundingStatus.CONTRADICTED,
        ),
    ],
)
def test_exact_assessed_status_mapping(
    verdict, has_support, has_conflict, expected
) -> None:
    first = EvidenceRef(task_id="task-1", evidence_id="evidence-1")
    second = EvidenceRef(task_id="task-1", evidence_id="evidence-2")
    outcome = _validate_and_materialize_grounding(
        _draft(
            verdict,
            supporting=[first] if has_support else [],
            contradicting=[second] if has_conflict else [],
        ),
        claim=_claim(),
        evaluated_evidence_refs=[first, second],
        limits=GlobalSynthesisLimits(),
    )

    assert outcome.record.status is expected
    assert outcome.record.evaluated_evidence_refs == [first, second]
    assert isinstance(outcome.receipt, AssessedGroundingReceipt)


def test_insufficient_preserves_material_sets_without_heuristic_override() -> None:
    first = EvidenceRef(task_id="task-1", evidence_id="evidence-1")
    second = EvidenceRef(task_id="task-1", evidence_id="evidence-2")
    outcome = _validate_and_materialize_grounding(
        _draft(
            ClaimEvidenceVerdict.INSUFFICIENT,
            supporting=[first],
            contradicting=[second],
        ),
        claim=_claim(),
        evaluated_evidence_refs=[first, second],
        limits=GlobalSynthesisLimits(),
    )
    assert outcome.record.status is GroundingStatus.INSUFFICIENT


def test_invalid_roles_refs_and_order_are_rejected() -> None:
    first = EvidenceRef(task_id="task-1", evidence_id="evidence-1")
    second = EvidenceRef(task_id="task-1", evidence_id="evidence-2")
    with pytest.raises(_StructuredValidationError, match="out of order"):
        _validate_and_materialize_grounding(
            _draft(ClaimEvidenceVerdict.SUPPORTED, supporting=[second, first]),
            claim=_claim(),
            evaluated_evidence_refs=[first, second],
            limits=GlobalSynthesisLimits(),
        )
    with pytest.raises(_StructuredValidationError, match="disjoint"):
        _validate_and_materialize_grounding(
            _draft(
                ClaimEvidenceVerdict.SUPPORTED,
                supporting=[first],
                contradicting=[first],
            ),
            claim=_claim(),
            evaluated_evidence_refs=[first],
            limits=GlobalSynthesisLimits(),
        )


def test_strict_unassessed_has_no_fake_evaluated_universe() -> None:
    outcome = _strict_unassessed("claim-1", error="provider failed")
    assert outcome.record.status is GroundingStatus.UNASSESSED
    assert outcome.record.evaluated_evidence_refs == []
    assert outcome.record.supporting_evidence_refs == []
    assert outcome.record.contradicting_evidence_refs == []
    assert outcome.record.reason is None
    assert outcome.degradation_observed is True


class _ConcurrentJudge:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def ainvoke(self, messages) -> object:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        content = messages[0].content
        await asyncio.sleep(0.02 if "claim-1" in content else 0)
        self.active -= 1
        if "claim-fail" in content:
            raise RuntimeError("claim-local")
        evidence_id = "shared-evidence"
        return _draft(
            ClaimEvidenceVerdict.SUPPORTED,
            supporting=[EvidenceRef(task_id="task-1", evidence_id=evidence_id)],
        )


@pytest.mark.asyncio
async def test_concurrency_is_bounded_ordered_and_failure_isolated(tmp_path) -> None:
    admissions = [
        _admission(tmp_path, claim_id="claim-1"),
        _admission(tmp_path, claim_id="claim-fail"),
        _admission(tmp_path, claim_id="claim-3"),
    ]
    judge = _ConcurrentJudge()
    outcomes = await _judge_claims(
        judge.ainvoke,
        admissions=admissions,
        max_concurrency=2,
        max_retries=0,
        limits=GlobalSynthesisLimits(),
    )

    assert judge.max_active == 2
    assert [outcome.record.claim_id for outcome in outcomes] == [
        "claim-1",
        "claim-fail",
        "claim-3",
    ]
    assert outcomes[1].record.status is GroundingStatus.UNASSESSED
    assert outcomes[0].record.status is GroundingStatus.SUPPORTED
    assert outcomes[2].record.status is GroundingStatus.SUPPORTED


@pytest.mark.asyncio
async def test_cancellation_propagates_from_claim_worker(tmp_path) -> None:
    async def cancel(_messages):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _judge_claims(
            cancel,
            admissions=[_admission(tmp_path)],
            max_concurrency=1,
            max_retries=3,
            limits=GlobalSynthesisLimits(),
        )
