import json
from collections.abc import Callable

import pytest
from pydantic import ValidationError

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


def _finding_ref(*, task_id: str = "task-1") -> FindingRef:
    return FindingRef(task_id=task_id, finding_id="finding-1")


def _evidence_ref(*, task_id: str = "task-1") -> EvidenceRef:
    return EvidenceRef(task_id=task_id, evidence_id="evidence-1")


def _claim() -> ClaimRecord:
    return ClaimRecord(
        claim_id="claim-1",
        text="Treatment A reduced the measured outcome.",
        materiality=ClaimMateriality.HIGH,
        finding_refs=[_finding_ref()],
        scope="Adults represented in the included studies",
        qualifiers=["Follow-up did not exceed one year."],
    )


def _grounding() -> ClaimGroundingRecord:
    evidence_ref = _evidence_ref()
    return ClaimGroundingRecord(
        claim_id="claim-1",
        evaluated_evidence_refs=[evidence_ref],
        supporting_evidence_refs=[evidence_ref],
        contradicting_evidence_refs=[],
        status=GroundingStatus.SUPPORTED,
        reason="The admitted evidence directly supports the complete Claim.",
    )


def _citation() -> Citation:
    return Citation(
        citation_id="citation-1",
        claim_id="claim-1",
        evidence_ref=_evidence_ref(),
    )


def test_manifest_round_trip_preserves_stable_wire_shape() -> None:
    manifest = GroundingManifest(
        claims=[_claim()],
        groundings=[_grounding()],
        citations=[_citation()],
    )

    serialized = manifest.model_dump(mode="json")

    assert serialized == {
        "contract_version": CONTRACT_VERSION,
        "claims": [
            {
                "claim_id": "claim-1",
                "text": "Treatment A reduced the measured outcome.",
                "materiality": "high",
                "finding_refs": [
                    {"task_id": "task-1", "finding_id": "finding-1"}
                ],
                "scope": "Adults represented in the included studies",
                "qualifiers": ["Follow-up did not exceed one year."],
            }
        ],
        "groundings": [
            {
                "claim_id": "claim-1",
                "evaluated_evidence_refs": [
                    {"task_id": "task-1", "evidence_id": "evidence-1"}
                ],
                "supporting_evidence_refs": [
                    {"task_id": "task-1", "evidence_id": "evidence-1"}
                ],
                "contradicting_evidence_refs": [],
                "status": "supported",
                "reason": (
                    "The admitted evidence directly supports the complete Claim."
                ),
            }
        ],
        "citations": [
            {
                "citation_id": "citation-1",
                "claim_id": "claim-1",
                "evidence_ref": {
                    "task_id": "task-1",
                    "evidence_id": "evidence-1",
                },
            }
        ],
    }
    assert GroundingManifest.model_validate_json(manifest.model_dump_json()) == manifest


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    [
        (
            ClaimMateriality,
            {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"},
        ),
        (
            GroundingStatus,
            {
                "SUPPORTED": "supported",
                "SUPPORTED_WITH_CONFLICT": "supported_with_conflict",
                "INSUFFICIENT": "insufficient",
                "CONTRADICTED": "contradicted",
                "UNASSESSED": "unassessed",
            },
        ),
    ],
)
def test_enum_values_are_exact(
    enum_type: type[ClaimMateriality] | type[GroundingStatus],
    expected: dict[str, str],
) -> None:
    assert {member.name: member.value for member in enum_type} == expected


def test_invalid_enum_and_missing_required_field_are_rejected() -> None:
    payload = _claim().model_dump(mode="json")

    with pytest.raises(ValidationError):
        ClaimRecord.model_validate_json(
            json.dumps({**payload, "materiality": "critical"})
        )
    payload.pop("qualifiers")
    with pytest.raises(ValidationError, match="qualifiers"):
        ClaimRecord.model_validate_json(json.dumps(payload))


def test_stable_contracts_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Citation.model_validate(
            {
                "citation_id": "citation-1",
                "claim_id": "claim-1",
                "evidence_ref": _evidence_ref(),
                "display_label": "[1]",
            }
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GroundingManifest.model_validate(
            {
                "claims": [],
                "groundings": [],
                "citations": [],
                "metrics": {"supported": 1},
            }
        )


@pytest.mark.parametrize(
    "reference",
    [
        lambda: EvidenceRef(task_id="", evidence_id="evidence-1"),
        lambda: EvidenceRef(task_id="task-1", evidence_id=" "),
        lambda: FindingRef(task_id="", finding_id="finding-1"),
        lambda: FindingRef(task_id="task-1", finding_id=" "),
    ],
)
def test_task_qualified_references_require_non_empty_ids(
    reference: Callable[[], object],
) -> None:
    with pytest.raises(ValidationError):
        reference()


def test_claim_requires_non_empty_finding_lineage() -> None:
    with pytest.raises(ValidationError, match="finding_refs"):
        ClaimRecord(
            claim_id="claim-1",
            text="A factual proposition.",
            materiality=ClaimMateriality.MEDIUM,
            finding_refs=[],
            scope=None,
            qualifiers=[],
        )


def test_manifest_requires_canonical_contract_version() -> None:
    manifest = GroundingManifest(claims=[], groundings=[], citations=[])

    assert manifest.contract_version == "evidenceflow.contracts.v1"
    with pytest.raises(ValidationError, match="contract_version must be"):
        GroundingManifest.model_validate_json(
            json.dumps(
                {
                    **manifest.model_dump(mode="json"),
                    "contract_version": "evidenceflow.contracts.v2",
                }
            )
        )


def test_same_bare_id_in_different_tasks_is_a_distinct_address() -> None:
    left_evidence = EvidenceRef(task_id="task-1", evidence_id="shared")
    right_evidence = EvidenceRef(task_id="task-2", evidence_id="shared")
    left_finding = FindingRef(task_id="task-1", finding_id="shared")
    right_finding = FindingRef(task_id="task-2", finding_id="shared")

    assert left_evidence != right_evidence
    assert left_finding != right_finding
    assert left_evidence.model_dump() == {
        "task_id": "task-1",
        "evidence_id": "shared",
    }


def test_stable_models_exclude_process_and_presentation_fields() -> None:
    assert set(ClaimRecord.model_fields) == {
        "claim_id",
        "text",
        "materiality",
        "finding_refs",
        "scope",
        "qualifiers",
    }
    assert set(GroundingManifest.model_fields) == {
        "contract_version",
        "claims",
        "groundings",
        "citations",
    }
