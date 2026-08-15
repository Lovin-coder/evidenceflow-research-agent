import pytest

from open_deep_research.deep_researcher import (
    deep_researcher,
    researcher_subgraph,
    supervisor_subgraph,
)
from open_deep_research.domain_models import (
    EvidenceNeed,
    EvidenceRecord,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
)
from open_deep_research.state import (
    evidence_records_reducer,
    research_results_reducer,
    source_records_reducer,
)


def result(task_id: str, summary: str = "Summary") -> ResearchTaskResult:
    """Build a minimal immutable result for reducer tests."""
    return ResearchTaskResult(
        task_id=task_id,
        status=ResearchTaskStatus.SUCCESS,
        findings=[],
        evidence_ids=[],
        source_ids=[],
        summary=summary,
        limitations=[],
        conflicts=[],
    )


def test_research_results_append_deduplicate_and_reject_conflicts() -> None:
    """Verify result replay is idempotent while conflicting payloads fail."""
    first = result("task:1")
    second = result("task:2")

    assert research_results_reducer([first], [second]) == [first, second]
    assert research_results_reducer([first], [first]) == [first]
    with pytest.raises(ValueError, match="Contract conflict"):
        research_results_reducer([first], [result("task:1", "Different")])


def test_source_and_evidence_reducers_use_stable_identity() -> None:
    """Protect identity-based deduplication for Source and Evidence channels."""
    source = SourceRecord(
        source_id="source-1",
        artifact_ref=None,
        metadata={"provider": "test"},
    )
    evidence = EvidenceRecord(
        evidence_id="evidence-1",
        source_id="source-1",
        locator="p1",
        excerpt="Source passage.",
        hash="sha256:abc",
    )

    assert source_records_reducer([], [source, source]) == [source]
    assert evidence_records_reducer([], [evidence, evidence]) == [evidence]
    with pytest.raises(ValueError, match="Contract conflict"):
        source_records_reducer(
            [source],
            [
                SourceRecord(
                    source_id="source-1",
                    artifact_ref=None,
                    metadata={"provider": "different"},
                )
            ],
        )


def test_state_channels_expose_structured_and_legacy_contracts() -> None:
    """Ensure structured contracts coexist with the frozen legacy state path."""
    assert {
        "medical_research_brief",
        "research_brief",
        "research_results",
        "raw_notes",
        "notes",
    } <= set(deep_researcher.channels)
    assert {
        "task",
        "research_topic",
        "source_records",
        "evidence_records",
        "findings",
        "research_task_status",
        "research_task_result",
        "compressed_research",
        "raw_notes",
    } <= set(researcher_subgraph.channels)


def _edges(graph) -> set[tuple[str, str]]:
    """Return graph edges in a deterministic comparison-friendly form."""
    return {(edge.source, edge.target) for edge in graph.get_graph().edges}


def test_graph_topology_matches_frozen_supervisor_researcher_loop() -> None:
    """Guard against accidental changes to the frozen Supervisor-Researcher topology."""
    assert _edges(deep_researcher) == {
        ("__start__", "clarify_with_user"),
        ("clarify_with_user", "__end__"),
        ("clarify_with_user", "write_research_brief"),
        ("write_research_brief", "research_supervisor"),
        ("research_supervisor", "final_report_generation"),
        ("final_report_generation", "__end__"),
    }
    assert _edges(supervisor_subgraph) == {
        ("__start__", "supervisor"),
        ("supervisor", "supervisor_tools"),
        ("supervisor_tools", "supervisor"),
        ("supervisor_tools", "__end__"),
    }
    assert _edges(researcher_subgraph) == {
        ("__start__", "researcher"),
        ("researcher", "researcher_tools"),
        ("researcher_tools", "researcher"),
        ("researcher_tools", "compress_research"),
        ("compress_research", "__end__"),
    }


def test_evidence_need_remains_nested_without_a_graph_channel() -> None:
    """Ensure EvidenceNeed remains nested domain data rather than a graph stage."""
    need = EvidenceNeed(evidence_types=["clinical outcomes"])
    assert need.evidence_types == ["clinical outcomes"]
    assert "evidence_need" not in deep_researcher.channels
    assert "evidence_need" not in researcher_subgraph.channels
