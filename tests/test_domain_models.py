import json

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from open_deep_research.domain_models import (
    CONTRACT_VERSION,
    EvidenceNeed,
    EvidenceRecord,
    MedicalResearchBrief,
    MedicalResearchTask,
    ResearchFinding,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
    validate_provenance_graph,
)


def evidence_need() -> EvidenceNeed:
    """Build a representative nested evidence-planning requirement."""
    return EvidenceNeed(
        evidence_types=["comparative clinical outcomes"],
        study_types=["randomized trials"],
        coverage_dimensions=["benefits", "harms"],
    )


def task() -> MedicalResearchTask:
    """Build a stable task shared by provenance contract tests."""
    return MedicalResearchTask(
        task_id="task:call-1",
        research_question="How do the treatments compare?",
        evidence_needs=[evidence_need()],
        source_preferences=["primary studies"],
        priority=1,
    )


def test_contract_version_and_open_medical_vocabulary() -> None:
    """Keep the v1 identifier stable without freezing a medical taxonomy."""
    brief = MedicalResearchBrief(
        normalized_question="What evidence supports the treatment?",
        question_type="locally-defined emerging clinical category",
        clinical_elements={"population": ["adults"], "outcome": "mortality"},
        constraints=[],
        research_intent="Support a balanced treatment comparison.",
        evidence_needs=[evidence_need()],
    )

    assert CONTRACT_VERSION == "evidenceflow.contracts.v1"
    assert brief.question_type == "locally-defined emerging clinical category"


def test_result_serializes_discoverable_contract_version() -> None:
    """Ensure cross-graph results expose and enforce their wire-contract version."""
    result = ResearchTaskResult(
        task_id="task:call-1",
        status=ResearchTaskStatus.SUCCESS,
        findings=[],
        evidence_ids=[],
        source_ids=[],
        summary="Task completed.",
        limitations=[],
        conflicts=[],
    )

    serialized = result.model_dump(mode="json")

    assert serialized["contract_version"] == CONTRACT_VERSION
    assert (
        ResearchTaskResult.model_validate_json(result.model_dump_json()).contract_version
        == CONTRACT_VERSION
    )
    with pytest.raises(ValidationError, match="contract_version must be"):
        ResearchTaskResult.model_validate_json(
            json.dumps(
                {**serialized, "contract_version": "evidenceflow.contracts.v2"}
            )
        )


def test_contracts_are_strict_and_forbid_extra_fields() -> None:
    """Prevent silent schema drift or coercion at frozen contract boundaries."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MedicalResearchTask(
            task_id="task:call-1",
            research_question="Question",
            evidence_needs=[evidence_need()],
            source_preferences=[],
            priority=1,
            source_count=3,
        )

    with pytest.raises(ValidationError):
        MedicalResearchTask(
            task_id="task:call-1",
            research_question="Question",
            evidence_needs=[evidence_need()],
            source_preferences=[],
            priority="1",
        )


def test_evidence_need_requires_domain_semantics() -> None:
    """Reject an empty EvidenceNeed that contributes no planning semantics."""
    with pytest.raises(ValidationError, match="at least one evidence requirement"):
        EvidenceNeed()


def test_finding_requires_evidence_or_explicit_insufficiency() -> None:
    """Keep unsupported findings explicit rather than presenting them as grounded."""
    with pytest.raises(ValidationError, match="evidence-insufficient"):
        ResearchFinding(
            finding_id="finding-1",
            task_id="task:call-1",
            text="No conclusion could be grounded.",
            evidence_ids=[],
            limitations=[],
            conflicts=[],
        )

    finding = ResearchFinding(
        finding_id="finding-1",
        task_id="task:call-1",
        text="No conclusion could be grounded.",
        evidence_ids=[],
        limitations=["evidence-insufficient: no eligible studies were found"],
        conflicts=[],
    )
    assert finding.evidence_ids == []


def test_result_status_rules_and_wire_values() -> None:
    """Protect operational status/error rules and their serialized enum values."""
    with pytest.raises(ValidationError, match="must include an error"):
        ResearchTaskResult(
            task_id="task:call-1",
            status=ResearchTaskStatus.FAILED,
            findings=[],
            evidence_ids=[],
            source_ids=[],
            summary="Task failed.",
            limitations=[],
            conflicts=[],
        )

    result = ResearchTaskResult(
        task_id="task:call-1",
        status=ResearchTaskStatus.PARTIAL,
        findings=[],
        evidence_ids=[],
        source_ids=[],
        summary="Only part of the task was completed.",
        limitations=["Tool budget reached."],
        conflicts=[],
    )
    assert result.model_dump(mode="json")["status"] == "partial"


def test_provenance_graph_accepts_valid_references() -> None:
    """Accept a fully resolvable Task-to-Source provenance graph."""
    source = SourceRecord(
        source_id="source-1",
        artifact_ref=None,
        metadata={
            "url": "https://example.test/study",
            "title": "Study",
            "provider": "test-provider",
            "retrieved_at": "2026-08-14T00:00:00Z",
        },
    )
    evidence = EvidenceRecord(
        evidence_id="evidence-1",
        source_id=source.source_id,
        locator="page 2, paragraph 3",
        excerpt="The source-derived evidence passage.",
        hash="sha256:abc123",
    )
    finding = ResearchFinding(
        finding_id="finding-1",
        task_id=task().task_id,
        text="The study reports a measurable effect.",
        evidence_ids=[evidence.evidence_id],
        limitations=[],
        conflicts=[],
    )
    result = ResearchTaskResult(
        task_id=task().task_id,
        status=ResearchTaskStatus.SUCCESS,
        findings=[finding],
        evidence_ids=[evidence.evidence_id],
        source_ids=[source.source_id],
        summary="One grounded finding.",
        limitations=[],
        conflicts=[],
    )

    validate_provenance_graph(
        task=task(), result=result, sources=[source], evidence=[evidence]
    )


def test_provenance_graph_rejects_invalid_source_and_evidence_references() -> None:
    """Reject Evidence whose Source identity cannot be resolved."""
    orphan_evidence = EvidenceRecord(
        evidence_id="evidence-orphan",
        source_id="source-missing",
        locator="section 1",
        excerpt="An orphan source passage.",
        hash="sha256:def456",
    )
    result = ResearchTaskResult(
        task_id=task().task_id,
        status=ResearchTaskStatus.PARTIAL,
        findings=[],
        evidence_ids=[orphan_evidence.evidence_id],
        source_ids=[],
        summary="Partial result.",
        limitations=["Source unavailable."],
        conflicts=[],
    )

    with pytest.raises(ValueError, match="unknown SourceRecord"):
        validate_provenance_graph(
            task=task(), result=result, sources=[], evidence=[orphan_evidence]
        )


def test_structured_records_reject_process_and_raw_artifact_payloads() -> None:
    """Keep model messages and raw artifacts out of structured evidence channels."""
    with pytest.raises(ValidationError):
        EvidenceRecord(
            evidence_id="evidence-1",
            source_id="source-1",
            locator="paragraph 1",
            excerpt=AIMessage(content="model-generated text"),
            hash="sha256:abc",
        )

    with pytest.raises(ValidationError, match="raw artifact payloads"):
        SourceRecord(
            source_id="source-1",
            artifact_ref=None,
            metadata={"provider": "test", "raw_html": "<html>full page</html>"},
        )


def test_provenance_graph_requires_sources_used_by_result_evidence() -> None:
    """Require every result-level Evidence reference to retain its Source identity."""
    source = SourceRecord(
        source_id="source-1",
        artifact_ref=None,
        metadata={"provider": "test"},
    )
    evidence = EvidenceRecord(
        evidence_id="evidence-1",
        source_id=source.source_id,
        locator="paragraph 1",
        excerpt="Source-derived text.",
        hash="sha256:abc",
    )
    result = ResearchTaskResult(
        task_id=task().task_id,
        status=ResearchTaskStatus.PARTIAL,
        findings=[],
        evidence_ids=[evidence.evidence_id],
        source_ids=[],
        summary="Partial result.",
        limitations=["Source projection incomplete."],
        conflicts=[],
    )

    with pytest.raises(ValueError, match="omits Sources"):
        validate_provenance_graph(
            task=task(), result=result, sources=[source], evidence=[evidence]
        )


def test_result_rejects_finding_from_another_task() -> None:
    """Prevent a result from adopting Findings produced for another task."""
    finding = ResearchFinding(
        finding_id="finding-1",
        task_id="task:other",
        text="A finding.",
        evidence_ids=["evidence-1"],
        limitations=[],
        conflicts=[],
    )
    with pytest.raises(ValidationError, match="result task_id"):
        ResearchTaskResult(
            task_id="task:call-1",
            status=ResearchTaskStatus.SUCCESS,
            findings=[finding],
            evidence_ids=["evidence-1"],
            source_ids=["source-1"],
            summary="Summary.",
            limitations=[],
            conflicts=[],
        )
