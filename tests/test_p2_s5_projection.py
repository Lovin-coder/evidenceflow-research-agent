"""Protect S5 task-qualified resolution and bounded Generator projection."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.domain_models import (
    EvidenceNeed,
    EvidenceRecord,
    EvidenceRef,
    FindingRef,
    MedicalResearchBrief,
    ResearchFinding,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
)
from open_deep_research.global_synthesis.projection import (
    ProjectionResolutionError,
    TaskQualifiedResolver,
    build_generator_projection,
)
from open_deep_research.global_synthesis.types import GlobalSynthesisLimits


def _brief() -> MedicalResearchBrief:
    return MedicalResearchBrief(
        normalized_question="What is the evidence?",
        question_type="therapy",
        clinical_elements=None,
        constraints=[],
        research_intent="Compare outcomes",
        evidence_needs=[
            EvidenceNeed(
                evidence_types=["clinical outcome evidence"],
                coverage_dimensions=["benefits and harms"],
            )
        ],
    )


def _result(
    task_id: str,
    *,
    finding_ids: tuple[str, ...] = ("shared-finding",),
    excerpt: str = "Exact evidence excerpt.",
    metadata: dict[str, str] | None = None,
    summary: str = "Task summary",
) -> ResearchTaskResult:
    source = SourceRecord(
        source_id="shared-source",
        artifact_ref="artifact:sha256:" + "a" * 64,
        metadata=metadata
        or {
            "url": f"https://example.test/{task_id}",
            "title": f"Title {task_id}",
            "provider": "test-provider",
            "retrieved_at": "2026-08-29T00:00:00Z",
            "unapproved": "must stay private",
        },
    )
    evidence = EvidenceRecord(
        evidence_id="shared-evidence",
        source_id=source.source_id,
        locator=f"char:0-{len(excerpt)}",
        excerpt=excerpt,
        hash="sha256:" + "b" * 64,
    )
    findings = [
        ResearchFinding(
            finding_id=finding_id,
            task_id=task_id,
            text=f"Finding {finding_id} in {task_id}",
            evidence_ids=[evidence.evidence_id],
            limitations=[],
            conflicts=[],
        )
        for finding_id in finding_ids
    ]
    return ResearchTaskResult(
        task_id=task_id,
        status=ResearchTaskStatus.SUCCESS,
        source_records=[source],
        evidence_records=[evidence],
        findings=findings,
        evidence_ids=[evidence.evidence_id],
        source_ids=[source.source_id],
        summary=summary,
        limitations=[],
        conflicts=[],
    )


def _serialized_projection_chars(value: object) -> int:
    model_dump = getattr(value, "model_dump")
    return len(
        json.dumps(
            model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def test_resolver_requires_unique_task_ids(tmp_path) -> None:
    result = _result("task-1")
    with pytest.raises(ProjectionResolutionError, match="Duplicate.*task_id"):
        TaskQualifiedResolver(
            [result, result], LocalFileArtifactStore(tmp_path, "run-one")
        )


def test_resolver_uses_task_qualified_refs_without_sibling_scan(tmp_path) -> None:
    first = _result("task-1")
    second = _result("task-2")
    resolver = TaskQualifiedResolver(
        [first, second], LocalFileArtifactStore(tmp_path, "run-one")
    )

    assert (
        resolver.resolve_finding(
            FindingRef(task_id="task-2", finding_id="shared-finding")
        ).task_id
        == "task-2"
    )
    assert (
        resolver.resolve_evidence(
            EvidenceRef(task_id="task-2", evidence_id="shared-evidence")
        )
        is second.evidence_records[0]
    )
    with pytest.raises(ProjectionResolutionError, match="Unknown FindingRef"):
        resolver.resolve_finding(
            FindingRef(task_id="task-1", finding_id="only-in-task-2")
        )
    with pytest.raises(ProjectionResolutionError, match="Unknown.*task_id"):
        resolver.resolve_evidence(
            EvidenceRef(task_id="missing", evidence_id="shared-evidence")
        )


def test_artifact_resolution_uses_supplied_current_run_store(tmp_path) -> None:
    current_store = LocalFileArtifactStore(tmp_path, "current-run")
    other_store = LocalFileArtifactStore(tmp_path, "other-run")
    artifact_ref = current_store.put_text("current run artifact")
    result = _result("task-1")
    result = result.model_copy(
        update={
            "source_records": [
                result.source_records[0].model_copy(
                    update={"artifact_ref": artifact_ref}
                )
            ]
        }
    )

    resolver = TaskQualifiedResolver([result], current_store)
    evidence_ref = EvidenceRef(task_id="task-1", evidence_id="shared-evidence")
    assert resolver.resolve_artifact_text(evidence_ref) == "current run artifact"

    with pytest.raises(ValueError, match="does not exist"):
        TaskQualifiedResolver([result], other_store).resolve_artifact_text(evidence_ref)


def test_generator_projection_preserves_result_finding_and_evidence_order(
    tmp_path,
) -> None:
    first = _result("task-1", finding_ids=("f-1", "f-2"))
    second = _result("task-2", finding_ids=("f-3",))

    outcome = build_generator_projection(
        brief=_brief(),
        results=[first, second],
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
        limits=GlobalSynthesisLimits(),
    )

    assert outcome.projection is not None
    assert [result.task_id for result in outcome.projection.results] == [
        "task-1",
        "task-2",
    ]
    assert [
        finding.finding_ref.finding_id
        for result in outcome.projection.results
        for finding in result.findings
    ] == ["f-1", "f-2", "f-3"]
    assert [ref.finding_id for ref in outcome.generator_visible_finding_refs] == [
        "f-1",
        "f-2",
        "f-3",
    ]
    assert outcome.skip_model_a is False


def test_projection_whitelists_metadata_and_excludes_artifact_fields(tmp_path) -> None:
    result = _result("task-1")
    outcome = build_generator_projection(
        brief=_brief(),
        results=[result],
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
        limits=GlobalSynthesisLimits(),
    )

    assert outcome.projection is not None
    payload = outcome.projection.model_dump(mode="json")
    serialized = json.dumps(payload)
    metadata = payload["results"][0]["findings"][0]["evidence"][0][
        "source_metadata"
    ]
    assert metadata["title"] == "Title task-1"
    assert metadata["url"] == "https://example.test/task-1"
    assert metadata["publisher"] is None
    assert "retrieved_at" not in metadata
    assert "unapproved" not in metadata
    assert "artifact_ref" not in serialized
    assert "locator" not in serialized
    assert "hash" not in serialized
    assert "must stay private" not in serialized


def test_optional_metadata_can_be_absent_without_blocking_evidence(tmp_path) -> None:
    result = _result("task-1", metadata={"retrieved_at": "2026-08-29T00:00:00Z"})
    outcome = build_generator_projection(
        brief=_brief(),
        results=[result],
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
        limits=GlobalSynthesisLimits(),
    )

    assert outcome.projection is not None
    evidence = outcome.projection.results[0].findings[0].evidence[0]
    assert evidence.excerpt == "Exact evidence excerpt."
    assert evidence.source_metadata is None


def test_evidence_overflow_omits_whole_excerpt_without_slicing(tmp_path) -> None:
    excerpt = "ABCDEFGHIJ"
    result = _result("task-1", excerpt=excerpt)
    limits = replace(GlobalSynthesisLimits(), max_generator_evidence_chars=9)

    outcome = build_generator_projection(
        brief=_brief(),
        results=[result],
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
        limits=limits,
    )

    assert outcome.projection is not None
    finding = outcome.projection.results[0].findings[0]
    assert finding.evidence == []
    assert finding.text == "Finding shared-finding in task-1"
    assert outcome.generator_visible_finding_refs == (
        FindingRef(task_id="task-1", finding_id="shared-finding"),
    )
    assert outcome.omitted_evidence_count == 1
    assert outcome.degradation_observed is True


def test_finding_and_total_context_admission_is_whole_and_bounded(tmp_path) -> None:
    result = _result("task-1", finding_ids=("first", "second"))
    one_finding = build_generator_projection(
        brief=_brief(),
        results=[result.model_copy(update={"findings": result.findings[:1]})],
        artifact_store=LocalFileArtifactStore(tmp_path, "measure-run"),
        limits=GlobalSynthesisLimits(),
    )
    assert one_finding.projection is not None
    exact_one_finding_size = _serialized_projection_chars(one_finding.projection)

    outcome = build_generator_projection(
        brief=_brief(),
        results=[result],
        artifact_store=LocalFileArtifactStore(tmp_path, "bounded-run"),
        limits=replace(
            GlobalSynthesisLimits(),
            max_generator_context_chars=exact_one_finding_size,
        ),
    )

    assert outcome.projection is not None
    assert _serialized_projection_chars(outcome.projection) <= exact_one_finding_size
    assert [
        finding.finding_ref.finding_id
        for finding in outcome.projection.results[0].findings
    ] == ["first"]
    assert outcome.omitted_finding_count == 1
    assert outcome.degradation_observed is True


def test_summary_truncation_is_observable_and_projection_is_deterministic(
    tmp_path,
) -> None:
    result = _result("task-1", summary="summary-too-long")
    limits = replace(GlobalSynthesisLimits(), max_task_summary_chars=7)
    store = LocalFileArtifactStore(tmp_path, "run-one")

    first = build_generator_projection(
        brief=_brief(), results=[result], artifact_store=store, limits=limits
    )
    second = build_generator_projection(
        brief=_brief(), results=[result], artifact_store=store, limits=limits
    )

    assert first == second
    assert first.projection is not None
    assert first.projection.results[0].summary == "summary"
    assert first.projection.results[0].summary_truncated is True
    assert first.degradation_observed is True


def test_no_visible_findings_skips_model_a_legally(tmp_path) -> None:
    result = _result("task-1")
    outcome = build_generator_projection(
        brief=_brief(),
        results=[result],
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
        limits=replace(GlobalSynthesisLimits(), max_findings_total=0),
    )

    assert outcome.projection is not None
    assert outcome.generator_visible_finding_refs == ()
    assert outcome.skip_model_a is True
    assert outcome.degradation_observed is True
    assert outcome.omitted_finding_count == 1


def test_brief_overflow_returns_no_invocable_projection(tmp_path) -> None:
    outcome = build_generator_projection(
        brief=_brief(),
        results=[_result("task-1")],
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
        limits=replace(GlobalSynthesisLimits(), max_generator_context_chars=1),
    )

    assert outcome.projection is None
    assert outcome.skip_model_a is True
    assert outcome.degradation_observed is True
    assert outcome.generator_visible_finding_refs == ()
