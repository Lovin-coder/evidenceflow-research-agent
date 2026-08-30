"""Task-qualified resolution and bounded Model A input projection."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import Field

from open_deep_research.artifact_store import ArtifactStore
from open_deep_research.domain_models import (
    ClaimGroundingRecord,
    ClaimRecord,
    ContractModel,
    EvidenceRecord,
    EvidenceRef,
    FindingRef,
    GroundingStatus,
    MedicalResearchBrief,
    NonEmptyText,
    ResearchFinding,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
)
from open_deep_research.global_synthesis.types import (
    GlobalSynthesisLimits,
    GroundingEvidenceView,
    RendererEvidenceRole,
    RendererEvidenceView,
    ReportClaimView,
)


class ProjectionResolutionError(ValueError):
    """Report an ambiguous or unresolved task-qualified provenance reference."""


class SourceMetadataView(ContractModel):
    """Whitelisted, best-effort Source metadata exposed to synthesis models."""

    url: NonEmptyText | None = None
    title: NonEmptyText | None = None
    provider: NonEmptyText | None = None
    publisher: NonEmptyText | None = None
    authors: NonEmptyText | None = None
    published_at: NonEmptyText | None = None
    document_type: NonEmptyText | None = None


class GeneratorEvidenceView(ContractModel):
    """One complete authoritative Evidence excerpt visible to Model A."""

    evidence_ref: EvidenceRef
    excerpt: str = Field(min_length=1)
    source_metadata: SourceMetadataView | None = None


class GeneratorFindingView(ContractModel):
    """One complete authoritative Finding and its admitted Evidence context."""

    finding_ref: FindingRef
    text: NonEmptyText
    limitations: list[NonEmptyText]
    conflicts: list[NonEmptyText]
    evidence: list[GeneratorEvidenceView]


class GeneratorResultView(ContractModel):
    """Bounded process view of one Result in Parent ledger order."""

    task_id: NonEmptyText
    status: ResearchTaskStatus
    summary: NonEmptyText
    summary_truncated: bool
    limitations: list[NonEmptyText]
    conflicts: list[NonEmptyText]
    error: NonEmptyText | None = None
    error_truncated: bool
    findings: list[GeneratorFindingView]


class GeneratorProjection(ContractModel):
    """Complete bounded semantic input for one Model A invocation."""

    medical_research_brief: MedicalResearchBrief
    results: list[GeneratorResultView]


@dataclass(frozen=True)
class GeneratorProjectionOutcome:
    """Projection plus Host admission facts used by downstream validation."""

    projection: GeneratorProjection | None
    generator_visible_finding_refs: tuple[FindingRef, ...]
    skip_model_a: bool
    degradation_observed: bool
    omitted_finding_count: int
    omitted_evidence_count: int


@dataclass(frozen=True)
class GroundingEvidenceAdmission:
    """Canonical Judge input plus whole-unit admission facts for one Claim."""

    claim: ClaimRecord
    evidence: tuple[GroundingEvidenceView, ...]
    skip_model_b: bool
    degradation_observed: bool
    omitted_evidence_count: int


@dataclass(frozen=True)
class RendererProjectionOutcome:
    """All eligible Claim propositions plus bounded material Evidence context."""

    claims: tuple[ReportClaimView, ...]
    degradation_observed: bool
    omitted_evidence_count: int


class TaskQualifiedResolver:
    """Resolve provenance only inside the Result named by a qualified reference."""

    def __init__(
        self,
        results: tuple[ResearchTaskResult, ...] | list[ResearchTaskResult],
        artifact_store: ArtifactStore,
    ) -> None:
        """Index one run's Results and retain only its current-run Artifact resolver."""
        indexed: dict[str, ResearchTaskResult] = {}
        for result in results:
            if result.task_id in indexed:
                raise ProjectionResolutionError(
                    f"Duplicate ResearchTaskResult task_id: {result.task_id!r}"
                )
            indexed[result.task_id] = result
        self._results = indexed
        self._artifact_store = artifact_store

    def resolve_result(self, task_id: str) -> ResearchTaskResult:
        """Resolve one unique Result by its task-qualified identity."""
        try:
            return self._results[task_id]
        except KeyError as error:
            raise ProjectionResolutionError(
                f"Unknown ResearchTaskResult task_id: {task_id!r}"
            ) from error

    def resolve_finding(self, finding_ref: FindingRef) -> ResearchFinding:
        """Resolve a Finding only within the explicitly owning Result."""
        result = self.resolve_result(finding_ref.task_id)
        for finding in result.findings:
            if finding.finding_id == finding_ref.finding_id:
                return finding
        raise ProjectionResolutionError(f"Unknown FindingRef: {finding_ref!r}")

    def resolve_evidence(self, evidence_ref: EvidenceRef) -> EvidenceRecord:
        """Resolve Evidence only within the explicitly owning Result."""
        result = self.resolve_result(evidence_ref.task_id)
        for evidence in result.evidence_records:
            if evidence.evidence_id == evidence_ref.evidence_id:
                return evidence
        raise ProjectionResolutionError(f"Unknown EvidenceRef: {evidence_ref!r}")

    def resolve_source(self, evidence_ref: EvidenceRef) -> SourceRecord:
        """Resolve an Evidence Source only inside the same owning Result."""
        result = self.resolve_result(evidence_ref.task_id)
        evidence = self.resolve_evidence(evidence_ref)
        for source in result.source_records:
            if source.source_id == evidence.source_id:
                return source
        raise ProjectionResolutionError(
            f"EvidenceRef {evidence_ref!r} has no SourceRecord in its owning Result"
        )

    def resolve_artifact_text(self, evidence_ref: EvidenceRef) -> str:
        """Resolve an Artifact through the supplied current-run Store only."""
        source = self.resolve_source(evidence_ref)
        if source.artifact_ref is None:
            raise ProjectionResolutionError(
                f"EvidenceRef {evidence_ref!r} has no Artifact reference"
            )
        return self._artifact_store.get_text(source.artifact_ref)


def _source_metadata_view(source: SourceRecord) -> SourceMetadataView | None:
    """Project only validated metadata fields, without inferring missing values."""
    allowed = {
        field: source.metadata[field]
        for field in SourceMetadataView.model_fields
        if field in source.metadata
    }
    return SourceMetadataView(**allowed) if allowed else None


def _grounding_evidence_view(
    evidence_ref: EvidenceRef,
    evidence: EvidenceRecord,
    source: SourceRecord,
) -> GroundingEvidenceView:
    """Project one exact excerpt plus only optional whitelisted Source metadata."""
    metadata = source.metadata
    return GroundingEvidenceView(
        evidence_ref=evidence_ref,
        excerpt=evidence.excerpt,
        title=metadata.get("title"),
        stored_url=metadata.get("url"),
        provider=metadata.get("provider"),
        publisher=metadata.get("publisher"),
        authors=metadata.get("authors"),
        published_at=metadata.get("published_at"),
        document_type=metadata.get("document_type"),
    )


def _grounding_projection_chars(
    claim: ClaimRecord, evidence: list[GroundingEvidenceView]
) -> int:
    """Measure the complete Claim and admitted Evidence Judge projection."""
    return len(
        json.dumps(
            {
                "claim": claim.model_dump(mode="json"),
                "evidence": [item.model_dump(mode="json") for item in evidence],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def build_grounding_evidence_admission(
    *,
    claim: ClaimRecord,
    resolver: TaskQualifiedResolver,
    limits: GlobalSynthesisLimits,
) -> GroundingEvidenceAdmission:
    """Derive and admit the Claim's canonical Finding-owned Evidence prefix."""
    universe: list[EvidenceRef] = []
    seen: set[tuple[str, str]] = set()
    for finding_ref in claim.finding_refs:
        finding = resolver.resolve_finding(finding_ref)
        for evidence_id in finding.evidence_ids:
            evidence_ref = EvidenceRef(
                task_id=finding_ref.task_id,
                evidence_id=evidence_id,
            )
            coordinate = (evidence_ref.task_id, evidence_ref.evidence_id)
            if coordinate not in seen:
                seen.add(coordinate)
                universe.append(evidence_ref)

    admitted: list[GroundingEvidenceView] = []
    admitted_excerpt_chars = 0
    for evidence_ref in universe:
        evidence = resolver.resolve_evidence(evidence_ref)
        source = resolver.resolve_source(evidence_ref)
        view = _grounding_evidence_view(evidence_ref, evidence, source)
        candidate = [*admitted, view]
        if (
            len(candidate) > limits.max_evidence_refs_per_claim
            or admitted_excerpt_chars + len(evidence.excerpt)
            > limits.max_judge_evidence_chars
            or _grounding_projection_chars(claim, candidate)
            > limits.max_judge_context_chars
        ):
            break
        admitted.append(view)
        admitted_excerpt_chars += len(evidence.excerpt)

    omitted = len(universe) - len(admitted)
    return GroundingEvidenceAdmission(
        claim=claim,
        evidence=tuple(admitted),
        skip_model_b=not admitted,
        degradation_observed=omitted > 0,
        omitted_evidence_count=omitted,
    )


def _renderer_evidence_view(
    evidence_ref: EvidenceRef,
    role: RendererEvidenceRole,
    resolver: TaskQualifiedResolver,
) -> RendererEvidenceView:
    evidence = resolver.resolve_evidence(evidence_ref)
    source = resolver.resolve_source(evidence_ref)
    metadata = source.metadata
    return RendererEvidenceView(
        evidence_ref=evidence_ref,
        role=role,
        excerpt=evidence.excerpt,
        title=metadata.get("title"),
        stored_url=metadata.get("url"),
        provider=metadata.get("provider"),
        publisher=metadata.get("publisher"),
        authors=metadata.get("authors"),
        published_at=metadata.get("published_at"),
        document_type=metadata.get("document_type"),
    )


def _renderer_projection_chars(claims: list[ReportClaimView]) -> int:
    return len(
        json.dumps(
            [claim.model_dump(mode="json") for claim in claims],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def build_renderer_projection(
    *,
    claims: list[ClaimRecord],
    groundings: list[ClaimGroundingRecord],
    resolver: TaskQualifiedResolver,
    limits: GlobalSynthesisLimits,
) -> RendererProjectionOutcome:
    """Retain all eligible Claims and admit only material Evidence in two phases."""
    if len(claims) != len(groundings):
        raise ProjectionResolutionError("Claims and Groundings must bind one-to-one")
    views: list[ReportClaimView] = []
    candidates: list[list[RendererEvidenceView]] = []
    for claim, grounding in zip(claims, groundings, strict=True):
        if grounding.claim_id != claim.claim_id:
            raise ProjectionResolutionError("Grounding order diverges from Claim order")
        if grounding.status not in (
            GroundingStatus.SUPPORTED,
            GroundingStatus.SUPPORTED_WITH_CONFLICT,
        ):
            continue
        views.append(
            ReportClaimView(
                claim_id=claim.claim_id,
                text=claim.text,
                scope=claim.scope,
                qualifiers=claim.qualifiers,
                materiality=claim.materiality,
                grounding_status=grounding.status,
                evidence=[],
            )
        )
        supporting = [
            _renderer_evidence_view(ref, RendererEvidenceRole.SUPPORTING, resolver)
            for ref in grounding.supporting_evidence_refs
        ]
        contradicting = [
            _renderer_evidence_view(ref, RendererEvidenceRole.CONTRADICTING, resolver)
            for ref in grounding.contradicting_evidence_refs
        ]
        candidates.append([*supporting, *contradicting])

    if _renderer_projection_chars(views) > limits.max_renderer_context_chars:
        raise ProjectionResolutionError(
            "Eligible Claim propositions exceed Renderer context capacity"
        )

    admitted_coordinates: set[tuple[int, str, str, RendererEvidenceRole]] = set()
    phase_one: list[tuple[int, RendererEvidenceView]] = []
    for index, (view, evidence) in enumerate(zip(views, candidates, strict=True)):
        supporting = [
            item for item in evidence if item.role is RendererEvidenceRole.SUPPORTING
        ]
        if supporting:
            phase_one.append((index, supporting[0]))
        if view.grounding_status is GroundingStatus.SUPPORTED_WITH_CONFLICT:
            contradicting = [
                item
                for item in evidence
                if item.role is RendererEvidenceRole.CONTRADICTING
            ]
            if contradicting:
                phase_one.append((index, contradicting[0]))
    phase_two = [
        (index, item)
        for index, evidence in enumerate(candidates)
        for item in evidence
    ]

    for index, item in [*phase_one, *phase_two]:
        coordinate = (
            index,
            item.evidence_ref.task_id,
            item.evidence_ref.evidence_id,
            item.role,
        )
        if coordinate in admitted_coordinates:
            continue
        updated_view = views[index].model_copy(
            update={"evidence": [*views[index].evidence, item]}
        )
        updated = [*views]
        updated[index] = updated_view
        if _renderer_projection_chars(updated) > limits.max_renderer_context_chars:
            continue
        views = updated
        admitted_coordinates.add(coordinate)

    total_material = sum(len(items) for items in candidates)
    omitted = total_material - len(admitted_coordinates)
    return RendererProjectionOutcome(
        claims=tuple(views),
        degradation_observed=omitted > 0,
        omitted_evidence_count=omitted,
    )


def _truncate_context(value: str, limit: int) -> tuple[str, bool]:
    """Bound non-authoritative context while making truncation observable."""
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _serialized_chars(projection: GeneratorProjection) -> int:
    """Measure the canonical serialized Generator input projection."""
    return len(
        json.dumps(
            projection.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _candidate_projection(
    brief: MedicalResearchBrief,
    results: list[GeneratorResultView],
) -> GeneratorProjection:
    return GeneratorProjection(medical_research_brief=brief, results=results)


def _replace_last_result(
    results: list[GeneratorResultView], result: GeneratorResultView
) -> list[GeneratorResultView]:
    return [*results[:-1], result]


def build_generator_projection(
    *,
    brief: MedicalResearchBrief,
    results: tuple[ResearchTaskResult, ...] | list[ResearchTaskResult],
    artifact_store: ArtifactStore,
    limits: GlobalSynthesisLimits,
) -> GeneratorProjectionOutcome:
    """Build a deterministic bounded Model A projection in canonical ledger order.

    Finding text and Evidence excerpts are authoritative units and are either included
    intact or omitted. Result summary and error strings are contextual and may be
    truncated to their explicit limits.
    """
    resolver = TaskQualifiedResolver(results, artifact_store)
    projected_results: list[GeneratorResultView] = []
    visible_refs: list[FindingRef] = []
    omitted_findings = 0
    omitted_evidence = 0
    admitted_evidence_chars = 0
    degradation = False

    empty = _candidate_projection(brief, [])
    if _serialized_chars(empty) > limits.max_generator_context_chars:
        return GeneratorProjectionOutcome(
            projection=None,
            generator_visible_finding_refs=(),
            skip_model_a=True,
            degradation_observed=True,
            omitted_finding_count=sum(len(result.findings) for result in results),
            omitted_evidence_count=sum(
                len(finding.evidence_ids)
                for result in results
                for finding in result.findings
            ),
        )

    for result in results:
        summary, summary_truncated = _truncate_context(
            result.summary, limits.max_task_summary_chars
        )
        error: str | None = None
        error_truncated = False
        if result.error is not None:
            error, error_truncated = _truncate_context(
                result.error, limits.max_task_error_context_chars
            )
        result_view = GeneratorResultView(
            task_id=result.task_id,
            status=result.status,
            summary=summary,
            summary_truncated=summary_truncated,
            limitations=result.limitations,
            conflicts=result.conflicts,
            error=error,
            error_truncated=error_truncated,
            findings=[],
        )
        with_result = _candidate_projection(brief, [*projected_results, result_view])
        if _serialized_chars(with_result) > limits.max_generator_context_chars:
            omitted_findings += len(result.findings)
            omitted_evidence += sum(
                len(finding.evidence_ids) for finding in result.findings
            )
            degradation = True
            continue
        projected_results.append(result_view)
        degradation = degradation or summary_truncated or error_truncated

        for finding_ordinal, finding in enumerate(result.findings):
            if finding_ordinal >= limits.max_findings_per_task:
                omitted_findings += 1
                omitted_evidence += len(finding.evidence_ids)
                degradation = True
                continue
            if len(visible_refs) >= limits.max_findings_total:
                omitted_findings += 1
                omitted_evidence += len(finding.evidence_ids)
                degradation = True
                continue

            finding_ref = FindingRef(
                task_id=result.task_id, finding_id=finding.finding_id
            )
            finding_view = GeneratorFindingView(
                finding_ref=finding_ref,
                text=finding.text,
                limitations=finding.limitations,
                conflicts=finding.conflicts,
                evidence=[],
            )
            candidate_result = result_view.model_copy(
                update={"findings": [*result_view.findings, finding_view]}
            )
            candidate_results = _replace_last_result(
                projected_results, candidate_result
            )
            candidate = _candidate_projection(brief, candidate_results)
            if _serialized_chars(candidate) > limits.max_generator_context_chars:
                omitted_findings += 1
                omitted_evidence += len(finding.evidence_ids)
                degradation = True
                continue

            result_view = candidate_result
            projected_results = candidate_results
            visible_refs.append(finding_ref)

            for evidence_id in finding.evidence_ids:
                evidence_ref = EvidenceRef(
                    task_id=result.task_id, evidence_id=evidence_id
                )
                evidence = resolver.resolve_evidence(evidence_ref)
                source = resolver.resolve_source(evidence_ref)
                if (
                    admitted_evidence_chars + len(evidence.excerpt)
                    > limits.max_generator_evidence_chars
                ):
                    omitted_evidence += 1
                    degradation = True
                    continue
                evidence_view = GeneratorEvidenceView(
                    evidence_ref=evidence_ref,
                    excerpt=evidence.excerpt,
                    source_metadata=_source_metadata_view(source),
                )
                updated_finding = finding_view.model_copy(
                    update={"evidence": [*finding_view.evidence, evidence_view]}
                )
                updated_findings = [*result_view.findings[:-1], updated_finding]
                updated_result = result_view.model_copy(
                    update={"findings": updated_findings}
                )
                updated_results = _replace_last_result(
                    projected_results, updated_result
                )
                updated_projection = _candidate_projection(brief, updated_results)
                if (
                    _serialized_chars(updated_projection)
                    > limits.max_generator_context_chars
                ):
                    omitted_evidence += 1
                    degradation = True
                    continue
                admitted_evidence_chars += len(evidence.excerpt)
                finding_view = updated_finding
                result_view = updated_result
                projected_results = updated_results

    projection = _candidate_projection(brief, projected_results)
    return GeneratorProjectionOutcome(
        projection=projection,
        generator_visible_finding_refs=tuple(visible_refs),
        skip_model_a=not visible_refs,
        degradation_observed=degradation,
        omitted_finding_count=omitted_findings,
        omitted_evidence_count=omitted_evidence,
    )
