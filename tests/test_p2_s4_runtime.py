"""Deterministic integration coverage for the complete P2-S4 runtime path."""

import importlib

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from open_deep_research.artifact_store import (
    LocalFileArtifactStore,
    artifact_store_from_config,
)
from open_deep_research.domain_models import (
    EvidenceNeed,
    MedicalResearchTask,
    ResearchTaskResult,
    ResearchTaskStatus,
    measure_result_provenance_chars,
)
from open_deep_research.evidence_ingestion import WebpageSelection, parse_locator
from open_deep_research.state import (
    ResearcherOutputState,
    ResearchExecutionSeverity,
    ResearchExecutionStage,
    make_research_execution_issue,
    research_results_reducer,
)
from open_deep_research.utils import (
    SearchExecutionResult,
    execute_tavily_search_structured,
)

runtime = importlib.import_module("open_deep_research.deep_researcher")


class SelectingModel:
    """Choose one deterministic Candidate without authoring Evidence fields."""

    async def ainvoke(self, _messages):
        """Return model-owned summary and an existing Candidate identity."""
        return WebpageSelection(
            summary="The guideline reports a conditional benefit-harm recommendation.",
            selected_chunk_ids=["C001"],
        )


class CompressionModel:
    """Return one fixed Finding draft tied to the supplied Evidence identity."""

    def __init__(self, evidence_id: str) -> None:
        self.evidence_id = evidence_id
        self.structured_schema = None
        self.messages = []
        self.bound_configs = []

    def with_structured_output(self, schema):
        self.structured_schema = schema
        return self

    def with_retry(self, **_kwargs):
        return self

    def with_config(self, config):
        self.bound_configs.append(config)
        return self

    async def ainvoke(self, messages):
        """Capture the bounded input and return model-owned finding semantics."""
        self.messages = messages
        return runtime.ResearchCompression(
            summary="Treatment may reduce recurrence; harms remain uncertain.",
            findings=[
                runtime.FindingDraft(
                    text="The reviewed recommendation supports individualized treatment.",
                    evidence_ids=[self.evidence_id],
                    limitations=["Applicability to very old adults is uncertain."],
                    conflicts=[],
                )
            ],
            limitations=[],
            conflicts=[],
        )


class EmptyCompressionModel(CompressionModel):
    """Produce a valid compression batch without Findings."""

    def __init__(self) -> None:
        super().__init__("")

    async def ainvoke(self, messages):
        """Capture context and return a minimal successful semantic layer."""
        self.messages = messages
        return runtime.ResearchCompression(
            summary="The task completed with bounded execution limitations.",
            findings=[],
            limitations=[],
            conflicts=[],
        )


class SupervisorSequenceModel:
    """Drive two Supervisor delegations followed by explicit completion."""

    def __init__(self) -> None:
        self.responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "ConductResearch",
                        "id": "run-scope-call-1",
                        "args": {
                            "research_question": "First artifact task",
                            "evidence_needs": [
                                {
                                    "evidence_types": ["clinical evidence"],
                                    "study_types": [],
                                    "source_policy": [],
                                    "date_constraints": [],
                                    "coverage_dimensions": [],
                                }
                            ],
                            "source_preferences": [],
                            "priority": 1,
                        },
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "ConductResearch",
                        "id": "run-scope-call-2",
                        "args": {
                            "research_question": "Resolve earlier artifact",
                            "evidence_needs": [
                                {
                                    "evidence_types": ["clinical evidence"],
                                    "study_types": [],
                                    "source_policy": [],
                                    "date_constraints": [],
                                    "coverage_dimensions": [],
                                }
                            ],
                            "source_preferences": [],
                            "priority": 1,
                        },
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "ResearchComplete", "id": "complete", "args": {}}
                ],
            ),
        ]

    def bind_tools(self, _tools):
        return self

    def with_retry(self, **_kwargs):
        return self

    def with_config(self, _config):
        return self

    async def ainvoke(self, _messages):
        return self.responses.pop(0)


class NamedTool:
    """Provide the minimum generic tool interface used by researcher_tools."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def ainvoke(self, _args, _config):
        """Return a bounded non-search observation."""
        return "Reflection recorded: continue checking uncertainty."


class SequentialRuntimeModel(CompressionModel):
    """Drive Researcher tool use, completion, and compression in graph order."""

    def __init__(self, evidence_id: str) -> None:
        super().__init__(evidence_id)
        self.responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "tavily_search",
                        "id": "compiled-search-1",
                        "args": {"queries": ["treatment guideline benefits harms"]},
                    }
                ],
            ),
            AIMessage(content="Research is complete."),
        ]

    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        """Return Researcher messages first, then structured compression."""
        if self.responses:
            return self.responses.pop(0)
        return await super().ainvoke(messages)


def task() -> MedicalResearchTask:
    """Build one deterministic medical research delegation."""
    return MedicalResearchTask(
        task_id="task:s4-integration",
        research_question="What are the benefits and harms of treatment?",
        evidence_needs=[
            EvidenceNeed(
                evidence_types=["clinical effectiveness"],
                coverage_dimensions=["benefits", "harms"],
            )
        ],
        source_preferences=["clinical guidelines"],
        priority=1,
    )


def provider_fixture() -> dict:
    """Return a fixed Tavily-like response with usable source content."""
    return {
        "query": "treatment guideline benefits harms",
        "results": [
            {
                "title": "Treatment guideline",
                "url": "https://example.test/treatment-guideline",
                "content": "Provider snippet must remain non-authoritative.",
                "raw_content": (
                    "Guideline recommendation\n\n"
                    "Adults should discuss treatment benefits and harms with a clinician. "
                    "The recommendation is conditional and should be individualized.\n\n"
                    "The evidence review found fewer recurrent events, while uncertainty "
                    "remained for serious adverse events and adults older than eighty."
                ),
            }
        ],
    }


@pytest.mark.asyncio
async def test_default_artifact_namespace_survives_supervisor_iterations(
    monkeypatch,
    tmp_path,
) -> None:
    """Keep one default namespace across nodes/children and isolate owning runs."""
    namespace_ids: list[str] = []
    refs_by_namespace: dict[str, str] = {}

    async def artifact_child(task, config, artifact_run_id):
        namespace_ids.append(artifact_run_id)
        store = artifact_store_from_config(config, artifact_run_id)
        if task.research_question == "First artifact task":
            refs_by_namespace[artifact_run_id] = store.put_text(
                "Stable normalized artifact across Supervisor iterations."
            )
        else:
            assert (
                store.get_text(refs_by_namespace[artifact_run_id])
                == "Stable normalized artifact across Supervisor iterations."
            )
        result = ResearchTaskResult(
            task_id=task.task_id,
            status=ResearchTaskStatus.SUCCESS,
            findings=[],
            evidence_ids=[],
            source_ids=[],
            summary="Child completed.",
            limitations=[],
            conflicts=[],
        )
        return {
            "research_task_result": result,
            "compressed_research": result.summary,
            "raw_notes": [],
        }

    monkeypatch.setattr(runtime, "_invoke_research_task", artifact_child)

    async def run_once(explicit_run_id=None):
        monkeypatch.setattr(runtime, "configurable_model", SupervisorSequenceModel())
        configurable = {
            "artifact_store_root": str(tmp_path),
            "thread_id": "reused-conversation-thread",
            "search_api": "none",
        }
        if explicit_run_id is not None:
            configurable["artifact_run_id"] = explicit_run_id
        output = await runtime.supervisor_subgraph.ainvoke(
            {
                "supervisor_messages": [HumanMessage(content="Research the question")],
                "research_results": [],
                "research_iterations": 0,
            },
            {"configurable": configurable},
        )
        return output["artifact_run_id"]

    first_default = await run_once()
    second_default = await run_once()
    first_explicit = await run_once("explicit-shared-run")
    second_explicit = await run_once("explicit-shared-run")

    assert namespace_ids[0:2] == [first_default, first_default]
    assert namespace_ids[2:4] == [second_default, second_default]
    assert first_default != second_default
    assert first_explicit == second_explicit == "explicit-shared-run"
    assert namespace_ids[4:8] == ["explicit-shared-run"] * 4

    new_root = await runtime.clarify_with_user(
        {
            "messages": [HumanMessage(content="Start another research run")],
            "artifact_run_id": "earlier-completed-run",
        },
        {"configurable": {"allow_clarification": False}},
    )
    assert new_root.update["artifact_run_id"] != "earlier-completed-run"


@pytest.mark.asyncio
async def test_deterministic_complete_s4_path_crosses_both_agent_boundaries(
    monkeypatch,
    tmp_path,
) -> None:
    """Prove the frozen search-to-Supervisor provenance chain without network or LLM."""
    run_config = {
        "configurable": {
            "artifact_store_root": str(tmp_path),
            "artifact_run_id": "integration-run",
            "search_api": "tavily",
            "max_search_tool_message_chars": 8_000,
            "max_supervisor_result_projection_chars": 4_000,
            "model_enable_thinking": False,
            "compression_model_enable_thinking": True,
        }
    }
    store = LocalFileArtifactStore(tmp_path, "integration-run")
    search_result = await execute_tavily_search_structured(
        ["treatment guideline benefits harms"],
        config=run_config,
        research_topic=runtime.render_medical_research_task(task()),
        provider_responses=[provider_fixture()],
        selection_model=SelectingModel(),
        artifact_store=store,
    )

    async def fixed_search(**_kwargs):
        """Return the already materialized structured search fixture."""
        return search_result

    async def fixed_tools(_config):
        """Expose Tavily plus one unaffected generic tool path."""
        return [NamedTool("tavily_search"), NamedTool("think_tool")]

    monkeypatch.setattr(runtime, "execute_tavily_search_structured", fixed_search)
    monkeypatch.setattr(runtime, "get_all_tools", fixed_tools)
    tool_command = await runtime.researcher_tools(
        {
            "task": task(),
            "research_topic": runtime.render_medical_research_task(task()),
            "researcher_messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "tavily_search",
                            "id": "search-1",
                            "args": {"queries": ["treatment guideline benefits harms"]},
                        },
                        {
                            "name": "think_tool",
                            "id": "think-1",
                            "args": {"reflection": "check uncertainty"},
                        },
                    ],
                )
            ],
            "tool_call_iterations": 1,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
        },
        run_config,
    )

    assert tool_command.goto == "researcher"
    assert tool_command.update["source_records"] == search_result.sources
    assert tool_command.update["evidence_records"] == search_result.evidences
    tool_messages = tool_command.update["researcher_messages"]
    assert [message.tool_call_id for message in tool_messages] == ["search-1", "think-1"]
    assert all(isinstance(message, ToolMessage) for message in tool_messages)
    assert search_result.evidences[0].evidence_id in tool_messages[0].content
    assert "Provider snippet must remain non-authoritative" not in tool_messages[0].content

    compression_model = CompressionModel(search_result.evidences[0].evidence_id)
    monkeypatch.setattr(runtime, "configurable_model", compression_model)
    compressed = await runtime.compress_research(
        {
            "task": task(),
            "research_topic": runtime.render_medical_research_task(task()),
            "researcher_messages": tool_messages,
            "research_task_status": ResearchTaskStatus.SUCCESS,
            "source_records": tool_command.update["source_records"],
            "evidence_records": tool_command.update["evidence_records"],
            "findings": [],
        },
        run_config,
    )
    boundary = ResearcherOutputState.model_validate(compressed)
    result = boundary.research_task_result
    parent_results = research_results_reducer([], [result])
    supervisor_projection = runtime.render_supervisor_result_projection(
        parent_results[0], max_chars=4_000
    )

    assert compression_model.structured_schema is runtime.ResearchCompression
    assert compression_model.bound_configs[-1]["configurable"]["extra_body"] == {
        "enable_thinking": True
    }
    compression_context = "\n".join(str(message.content) for message in compression_model.messages)
    assert search_result.evidences[0].evidence_id in compression_context
    assert search_result.evidences[0].excerpt in compression_context
    assert result.source_records == search_result.sources
    assert result.evidence_records == search_result.evidences
    assert result.source_ids == [record.source_id for record in result.source_records]
    assert result.evidence_ids == [record.evidence_id for record in result.evidence_records]
    assert result.findings[0].evidence_ids == result.evidence_ids
    assert parent_results == [result]
    assert "source_records" not in supervisor_projection
    assert "evidence_records" not in supervisor_projection
    assert result.evidence_records[0].excerpt not in supervisor_projection
    assert result.findings[0].text in supervisor_projection

    source = result.source_records[0]
    evidence = result.evidence_records[0]
    artifact = store.get_text(source.artifact_ref)
    start, end = parse_locator(evidence.locator)
    assert artifact[start:end] == evidence.excerpt


@pytest.mark.asyncio
async def test_structured_issue_degrades_status_when_tool_message_omits_warning(
    monkeypatch,
) -> None:
    """Keep Host status independent from bounded model-facing warning text."""
    provider_issue = make_research_execution_issue(
        stage=ResearchExecutionStage.PROVIDER,
        code="provider_query_failed",
        severity=ResearchExecutionSeverity.ERROR,
        message="A provider query failed and is intentionally absent from model context.",
        tool_call_id="bounded-warning-search",
        degrades_task_status=True,
        occurrence_key="query:1",
    )
    search_result = SearchExecutionResult(
        model_content="[Additional search observations omitted at configured bound.]",
        sources=[],
        evidences=[],
        issues=[provider_issue],
        tool_call_id="bounded-warning-search",
    )

    async def fixed_search(**_kwargs):
        return search_result

    async def fixed_tools(_config):
        return [NamedTool("tavily_search")]

    monkeypatch.setattr(runtime, "execute_tavily_search_structured", fixed_search)
    monkeypatch.setattr(runtime, "get_all_tools", fixed_tools)
    command = await runtime.researcher_tools(
        {
            "task": task(),
            "research_topic": runtime.render_medical_research_task(task()),
            "researcher_messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "tavily_search",
                            "id": "bounded-warning-search",
                            "args": {"queries": ["provider failure"]},
                        }
                    ],
                )
            ],
            "tool_call_iterations": 1,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
            "execution_issues": [],
            "execution_failure_observed": False,
        },
        {"configurable": {"search_api": "tavily"}},
    )

    tool_content = command.update["researcher_messages"][0].content
    assert provider_issue.message not in tool_content
    assert command.update["execution_issues"] == [provider_issue]
    assert command.update["execution_failure_observed"] is True

    monkeypatch.setattr(runtime, "configurable_model", EmptyCompressionModel())
    compressed = await runtime.compress_research(
        {
            "task": task(),
            "researcher_messages": command.update["researcher_messages"],
            "research_task_status": ResearchTaskStatus.SUCCESS,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
            "execution_issues": command.update["execution_issues"],
            "execution_failure_observed": command.update[
                "execution_failure_observed"
            ],
        },
        {},
    )

    assert compressed["research_task_result"].status is ResearchTaskStatus.PARTIAL


@pytest.mark.asyncio
async def test_provenance_payload_bound_participates_in_state_admission(
    monkeypatch,
    tmp_path,
) -> None:
    """Admit a deterministic publishable prefix and hide rejected Evidence."""
    fixture = provider_fixture()
    fixture["results"].append(
        {
            **fixture["results"][0],
            "title": "Second treatment guideline",
            "url": "https://example.test/second-treatment-guideline",
            "raw_content": (
                "Independent recommendation\n\n"
                "A second guideline reports another bounded clinical observation "
                "for deterministic provenance admission."
            ),
        }
    )
    artifact_run_id = "provenance-admission-run"
    base_config = {
        "configurable": {
            "artifact_store_root": str(tmp_path),
            "artifact_run_id": artifact_run_id,
            "search_api": "tavily",
        }
    }
    search_result = await execute_tavily_search_structured(
        ["two guidelines"],
        config=base_config,
        provider_responses=[fixture],
        selection_model=SelectingModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, artifact_run_id),
        tool_call_id="payload-bound-search",
    )
    assert len(search_result.sources) == len(search_result.evidences) == 2
    configured_bound = measure_result_provenance_chars(
        search_result.sources,
        [search_result.evidences[0]],
    )
    bounded_config = {
        "configurable": {
            **base_config["configurable"],
            "max_result_provenance_chars": configured_bound,
        }
    }

    async def fixed_search(**_kwargs):
        return search_result

    async def fixed_tools(_config):
        return [NamedTool("tavily_search")]

    monkeypatch.setattr(runtime, "execute_tavily_search_structured", fixed_search)
    monkeypatch.setattr(runtime, "get_all_tools", fixed_tools)
    command = await runtime.researcher_tools(
        {
            "task": task(),
            "artifact_run_id": artifact_run_id,
            "research_topic": runtime.render_medical_research_task(task()),
            "researcher_messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "tavily_search",
                            "id": "payload-bound-search",
                            "args": {"queries": ["two guidelines"]},
                        }
                    ],
                )
            ],
            "tool_call_iterations": 1,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
            "execution_issues": [],
            "execution_failure_observed": False,
        },
        bounded_config,
    )

    assert command.update["source_records"] == search_result.sources
    assert command.update["evidence_records"] == [search_result.evidences[0]]
    assert any(
        issue.code == "provenance_payload_bound"
        for issue in command.update["execution_issues"]
    )
    tool_content = command.update["researcher_messages"][0].content
    assert search_result.evidences[0].evidence_id in tool_content
    assert search_result.evidences[1].evidence_id not in tool_content
    assert search_result.evidences[1].excerpt not in tool_content

    result = runtime._build_and_publish_research_result(
        task=task(),
        config=bounded_config,
        artifact_run_id=artifact_run_id,
        status=ResearchTaskStatus.PARTIAL,
        source_records=command.update["source_records"],
        evidence_records=command.update["evidence_records"],
        findings=[],
        summary="A bounded deterministic subset was admitted.",
        limitations=["One Evidence record reached configured capacity."],
        conflicts=[],
        error=None,
    )
    assert (
        measure_result_provenance_chars(
            result.source_records,
            result.evidence_records,
        )
        <= configured_bound
    )


@pytest.mark.asyncio
async def test_compression_rejects_unknown_evidence_id_host_side(
    monkeypatch,
    tmp_path,
) -> None:
    """Reject an invalid Finding batch without erasing valid Source/Evidence."""
    run_config = {
        "configurable": {
            "artifact_store_root": str(tmp_path),
            "artifact_run_id": "compression-preservation-run",
        }
    }
    search_result = await execute_tavily_search_structured(
        ["treatment guideline benefits harms"],
        config=run_config,
        provider_responses=[provider_fixture()],
        selection_model=SelectingModel(),
        artifact_store=LocalFileArtifactStore(
            tmp_path, "compression-preservation-run"
        ),
    )
    model = CompressionModel("evidence:invented")
    monkeypatch.setattr(runtime, "configurable_model", model)

    output = await runtime.compress_research(
        {
            "task": task(),
            "artifact_run_id": "compression-preservation-run",
            "researcher_messages": [AIMessage(content="Valid evidence was collected")],
            "research_task_status": ResearchTaskStatus.SUCCESS,
            "source_records": search_result.sources,
            "evidence_records": search_result.evidences,
            "findings": [],
        },
        run_config,
    )

    result = output["research_task_result"]
    assert result.status is ResearchTaskStatus.FAILED
    assert result.error == "finding_materialization_failure: maximum retries exceeded"
    assert result.source_records == search_result.sources
    assert result.evidence_records == search_result.evidences
    assert result.findings == []


@pytest.mark.asyncio
async def test_invalid_finding_batch_is_consumed_at_researcher_child_boundary(
    monkeypatch,
    tmp_path,
) -> None:
    """Return a gated FAILED child Result while retaining earlier provenance."""
    artifact_run_id = "child-finding-failure-run"
    run_config = {
        "configurable": {
            "artifact_store_root": str(tmp_path),
            "artifact_run_id": artifact_run_id,
            "search_api": "tavily",
        }
    }
    search_result = await execute_tavily_search_structured(
        ["treatment guideline benefits harms"],
        config=run_config,
        provider_responses=[provider_fixture()],
        selection_model=SelectingModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, artifact_run_id),
    )

    async def fixed_search(**_kwargs):
        return search_result

    async def fixed_tools(_config):
        return [NamedTool("tavily_search")]

    monkeypatch.setattr(runtime, "execute_tavily_search_structured", fixed_search)
    monkeypatch.setattr(runtime, "get_all_tools", fixed_tools)
    monkeypatch.setattr(
        runtime,
        "configurable_model",
        SequentialRuntimeModel("evidence:invented"),
    )

    output = await runtime._invoke_research_task(
        task(),
        run_config,
        artifact_run_id,
    )
    result = output["research_task_result"]

    assert result.status is ResearchTaskStatus.FAILED
    assert result.error == "finding_materialization_failure: maximum retries exceeded"
    assert result.source_records == search_result.sources
    assert result.evidence_records == search_result.evidences
    assert result.findings == []


@pytest.mark.asyncio
async def test_compiled_researcher_publishes_resolvable_self_contained_result(
    monkeypatch,
    tmp_path,
) -> None:
    """Keep every compact provenance target valid after local State is projected out."""
    run_config = {
        "configurable": {
            "artifact_store_root": str(tmp_path),
            "artifact_run_id": "compiled-boundary-run",
            "search_api": "tavily",
        }
    }
    store = LocalFileArtifactStore(tmp_path, "compiled-boundary-run")
    search_result = await execute_tavily_search_structured(
        ["treatment guideline benefits harms"],
        config=run_config,
        research_topic=runtime.render_medical_research_task(task()),
        provider_responses=[provider_fixture()],
        selection_model=SelectingModel(),
        artifact_store=store,
    )

    async def fixed_search(**_kwargs):
        return search_result

    async def fixed_tools(_config):
        return [NamedTool("tavily_search")]

    monkeypatch.setattr(runtime, "execute_tavily_search_structured", fixed_search)
    monkeypatch.setattr(runtime, "get_all_tools", fixed_tools)
    monkeypatch.setattr(
        runtime,
        "configurable_model",
        SequentialRuntimeModel(search_result.evidences[0].evidence_id),
    )
    research_topic = runtime.render_medical_research_task(task())
    output = await runtime.researcher_subgraph.ainvoke(
        {
            "task": task(),
            "researcher_messages": [AIMessage(content=research_topic)],
            "research_topic": research_topic,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
        },
        run_config,
    )

    result = output["research_task_result"]
    assert result.source_records == search_result.sources
    assert result.evidence_records == search_result.evidences
    assert result.findings[0].evidence_ids == result.evidence_ids
    assert "researcher_messages" not in output
    source = result.source_records[0]
    evidence = result.evidence_records[0]
    artifact = store.get_text(source.artifact_ref)
    start, end = parse_locator(evidence.locator)
    assert artifact[start:end] == evidence.excerpt


@pytest.mark.asyncio
async def test_state_bounds_remove_unretained_evidence_from_researcher_context(
    monkeypatch,
    tmp_path,
) -> None:
    """Keep bounded ToolMessage references aligned with admitted structured records."""
    fixture = provider_fixture()
    second = {
        **fixture["results"][0],
        "title": "Second treatment guideline",
        "url": "https://example.test/second-treatment-guideline",
        "raw_content": (
            "Second-source recommendation\n\n"
            "This independent guideline describes a distinct monitoring schedule "
            "and a separate follow-up interval for the bounded-state regression."
        ),
    }
    fixture["results"].append(second)
    run_config = {
        "configurable": {
            "artifact_store_root": str(tmp_path),
            "artifact_run_id": "state-bound-run",
            "search_api": "tavily",
            "max_sources_per_research_task": 1,
        }
    }
    search_result = await execute_tavily_search_structured(
        ["treatment guidelines"],
        config=run_config,
        research_topic=runtime.render_medical_research_task(task()),
        provider_responses=[fixture],
        selection_model=SelectingModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, "state-bound-run"),
    )

    async def fixed_search(**_kwargs):
        return search_result

    async def fixed_tools(_config):
        return [NamedTool("tavily_search")]

    monkeypatch.setattr(runtime, "execute_tavily_search_structured", fixed_search)
    monkeypatch.setattr(runtime, "get_all_tools", fixed_tools)
    command = await runtime.researcher_tools(
        {
            "task": task(),
            "research_topic": runtime.render_medical_research_task(task()),
            "researcher_messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "tavily_search",
                            "id": "bounded-search-1",
                            "args": {"queries": ["treatment guidelines"]},
                        }
                    ],
                )
            ],
            "tool_call_iterations": 1,
            "source_records": [],
            "evidence_records": [],
            "findings": [],
        },
        run_config,
    )

    assert command.update["source_records"] == [search_result.sources[0]]
    assert command.update["evidence_records"] == [search_result.evidences[0]]
    content = command.update["researcher_messages"][0].content
    assert search_result.evidences[0].evidence_id in content
    assert search_result.evidences[1].evidence_id not in content
    assert search_result.evidences[1].excerpt not in content
    assert "was omitted because its Source was not admitted" in content


def test_supervisor_projection_is_bounded_without_structured_ledger_dump() -> None:
    """Keep Data Plane retention independent from Supervisor model visibility."""
    result = runtime._build_and_publish_research_result(
        task=task(),
        config={},
        artifact_run_id=None,
        status=ResearchTaskStatus.SUCCESS,
        source_records=[],
        evidence_records=[],
        findings=[],
        summary="x" * 2_000,
        limitations=[],
        conflicts=[],
        error=None,
    )

    projection = runtime.render_supervisor_result_projection(result, max_chars=1_000)

    assert len(projection) <= 1_000
    assert projection.endswith("[Supervisor observation truncated at configured bound.]")
    assert "source_records" not in projection
    assert "evidence_records" not in projection
