"""Focused tests for P2-S5 reader-facing Source display grouping."""

from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.domain_models import (
    Citation,
    EvidenceRecord,
    EvidenceRef,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
)
from open_deep_research.global_synthesis.projection import TaskQualifiedResolver
from open_deep_research.global_synthesis.renderer import (
    TaskSourceDisplayKey,
    UrlArtifactDisplayKey,
    build_source_display_entries,
)


def _result(task_id, artifact_ref, url, title, *, evidence_id="evidence-1"):
    metadata = {"provider": "test", "title": title}
    if url is not None:
        metadata["url"] = url
    source = SourceRecord(
        source_id="source-1",
        artifact_ref=artifact_ref,
        metadata=metadata,
    )
    evidence = EvidenceRecord(
        evidence_id=evidence_id,
        source_id=source.source_id,
        locator="char:0-7",
        excerpt="Excerpt",
        hash="sha256:abc",
    )
    return ResearchTaskResult(
        task_id=task_id,
        status=ResearchTaskStatus.SUCCESS,
        source_records=[source],
        evidence_records=[evidence],
        findings=[],
        evidence_ids=[evidence.evidence_id],
        source_ids=[source.source_id],
        summary="Summary",
        limitations=[],
        conflicts=[],
    )


def _citation(index, task_id, evidence_id="evidence-1"):
    return Citation(
        citation_id=f"citation-{index}",
        claim_id=f"claim-{index}",
        evidence_ref=EvidenceRef(task_id=task_id, evidence_id=evidence_id),
    )


def test_cross_task_group_requires_exact_url_artifact_and_run(tmp_path) -> None:
    store = LocalFileArtifactStore(tmp_path, "run-one")
    artifact_ref = store.put_text("same artifact")
    results = [
        _result("task-1", artifact_ref, "https://example.test/a", "First title"),
        _result("task-2", artifact_ref, "https://example.test/a", "Later title"),
    ]
    entries = build_source_display_entries(
        [_citation(1, "task-1"), _citation(2, "task-2")],
        resolver=TaskQualifiedResolver(results, store),
        artifact_run_id="run-one",
        artifact_store=store,
    )

    assert len(entries) == 1
    assert isinstance(entries[0].key, UrlArtifactDisplayKey)
    assert entries[0].metadata.title == "First title"
    assert entries[0].label == "[1]"
    assert len(entries[0].source_refs) == 2
    assert entries[0].citation_ids == ("citation-1", "citation-2")


def test_missing_or_different_url_does_not_cross_group(tmp_path) -> None:
    store = LocalFileArtifactStore(tmp_path, "run-one")
    artifact_ref = store.put_text("same artifact")
    results = [
        _result("task-1", artifact_ref, None, "One"),
        _result("task-2", artifact_ref, None, "Two"),
        _result("task-3", artifact_ref, "https://example.test/a", "Three"),
        _result("task-4", artifact_ref, "https://example.test/b", "Four"),
    ]
    entries = build_source_display_entries(
        [_citation(index, f"task-{index}") for index in range(1, 5)],
        resolver=TaskQualifiedResolver(results, store),
        artifact_run_id="run-one",
        artifact_store=store,
    )

    assert len(entries) == 4
    assert isinstance(entries[0].key, TaskSourceDisplayKey)
    assert isinstance(entries[1].key, TaskSourceDisplayKey)
    assert [entry.label for entry in entries] == ["[1]", "[2]", "[3]", "[4]"]


def test_unresolvable_or_different_artifact_does_not_group(tmp_path) -> None:
    store = LocalFileArtifactStore(tmp_path, "run-one")
    first_ref = store.put_text("first artifact")
    second_ref = store.put_text("second artifact")
    missing_ref = "artifact:sha256:" + "f" * 64
    results = [
        _result("task-1", first_ref, "https://example.test/a", "One"),
        _result("task-2", second_ref, "https://example.test/a", "Two"),
        _result("task-3", missing_ref, "https://example.test/a", "Three"),
    ]
    entries = build_source_display_entries(
        [_citation(index, f"task-{index}") for index in range(1, 4)],
        resolver=TaskQualifiedResolver(results, store),
        artifact_run_id="run-one",
        artifact_store=store,
    )

    assert len(entries) == 3
    assert entries[0].key != entries[1].key
    assert isinstance(entries[2].key, TaskSourceDisplayKey)


def test_bibliography_uses_only_available_validated_metadata(tmp_path) -> None:
    store = LocalFileArtifactStore(tmp_path, "run-one")
    artifact_ref = store.put_text("artifact")
    result = _result(
        "task-1", artifact_ref, "https://example.test/a", "Clinical Study"
    )
    source = result.source_records[0]
    result = result.model_copy(
        update={
            "source_records": [
                source.model_copy(
                    update={
                        "metadata": {
                            **source.metadata,
                            "authors": "A. Author",
                            "publisher": "Medical Press",
                            "published_at": "2026-01-02",
                            "document_type": "journal article",
                        }
                    }
                )
            ]
        }
    )
    entry = build_source_display_entries(
        [_citation(1, "task-1")],
        resolver=TaskQualifiedResolver([result], store),
        artifact_run_id="run-one",
        artifact_store=store,
    )[0]

    assert entry.bibliography == (
        "A. Author. Clinical Study[journal article]. Medical Press. "
        "2026-01-02. test. https://example.test/a"
    )
