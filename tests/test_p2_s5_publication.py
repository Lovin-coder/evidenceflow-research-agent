"""Focused tests for canonical Citations and atomic Manifest publication."""

from __future__ import annotations

from dataclasses import replace

import pytest
from test_p2_s5_projection import _result

from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.domain_models import (
    ClaimGroundingRecord,
    ClaimMateriality,
    EvidenceRef,
    FindingRef,
    GroundingManifest,
    GroundingStatus,
)
from open_deep_research.global_synthesis.claims import _materialize_claims
from open_deep_research.global_synthesis.grounding import (
    _validate_and_materialize_grounding,
)
from open_deep_research.global_synthesis.projection import TaskQualifiedResolver
from open_deep_research.global_synthesis.publication import (
    PublicationGateError,
    ReplayDisposition,
    _materialize_citations,
    derive_grounding_metrics,
    publish_manifest_candidate,
    replay_disposition,
)
from open_deep_research.global_synthesis.types import (
    ClaimDraft,
    ClaimDraftBatch,
    ClaimEvidenceVerdict,
    ClaimGroundingDraft,
    GlobalSynthesisLimits,
)
from open_deep_research.state import GlobalSynthesisStatus


def _published_fixture(tmp_path, *, conflict: bool = False):
    result = _result("task-1")
    resolver = TaskQualifiedResolver(
        [result], LocalFileArtifactStore(tmp_path, "publication-run")
    )
    finding_ref = FindingRef(task_id="task-1", finding_id="shared-finding")
    claims = _materialize_claims(
        ClaimDraftBatch(
            claims=[
                ClaimDraft(
                    text="Treatment improves outcomes.",
                    materiality=ClaimMateriality.HIGH,
                    finding_refs=[finding_ref],
                    scope=None,
                    qualifiers=[],
                )
            ]
        ),
        resolver=resolver,
        generator_visible_finding_refs=[finding_ref],
        limits=GlobalSynthesisLimits(),
    )
    evidence_ref = EvidenceRef(task_id="task-1", evidence_id="shared-evidence")
    grounding = _validate_and_materialize_grounding(
        ClaimGroundingDraft(
            verdict=ClaimEvidenceVerdict.SUPPORTED,
            supporting_evidence_refs=[evidence_ref],
            contradicting_evidence_refs=[evidence_ref] if conflict else [],
            reason="Direct assessment.",
        ),
        claim=claims.claims[0],
        evaluated_evidence_refs=[evidence_ref],
        limits=GlobalSynthesisLimits(),
    )
    citations = _materialize_citations(
        claims.claims, [grounding.record], resolver=resolver
    )
    manifest = GroundingManifest(
        claims=list(claims.claims),
        groundings=[grounding.record],
        citations=list(citations),
    )
    return manifest, claims, grounding, resolver, finding_ref


def test_citation_identity_and_order_are_deterministic(tmp_path) -> None:
    manifest, *_ = _published_fixture(tmp_path)
    first = manifest.citations[0]
    again, *_ = _published_fixture(tmp_path)

    assert first == again.citations[0]
    assert first.claim_id == manifest.claims[0].claim_id
    assert first.evidence_ref.evidence_id == "shared-evidence"


def test_publication_gate_accepts_complete_candidate_unchanged(tmp_path) -> None:
    manifest, claims, grounding, resolver, finding_ref = _published_fixture(tmp_path)

    published = publish_manifest_candidate(
        manifest,
        claim_receipts=claims.receipts,
        grounding_receipts=[grounding.receipt],
        resolver=resolver,
        generator_visible_finding_refs=[finding_ref],
        limits=GlobalSynthesisLimits(),
    )

    assert published is manifest


def test_publication_gate_recomputes_receipt_backed_claim_identity(tmp_path) -> None:
    manifest, claims, grounding, resolver, finding_ref = _published_fixture(tmp_path)
    forged_id = "claim:sha256:" + "f" * 64
    manifest.claims[0] = manifest.claims[0].model_copy(
        update={"claim_id": forged_id}
    )
    manifest.groundings[0] = manifest.groundings[0].model_copy(
        update={"claim_id": forged_id}
    )
    forged_receipt = replace(claims.receipts[0], expected_claim_id=forged_id)
    forged_grounding_receipt = replace(grounding.receipt, claim_id=forged_id)

    with pytest.raises(PublicationGateError, match="Claim ID"):
        publish_manifest_candidate(
            manifest,
            claim_receipts=[forged_receipt],
            grounding_receipts=[forged_grounding_receipt],
            resolver=resolver,
            generator_visible_finding_refs=[finding_ref],
            limits=GlobalSynthesisLimits(),
        )


def test_publication_gate_resolves_every_evaluated_evidence_ref(tmp_path) -> None:
    manifest, claims, grounding, resolver, finding_ref = _published_fixture(tmp_path)
    dangling = EvidenceRef(task_id="task-1", evidence_id="missing-evidence")
    manifest.groundings[0] = manifest.groundings[0].model_copy(
        update={
            "evaluated_evidence_refs": [
                *manifest.groundings[0].evaluated_evidence_refs,
                dangling,
            ]
        }
    )
    forged_receipt = replace(
        grounding.receipt,
        evaluated_evidence_refs=(*grounding.receipt.evaluated_evidence_refs, dangling),
    )

    with pytest.raises(PublicationGateError, match="Unknown EvidenceRef"):
        publish_manifest_candidate(
            manifest,
            claim_receipts=claims.receipts,
            grounding_receipts=[forged_receipt],
            resolver=resolver,
            generator_visible_finding_refs=[finding_ref],
            limits=GlobalSynthesisLimits(),
        )


@pytest.mark.parametrize("mutation", ["claim", "grounding", "missing", "extra", "order"])
def test_publication_gate_rejects_aggregate_mutation_without_repair(
    tmp_path, mutation
) -> None:
    manifest, claims, grounding, resolver, finding_ref = _published_fixture(tmp_path)
    if mutation == "claim":
        manifest.claims[0] = manifest.claims[0].model_copy(
            update={"claim_id": "claim:mutated"}
        )
    elif mutation == "grounding":
        manifest.groundings[0] = manifest.groundings[0].model_copy(
            update={"status": GroundingStatus.INSUFFICIENT}
        )
    elif mutation == "missing":
        manifest.citations = []
    elif mutation == "extra":
        manifest.citations.append(manifest.citations[0].model_copy())
    else:
        manifest.citations[0] = manifest.citations[0].model_copy(
            update={"citation_id": "citation:wrong-order-or-id"}
        )

    with pytest.raises(PublicationGateError):
        publish_manifest_candidate(
            manifest,
            claim_receipts=claims.receipts,
            grounding_receipts=[grounding.receipt],
            resolver=resolver,
            generator_visible_finding_refs=[finding_ref],
            limits=GlobalSynthesisLimits(),
        )


def test_manifest_payload_bound_is_validate_not_truncate(tmp_path) -> None:
    manifest, claims, grounding, resolver, finding_ref = _published_fixture(tmp_path)
    with pytest.raises(PublicationGateError, match="serialized"):
        publish_manifest_candidate(
            manifest,
            claim_receipts=claims.receipts,
            grounding_receipts=[grounding.receipt],
            resolver=resolver,
            generator_visible_finding_refs=[finding_ref],
            limits=replace(GlobalSynthesisLimits(), max_manifest_serialized_chars=1),
        )
    assert len(manifest.claims) == 1
    assert len(manifest.citations) == 1


def test_replay_paths_distinguish_synthesis_short_circuit_and_partial() -> None:
    manifest = GroundingManifest(claims=[], groundings=[], citations=[])
    assert replay_disposition(None, None, None) is ReplayDisposition.SYNTHESIS_REQUIRED
    assert (
        replay_disposition(manifest, "report", GlobalSynthesisStatus.SUCCESS)
        is ReplayDisposition.FULL_SHORT_CIRCUIT
    )
    assert (
        replay_disposition(manifest, None, GlobalSynthesisStatus.PARTIAL)
        is ReplayDisposition.PRESERVE_PARTIAL
    )


def test_metrics_cover_all_statuses_and_zero_denominators() -> None:
    empty = derive_grounding_metrics(
        GroundingManifest(claims=[], groundings=[], citations=[])
    )
    assert empty.assessed_claim_coverage is None
    assert empty.report_eligible_claim_coverage is None
    assert empty.material_report_eligible_claim_coverage is None

    manifest = GroundingManifest(
        claims=[],
        groundings=[
            ClaimGroundingRecord(
                claim_id=f"claim-{status.value}",
                evaluated_evidence_refs=[],
                supporting_evidence_refs=[],
                contradicting_evidence_refs=[],
                status=status,
                reason=None if status is GroundingStatus.UNASSESSED else "Reason",
            )
            for status in GroundingStatus
        ],
        citations=[],
    )
    metrics = derive_grounding_metrics(manifest)
    assert metrics.supported_claim_count == 1
    assert metrics.supported_with_conflict_claim_count == 1
    assert metrics.insufficient_claim_count == 1
    assert metrics.contradicted_claim_count == 1
    assert metrics.unassessed_claim_count == 1
