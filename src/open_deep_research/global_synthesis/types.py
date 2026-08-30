"""Typed process-local boundaries for global claim synthesis.

Stable Claim, Grounding, Citation, and Manifest wire contracts live in
``domain_models``.  This module contains only model-facing DTOs and immutable
Host execution values that must never be persisted as a second authority.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from enum import Enum
from typing import TypeVar

from pydantic import Field, ValidationError

from open_deep_research.artifact_store import ArtifactStore
from open_deep_research.domain_models import (
    ClaimMateriality,
    ContractModel,
    EvidenceRef,
    FindingRef,
    GroundingManifest,
    GroundingStatus,
    MedicalResearchBrief,
    NonEmptyText,
    ResearchTaskResult,
)
from open_deep_research.state import (
    GlobalSynthesisIssue,
    GlobalSynthesisStatus,
)

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")
ValidatedT = TypeVar("ValidatedT")


class ClaimDraft(ContractModel):
    """Model A proposal before Host reference validation and identity assignment."""

    text: str = Field(min_length=1)
    materiality: ClaimMateriality
    finding_refs: list[FindingRef] = Field(min_length=1)
    scope: str | None = None
    qualifiers: list[str]


class ClaimDraftBatch(ContractModel):
    """Outer Model A batch shell that preserves raw siblings for Host validation."""

    claims: list[object]


class ClaimEvidenceVerdict(str, Enum):
    """Model B's semantic judgment over one complete Claim proposition."""

    SUPPORTED = "supported"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"


class ClaimGroundingDraft(ContractModel):
    """Model B proposal before Host allowlist and status validation."""

    verdict: ClaimEvidenceVerdict
    supporting_evidence_refs: list[EvidenceRef]
    contradicting_evidence_refs: list[EvidenceRef]
    reason: str = Field(min_length=1)


class GroundingEvidenceView(ContractModel):
    """Bounded Evidence unit visible to the Grounding Judge."""

    evidence_ref: EvidenceRef
    excerpt: str = Field(min_length=1)
    title: NonEmptyText | None = None
    stored_url: NonEmptyText | None = None
    provider: NonEmptyText | None = None
    publisher: NonEmptyText | None = None
    authors: NonEmptyText | None = None
    published_at: NonEmptyText | None = None
    document_type: NonEmptyText | None = None


class RendererEvidenceRole(str, Enum):
    """Material Evidence role already fixed by authoritative Grounding."""

    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"


class RendererEvidenceView(ContractModel):
    """Material Evidence unit visible to the shadow Renderer."""

    evidence_ref: EvidenceRef
    role: RendererEvidenceRole
    excerpt: str = Field(min_length=1)
    title: NonEmptyText | None = None
    stored_url: NonEmptyText | None = None
    provider: NonEmptyText | None = None
    publisher: NonEmptyText | None = None
    authors: NonEmptyText | None = None
    published_at: NonEmptyText | None = None
    document_type: NonEmptyText | None = None


class ReportClaimView(ContractModel):
    """Complete authoritative Claim proposition supplied to Model C."""

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    scope: str | None = None
    qualifiers: list[str]
    materiality: ClaimMateriality
    grounding_status: GroundingStatus
    evidence: list[RendererEvidenceView]


class ReportParagraphDraft(ContractModel):
    """Model-owned prose paragraph with Host-validated Claim bindings."""

    text: str = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=1)


class ReportSectionDraft(ContractModel):
    """Model-owned report section without a Host-fixed section taxonomy."""

    title: str = Field(min_length=1)
    paragraphs: list[ReportParagraphDraft] = Field(min_length=1)


class ShadowReportDraft(ContractModel):
    """Complete Model C structured output before Host finalization."""

    sections: list[ReportSectionDraft]


@dataclass(frozen=True)
class ClaimMaterializationReceipt:
    """Bind one accepted Generator ordinal to its Host-owned Claim identity."""

    original_generator_ordinal: int
    canonical_claim_payload: bytes
    expected_claim_id: str


@dataclass(frozen=True)
class AssessedGroundingReceipt:
    """Record the exact successful Judge input and expected Host status."""

    claim_id: str
    validated_verdict: ClaimEvidenceVerdict
    evaluated_evidence_refs: tuple[EvidenceRef, ...]
    expected_status: GroundingStatus


@dataclass(frozen=True)
class UnassessedGroundingReceipt:
    """Tag a strict UNASSESSED result without inventing an evaluated universe."""

    claim_id: str


class GlobalSynthesisStage(str, Enum):
    """Closed vocabulary for Host-produced global synthesis issue stages."""

    INPUT_PROJECTION = "input_projection"
    CLAIM_GENERATION = "claim_generation"
    CLAIM_MATERIALIZATION = "claim_materialization"
    EVIDENCE_ADMISSION = "evidence_admission"
    GROUNDING_JUDGE = "grounding_judge"
    GROUNDING_MATERIALIZATION = "grounding_materialization"
    CITATION_MATERIALIZATION = "citation_materialization"
    PUBLICATION_GATE = "publication_gate"
    SHADOW_RENDERING = "shadow_rendering"
    RENDERER_VALIDATION = "renderer_validation"


@dataclass(frozen=True)
class GlobalSynthesisLimits:
    """Frozen engineering guardrails shared by S5 projections and validators."""

    max_findings_total: int = 40
    max_findings_per_task: int = 8
    max_generator_evidence_chars: int = 96_000
    max_task_summary_chars: int = 2_000
    max_task_error_context_chars: int = 1_000
    max_generator_context_chars: int = 128_000
    max_claim_drafts_returned: int = 64
    max_claim_batch_serialized_chars: int = 128_000
    max_claims: int = 20
    max_claim_text_chars: int = 1_500
    max_claim_scope_chars: int = 500
    max_qualifiers_per_claim: int = 8
    max_qualifier_chars: int = 300
    max_finding_refs_per_claim: int = 8
    max_evidence_refs_per_claim: int = 24
    max_judge_evidence_chars: int = 64_000
    max_judge_context_chars: int = 80_000
    max_grounding_reason_chars: int = 2_000
    max_grounding_draft_serialized_chars: int = 16_000
    max_citations: int = 512
    max_manifest_serialized_chars: int = 1_000_000
    max_global_synthesis_issues: int = 64
    max_issue_message_chars: int = 1_000
    max_issue_ledger_chars: int = 128_000
    max_renderer_context_chars: int = 128_000
    max_sections: int = 8
    max_section_title_chars: int = 300
    max_paragraphs_total: int = 24
    max_paragraph_chars: int = 2_000
    max_claim_ids_per_paragraph: int = 6
    max_claim_occurrences_per_claim: int = 3
    max_shadow_report_chars: int = 30_000
    max_renderer_draft_serialized_chars: int = 128_000

    def __post_init__(self) -> None:
        """Reject limit sets unable to represent the maximum Citation universe."""
        if self.max_citations < self.max_claims * self.max_evidence_refs_per_claim:
            raise ValueError(
                "max_citations must cover max_claims * max_evidence_refs_per_claim"
            )


@dataclass(frozen=True)
class GlobalSynthesisExecutionContext:
    """Immutable snapshot of one process-local global synthesis execution."""

    artifact_run_id: str
    medical_research_brief: MedicalResearchBrief
    research_results: tuple[ResearchTaskResult, ...]
    artifact_store: ArtifactStore
    limits: GlobalSynthesisLimits = GlobalSynthesisLimits()
    issues: tuple[GlobalSynthesisIssue, ...] = ()
    degradation_observed: bool = False

    def observe_degradation(self) -> GlobalSynthesisExecutionContext:
        """Return a context whose sticky degradation bit can only become true."""
        if self.degradation_observed:
            return self
        return replace(self, degradation_observed=True)


@dataclass(frozen=True)
class GroundingMetrics:
    """Pure, recomputable Manifest metrics that never enter Graph State."""

    supported_claim_count: int
    supported_with_conflict_claim_count: int
    insufficient_claim_count: int
    contradicted_claim_count: int
    unassessed_claim_count: int
    assessed_claim_coverage: float | None
    report_eligible_claim_coverage: float | None
    material_report_eligible_claim_coverage: float | None


@dataclass(frozen=True)
class GlobalSynthesisOutcome:
    """Single bounded result returned to the owning Parent graph node."""

    manifest: GroundingManifest | None
    shadow_report: str | None
    status: GlobalSynthesisStatus
    issues: tuple[GlobalSynthesisIssue, ...]
    metrics: GroundingMetrics | None


@dataclass(frozen=True)
class IssueCollectionOutcome:
    """Bounded retained issue ledger plus its independent sticky degradation fact."""

    issues: tuple[GlobalSynthesisIssue, ...]
    degradation_observed: bool


class _StructuredValidationError(ValueError):
    """Mark a Host validation failure that retries immediately without sleeping."""


async def _invoke_structured_once(
    invoke: Callable[[RequestT], Awaitable[ResponseT]],
    request: RequestT,
    *,
    timeout_seconds: float,
) -> ResponseT:
    """Send exactly one actual structured request with a per-request timeout."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    return await asyncio.wait_for(invoke(request), timeout=timeout_seconds)


async def _invoke_with_host_retry(
    invoke_once: Callable[[], Awaitable[ResponseT]],
    validate: Callable[[ResponseT], ValidatedT],
    *,
    max_retries: int,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ValidatedT:
    """Run the sole logical retry loop for one structured Model stage.

    Schema and Host validation failures retry immediately. Ordinary provider,
    transport, and timeout failures use the frozen deterministic capped
    backoff. Cancellation and system control flow are not caught.
    """
    if max_retries < 0:
        raise ValueError("max_retries must not be negative")

    for attempt in range(max_retries + 1):
        try:
            return validate(await invoke_once())
        except (ValidationError, _StructuredValidationError):
            if attempt == max_retries:
                raise
        except Exception:
            if attempt == max_retries:
                raise
            retry_index = attempt + 1
            delay = min(0.5 * (2 ** (retry_index - 1)), 2.0)
            await sleep(delay)
    raise RuntimeError("unreachable structured retry state")


def _serialized_model_chars(model: ContractModel) -> int:
    """Measure canonical structured output size for aggregate Host validation."""
    return len(
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _validate_claim_draft_batch(
    batch: ClaimDraftBatch, limits: GlobalSynthesisLimits
) -> ClaimDraftBatch:
    """Validate Model A aggregate bounds without applying sibling semantics."""
    if len(batch.claims) > limits.max_claim_drafts_returned:
        raise _StructuredValidationError("ClaimDraftBatch exceeds item capacity")
    try:
        serialized_chars = _serialized_model_chars(batch)
    except (TypeError, ValueError) as error:
        raise _StructuredValidationError(
            "ClaimDraftBatch contains a non-serializable outer payload"
        ) from error
    if serialized_chars > limits.max_claim_batch_serialized_chars:
        raise _StructuredValidationError("ClaimDraftBatch exceeds serialized capacity")
    return batch


def _validate_shadow_report_draft(
    draft: ShadowReportDraft, limits: GlobalSynthesisLimits
) -> ShadowReportDraft:
    """Validate Model C aggregate shape before role-specific binding checks."""
    if len(draft.sections) > limits.max_sections:
        raise _StructuredValidationError("ShadowReportDraft exceeds section capacity")
    paragraphs = [paragraph for section in draft.sections for paragraph in section.paragraphs]
    if len(paragraphs) > limits.max_paragraphs_total:
        raise _StructuredValidationError("ShadowReportDraft exceeds paragraph capacity")
    if any(len(section.title) > limits.max_section_title_chars for section in draft.sections):
        raise _StructuredValidationError("ShadowReportDraft section title exceeds capacity")
    if any(len(paragraph.text) > limits.max_paragraph_chars for paragraph in paragraphs):
        raise _StructuredValidationError("ShadowReportDraft paragraph exceeds capacity")
    if any(
        len(paragraph.claim_ids) > limits.max_claim_ids_per_paragraph
        for paragraph in paragraphs
    ):
        raise _StructuredValidationError("ShadowReportDraft Claim binding exceeds capacity")
    if _serialized_model_chars(draft) > limits.max_renderer_draft_serialized_chars:
        raise _StructuredValidationError("ShadowReportDraft exceeds serialized capacity")
    return draft
