"""Global synthesis orchestration and Host-owned execution helpers.

The full pipeline is introduced by T18.  This foundation owns issue identity,
bounded reconciliation, and final process status because those semantics span
individual Model stages without belonging to stable Domain contracts.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from open_deep_research.artifact_store import ArtifactStore, artifact_store_from_config
from open_deep_research.configuration import Configuration
from open_deep_research.domain_models import (
    EvidenceRef,
    GroundingManifest,
    MedicalResearchBrief,
    ResearchTaskResult,
)
from open_deep_research.global_synthesis.claims import (
    _invoke_claim_generator,
    _materialize_claims,
)
from open_deep_research.global_synthesis.grounding import _judge_claims
from open_deep_research.global_synthesis.projection import (
    TaskQualifiedResolver,
    build_generator_projection,
    build_grounding_evidence_admission,
    build_renderer_projection,
)
from open_deep_research.global_synthesis.publication import (
    ReplayDisposition,
    _materialize_citations,
    derive_grounding_metrics,
    publish_manifest_candidate,
    replay_disposition,
)
from open_deep_research.global_synthesis.renderer import (
    _render_shadow_report,
    build_source_display_entries,
)
from open_deep_research.global_synthesis.types import (
    ClaimDraftBatch,
    ClaimGroundingDraft,
    GlobalSynthesisExecutionContext,
    GlobalSynthesisLimits,
    GlobalSynthesisOutcome,
    GlobalSynthesisStage,
    IssueCollectionOutcome,
    ShadowReportDraft,
)
from open_deep_research.model_runtime import (
    build_model_runtime_fields,
    resolve_model_enable_thinking,
)
from open_deep_research.state import (
    GlobalSynthesisIssue,
    GlobalSynthesisSeverity,
    GlobalSynthesisStatus,
    measure_global_synthesis_issues_chars,
)
from open_deep_research.utils import get_api_key_for_model

_MAX_ISSUE_OCCURRENCE_KEY_CHARS = 512
_ISSUE_PAYLOAD_CONFLICT_CODE = "ISSUE_PAYLOAD_CONFLICT"


@dataclass(frozen=True)
class _SynthesisModels:
    claim_generator: Callable[[object], Awaitable[object]]
    grounding_judge: Callable[[object], Awaitable[object]]
    shadow_renderer: Callable[[object], Awaitable[object]]


def _make_global_synthesis_issue(
    *,
    stage: GlobalSynthesisStage,
    code: str,
    severity: GlobalSynthesisSeverity,
    message: str,
    degrades_global_status: bool,
    claim_id: str | None = None,
    task_id: str | None = None,
    evidence_ref: EvidenceRef | None = None,
    attempt: int | None = None,
    occurrence_key: str = "",
    limits: GlobalSynthesisLimits = GlobalSynthesisLimits(),
) -> GlobalSynthesisIssue:
    """Build a deterministic bounded issue whose wording is not its identity."""
    normalized_message = re.sub(r"\s+", " ", message).strip()
    if not normalized_message:
        raise ValueError("Global Synthesis issue message must not be blank")
    bounded_message = normalized_message[: limits.max_issue_message_chars]
    bounded_occurrence_key = occurrence_key[:_MAX_ISSUE_OCCURRENCE_KEY_CHARS]
    identity_payload = json.dumps(
        {
            "version": "p2-s5-global-synthesis-issue-v1",
            "stage": stage.value,
            "code": code,
            "claim_id": claim_id,
            "task_id": task_id,
            "evidence_ref": (
                evidence_ref.model_dump(mode="json") if evidence_ref else None
            ),
            "attempt": attempt,
            "occurrence_key": bounded_occurrence_key,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity_payload.encode("utf-8")).hexdigest()[:32]
    return GlobalSynthesisIssue(
        issue_id=f"issue:sha256:{digest}",
        stage=stage.value,
        code=code,
        severity=severity,
        message=bounded_message,
        claim_id=claim_id,
        task_id=task_id,
        evidence_ref=evidence_ref,
        attempt=attempt,
        degrades_global_status=degrades_global_status,
    )


def _issue_semantic_payload(issue: GlobalSynthesisIssue) -> tuple[object, ...]:
    """Return every semantic issue field except diagnostic wording and identity."""
    return (
        issue.stage,
        issue.code,
        issue.severity,
        issue.claim_id,
        issue.task_id,
        issue.evidence_ref,
        issue.attempt,
        issue.degrades_global_status,
    )


def _make_issue_payload_conflict(
    conflicting_issue: GlobalSynthesisIssue,
    *,
    limits: GlobalSynthesisLimits,
) -> GlobalSynthesisIssue:
    """Describe one same-ID semantic conflict without copying divergent payloads."""
    return _make_global_synthesis_issue(
        stage=GlobalSynthesisStage.PUBLICATION_GATE,
        code=_ISSUE_PAYLOAD_CONFLICT_CODE,
        severity=GlobalSynthesisSeverity.ERROR,
        message="A Global Synthesis issue ID was observed with divergent semantics.",
        degrades_global_status=True,
        occurrence_key=conflicting_issue.issue_id,
        limits=limits,
    )


def _admit_issue_if_bounded(
    retained: list[GlobalSynthesisIssue],
    issue: GlobalSynthesisIssue,
    *,
    limits: GlobalSynthesisLimits,
) -> bool:
    """Append one whole issue only when both ledger bounds remain satisfied."""
    if len(retained) >= limits.max_global_synthesis_issues:
        return False
    candidate = [*retained, issue]
    if measure_global_synthesis_issues_chars(candidate) > limits.max_issue_ledger_chars:
        return False
    retained.append(issue)
    return True


def _reconcile_global_synthesis_issues(
    current: Iterable[GlobalSynthesisIssue],
    observed: Iterable[GlobalSynthesisIssue],
    *,
    degradation_observed: bool,
    limits: GlobalSynthesisLimits = GlobalSynthesisLimits(),
) -> IssueCollectionOutcome:
    """Retain first writes, reconcile P05 conflicts, and preserve degradation.

    The sticky bit is deliberately independent of the bounded ledger: a late
    degrading observation remains authoritative even when no additional issue
    record fits.
    """
    retained: list[GlobalSynthesisIssue] = []
    by_id: dict[str, GlobalSynthesisIssue] = {}

    for issue in [*current, *observed]:
        if issue.degrades_global_status:
            degradation_observed = True
        existing = by_id.get(issue.issue_id)
        if existing is not None:
            if _issue_semantic_payload(existing) != _issue_semantic_payload(issue):
                degradation_observed = True
                conflict = _make_issue_payload_conflict(issue, limits=limits)
                if conflict.issue_id not in by_id and _admit_issue_if_bounded(
                    retained, conflict, limits=limits
                ):
                    by_id[conflict.issue_id] = conflict
            continue
        if _admit_issue_if_bounded(retained, issue, limits=limits):
            by_id[issue.issue_id] = issue

    return IssueCollectionOutcome(tuple(retained), degradation_observed)


def _derive_global_synthesis_status(
    *,
    manifest: GroundingManifest | None,
    degradation_observed: bool,
    renderer_succeeded: bool,
) -> GlobalSynthesisStatus:
    """Derive process status without interpreting Claim grounding semantics."""
    if manifest is None:
        return GlobalSynthesisStatus.FAILED
    if degradation_observed or not renderer_succeeded:
        return GlobalSynthesisStatus.PARTIAL
    return GlobalSynthesisStatus.SUCCESS


def _configured_structured_model(
    *,
    model_name: str,
    max_tokens: int,
    enable_thinking: bool | None,
    schema: type,
    config: RunnableConfig,
) -> Callable[[object], Awaitable[object]]:
    """Construct one no-nested-retry structured request boundary."""
    model_fields = build_model_runtime_fields(
        model=model_name,
        max_tokens=max_tokens,
        api_key=get_api_key_for_model(model_name, config),
        enable_thinking=enable_thinking,
    )
    model = init_chat_model(
        max_retries=0,
        **model_fields,
    )
    structured = model.with_structured_output(schema)
    return structured.ainvoke


def _configured_synthesis_models(
    config: RunnableConfig, configurable: Configuration
) -> _SynthesisModels:
    final_report_enable_thinking = resolve_model_enable_thinking(
        configurable.model_enable_thinking,
        configurable.final_report_model_enable_thinking,
    )
    compression_enable_thinking = resolve_model_enable_thinking(
        configurable.model_enable_thinking,
        configurable.compression_model_enable_thinking,
    )
    return _SynthesisModels(
        claim_generator=_configured_structured_model(
            model_name=configurable.final_report_model,
            max_tokens=configurable.final_report_model_max_tokens,
            enable_thinking=final_report_enable_thinking,
            schema=ClaimDraftBatch,
            config=config,
        ),
        grounding_judge=_configured_structured_model(
            model_name=configurable.compression_model,
            max_tokens=configurable.compression_model_max_tokens,
            enable_thinking=compression_enable_thinking,
            schema=ClaimGroundingDraft,
            config=config,
        ),
        shadow_renderer=_configured_structured_model(
            model_name=configurable.final_report_model,
            max_tokens=configurable.final_report_model_max_tokens,
            enable_thinking=final_report_enable_thinking,
            schema=ShadowReportDraft,
            config=config,
        ),
    )


async def run_global_synthesis(
    *,
    medical_research_brief: MedicalResearchBrief | None,
    research_results: Sequence[ResearchTaskResult],
    artifact_run_id: str | None,
    config: RunnableConfig,
    existing_manifest: GroundingManifest | None = None,
    existing_shadow_report: str | None = None,
    existing_status: GlobalSynthesisStatus | None = None,
    existing_issues: Sequence[GlobalSynthesisIssue] = (),
    artifact_store: ArtifactStore | None = None,
    models: _SynthesisModels | None = None,
    limits: GlobalSynthesisLimits = GlobalSynthesisLimits(),
) -> GlobalSynthesisOutcome:
    """Execute the frozen synthesis order without writing Parent Graph State."""
    try:
        replay = replay_disposition(
            existing_manifest, existing_shadow_report, existing_status
        )
    except Exception as error:
        return _contained_pipeline_failure(
            error=error,
            existing_manifest=existing_manifest,
            existing_issues=existing_issues,
        )
    if replay is ReplayDisposition.FULL_SHORT_CIRCUIT:
        assert existing_manifest is not None
        return GlobalSynthesisOutcome(
            manifest=existing_manifest,
            shadow_report=existing_shadow_report,
            status=existing_status or GlobalSynthesisStatus.SUCCESS,
            issues=tuple(existing_issues),
            metrics=derive_grounding_metrics(existing_manifest),
        )
    if replay is ReplayDisposition.PRESERVE_PARTIAL:
        assert existing_manifest is not None
        return GlobalSynthesisOutcome(
            manifest=existing_manifest,
            shadow_report=None,
            status=GlobalSynthesisStatus.PARTIAL,
            issues=tuple(existing_issues),
            metrics=derive_grounding_metrics(existing_manifest),
        )

    issues = tuple(existing_issues)
    degradation_observed = False
    stage = GlobalSynthesisStage.INPUT_PROJECTION

    def observe(issue: GlobalSynthesisIssue) -> None:
        nonlocal issues, degradation_observed
        reconciled = _reconcile_global_synthesis_issues(
            issues,
            [issue],
            degradation_observed=degradation_observed,
            limits=limits,
        )
        issues = reconciled.issues
        degradation_observed = reconciled.degradation_observed

    def issue(
        *,
        code: str,
        message: str,
        degrades: bool,
        claim_id: str | None = None,
        occurrence_key: str = "",
        severity: GlobalSynthesisSeverity = GlobalSynthesisSeverity.WARNING,
    ) -> None:
        observe(
            _make_global_synthesis_issue(
                stage=stage,
                code=code,
                severity=severity,
                message=message,
                degrades_global_status=degrades,
                claim_id=claim_id,
                occurrence_key=occurrence_key,
                limits=limits,
            )
        )

    if medical_research_brief is None or not artifact_run_id:
        issue(
            code="GLOBAL_SYNTHESIS_INPUT_MISSING",
            message="Global Synthesis requires a research brief and Artifact Run identity.",
            degrades=True,
            severity=GlobalSynthesisSeverity.ERROR,
        )
        return GlobalSynthesisOutcome(
            None, None, GlobalSynthesisStatus.FAILED, issues, None
        )

    if artifact_store is not None:
        store = artifact_store
    else:
        store = await asyncio.to_thread(
            artifact_store_from_config,
            config,
            artifact_run_id,
        )
    configurable = Configuration.from_runnable_config(config)
    execution = GlobalSynthesisExecutionContext(
        artifact_run_id=artifact_run_id,
        medical_research_brief=medical_research_brief,
        research_results=tuple(research_results),
        artifact_store=store,
        limits=limits,
        issues=issues,
        degradation_observed=degradation_observed,
    )
    manifest: GroundingManifest | None = None

    try:
        resolver = TaskQualifiedResolver(execution.research_results, store)
        projection = build_generator_projection(
            brief=execution.medical_research_brief,
            results=execution.research_results,
            artifact_store=store,
            limits=limits,
        )
        if projection.degradation_observed:
            issue(
                code="GENERATOR_CONTEXT_OMISSION",
                message="Generator context admission omitted bounded semantic units.",
                degrades=True,
            )
        configured_models = models

        stage = GlobalSynthesisStage.CLAIM_GENERATION
        if projection.skip_model_a:
            claim_batch = ClaimDraftBatch(claims=[])
        else:
            if projection.projection is None:
                raise ValueError("Generator projection is not invocable")
            if configured_models is None:
                configured_models = _configured_synthesis_models(config, configurable)
            claim_batch = await _invoke_claim_generator(
                configured_models.claim_generator,
                projection=projection.projection,
                max_retries=configurable.max_structured_output_retries,
                limits=limits,
                sleep=asyncio.sleep,
            )

        stage = GlobalSynthesisStage.CLAIM_MATERIALIZATION
        materialized = _materialize_claims(
            claim_batch,
            resolver=resolver,
            generator_visible_finding_refs=projection.generator_visible_finding_refs,
            limits=limits,
        )
        if materialized.degradation_observed:
            invalid_details = " | ".join(
                materialized.invalid_sibling_diagnostics[:3]
            )
            diagnostic_suffix = (
                f" Invalid sibling diagnostics: {invalid_details}."
                if invalid_details
                else ""
            )
            issue(
                code="CLAIM_SIBLING_OMISSION",
                message=(
                    "One or more Claim proposals were omitted before publication: "
                    f"invalid={materialized.invalid_sibling_count}, "
                    f"duplicate={materialized.duplicate_count}, "
                    f"capacity={materialized.capacity_omission_count}."
                    f"{diagnostic_suffix}"
                ),
                degrades=True,
            )

        stage = GlobalSynthesisStage.EVIDENCE_ADMISSION
        admissions = [
            build_grounding_evidence_admission(
                claim=claim, resolver=resolver, limits=limits
            )
            for claim in materialized.claims
        ]
        for admission in admissions:
            if admission.degradation_observed:
                issue(
                    code="JUDGE_EVIDENCE_OMISSION",
                    message="Judge Evidence admission omitted a canonical suffix.",
                    degrades=True,
                    claim_id=admission.claim.claim_id,
                    occurrence_key=admission.claim.claim_id,
                )

        stage = GlobalSynthesisStage.GROUNDING_JUDGE
        if materialized.claims and configured_models is None:
            raise RuntimeError("Model A execution did not establish synthesis models")

        async def unused_model(_request: object) -> object:
            raise RuntimeError("A skipped model role must not be invoked")

        judged = await _judge_claims(
            (
                configured_models.grounding_judge
                if configured_models is not None
                else unused_model
            ),
            admissions=admissions,
            max_concurrency=configurable.max_concurrent_grounding_judgments,
            max_retries=configurable.max_structured_output_retries,
            limits=limits,
        )
        for outcome in judged:
            if outcome.degradation_observed:
                issue(
                    code="GROUNDING_UNASSESSED",
                    message="A Claim has no valid semantic Grounding assessment.",
                    degrades=True,
                    claim_id=outcome.record.claim_id,
                    occurrence_key=outcome.record.claim_id,
                    severity=GlobalSynthesisSeverity.ERROR,
                )

        stage = GlobalSynthesisStage.CITATION_MATERIALIZATION
        groundings = [outcome.record for outcome in judged]
        citations = _materialize_citations(
            materialized.claims, groundings, resolver=resolver
        )
        candidate = GroundingManifest(
            claims=list(materialized.claims),
            groundings=groundings,
            citations=list(citations),
        )

        stage = GlobalSynthesisStage.PUBLICATION_GATE
        manifest = publish_manifest_candidate(
            candidate,
            claim_receipts=materialized.receipts,
            grounding_receipts=[outcome.receipt for outcome in judged],
            resolver=resolver,
            generator_visible_finding_refs=projection.generator_visible_finding_refs,
            limits=limits,
        )
    except Exception as error:
        issue(
            code="GLOBAL_SYNTHESIS_PRE_GATE_FAILURE",
            message=f"Global Synthesis failed before Manifest publication: {type(error).__name__}.",
            degrades=True,
            severity=GlobalSynthesisSeverity.ERROR,
            occurrence_key=type(error).__name__,
        )
        return GlobalSynthesisOutcome(
            None, None, GlobalSynthesisStatus.FAILED, issues, None
        )

    metrics = derive_grounding_metrics(manifest)
    try:
        display_entries = await asyncio.to_thread(
            build_source_display_entries,
            manifest.citations,
            resolver=resolver,
            artifact_run_id=artifact_run_id,
            artifact_store=store,
        )
        stage = GlobalSynthesisStage.SHADOW_RENDERING
        renderer_projection = build_renderer_projection(
            claims=manifest.claims,
            groundings=manifest.groundings,
            resolver=resolver,
            limits=limits,
        )
        if renderer_projection.degradation_observed:
            issue(
                code="RENDERER_EVIDENCE_OMISSION",
                message="Renderer context omitted material Evidence views.",
                degrades=True,
            )
        report = await _render_shadow_report(
            (
                configured_models.shadow_renderer
                if configured_models is not None
                else unused_model
            ),
            projection=renderer_projection,
            manifest=manifest,
            display_entries=display_entries,
            max_retries=configurable.max_structured_output_retries,
            limits=limits,
            sleep=asyncio.sleep,
        )
    except Exception as error:
        stage = GlobalSynthesisStage.RENDERER_VALIDATION
        issue(
            code="SHADOW_RENDERER_FAILURE",
            message=f"Shadow Renderer failed: {type(error).__name__}.",
            degrades=True,
            severity=GlobalSynthesisSeverity.ERROR,
            occurrence_key=type(error).__name__,
        )
        return GlobalSynthesisOutcome(
            manifest,
            None,
            GlobalSynthesisStatus.PARTIAL,
            issues,
            metrics,
        )

    status = _derive_global_synthesis_status(
        manifest=manifest,
        degradation_observed=degradation_observed,
        renderer_succeeded=True,
    )
    return GlobalSynthesisOutcome(manifest, report, status, issues, metrics)


def _contained_pipeline_failure(
    *,
    error: Exception,
    existing_manifest: GroundingManifest | None,
    existing_issues: Sequence[GlobalSynthesisIssue],
) -> GlobalSynthesisOutcome:
    """Contain an unexpected ordinary node-boundary failure without erasing authority."""
    limits = GlobalSynthesisLimits()
    issue = _make_global_synthesis_issue(
        stage=GlobalSynthesisStage.PUBLICATION_GATE,
        code="GLOBAL_SYNTHESIS_BOUNDARY_FAILURE",
        severity=GlobalSynthesisSeverity.ERROR,
        message=f"Global Synthesis boundary failed: {type(error).__name__}.",
        degrades_global_status=True,
        occurrence_key=type(error).__name__,
        limits=limits,
    )
    reconciled = _reconcile_global_synthesis_issues(
        existing_issues,
        [issue],
        degradation_observed=True,
        limits=limits,
    )
    return GlobalSynthesisOutcome(
        manifest=existing_manifest,
        shadow_report=None,
        status=(
            GlobalSynthesisStatus.PARTIAL
            if existing_manifest is not None
            else GlobalSynthesisStatus.FAILED
        ),
        issues=reconciled.issues,
        metrics=(
            derive_grounding_metrics(existing_manifest)
            if existing_manifest is not None
            else None
        ),
    )
