"""Canonical Citation construction and atomic Manifest Publication Gate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from enum import Enum
from typing import TypeAlias

from open_deep_research.domain_models import (
    CONTRACT_VERSION,
    Citation,
    ClaimGroundingRecord,
    ClaimMateriality,
    ClaimRecord,
    EvidenceRef,
    FindingRef,
    GroundingManifest,
    GroundingStatus,
)
from open_deep_research.global_synthesis.claims import (
    _canonical_claim_payload,
    _claim_id,
)
from open_deep_research.global_synthesis.grounding import (
    _validate_and_materialize_grounding,
)
from open_deep_research.global_synthesis.projection import TaskQualifiedResolver
from open_deep_research.global_synthesis.types import (
    AssessedGroundingReceipt,
    ClaimDraft,
    ClaimGroundingDraft,
    ClaimMaterializationReceipt,
    GlobalSynthesisLimits,
    GroundingMetrics,
    UnassessedGroundingReceipt,
)
from open_deep_research.state import GlobalSynthesisStatus

GroundingReceipt: TypeAlias = AssessedGroundingReceipt | UnassessedGroundingReceipt


class PublicationGateError(ValueError):
    """Reject an invalid aggregate without repairing or partially publishing it."""


class ReplayDisposition(str, Enum):
    """Distinguish normal synthesis from the two frozen replay paths."""

    SYNTHESIS_REQUIRED = "synthesis_required"
    FULL_SHORT_CIRCUIT = "full_short_circuit"
    PRESERVE_PARTIAL = "preserve_partial"


def _citation_id(claim_id: str, evidence_ref: EvidenceRef) -> str:
    """Assign identity using only the canonical Claim/EvidenceRef coordinates."""
    payload = json.dumps(
        {
            "claim_id": claim_id,
            "task_id": evidence_ref.task_id,
            "evidence_id": evidence_ref.evidence_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"citation:sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _required_citation_refs(grounding: ClaimGroundingRecord) -> list[EvidenceRef]:
    """Derive the exact reportable Evidence set from authoritative status."""
    if grounding.status is GroundingStatus.SUPPORTED:
        return list(grounding.supporting_evidence_refs)
    if grounding.status is GroundingStatus.SUPPORTED_WITH_CONFLICT:
        return [
            *grounding.supporting_evidence_refs,
            *grounding.contradicting_evidence_refs,
        ]
    return []


def _materialize_citations(
    claims: Sequence[ClaimRecord],
    groundings: Sequence[ClaimGroundingRecord],
    *,
    resolver: TaskQualifiedResolver,
) -> tuple[Citation, ...]:
    """Materialize complete Citations in Claim/support/conflict canonical order."""
    if len(claims) != len(groundings):
        raise PublicationGateError("Claims and Groundings must bind one-to-one")
    citations: list[Citation] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for claim, grounding in zip(claims, groundings, strict=True):
        if grounding.claim_id != claim.claim_id:
            raise PublicationGateError("Grounding order must match canonical Claim order")
        for evidence_ref in _required_citation_refs(grounding):
            resolver.resolve_source(evidence_ref)
            pair = (claim.claim_id, evidence_ref.task_id, evidence_ref.evidence_id)
            if pair in seen_pairs:
                raise PublicationGateError("Required Citation pair is duplicated")
            seen_pairs.add(pair)
            citations.append(
                Citation(
                    citation_id=_citation_id(claim.claim_id, evidence_ref),
                    claim_id=claim.claim_id,
                    evidence_ref=evidence_ref,
                )
            )
    return tuple(citations)


def _validate_claims(
    manifest: GroundingManifest,
    receipts: Sequence[ClaimMaterializationReceipt],
    *,
    resolver: TaskQualifiedResolver,
    visible_refs: set[tuple[str, str]],
    limits: GlobalSynthesisLimits,
) -> None:
    if len(manifest.claims) > limits.max_claims:
        raise PublicationGateError("Manifest Claim count exceeds capacity")
    if len(receipts) != len(manifest.claims):
        raise PublicationGateError("Every Claim must have one materialization receipt")
    if len({claim.claim_id for claim in manifest.claims}) != len(manifest.claims):
        raise PublicationGateError("Manifest Claim IDs must be unique")
    prior_ordinal = -1
    for claim, receipt in zip(manifest.claims, receipts, strict=True):
        if receipt.original_generator_ordinal <= prior_ordinal:
            raise PublicationGateError("Claim receipts are not in Generator order")
        prior_ordinal = receipt.original_generator_ordinal
        draft = ClaimDraft(
            text=claim.text,
            materiality=claim.materiality,
            finding_refs=claim.finding_refs,
            scope=claim.scope,
            qualifiers=claim.qualifiers,
        )
        payload = _canonical_claim_payload(draft)
        if payload != receipt.canonical_claim_payload:
            raise PublicationGateError("Claim semantic payload does not match receipt")
        expected_claim_id = _claim_id(receipt.original_generator_ordinal, payload)
        if (
            receipt.expected_claim_id != expected_claim_id
            or claim.claim_id != expected_claim_id
        ):
            raise PublicationGateError("Claim ID does not match receipt")
        if len(claim.text) > limits.max_claim_text_chars:
            raise PublicationGateError("Claim text exceeds capacity")
        if claim.scope is not None and len(claim.scope) > limits.max_claim_scope_chars:
            raise PublicationGateError("Claim scope exceeds capacity")
        if len(claim.qualifiers) > limits.max_qualifiers_per_claim:
            raise PublicationGateError("Claim qualifiers exceed capacity")
        if any(
            len(qualifier) > limits.max_qualifier_chars
            for qualifier in claim.qualifiers
        ):
            raise PublicationGateError("Claim qualifier exceeds capacity")
        coordinates = [(ref.task_id, ref.finding_id) for ref in claim.finding_refs]
        if len(coordinates) != len(set(coordinates)):
            raise PublicationGateError("Claim FindingRefs must be unique")
        if len(coordinates) > limits.max_finding_refs_per_claim:
            raise PublicationGateError("Claim FindingRefs exceed capacity")
        for ref, coordinate in zip(claim.finding_refs, coordinates, strict=True):
            resolver.resolve_finding(ref)
            if coordinate not in visible_refs:
                raise PublicationGateError("Claim FindingRef was not Generator-visible")


def _validate_groundings(
    manifest: GroundingManifest,
    receipts: Sequence[GroundingReceipt],
    *,
    resolver: TaskQualifiedResolver,
    limits: GlobalSynthesisLimits,
) -> None:
    if len(manifest.groundings) != len(manifest.claims):
        raise PublicationGateError("Every Claim must have exactly one Grounding")
    if len(receipts) != len(manifest.claims):
        raise PublicationGateError("Every Grounding must have one receipt")
    for claim, grounding, receipt in zip(
        manifest.claims, manifest.groundings, receipts, strict=True
    ):
        if grounding.claim_id != claim.claim_id or receipt.claim_id != claim.claim_id:
            raise PublicationGateError("Grounding and receipt Claim bindings diverge")
        if isinstance(receipt, UnassessedGroundingReceipt):
            if grounding != ClaimGroundingRecord(
                claim_id=claim.claim_id,
                evaluated_evidence_refs=[],
                supporting_evidence_refs=[],
                contradicting_evidence_refs=[],
                status=GroundingStatus.UNASSESSED,
                reason=None,
            ):
                raise PublicationGateError("UNASSESSED Grounding is not strict")
            continue
        evaluated_refs = receipt.evaluated_evidence_refs
        if len(evaluated_refs) > limits.max_evidence_refs_per_claim:
            raise PublicationGateError("Evaluated EvidenceRefs exceed capacity")
        evaluated_coordinates = [
            (ref.task_id, ref.evidence_id) for ref in evaluated_refs
        ]
        if len(evaluated_coordinates) != len(set(evaluated_coordinates)):
            raise PublicationGateError("Evaluated EvidenceRefs must be unique")
        for evidence_ref in evaluated_refs:
            resolver.resolve_source(evidence_ref)
        if grounding.reason is None:
            raise PublicationGateError("Assessed Grounding requires a reason")
        validated = _validate_and_materialize_grounding(
            ClaimGroundingDraft(
                verdict=receipt.validated_verdict,
                supporting_evidence_refs=grounding.supporting_evidence_refs,
                contradicting_evidence_refs=grounding.contradicting_evidence_refs,
                reason=grounding.reason,
            ),
            claim=claim,
            evaluated_evidence_refs=receipt.evaluated_evidence_refs,
            limits=limits,
        )
        if validated.record != grounding or receipt.expected_status is not grounding.status:
            raise PublicationGateError("Assessed Grounding diverges from its receipt")


def publish_manifest_candidate(
    candidate: GroundingManifest,
    *,
    claim_receipts: Sequence[ClaimMaterializationReceipt],
    grounding_receipts: Sequence[GroundingReceipt],
    resolver: TaskQualifiedResolver,
    generator_visible_finding_refs: Sequence[FindingRef],
    limits: GlobalSynthesisLimits,
) -> GroundingManifest:
    """Atomically validate the entire candidate and return it unchanged on success."""
    if candidate.contract_version != CONTRACT_VERSION:
        raise PublicationGateError("Manifest contract version is not canonical")
    visible_refs = {
        (ref.task_id, ref.finding_id) for ref in generator_visible_finding_refs
    }
    try:
        _validate_claims(
            candidate,
            claim_receipts,
            resolver=resolver,
            visible_refs=visible_refs,
            limits=limits,
        )
        _validate_groundings(
            candidate,
            grounding_receipts,
            resolver=resolver,
            limits=limits,
        )
        expected_citations = _materialize_citations(
            candidate.claims, candidate.groundings, resolver=resolver
        )
    except (ValueError, TypeError) as error:
        if isinstance(error, PublicationGateError):
            raise
        raise PublicationGateError(str(error)) from error
    if list(expected_citations) != candidate.citations:
        raise PublicationGateError("Manifest Citations are not the exact canonical set")
    if len(candidate.citations) > limits.max_citations:
        raise PublicationGateError("Manifest Citations exceed capacity")
    serialized = json.dumps(
        candidate.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(serialized) > limits.max_manifest_serialized_chars:
        raise PublicationGateError("Manifest exceeds serialized capacity")
    return candidate


def replay_disposition(
    manifest: GroundingManifest | None,
    shadow_report: str | None,
    status: GlobalSynthesisStatus | None,
) -> ReplayDisposition:
    """Apply frozen replay semantics without repairing or regenerating artifacts."""
    if manifest is None:
        return ReplayDisposition.SYNTHESIS_REQUIRED
    if shadow_report is not None:
        return ReplayDisposition.FULL_SHORT_CIRCUIT
    if status is GlobalSynthesisStatus.PARTIAL:
        return ReplayDisposition.PRESERVE_PARTIAL
    raise PublicationGateError("Existing Manifest has an invalid replay envelope")


def derive_grounding_metrics(manifest: GroundingManifest) -> GroundingMetrics:
    """Derive non-authoritative shadow metrics from a valid Manifest."""
    counts = {status: 0 for status in GroundingStatus}
    for grounding in manifest.groundings:
        counts[grounding.status] += 1
    claim_count = len(manifest.claims)
    assessed_count = claim_count - counts[GroundingStatus.UNASSESSED]
    eligible_count = (
        counts[GroundingStatus.SUPPORTED]
        + counts[GroundingStatus.SUPPORTED_WITH_CONFLICT]
    )
    high_claim_ids = {
        claim.claim_id
        for claim in manifest.claims
        if claim.materiality is ClaimMateriality.HIGH
    }
    eligible_high = sum(
        grounding.claim_id in high_claim_ids
        and grounding.status
        in (GroundingStatus.SUPPORTED, GroundingStatus.SUPPORTED_WITH_CONFLICT)
        for grounding in manifest.groundings
    )
    return GroundingMetrics(
        supported_claim_count=counts[GroundingStatus.SUPPORTED],
        supported_with_conflict_claim_count=counts[
            GroundingStatus.SUPPORTED_WITH_CONFLICT
        ],
        insufficient_claim_count=counts[GroundingStatus.INSUFFICIENT],
        contradicted_claim_count=counts[GroundingStatus.CONTRADICTED],
        unassessed_claim_count=counts[GroundingStatus.UNASSESSED],
        assessed_claim_coverage=(assessed_count / claim_count if claim_count else None),
        report_eligible_claim_coverage=(
            eligible_count / claim_count if claim_count else None
        ),
        material_report_eligible_claim_coverage=(
            eligible_high / len(high_claim_ids) if high_claim_ids else None
        ),
    )
