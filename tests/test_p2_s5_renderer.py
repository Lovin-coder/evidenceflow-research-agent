"""Focused tests for bounded Model C projection and Host finalization."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.domain_models import (
    Citation,
    ClaimGroundingRecord,
    ClaimMateriality,
    ClaimRecord,
    EvidenceRecord,
    EvidenceRef,
    FindingRef,
    GroundingManifest,
    GroundingStatus,
    ResearchFinding,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
)
from open_deep_research.global_synthesis.projection import (
    RendererProjectionOutcome,
    TaskQualifiedResolver,
    _renderer_projection_chars,
    build_renderer_projection,
)
from open_deep_research.global_synthesis.renderer import (
    _CONFLICT_MARKER,
    _render_shadow_report,
    build_source_display_entries,
)
from open_deep_research.global_synthesis.types import (
    GlobalSynthesisLimits,
    RendererEvidenceRole,
    ReportParagraphDraft,
    ReportSectionDraft,
    ShadowReportDraft,
)


def _fixture(tmp_path):
    store = LocalFileArtifactStore(tmp_path, "renderer-run")
    source_specs = [
        ("source-support", "support artifact", "https://example.test/support"),
        ("source-conflict", "conflict artifact", "https://example.test/conflict"),
        ("source-neutral", "neutral artifact", "https://example.test/neutral"),
    ]
    sources = [
        SourceRecord(
            source_id=source_id,
            artifact_ref=store.put_text(artifact),
            metadata={"title": source_id, "url": url, "provider": "test"},
        )
        for source_id, artifact, url in source_specs
    ]
    evidence = [
        EvidenceRecord(
            evidence_id=evidence_id,
            source_id=source.source_id,
            locator="char:0-7",
            excerpt=excerpt,
            hash=f"sha256:{index}",
        )
        for index, (evidence_id, source, excerpt) in enumerate(
            zip(
                ("e-support", "e-conflict", "e-neutral"),
                sources,
                ("Supports claim.", "Conflicts claim.", "Neutral context."),
                strict=True,
            )
        )
    ]
    finding = ResearchFinding(
        finding_id="finding-1",
        task_id="task-1",
        text="Finding text",
        evidence_ids=[item.evidence_id for item in evidence],
        limitations=[],
        conflicts=[],
    )
    result = ResearchTaskResult(
        task_id="task-1",
        status=ResearchTaskStatus.SUCCESS,
        source_records=sources,
        evidence_records=evidence,
        findings=[finding],
        evidence_ids=[item.evidence_id for item in evidence],
        source_ids=[source.source_id for source in sources],
        summary="Summary",
        limitations=[],
        conflicts=[],
    )
    claim = ClaimRecord(
        claim_id="claim-1",
        text="Treatment improves outcomes.",
        materiality=ClaimMateriality.HIGH,
        finding_refs=[FindingRef(task_id="task-1", finding_id="finding-1")],
        scope="Adults",
        qualifiers=["At twelve weeks"],
    )
    refs = [EvidenceRef(task_id="task-1", evidence_id=item.evidence_id) for item in evidence]
    grounding = ClaimGroundingRecord(
        claim_id=claim.claim_id,
        evaluated_evidence_refs=refs,
        supporting_evidence_refs=[refs[0]],
        contradicting_evidence_refs=[refs[1]],
        status=GroundingStatus.SUPPORTED_WITH_CONFLICT,
        reason="Must never enter Renderer input.",
    )
    citations = [
        Citation(
            citation_id=f"citation-{index}",
            claim_id=claim.claim_id,
            evidence_ref=ref,
        )
        for index, ref in enumerate(refs[:2], start=1)
    ]
    manifest = GroundingManifest(
        claims=[claim], groundings=[grounding], citations=citations
    )
    resolver = TaskQualifiedResolver([result], store)
    entries = build_source_display_entries(
        citations,
        resolver=resolver,
        artifact_run_id="renderer-run",
        artifact_store=store,
    )
    return store, resolver, manifest, entries


def test_renderer_projection_retains_claim_and_only_material_evidence(tmp_path) -> None:
    _store, resolver, manifest, _entries = _fixture(tmp_path)
    projection = build_renderer_projection(
        claims=manifest.claims,
        groundings=manifest.groundings,
        resolver=resolver,
        limits=GlobalSynthesisLimits(),
    )

    assert len(projection.claims) == 1
    view = projection.claims[0]
    assert view.scope == "Adults"
    assert view.qualifiers == ["At twelve weeks"]
    assert [item.role for item in view.evidence] == [
        RendererEvidenceRole.SUPPORTING,
        RendererEvidenceRole.CONTRADICTING,
    ]
    serialized = str(view.model_dump(mode="json"))
    assert "Neutral context" not in serialized
    assert "Must never enter" not in serialized
    assert "artifact_ref" not in serialized


def test_context_overflow_keeps_claim_and_does_not_change_manifest(tmp_path) -> None:
    _store, resolver, manifest, _entries = _fixture(tmp_path)
    base = build_renderer_projection(
        claims=manifest.claims,
        groundings=[
            manifest.groundings[0].model_copy(
                update={
                    "supporting_evidence_refs": [],
                    "contradicting_evidence_refs": [],
                }
            )
        ],
        resolver=resolver,
        limits=GlobalSynthesisLimits(),
    )
    base_size = _renderer_projection_chars(list(base.claims))
    projection = build_renderer_projection(
        claims=manifest.claims,
        groundings=manifest.groundings,
        resolver=resolver,
        limits=replace(GlobalSynthesisLimits(), max_renderer_context_chars=base_size),
    )

    assert len(projection.claims) == 1
    assert projection.claims[0].evidence == []
    assert projection.omitted_evidence_count == 2
    assert projection.degradation_observed is True
    assert len(manifest.citations) == 2


def _draft(text="Evidence-based paragraph.", *, repeated=False):
    paragraphs = [ReportParagraphDraft(text=text, claim_ids=["claim-1"])]
    if repeated:
        paragraphs.append(ReportParagraphDraft(text="Second mention.", claim_ids=["claim-1"]))
    return ShadowReportDraft(
        sections=[ReportSectionDraft(title="Findings", paragraphs=paragraphs)]
    )


class _RendererModel:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = 0

    async def ainvoke(self, _request):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_finalization_injects_conflict_once_both_labels_and_bibliography(
    tmp_path,
) -> None:
    _store, resolver, manifest, entries = _fixture(tmp_path)
    projection = build_renderer_projection(
        claims=manifest.claims,
        groundings=manifest.groundings,
        resolver=resolver,
        limits=GlobalSynthesisLimits(),
    )
    model = _RendererModel([_draft(repeated=True)])

    report = await _render_shadow_report(
        model.ainvoke,
        projection=projection,
        manifest=manifest,
        display_entries=entries,
        max_retries=0,
        limits=GlobalSynthesisLimits(),
        sleep=asyncio.sleep,
    )

    assert report.count(_CONFLICT_MARKER) == 1
    assert "[1]" in report and "[2]" in report
    assert "## 参考文献" in report
    assert model.calls == 1


@pytest.mark.asyncio
async def test_final_size_failure_retries_with_same_model_c_budget(tmp_path) -> None:
    _store, resolver, manifest, entries = _fixture(tmp_path)
    projection = build_renderer_projection(
        claims=manifest.claims,
        groundings=manifest.groundings,
        resolver=resolver,
        limits=GlobalSynthesisLimits(),
    )
    model = _RendererModel([_draft("x" * 500), _draft("short")])
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)

    report = await _render_shadow_report(
        model.ainvoke,
        projection=projection,
        manifest=manifest,
        display_entries=entries,
        max_retries=1,
        limits=replace(GlobalSynthesisLimits(), max_shadow_report_chars=400),
        sleep=sleep,
    )

    assert "short" in report
    assert model.calls == 2
    assert sleeps == []


@pytest.mark.asyncio
async def test_zero_eligible_skips_model_c_without_fake_citations() -> None:
    model = _RendererModel([AssertionError("must not call")])
    report = await _render_shadow_report(
        model.ainvoke,
        projection=RendererProjectionOutcome((), False, 0),
        manifest=GroundingManifest(claims=[], groundings=[], citations=[]),
        display_entries=(),
        max_retries=3,
        limits=GlobalSynthesisLimits(),
        sleep=asyncio.sleep,
    )

    assert model.calls == 0
    assert "[" not in report
    assert "参考文献" not in report
