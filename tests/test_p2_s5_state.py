"""Contract tests for P2-S5 Parent process State and reducer semantics."""

import json

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Overwrite
from pydantic import ValidationError

from open_deep_research.domain_models import (
    Citation,
    ClaimGroundingRecord,
    ClaimMateriality,
    ClaimRecord,
    EvidenceRef,
    FindingRef,
    GroundingManifest,
    GroundingStatus,
    ResearchTaskResult,
    ResearchTaskStatus,
)
from open_deep_research.state import (
    AgentState,
    GlobalSynthesisIssue,
    GlobalSynthesisSeverity,
    GlobalSynthesisStatus,
    ResearchRunStatus,
    global_synthesis_issues_reducer,
    grounding_manifest_reducer,
)


def _manifest(*, claim_text: str = "Treatment improves outcomes.") -> GroundingManifest:
    finding_ref = FindingRef(task_id="task-1", finding_id="finding-1")
    evidence_ref = EvidenceRef(task_id="task-1", evidence_id="evidence-1")
    claim = ClaimRecord(
        claim_id="claim-1",
        text=claim_text,
        materiality=ClaimMateriality.HIGH,
        finding_refs=[finding_ref],
        scope=None,
        qualifiers=[],
    )
    grounding = ClaimGroundingRecord(
        claim_id=claim.claim_id,
        evaluated_evidence_refs=[evidence_ref],
        supporting_evidence_refs=[evidence_ref],
        contradicting_evidence_refs=[],
        status=GroundingStatus.SUPPORTED,
        reason="Directly supported.",
    )
    citation = Citation(
        citation_id="citation-1",
        claim_id=claim.claim_id,
        evidence_ref=evidence_ref,
    )
    return GroundingManifest(
        claims=[claim],
        groundings=[grounding],
        citations=[citation],
    )


def _issue(
    *,
    issue_id: str = "issue-1",
    message: str = "One bounded diagnostic.",
) -> GlobalSynthesisIssue:
    return GlobalSynthesisIssue(
        issue_id=issue_id,
        stage="future_host_stage.v2",
        code="bounded_diagnostic",
        severity=GlobalSynthesisSeverity.WARNING,
        message=message,
        claim_id=None,
        task_id="task-1",
        evidence_ref=None,
        attempt=None,
        degrades_global_status=False,
    )


def _result() -> ResearchTaskResult:
    return ResearchTaskResult(
        task_id="task-1",
        status=ResearchTaskStatus.SUCCESS,
        findings=[],
        evidence_ids=[],
        source_ids=[],
        summary="Bounded result.",
        limitations=[],
        conflicts=[],
    )


def test_global_synthesis_process_contracts_are_strict_and_serializable() -> None:
    """Accept open legal stages while keeping severity and extra fields closed."""
    issue = _issue()

    assert issue.stage == "future_host_stage.v2"
    assert json.loads(issue.model_dump_json()) == issue.model_dump(mode="json")
    assert GlobalSynthesisStatus.SUCCESS.value == "success"
    assert ResearchRunStatus.AWAITING_CLARIFICATION.value == "awaiting_clarification"
    with pytest.raises(ValidationError):
        GlobalSynthesisIssue.model_validate(
            {**issue.model_dump(mode="python"), "severity": "notice"}
        )
    with pytest.raises(ValidationError):
        GlobalSynthesisIssue.model_validate(
            {**issue.model_dump(mode="python"), "unexpected": True}
        )
    assert GlobalSynthesisIssue.model_validate(
        {**issue.model_dump(mode="python"), "stage": "future stage vocabulary"}
    ).stage == "future stage vocabulary"


def test_manifest_reducer_publishes_once_and_detects_divergent_replay() -> None:
    """Protect atomic same-run Manifest publication and replay semantics."""
    manifest = _manifest()

    assert grounding_manifest_reducer(None, manifest) is manifest
    assert grounding_manifest_reducer(manifest, manifest) is manifest
    with pytest.raises(ValueError, match="divergent"):
        grounding_manifest_reducer(manifest, None)
    with pytest.raises(ValueError, match="divergent"):
        grounding_manifest_reducer(
            manifest,
            _manifest(claim_text="Treatment changes a different outcome."),
        )


def test_issue_reducer_deduplicates_and_defensively_retains_first_payload() -> None:
    """Leave P05 reconciliation to Host logic while retaining the first State write."""
    issue = _issue()
    divergent = _issue(message="Different wording or payload remains a Host concern.")

    assert global_synthesis_issues_reducer([], [issue, issue]) == [issue]
    assert global_synthesis_issues_reducer([issue], [divergent]) == [issue]


def test_issue_reducer_enforces_ledger_count_bound() -> None:
    """Reject an update that would exceed the frozen bounded issue ledger."""
    issues = [_issue(issue_id=f"issue-{index}") for index in range(65)]

    with pytest.raises(ValueError, match="count exceeds"):
        global_synthesis_issues_reducer([], issues)


def test_overwrite_resets_reducer_backed_run_channels() -> None:
    """Verify framework Overwrite clears channels that ordinary empty updates retain."""
    issue = _issue()
    manifest = _manifest()

    ordinary_builder = StateGraph(AgentState)
    ordinary_builder.add_node(
        "ordinary_empty",
        lambda _state: {"global_synthesis_issues": []},
    )
    ordinary_builder.add_edge(START, "ordinary_empty")
    ordinary_builder.add_edge("ordinary_empty", END)
    ordinary_result = ordinary_builder.compile().invoke(
        {
            "messages": [],
            "grounding_manifest": manifest,
            "global_synthesis_issues": [issue],
        }
    )
    assert ordinary_result["global_synthesis_issues"] == [issue]

    reset_builder = StateGraph(AgentState)
    reset_builder.add_node(
        "reset",
        lambda _state: {
            "supervisor_messages": Overwrite([]),
            "research_results": Overwrite([]),
            "raw_notes": Overwrite([]),
            "notes": Overwrite([]),
            "grounding_manifest": Overwrite(None),
            "global_synthesis_issues": Overwrite([]),
        },
    )
    reset_builder.add_edge(START, "reset")
    reset_builder.add_edge("reset", END)
    reset_result = reset_builder.compile().invoke(
        {
            "messages": [],
            "supervisor_messages": ["prior supervisor context"],
            "research_results": [_result()],
            "raw_notes": ["prior raw note"],
            "notes": ["prior note"],
            "grounding_manifest": manifest,
            "global_synthesis_issues": [issue],
        }
    )

    assert reset_result["grounding_manifest"] is None
    assert reset_result["global_synthesis_issues"] == []
    assert reset_result["supervisor_messages"] == []
    assert reset_result["research_results"] == []
    assert reset_result["raw_notes"] == []
    assert reset_result["notes"] == []


def test_agent_state_exposes_all_p2_s5_parent_channels() -> None:
    """Keep lifecycle and Global Synthesis process fields on Parent State only."""
    assert {
        "grounding_manifest",
        "global_synthesis_status",
        "global_synthesis_issues",
        "v2_shadow_report",
        "research_run_status",
        "research_run_input_cursor",
    } <= AgentState.__annotations__.keys()
