"""Focused Parent graph integration tests for the P2-S5 shadow pipeline."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import open_deep_research.deep_researcher as runtime
from open_deep_research.domain_models import GroundingManifest
from open_deep_research.global_synthesis.types import GlobalSynthesisOutcome
from open_deep_research.state import GlobalSynthesisStatus, ResearchRunStatus


def _edges(graph) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in graph.get_graph().edges}


def test_parent_graph_adds_only_the_frozen_global_synthesis_node() -> None:
    assert _edges(runtime.deep_researcher) == {
        ("__start__", "clarify_with_user"),
        ("clarify_with_user", "__end__"),
        ("clarify_with_user", "write_research_brief"),
        ("write_research_brief", "research_supervisor"),
        ("research_supervisor", "global_synthesis"),
        ("global_synthesis", "final_report_generation"),
        ("final_report_generation", "__end__"),
    }


@pytest.mark.asyncio
async def test_parent_node_applies_one_bounded_update_without_erasing_v1_inputs(
    monkeypatch,
) -> None:
    manifest = GroundingManifest(claims=[], groundings=[], citations=[])

    async def fake_pipeline(**_kwargs):
        return GlobalSynthesisOutcome(
            manifest=manifest,
            shadow_report="shadow",
            status=GlobalSynthesisStatus.SUCCESS,
            issues=(),
            metrics=None,
        )

    monkeypatch.setattr(runtime, "run_global_synthesis", fake_pipeline)
    state = {
        "messages": [HumanMessage(content="question")],
        "research_results": [],
        "raw_notes": ["raw preserved"],
        "notes": ["note preserved"],
        "final_report": "v1 preserved",
        "global_synthesis_issues": [],
    }
    update = await runtime.global_synthesis(state, {})

    assert update == {
        "grounding_manifest": manifest,
        "global_synthesis_status": GlobalSynthesisStatus.SUCCESS,
        "global_synthesis_issues": [],
        "v2_shadow_report": "shadow",
    }
    assert state["raw_notes"] == ["raw preserved"]
    assert state["notes"] == ["note preserved"]
    assert state["final_report"] == "v1 preserved"


@pytest.mark.asyncio
async def test_unexpected_v2_failure_is_contained_and_v1_inputs_survive(
    monkeypatch,
    caplog,
) -> None:
    async def fail(**_kwargs):
        raise RuntimeError("SECRET_SYNTHESIS_PAYLOAD")

    monkeypatch.setattr(runtime, "run_global_synthesis", fail)
    caplog.set_level("ERROR", logger=runtime.__name__)
    state = {
        "messages": [HumanMessage(content="question")],
        "research_results": [],
        "raw_notes": ["raw preserved"],
        "notes": ["note preserved"],
        "global_synthesis_issues": [],
    }
    update = await runtime.global_synthesis(state, {})

    records = [
        record
        for record in caplog.records
        if record.getMessage() == "Global Synthesis boundary failed"
    ]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert records[0].exc_info[0] is RuntimeError
    assert update["global_synthesis_status"] is GlobalSynthesisStatus.FAILED
    assert "grounding_manifest" not in update
    issue = update["global_synthesis_issues"][0]
    assert issue.stage == "publication_gate"
    assert issue.code == "GLOBAL_SYNTHESIS_BOUNDARY_FAILURE"
    assert issue.message == "Global Synthesis boundary failed: RuntimeError."
    assert "SECRET_SYNTHESIS_PAYLOAD" not in issue.message
    assert state["raw_notes"] == ["raw preserved"]
    assert state["notes"] == ["note preserved"]


class _WriterModel:
    def __init__(self, *, error=None) -> None:
        self.error = error
        self.bound_configs = []

    def with_config(self, config):
        self.bound_configs.append(config)
        return self

    async def ainvoke(self, _request):
        if self.error:
            raise self.error
        return AIMessage(content="V1 report")


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [None, RuntimeError("provider failed")])
async def test_controlled_v1_terminal_paths_finalize_run(monkeypatch, error) -> None:
    writer_model = _WriterModel(error=error)
    monkeypatch.setattr(runtime, "configurable_model", writer_model)
    output = await runtime.final_report_generation(
        {
            "messages": [HumanMessage(content="question")],
            "research_brief": "brief",
            "notes": ["legacy note"],
        },
        {
            "configurable": {
                "model_enable_thinking": True,
                "final_report_model_enable_thinking": False,
            }
        },
    )

    assert output["research_run_status"] is ResearchRunStatus.FINALIZED
    assert isinstance(output["final_report"], str)
    assert writer_model.bound_configs[-1]["configurable"]["extra_body"] == {
        "enable_thinking": False
    }
