import importlib

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from open_deep_research.domain_models import (
    EvidenceNeed,
    EvidenceRecord,
    MedicalResearchBrief,
    MedicalResearchTask,
    ResearchFinding,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
)

runtime = importlib.import_module("open_deep_research.deep_researcher")


def need() -> EvidenceNeed:
    return EvidenceNeed(
        evidence_types=["treatment effectiveness"],
        coverage_dimensions=["benefits", "harms"],
    )


def task_args(question: str) -> dict:
    return {
        "research_question": question,
        "evidence_needs": [need().model_dump()],
        "source_preferences": ["primary clinical studies"],
        "priority": 1,
    }


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.structured_schema = None

    def with_structured_output(self, schema):
        self.structured_schema = schema
        return self

    def with_retry(self, **_kwargs):
        return self

    def bind_tools(self, _tools):
        return self

    def with_config(self, *_args, **_kwargs):
        return self

    async def ainvoke(self, _messages):
        return self.response


class FailingModel(FakeModel):
    async def ainvoke(self, _messages):
        raise RuntimeError("model unavailable")


class LocalTool:
    def __init__(self, name: str):
        self.name = name

    async def ainvoke(self, _args, _config):
        return f"{self.name} completed"


async def local_researcher_tools(_config):
    return [LocalTool("think_tool"), LocalTool("ResearchComplete")]


def successful_result(task: MedicalResearchTask) -> ResearchTaskResult:
    return ResearchTaskResult(
        task_id=task.task_id,
        status=ResearchTaskStatus.SUCCESS,
        findings=[],
        evidence_ids=[],
        source_ids=[],
        summary=f"Completed {task.research_question}",
        limitations=[],
        conflicts=[],
    )


def test_host_materializes_stable_task_ids_and_deterministic_legacy_text() -> None:
    call = {"name": "ConductResearch", "id": "call-123", "args": task_args("Q")}
    first, call_id = runtime.materialize_medical_research_task(call, 2, 1)
    second, _ = runtime.materialize_medical_research_task(call, 2, 1)
    fallback, fallback_call_id = runtime.materialize_medical_research_task(
        {"name": "ConductResearch", "args": task_args("Fallback")}, 2, 3
    )

    assert first.task_id == second.task_id == "task:call-123"
    assert call_id == "call-123"
    assert fallback.task_id == "task:iteration:2:call:3"
    assert fallback_call_id == "iteration:2:call:3"
    assert runtime.render_medical_research_task(first) == runtime.render_medical_research_task(
        second
    )


def test_distinct_tool_call_ids_have_distinct_injective_task_ids() -> None:
    first, first_call_id = runtime.materialize_medical_research_task(
        {"name": "ConductResearch", "id": "call a", "args": task_args("Q")},
        1,
        1,
    )
    second, second_call_id = runtime.materialize_medical_research_task(
        {"name": "ConductResearch", "id": "call-a", "args": task_args("Q")},
        1,
        2,
    )

    assert first_call_id == "call a"
    assert second_call_id == "call-a"
    assert first.task_id == "task:call%20a"
    assert second.task_id == "task:call-a"
    assert first.task_id != second.task_id


@pytest.mark.asyncio
async def test_write_research_brief_dual_writes_one_structured_source(
    monkeypatch,
) -> None:
    brief = MedicalResearchBrief(
        normalized_question="Compare treatment A and treatment B in adults.",
        question_type="treatment comparison",
        clinical_elements={"population": "adults"},
        constraints=["English-language output"],
        research_intent="Compare benefits and harms.",
        evidence_needs=[need()],
    )
    fake_model = FakeModel(brief)
    monkeypatch.setattr(runtime, "configurable_model", fake_model)

    command = await runtime.write_research_brief(
        {"messages": [HumanMessage(content="Compare A and B")]}, {}
    )

    assert command.update["medical_research_brief"] == brief
    assert command.update["research_brief"] == runtime.render_medical_research_brief(brief)
    legacy_messages = command.update["supervisor_messages"]["value"]
    assert legacy_messages[-1].content == command.update["research_brief"]
    assert fake_model.structured_schema is MedicalResearchBrief


@pytest.mark.asyncio
async def test_supervisor_tools_preserves_success_and_isolates_child_failure(
    monkeypatch,
) -> None:
    class FakeResearcherSubgraph:
        async def ainvoke(self, state, _config):
            task = state["task"]
            if "fails" in task.research_question:
                raise RuntimeError("provider unavailable")
            result = successful_result(task)
            return {
                "research_task_result": result,
                "compressed_research": result.summary,
                "raw_notes": ["legacy raw note"],
            }

    monkeypatch.setattr(runtime, "researcher_subgraph", FakeResearcherSubgraph())
    message = AIMessage(
        content="",
        tool_calls=[
            {"name": "ConductResearch", "id": "call-1", "args": task_args("works")},
            {"name": "ConductResearch", "id": "call-2", "args": task_args("fails")},
        ],
    )
    command = await runtime.supervisor_tools(
        {
            "supervisor_messages": [message],
            "research_iterations": 1,
            "research_brief": "legacy brief",
            "research_results": [],
        },
        {"configurable": {"max_concurrent_research_units": 2}},
    )

    results = command.update["research_results"]
    assert [item.status for item in results] == [
        ResearchTaskStatus.SUCCESS,
        ResearchTaskStatus.FAILED,
    ]
    assert results[1].error.startswith("execution_failure:")
    assert command.update["raw_notes"] == ["legacy raw note"]
    assert all(
        isinstance(message, ToolMessage)
        for message in command.update["supervisor_messages"]
    )
    assert [
        message.tool_call_id for message in command.update["supervisor_messages"]
    ] == ["call-1", "call-2"]


@pytest.mark.asyncio
async def test_supervisor_tools_materializes_overflow_as_failed_result(
    monkeypatch,
) -> None:
    class FakeResearcherSubgraph:
        async def ainvoke(self, state, _config):
            result = successful_result(state["task"])
            return {
                "research_task_result": result,
                "compressed_research": result.summary,
                "raw_notes": [],
            }

    monkeypatch.setattr(runtime, "researcher_subgraph", FakeResearcherSubgraph())
    message = AIMessage(
        content="",
        tool_calls=[
            {"name": "ConductResearch", "id": "call-1", "args": task_args("one")},
            {"name": "ConductResearch", "id": "call-2", "args": task_args("two")},
        ],
    )
    command = await runtime.supervisor_tools(
        {
            "supervisor_messages": [message],
            "research_iterations": 1,
            "research_brief": "legacy brief",
            "research_results": [],
        },
        {"configurable": {"max_concurrent_research_units": 1}},
    )

    assert len(command.update["research_results"]) == 2
    assert command.update["research_results"][1].status is ResearchTaskStatus.FAILED
    assert command.update["research_results"][1].error.startswith("admission_failure:")


@pytest.mark.asyncio
async def test_supervisor_can_finish_without_materializing_a_task() -> None:
    command = await runtime.supervisor_tools(
        {
            "supervisor_messages": [AIMessage(content="Research is sufficient")],
            "research_iterations": 1,
            "research_brief": "legacy brief",
            "research_results": [],
        },
        {},
    )

    assert command.goto == "__end__"
    assert "research_results" not in command.update


@pytest.mark.asyncio
async def test_compression_returns_partial_shadow_result_and_legacy_output(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime, "configurable_model", FakeModel(AIMessage(content="Summary")))
    task = MedicalResearchTask(
        task_id="task:call-1",
        research_question="Question",
        evidence_needs=[need()],
        source_preferences=[],
        priority=0,
    )
    output = await runtime.compress_research(
        {
            "task": task,
            "researcher_messages": [AIMessage(content="Research notes")],
            "research_task_status": ResearchTaskStatus.PARTIAL,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
        },
        {},
    )

    assert output["compressed_research"] == "Summary"
    assert output["raw_notes"]
    assert output["research_task_result"].status is ResearchTaskStatus.PARTIAL
    assert output["research_task_result"].findings == []
    assert "tool-call budget" in output["research_task_result"].limitations[0]


@pytest.mark.asyncio
async def test_compression_failure_preserves_structured_artifacts_and_legacy_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime, "configurable_model", FailingModel(None))
    task = MedicalResearchTask(
        task_id="task:call-1",
        research_question="Question",
        evidence_needs=[need()],
        source_preferences=[],
        priority=0,
    )
    source = SourceRecord(
        source_id="source:1",
        artifact_ref=None,
        metadata={"provider": "test"},
    )
    evidence = EvidenceRecord(
        evidence_id="evidence:1",
        source_id=source.source_id,
        locator="section 1",
        excerpt="Source-derived passage.",
        hash="sha256:abc123",
    )
    finding = ResearchFinding(
        finding_id="finding:1",
        task_id=task.task_id,
        text="A materialized finding.",
        evidence_ids=[evidence.evidence_id],
        limitations=["Compression was unavailable."],
        conflicts=[],
    )
    output = await runtime.compress_research(
        {
            "task": task,
            "researcher_messages": [AIMessage(content="Research notes")],
            "research_task_status": ResearchTaskStatus.SUCCESS,
            "source_records": [source],
            "evidence_records": [evidence],
            "findings": [finding],
        },
        {},
    )

    result = output["research_task_result"]
    assert result.status is ResearchTaskStatus.FAILED
    assert result.error.startswith("compression_failure:")
    assert result.source_ids == [source.source_id]
    assert result.evidence_ids == [evidence.evidence_id]
    assert result.findings == [finding]
    assert result.limitations == finding.limitations
    assert output["compressed_research"].startswith("Error synthesizing")


@pytest.mark.asyncio
async def test_no_tool_calls_maps_to_success_termination() -> None:
    command = await runtime.researcher_tools(
        {
            "researcher_messages": [AIMessage(content="Done")],
            "tool_call_iterations": 1,
        },
        {},
    )

    assert command.goto == "compress_research"
    assert command.update["research_task_status"] is ResearchTaskStatus.SUCCESS


@pytest.mark.asyncio
async def test_tool_budget_boundary_maps_to_partial_termination(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "get_all_tools", local_researcher_tools)
    command = await runtime.researcher_tools(
        {
            "researcher_messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "think_tool",
                            "id": "think-1",
                            "args": {"reflection": "Review progress"},
                        }
                    ],
                )
            ],
            "tool_call_iterations": 1,
        },
        {"configurable": {"search_api": "none", "max_react_tool_calls": 1}},
    )

    assert command.goto == "compress_research"
    assert command.update["research_task_status"] is ResearchTaskStatus.PARTIAL


@pytest.mark.asyncio
async def test_explicit_research_complete_precedes_budget_boundary(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "get_all_tools", local_researcher_tools)
    command = await runtime.researcher_tools(
        {
            "researcher_messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "ResearchComplete",
                            "id": "complete-1",
                            "args": {},
                        }
                    ],
                )
            ],
            "tool_call_iterations": 1,
        },
        {"configurable": {"search_api": "none", "max_react_tool_calls": 1}},
    )

    assert command.goto == "compress_research"
    assert command.update["research_task_status"] is ResearchTaskStatus.SUCCESS


@pytest.mark.asyncio
async def test_tool_execution_error_downgrades_shadow_result_to_partial(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime, "configurable_model", FakeModel(AIMessage(content="Summary")))
    task = MedicalResearchTask(
        task_id="task:call-1",
        research_question="Question",
        evidence_needs=[need()],
        source_preferences=[],
        priority=0,
    )
    output = await runtime.compress_research(
        {
            "task": task,
            "researcher_messages": [
                ToolMessage(
                    content="Error executing tool: provider unavailable",
                    tool_call_id="search-1",
                )
            ],
            "research_task_status": ResearchTaskStatus.SUCCESS,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
        },
        {},
    )

    result = output["research_task_result"]
    assert result.status is ResearchTaskStatus.PARTIAL
    assert "research tool failed" in result.limitations[0]


@pytest.mark.asyncio
async def test_compiled_researcher_crosses_task_result_boundary(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "configurable_model", FakeModel(AIMessage(content="Summary")))
    task = MedicalResearchTask(
        task_id="task:compiled-1",
        research_question="Question",
        evidence_needs=[need()],
        source_preferences=[],
        priority=0,
    )
    research_topic = runtime.render_medical_research_task(task)

    output = await runtime.researcher_subgraph.ainvoke(
        {
            "task": task,
            "researcher_messages": [HumanMessage(content=research_topic)],
            "research_topic": research_topic,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
        },
        {"configurable": {"search_api": "none"}},
    )

    result = ResearchTaskResult.model_validate(output["research_task_result"])
    assert result.task_id == task.task_id
    assert result.status is ResearchTaskStatus.SUCCESS
    assert output["compressed_research"] == result.summary
    assert "researcher_messages" not in output
