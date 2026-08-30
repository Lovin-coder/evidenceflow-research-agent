"""EvidenceFlow v1 domain contracts.

These models describe stable business boundaries. They intentionally do not
model LangGraph process state, provider payloads, model drafts, or stores.
"""

import json
from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = "evidenceflow.contracts.v1"
EVIDENCE_INSUFFICIENT_MARKER = "evidence-insufficient"
MAX_EVIDENCE_EXCERPT_CHARS = 8_000
MAX_RESULT_EVIDENCE_CHARS = 32_000
MAX_RESULT_EVIDENCE_RECORDS = 40
MAX_RESULT_PROVENANCE_SERIALIZED_CHARS = 256_000
MAX_RESULT_SOURCE_RECORDS = 20
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

    @field_validator("excerpt", mode="before")
    @classmethod
    def preserve_exact_excerpt_boundaries(cls, value: object) -> object:
        """Reject edge whitespace before shared string stripping can change provenance."""
        if isinstance(value, str) and value != value.strip():
            raise ValueError(
                "EvidenceRecord.excerpt must not contain leading or trailing whitespace"
            )
        return value


def measure_result_provenance_chars(
    source_records: Sequence[SourceRecord],
    evidence_records: Sequence[EvidenceRecord],
) -> int:
    """Measure the canonical compact provenance projection in characters.

    State admission and the Publication Gate share this exact definition so a
    record accepted under configured capacity cannot fail later because of a
    different serialization order or whitespace policy.
    """
    provenance_payload = {
        "source_records": [
            record.model_dump(mode="json") for record in source_records
        ],
        "evidence_records": [
            record.model_dump(mode="json") for record in evidence_records
        ],
    }
    return len(
        json.dumps(
            provenance_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


MIN_RESULT_PROVENANCE_SERIALIZED_CHARS = measure_result_provenance_chars([], [])


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
    source_records: list[SourceRecord] = Field(
        default_factory=list,
        max_length=MAX_RESULT_SOURCE_RECORDS,
        description=(
            "Compact Source targets required to resolve every published source identity."
        ),
    )
    evidence_records: list[EvidenceRecord] = Field(
        default_factory=list,
        max_length=MAX_RESULT_EVIDENCE_RECORDS,
        description=(
            "Bounded Evidence targets required to resolve every published evidence identity."
        ),
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
        _ensure_unique(
            [record.source_id for record in self.source_records], "source_record IDs"
        )
        _ensure_unique(
            [record.evidence_id for record in self.evidence_records],
            "evidence_record IDs",
        )
        _ensure_unique([finding.finding_id for finding in self.findings], "finding_ids")

        projected_source_ids = [record.source_id for record in self.source_records]
        projected_evidence_ids = [record.evidence_id for record in self.evidence_records]
        if self.source_ids != projected_source_ids:
            raise ValueError(
                "source_ids must exactly project source_records in record order"
            )
        if self.evidence_ids != projected_evidence_ids:
            raise ValueError(
                "evidence_ids must exactly project evidence_records in record order"
            )

        known_source_ids = set(projected_source_ids)
        for record in self.evidence_records:
            if record.source_id not in known_source_ids:
                raise ValueError(
                    f"EvidenceRecord {record.evidence_id!r} references unknown "
                    f"SourceRecord {record.source_id!r} in the result"
                )

        known_evidence_ids = set(projected_evidence_ids)
        for finding in self.findings:
            if finding.task_id != self.task_id:
                raise ValueError("Every finding must reference the result task_id")
            missing = set(finding.evidence_ids) - known_evidence_ids
            if missing:
                raise ValueError(
                    f"Finding references Evidence IDs missing from the result: {sorted(missing)}"
                )

        total_evidence_chars = sum(
            len(record.excerpt) for record in self.evidence_records
        )
        if total_evidence_chars > MAX_RESULT_EVIDENCE_CHARS:
            raise ValueError(
                "ResearchTaskResult Evidence excerpts must not exceed "
                f"{MAX_RESULT_EVIDENCE_CHARS} total characters"
            )

        serialized_size = measure_result_provenance_chars(
            self.source_records,
            self.evidence_records,
        )
        if serialized_size > MAX_RESULT_PROVENANCE_SERIALIZED_CHARS:
            raise ValueError(
                "ResearchTaskResult provenance payload must not exceed "
                f"{MAX_RESULT_PROVENANCE_SERIALIZED_CHARS} serialized characters"
            )
        return self


class EvidenceRef(ContractModel):
    """Address one Evidence record within its owning research task result."""

    task_id: NonEmptyText = Field(
        description="Identity of the ResearchTaskResult owning the Evidence record."
    )
    evidence_id: NonEmptyText = Field(
        description="Task-local identity of the addressed Evidence record."
    )


class FindingRef(ContractModel):
    """Address one Finding within its owning research task result."""

    task_id: NonEmptyText = Field(
        description="Identity of the ResearchTaskResult owning the Finding."
    )
    finding_id: NonEmptyText = Field(
        description="Task-local identity of the addressed Finding."
    )


class ClaimMateriality(str, Enum):
    """Represent a Claim's importance to the user's core question."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClaimRecord(ContractModel):
    """Represent one Host-materialized authoritative synthesis Claim."""

    claim_id: NonEmptyText = Field(
        description="Host-assigned identity unique within the owning Manifest."
    )
    text: NonEmptyText = Field(
        description="Bounded factual proposition proposed for V2 report space."
    )
    materiality: ClaimMateriality = Field(
        description="Importance of the Claim to the user's core question."
    )
    finding_refs: list[FindingRef] = Field(
        min_length=1,
        description="Non-empty task-qualified Finding lineage for this Claim."
    )
    scope: NonEmptyText | None = Field(
        default=None,
        description="Optional population, condition, or applicability boundary."
    )
    qualifiers: list[NonEmptyText] = Field(
        description="Limitations that authoritative expression of the Claim must retain."
    )


class GroundingStatus(str, Enum):
    """Represent the Host-materialized grounding state of a Claim."""

    SUPPORTED = "supported"
    SUPPORTED_WITH_CONFLICT = "supported_with_conflict"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"
    UNASSESSED = "unassessed"


class ClaimGroundingRecord(ContractModel):
    """Represent the authoritative grounding assessment for one Claim."""

    claim_id: NonEmptyText = Field(
        description="Identity of the Claim assessed by this record."
    )
    evaluated_evidence_refs: list[EvidenceRef] = Field(
        description="Ordered Evidence inputs used for the valid semantic assessment."
    )
    supporting_evidence_refs: list[EvidenceRef] = Field(
        description="Evaluated Evidence providing material positive support."
    )
    contradicting_evidence_refs: list[EvidenceRef] = Field(
        description="Evaluated Evidence providing material negative evidence."
    )
    status: GroundingStatus = Field(
        description="Host-materialized semantic or unassessed grounding state."
    )
    reason: NonEmptyText | None = Field(
        default=None,
        description="Optional bounded semantic explanation for an assessed status."
    )


class Citation(ContractModel):
    """Represent one canonical Claim-to-Evidence provenance handle."""

    citation_id: NonEmptyText = Field(
        description="Host-assigned identity for the canonical Claim/Evidence pair."
    )
    claim_id: NonEmptyText = Field(
        description="Identity of the report-eligible Claim being cited."
    )
    evidence_ref: EvidenceRef = Field(
        description="Task-qualified Evidence address supporting this Citation."
    )


class GroundingManifest(ContractModel):
    """Represent the authoritative P2-S5 structured shadow output."""

    contract_version: NonEmptyText = Field(
        default=CONTRACT_VERSION,
        frozen=True,
        description="Serialized EvidenceFlow contract version for this Manifest."
    )
    claims: list[ClaimRecord] = Field(
        description="Canonical ordered Claims materialized for Global Synthesis."
    )
    groundings: list[ClaimGroundingRecord] = Field(
        description="Canonical ordered grounding records corresponding to Claims."
    )
    citations: list[Citation] = Field(
        description="Canonical ordered Citations for report-eligible Claims."
    )

    @model_validator(mode="after")
    def require_contract_version(self) -> "GroundingManifest":
        """Reject a Manifest serialized against any non-canonical contract version."""
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(
                f"GroundingManifest contract_version must be {CONTRACT_VERSION!r}"
            )
        return self


def validate_provenance_graph(
    *,
    task: MedicalResearchTask,
    result: ResearchTaskResult,
) -> None:
    """Validate the self-contained task-level provenance graph.

    Args:
        task: Delegated task that owns the result and its findings.
        result: Cross-graph result whose references must be resolvable.

    Raises:
        ValueError: If an identity is duplicated, dangling, or inconsistent with the
            task/result provenance graph.
    """
    if result.task_id != task.task_id:
        raise ValueError("ResearchTaskResult.task_id must match MedicalResearchTask.task_id")

    # Revalidation at the publication boundary protects callers that receive a
    # deserialized model instance rather than constructing it locally.
    ResearchTaskResult.model_validate(result.model_dump(mode="python"))


def _ensure_unique(values: list[str], field_name: str) -> None:
    """Reject duplicate identities within one immutable contract envelope."""
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique IDs")


def _normalize_metadata_key(key: str) -> str:
    """Normalize metadata key spelling for raw-content defense-in-depth checks."""
    return "".join(character.lower() for character in key if character.isalnum())
