"""EvidenceFlow v1 domain contracts.

These models describe stable business boundaries. They intentionally do not
model LangGraph process state, provider payloads, claims, citations, or stores.
"""

import json
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "evidenceflow.contracts.v1"
EVIDENCE_INSUFFICIENT_MARKER = "evidence-insufficient"
MAX_EVIDENCE_EXCERPT_CHARS = 8_000
MAX_SOURCE_METADATA_SERIALIZED_CHARS = 8_000
NonEmptyText = Annotated[str, Field(min_length=1)]
RAW_ARTIFACT_METADATA_KEYS = {
    "binary_document",
    "complete_payload",
    "content",
    "full_html",
    "full_pdf_text",
    "full_text",
    "large_source_snapshot",
    "page_content",
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

    evidence_types: list[NonEmptyText] = Field(
        default_factory=list,
        description="Evidence categories needed to answer the medical question.",
    )
    study_types: list[NonEmptyText] = Field(
        default_factory=list,
        description="Preferred or required study designs without implying quality judgment.",
    )
    source_policy: list[NonEmptyText] = Field(
        default_factory=list,
        description="Inclusion, exclusion, or required-source constraints for research.",
    )
    date_constraints: list[NonEmptyText] = Field(
        default_factory=list,
        description="Time boundaries governing evidence retrieval and inclusion.",
    )
    coverage_dimensions: list[NonEmptyText] = Field(
        default_factory=list,
        description="Clinical or analytical dimensions the evidence must cover.",
    )

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

    normalized_question: NonEmptyText = Field(
        description="Normalized medical question driving research planning."
    )
    question_type: NonEmptyText = Field(
        description="Open-text medical question category used for domain-aware planning."
    )
    clinical_elements: dict[str, NonEmptyText | list[NonEmptyText]] | None = Field(
        default=None,
        description="Structured clinical elements, including PICO concepts when applicable.",
    )
    constraints: list[NonEmptyText] = Field(
        description="Run-level population, time, language, region, or output constraints."
    )
    research_intent: NonEmptyText = Field(
        description="Decision, comparison, explanation, or exploration the research supports."
    )
    evidence_needs: list[EvidenceNeed] = Field(
        min_length=1,
        description="Nested evidence requirements guiding downstream task planning and retrieval.",
    )


class MedicalResearchTask(ContractModel):
    """Represent one stable Supervisor-to-Researcher delegation."""

    task_id: NonEmptyText = Field(
        description="Host-assigned run-local identity for one logical research delegation."
    )
    research_question: NonEmptyText = Field(
        description="Focused, self-contained question assigned to one Researcher invocation."
    )
    evidence_needs: list[EvidenceNeed] = Field(
        min_length=1,
        description="Evidence requirements this delegated task must address."
    )
    source_preferences: list[NonEmptyText] = Field(
        description="Non-binding source or provider preferences that cannot weaken source policy."
    )
    priority: int = Field(
        ge=0,
        description="Relative planning priority without an execution-order guarantee.",
    )


class SourceRecord(ContractModel):
    """Represent a compact, externally sourced artifact identity."""

    source_id: NonEmptyText = Field(
        description="Stable run-local identity used by Evidence provenance references."
    )
    artifact_ref: NonEmptyText | None = Field(
        default=None,
        description="Optional opaque reference to raw content outside Graph State.",
    )
    metadata: dict[str, str] = Field(
        description="Compact source and retrieval provenance metadata, never the raw artifact."
    )

    @model_validator(mode="after")
    def require_compact_metadata(self) -> "SourceRecord":
        """Reject blank, raw-content-bearing, or oversized source metadata."""
        if not self.metadata:
            raise ValueError("SourceRecord.metadata must not be empty")
        if any(not key.strip() or not value.strip() for key, value in self.metadata.items()):
            raise ValueError("SourceRecord.metadata keys and values must not be blank")
        forbidden_normalized_keys = {
            _normalize_metadata_key(key) for key in RAW_ARTIFACT_METADATA_KEYS
        }
        forbidden_keys = {
            key
            for key in self.metadata
            if _normalize_metadata_key(key) in forbidden_normalized_keys
        }
        if forbidden_keys:
            raise ValueError(
                "SourceRecord.metadata must not contain raw artifact payloads: "
                f"{sorted(forbidden_keys)}"
            )
        serialized_metadata = json.dumps(
            self.metadata,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(serialized_metadata) > MAX_SOURCE_METADATA_SERIALIZED_CHARS:
            raise ValueError(
                "SourceRecord.metadata serialized content must not exceed "
                f"{MAX_SOURCE_METADATA_SERIALIZED_CHARS} characters"
            )
        return self


class EvidenceRecord(ContractModel):
    """Represent a compact source-derived passage with auditable provenance."""

    evidence_id: NonEmptyText = Field(
        description="Stable identity for one selected, auditable evidence passage."
    )
    source_id: NonEmptyText = Field(
        description="Identity of the SourceRecord from which this evidence was selected."
    )
    locator: NonEmptyText = Field(
        description="Auditable location of the passage within its source artifact."
    )
    excerpt: str = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_EXCERPT_CHARS,
        description=(
            "Source-derived passage bounded for Graph State compactness, not an "
            "evidence-quality judgment."
        ),
    )
    hash: NonEmptyText = Field(
        description="Content hash supporting passage audit and change detection."
    )


class ResearchFinding(ContractModel):
    """Represent a task-local interpretation grounded in Evidence records."""

    finding_id: NonEmptyText = Field(
        description="Stable identity for one task-local research conclusion."
    )
    task_id: NonEmptyText = Field(
        description="MedicalResearchTask identity that produced this finding."
    )
    text: NonEmptyText = Field(
        description="Bounded model interpretation derived from the referenced evidence."
    )
    evidence_ids: list[NonEmptyText] = Field(
        description="Evidence identities supporting or constraining this finding."
    )
    limitations: list[NonEmptyText] = Field(
        description="Evidence gaps, applicability limits, or methodological caveats."
    )
    conflicts: list[NonEmptyText] = Field(
        description="Materially conflicting evidence or interpretations that remain visible."
    )

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

    contract_version: NonEmptyText = Field(
        default=CONTRACT_VERSION,
        frozen=True,
        description="Serialized EvidenceFlow contract version for this cross-graph result.",
    )
    task_id: NonEmptyText = Field(
        description="Identity of the MedicalResearchTask represented by this result."
    )
    status: ResearchTaskStatus = Field(
        description="Execution and termination outcome, not an evidence-quality judgment."
    )
    findings: list[ResearchFinding] = Field(
        description="Task-local findings exposed across the Researcher boundary."
    )
    evidence_ids: list[NonEmptyText] = Field(
        description="Evidence identities used or preserved by this task result."
    )
    source_ids: list[NonEmptyText] = Field(
        description="Source identities used or explicitly preserved by this task result."
    )
    summary: NonEmptyText = Field(
        description="Bounded Supervisor-facing synthesis that is not a provenance source."
    )
    limitations: list[NonEmptyText] = Field(
        description="Task-level scope limits, execution constraints, or evidence gaps."
    )
    conflicts: list[NonEmptyText] = Field(
        description="Task-level conflicts requiring visibility or later synthesis."
    )
    error: NonEmptyText | None = Field(
        default=None,
        description="Operational failure detail for partial or failed execution outcomes.",
    )

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
    """Validate all run-local provenance references exposed by a task result.

    Args:
        task: Delegated task that owns the result and its findings.
        result: Cross-graph result whose references must be resolvable.
        sources: Run-local SourceRecord registry available to the result.
        evidence: Run-local EvidenceRecord registry available to the result.

    Raises:
        ValueError: If an identity is duplicated, dangling, or inconsistent with the
            task/result provenance graph.
    """
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


def _normalize_metadata_key(key: str) -> str:
    """Normalize metadata key spelling for raw-content defense-in-depth checks."""
    return "".join(character.lower() for character in key if character.isalnum())


def _index_unique(records: list[Any], id_field: str) -> set[str]:
    """Build a unique ID set for provenance validation."""
    identities = [getattr(record, id_field) for record in records]
    _ensure_unique(identities, id_field)
    return set(identities)
