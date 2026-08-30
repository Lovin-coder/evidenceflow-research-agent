"""Checkpoint and state-machine tests for the P2-S5 Research Run lifecycle."""

from __future__ import annotations

from typing import Any, cast

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Overwrite

from open_deep_research.deep_researcher import (
    _bootstrap_or_resume_research_run,
    _ResearchRunLifecycleConflict,
)
from open_deep_research.domain_models import GroundingManifest
from open_deep_research.state import (
    AgentState,
    GlobalSynthesisStatus,
    ResearchRunStatus,
)


def _state(
    status: ResearchRunStatus | None,
    cursor: int | None,
    human_count: int,
) -> AgentState:
    values: dict[str, Any] = {
        "messages": [
            HumanMessage(content=f"input-{index}", id=f"human-{index}")
            for index in range(human_count)
        ],
        "artifact_run_id": "run-established" if status is not None else None,
        "research_run_status": status,
        "research_run_input_cursor": cursor,
    }
    return cast(AgentState, values)


def test_first_run_bootstrap_resets_every_run_scoped_channel() -> None:
    state = _state(None, None, 1)
    state.update(
        {
            "supervisor_messages": [HumanMessage(content="old")],
            "research_results": [],
            "raw_notes": ["old"],
            "notes": ["old"],
            "final_report": "old report",
            "grounding_manifest": GroundingManifest(
                claims=[], groundings=[], citations=[]
            ),
            "global_synthesis_status": GlobalSynthesisStatus.SUCCESS,
            "global_synthesis_issues": [],
            "v2_shadow_report": "old shadow",
        }
    )

    update, should_end = _bootstrap_or_resume_research_run(
        state, cast(RunnableConfig, {})
    )

    assert should_end is False
    assert update["research_run_status"] is ResearchRunStatus.ACTIVE
    assert update["research_run_input_cursor"] == 1
    assert update["artifact_run_id"] != "run-established"
    assert isinstance(update["supervisor_messages"], Overwrite)
    assert isinstance(update["research_results"], Overwrite)
    assert isinstance(update["raw_notes"], Overwrite)
    assert isinstance(update["notes"], Overwrite)
    assert isinstance(update["grounding_manifest"], Overwrite)
    assert isinstance(update["global_synthesis_issues"], Overwrite)
    assert update["medical_research_brief"] is None
    assert update["research_brief"] is None
    assert update["final_report"] == ""
    assert update["global_synthesis_status"] is None
    assert update["v2_shadow_report"] is None


@pytest.mark.parametrize("human_count", [0, 2])
def test_uninitialized_lifecycle_requires_exactly_one_human(human_count: int) -> None:
    with pytest.raises(_ResearchRunLifecycleConflict):
        _bootstrap_or_resume_research_run(
            _state(None, None, human_count), cast(RunnableConfig, {})
        )


def test_active_recovery_and_mid_run_steering_mapping() -> None:
    update, should_end = _bootstrap_or_resume_research_run(
        _state(ResearchRunStatus.ACTIVE, 1, 1), cast(RunnableConfig, {})
    )
    assert update == {}
    assert should_end is False

    with pytest.raises(_ResearchRunLifecycleConflict, match="steering"):
        _bootstrap_or_resume_research_run(
            _state(ResearchRunStatus.ACTIVE, 1, 2), cast(RunnableConfig, {})
        )


def test_clarification_wait_and_resume_mapping() -> None:
    waiting, should_end = _bootstrap_or_resume_research_run(
        _state(ResearchRunStatus.AWAITING_CLARIFICATION, 1, 1),
        cast(RunnableConfig, {}),
    )
    assert waiting == {}
    assert should_end is True

    resumed, should_end = _bootstrap_or_resume_research_run(
        _state(ResearchRunStatus.AWAITING_CLARIFICATION, 1, 2),
        cast(RunnableConfig, {}),
    )
    assert should_end is False
    assert resumed == {
        "research_run_status": ResearchRunStatus.ACTIVE,
        "research_run_input_cursor": 2,
    }


def test_finalized_replay_and_new_run_mapping() -> None:
    replay, should_end = _bootstrap_or_resume_research_run(
        _state(ResearchRunStatus.FINALIZED, 1, 1), cast(RunnableConfig, {})
    )
    assert replay == {}
    assert should_end is True

    state = _state(ResearchRunStatus.FINALIZED, 1, 2)
    new_run, should_end = _bootstrap_or_resume_research_run(
        state, cast(RunnableConfig, {})
    )
    assert should_end is False
    assert new_run["research_run_status"] is ResearchRunStatus.ACTIVE
    assert new_run["research_run_input_cursor"] == 2
    assert new_run["artifact_run_id"] != state["artifact_run_id"]


def test_impossible_cursor_and_initialized_shape_are_conflicts() -> None:
    with pytest.raises(_ResearchRunLifecycleConflict, match="inconsistent"):
        _bootstrap_or_resume_research_run(
            _state(ResearchRunStatus.ACTIVE, None, 1), cast(RunnableConfig, {})
        )
    with pytest.raises(_ResearchRunLifecycleConflict, match="occurrence count"):
        _bootstrap_or_resume_research_run(
            _state(ResearchRunStatus.ACTIVE, 2, 1), cast(RunnableConfig, {})
        )


def test_langgraph_message_identity_uses_occurrences_not_text_fingerprints() -> None:
    original = HumanMessage(content="same text", id="stable-id")

    replay = add_messages([original], [HumanMessage(content="same text", id="stable-id")])
    new_occurrence = add_messages([original], [HumanMessage(content="same text")])

    assert len(replay) == 1
    assert len(new_occurrence) == 2


def test_checkpoint_conflict_preserves_evidenceflow_state_after_message_admission() -> None:
    def entry(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        update, _should_end = _bootstrap_or_resume_research_run(state, config)
        return update

    builder = StateGraph(AgentState)
    builder.add_node("entry", entry)
    builder.add_edge(START, "entry")
    builder.add_edge("entry", END)
    graph = builder.compile(checkpointer=MemorySaver())
    config: RunnableConfig = {
        "configurable": {"thread_id": "p2-s5-lifecycle-conflict"}
    }

    first = graph.invoke(
        {"messages": [HumanMessage(content="first", id="human-1")]}, config
    )
    manifest = GroundingManifest(claims=[], groundings=[], citations=[])
    graph.update_state(
        config,
        {
            "medical_research_brief": None,
            "research_brief": "preserved brief",
            "research_results": Overwrite([]),
            "raw_notes": Overwrite(["preserved raw note"]),
            "notes": Overwrite(["preserved note"]),
            "final_report": "preserved v1",
            "grounding_manifest": manifest,
            "global_synthesis_status": GlobalSynthesisStatus.SUCCESS,
            "global_synthesis_issues": Overwrite([]),
            "v2_shadow_report": "preserved v2",
        },
    )
    before = graph.get_state(config).values

    with pytest.raises(_ResearchRunLifecycleConflict, match="steering"):
        graph.invoke(
            {"messages": [HumanMessage(content="conflict", id="human-2")]},
            config,
        )

    after = graph.get_state(config).values
    assert [message.id for message in after["messages"]] == ["human-1", "human-2"]
    for field in (
        "research_run_input_cursor",
        "research_run_status",
        "artifact_run_id",
        "medical_research_brief",
        "research_brief",
        "research_results",
        "raw_notes",
        "notes",
        "final_report",
        "grounding_manifest",
        "global_synthesis_status",
        "global_synthesis_issues",
        "v2_shadow_report",
    ):
        assert after[field] == before[field]
    assert first["research_run_input_cursor"] == 1
