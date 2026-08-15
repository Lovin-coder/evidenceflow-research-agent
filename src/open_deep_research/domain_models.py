"""EvidenceFlow v1 domain contracts.

These models describe stable business boundaries. They intentionally do not
model LangGraph process state, provider payloads, claims, citations, or stores.
"""

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "evidenceflow.contracts.v1"
EVIDENCE_INSUFFICIENT_MARKER = "evidence-insufficient"
NonEmptyText = Annotated[str, Field(min_length=1)]
RAW_ARTIFACT_METADATA_KEYS = {
    "binary_document",
    "complete_payload",
    "full_html",
    "full_pdf_text",
    "full_text",
    "large_source_snapshot",
    "provider_payload",
    "raw_content",
    "raw_html",
    "raw_payload",
}


class ContractModel(BaseModel):
    """Base configuration shared by EvidenceFlow v1 contracts."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class EvidenceNeed(ContractModel):
    """Describe the evidence properties needed to answer a medical question."""

    evidence_types: list[NonEmptyText] = Field(default_factory=list)
    study_types: list[NonEmptyText] = Field(default_factory=list)
    source_policy: list[NonEmptyText] = Field(default_factory=list)
    date_constraints: list[NonEmptyText] = Field(default_factory=list)
    coverage_dimensions: list[NonEmptyText] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_domain_semantics(self) -> "EvidenceNeed":
        """Reject an empty object that carries no evidence-planning semantics."""
        if not any(
            (
                self.evidence_types,
                self.study_types,
                self.source_policy,
                self.date_constraints,
                self.coverage_dimensions,
            )
        ):
            raise ValueError("EvidenceNeed must define at least one evidence requirement")
        return self


class MedicalResearchBrief(ContractModel):
    """Represent the normalized medical research specification for a run."""

    normalized_question: NonEmptyText
    question_type: NonEmptyText
    clinical_elements: dict[str, NonEmptyText | list[NonEmptyText]] | None = None
    constraints: list[NonEmptyText]
    research_intent: NonEmptyText
    evidence_needs: list[EvidenceNeed] = Field(min_length=1)


class MedicalResearchTask(ContractModel):
    """Represent one stable Supervisor-to-Researcher delegation."""

    task_id: NonEmptyText
    research_question: NonEmptyText
    evidence_needs: list[EvidenceNeed] = Field(min_length=1)
    source_preferences: list[NonEmptyText]
    priority: int = Field(ge=0)


class SourceRecord(ContractModel):
    """Represent a compact, externally sourced artifact identity."""

    source_id: NonEmptyText
    artifact_ref: NonEmptyText | None = None
    metadata: dict[str, str]

    @model_validator(mode="after")
    def require_compact_metadata(self) -> "SourceRecord":
        """Require useful compact metadata without freezing provider-specific keys."""
        if not self.metadata:
            raise ValueError("SourceRecord.metadata must not be empty")
        if any(not key.strip() or not value.strip() for key, value in self.metadata.items()):
            raise ValueError("SourceRecord.metadata keys and values must not be blank")
        normalized_keys = {key.strip().lower().replace("-", "_") for key in self.metadata}
        forbidden_keys = normalized_keys & RAW_ARTIFACT_METADATA_KEYS
        if forbidden_keys:
            raise ValueError(
                "SourceRecord.metadata must not contain raw artifact payloads: "
                f"{sorted(forbidden_keys)}"
            )
        return self


class EvidenceRecord(ContractModel):
    """Represent a compact source-derived passage with auditable provenance."""

    evidence_id: NonEmptyText
    source_id: NonEmptyText
    locator: NonEmptyText
    excerpt: NonEmptyText
    hash: NonEmptyText


class ResearchFinding(ContractModel):
    """Represent a task-local interpretation grounded in Evidence records."""

    finding_id: NonEmptyText
    task_id: NonEmptyText
    text: NonEmptyText
    evidence_ids: list[NonEmptyText]
    limitations: list[NonEmptyText]
    conflicts: list[NonEmptyText]

    @model_validator(mode="after")
    def require_evidence_or_explicit_insufficiency(self) -> "ResearchFinding":
        """Prevent unsupported findings from silently looking evidence-grounded."""
        if not self.evidence_ids and not any(
            EVIDENCE_INSUFFICIENT_MARKER in limitation.lower()
            for limitation in self.limitations
        ):
            raise ValueError(
                "A finding without evidence_ids must be marked evidence-insufficient"
            )
        return self


class ResearchTaskStatus(str, Enum):
    """Represent the execution/termination outcome of a Researcher invocation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ResearchTaskResult(ContractModel):
    """Represent the stable Researcher-to-Supervisor output boundary."""

    contract_version: NonEmptyText = Field(default=CONTRACT_VERSION, frozen=True)
    task_id: NonEmptyText
    status: ResearchTaskStatus
    findings: list[ResearchFinding]
    evidence_ids: list[NonEmptyText]
    source_ids: list[NonEmptyText]
    summary: NonEmptyText
    limitations: list[NonEmptyText]
    conflicts: list[NonEmptyText]
    error: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_result_envelope(self) -> "ResearchTaskResult":
        """Validate status and references that are resolvable inside the envelope."""
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(
                f"ResearchTaskResult contract_version must be {CONTRACT_VERSION!r}"
            )
        if self.status is ResearchTaskStatus.FAILED and not self.error:
            raise ValueError("A failed ResearchTaskResult must include an error")
        if self.status is ResearchTaskStatus.SUCCESS and self.error:
            raise ValueError("A successful ResearchTaskResult must not include an error")

        _ensure_unique(self.evidence_ids, "evidence_ids")
        _ensure_unique(self.source_ids, "source_ids")
        _ensure_unique([finding.finding_id for finding in self.findings], "finding_ids")

        known_evidence_ids = set(self.evidence_ids)
        for finding in self.findings:
            if finding.task_id != self.task_id:
                raise ValueError("Every finding must reference the result task_id")
            missing = set(finding.evidence_ids) - known_evidence_ids
            if missing:
                raise ValueError(
                    f"Finding references Evidence IDs missing from the result: {sorted(missing)}"
                )
        return self


def validate_provenance_graph(
    *,
    task: MedicalResearchTask,
    result: ResearchTaskResult,
    sources: list[SourceRecord],
    evidence: list[EvidenceRecord],
) -> None:
    """Validate run-local Task, Source, Evidence, Finding, and Result references."""
    if result.task_id != task.task_id:
        raise ValueError("ResearchTaskResult.task_id must match MedicalResearchTask.task_id")

    source_ids = _index_unique(sources, "source_id")
    evidence_ids = _index_unique(evidence, "evidence_id")

    for record in evidence:
        if record.source_id not in source_ids:
            raise ValueError(
                f"EvidenceRecord {record.evidence_id!r} references unknown SourceRecord "
                f"{record.source_id!r}"
            )

    missing_result_sources = set(result.source_ids) - source_ids
    if missing_result_sources:
        raise ValueError(
            f"ResearchTaskResult references unknown Source IDs: {sorted(missing_result_sources)}"
        )
    missing_result_evidence = set(result.evidence_ids) - evidence_ids
    if missing_result_evidence:
        raise ValueError(
            "ResearchTaskResult references unknown Evidence IDs: "
            f"{sorted(missing_result_evidence)}"
        )

    evidence_by_id = {record.evidence_id: record for record in evidence}
    required_source_ids = {
        evidence_by_id[evidence_id].source_id for evidence_id in result.evidence_ids
    }
    missing_evidence_sources = required_source_ids - set(result.source_ids)
    if missing_evidence_sources:
        raise ValueError(
            "ResearchTaskResult.source_ids omits Sources used by its Evidence: "
            f"{sorted(missing_evidence_sources)}"
        )

    for finding in result.findings:
        missing_finding_evidence = set(finding.evidence_ids) - evidence_ids
        if missing_finding_evidence:
            raise ValueError(
                f"ResearchFinding {finding.finding_id!r} references unknown Evidence IDs: "
                f"{sorted(missing_finding_evidence)}"
            )


def _ensure_unique(values: list[str], field_name: str) -> None:
    """Reject duplicate identities within one immutable contract envelope."""
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique IDs")


def _index_unique(records: list[Any], id_field: str) -> set[str]:
    """Build a unique ID set for provenance validation."""
    identities = [getattr(record, id_field) for record in records]
    _ensure_unique(identities, id_field)
    return set(identities)
