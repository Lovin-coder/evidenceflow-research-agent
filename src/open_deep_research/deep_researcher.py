"""Main LangGraph implementation for the Deep Research agent."""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
    get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, Overwrite
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from open_deep_research.artifact_store import (
    artifact_store_from_config,
    resolve_artifact_run_id,
)
from open_deep_research.configuration import (
    Configuration,
)
from open_deep_research.domain_models import (
    EVIDENCE_INSUFFICIENT_MARKER,
    MAX_RESULT_EVIDENCE_CHARS,
    MAX_RESULT_EVIDENCE_RECORDS,
    MAX_RESULT_PROVENANCE_SERIALIZED_CHARS,
    MAX_RESULT_SOURCE_RECORDS,
    EvidenceNeed,
    EvidenceRecord,
    GroundingManifest,
    MedicalResearchBrief,
    MedicalResearchTask,
    ResearchFinding,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
    measure_result_provenance_chars,
    validate_provenance_graph,
)
from open_deep_research.evidence_ingestion import (
    render_researcher_observation,
    validate_evidence_provenance,
    validate_source_artifact,
)
from open_deep_research.global_synthesis import run_global_synthesis
from open_deep_research.global_synthesis.pipeline import _contained_pipeline_failure
from open_deep_research.model_runtime import (
    build_configurable_model_runtime_config,
    resolve_model_enable_thinking,
)
from open_deep_research.prompts import (
    clarify_with_user_instructions,
    compress_research_simple_human_message,
    compress_research_system_prompt,
    final_report_generation_prompt,
    lead_researcher_prompt,
    research_system_prompt,
    transform_messages_into_research_topic_prompt,
)
from open_deep_research.state import (
    AgentInputState,
    AgentState,
    ClarifyWithUser,
    ConductResearch,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    ResearchExecutionIssue,
    ResearchExecutionSeverity,
    ResearchExecutionStage,
    ResearchRunStatus,
    SupervisorState,
    admit_research_execution_issues,
    make_research_execution_issue,
)
from open_deep_research.utils import (
    SearchExecutionResult,
    anthropic_websearch_called,
    execute_tavily_search_structured,
    get_all_tools,
    get_api_key_for_model,
    get_model_token_limit,
    get_notes_from_tool_calls,
    get_today_str,
    is_token_limit_exceeded,
    openai_websearch_called,
    remove_up_to_last_ai_message,
    think_tool,
)

logger = logging.getLogger(__name__)

# Initialize a configurable model that we will use throughout the agent
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key", "extra_body"),
)


class _ResearchRunLifecycleConflict(RuntimeError):
    """Reject an input occurrence that cannot enter the current Research Run."""


def _artifact_run_id_for_node(
    state_run_id: str | None,
    config: RunnableConfig,
    runtime: Runtime[Any] | None = None,
) -> str:
    """Resolve the state-carried namespace at a graph ownership boundary."""
    runtime_run_id = (
        runtime.execution_info.run_id
        if runtime is not None and runtime.execution_info is not None
        else None
    )
    return resolve_artifact_run_id(
        state_run_id,
        config,
        runtime_run_id=runtime_run_id,
    )


def _new_research_run_update(
    *,
    state: AgentState,
    current_human_count: int,
    config: RunnableConfig,
    runtime: Runtime[Any] | None,
) -> dict[str, Any]:
    """Build the atomic reset and admission update for one new Research Run."""
    prior_artifact_run_id = state.get("artifact_run_id")
    artifact_run_id = _artifact_run_id_for_node(None, config, runtime)
    if prior_artifact_run_id and artifact_run_id == prior_artifact_run_id:
        raise _ResearchRunLifecycleConflict(
            "A new Research Run requires a fresh Artifact namespace"
        )
    manifest_reset: GroundingManifest | None | Overwrite
    if "grounding_manifest" in state:
        manifest_reset = Overwrite(None)
    else:
        # A reducer channel with no prior value stores its first value directly;
        # wrapping that absent first value would persist the wrapper itself.
        manifest_reset = None
    return {
        "supervisor_messages": Overwrite([]),
        "medical_research_brief": None,
        "research_brief": None,
        "research_results": Overwrite([]),
        "raw_notes": Overwrite([]),
        "notes": Overwrite([]),
        "final_report": "",
        "grounding_manifest": manifest_reset,
        "global_synthesis_status": None,
        "global_synthesis_issues": Overwrite([]),
        "v2_shadow_report": None,
        "artifact_run_id": artifact_run_id,
        "research_run_status": ResearchRunStatus.ACTIVE,
        "research_run_input_cursor": current_human_count,
    }


def _bootstrap_or_resume_research_run(
    state: AgentState,
    config: RunnableConfig,
    runtime: Runtime[Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Admit at most one Human occurrence according to the frozen P01 lifecycle.

    The boolean result tells the entry node to end without any EvidenceFlow-owned
    update. All conflicts are detected before a reset, cursor advance, or provenance
    mutation is returned to LangGraph.
    """
    current_human_count = sum(
        isinstance(message, HumanMessage) for message in state.get("messages", [])
    )
    status = state.get("research_run_status")
    cursor = state.get("research_run_input_cursor")

    if status is None and cursor is None:
        if current_human_count != 1:
            raise _ResearchRunLifecycleConflict(
                "Initial Research Run admission requires exactly one HumanMessage"
            )
        return (
            _new_research_run_update(
                state=state,
                current_human_count=current_human_count,
                config=config,
                runtime=runtime,
            ),
            False,
        )

    if (
        not isinstance(status, ResearchRunStatus)
        or not isinstance(cursor, int)
        or isinstance(cursor, bool)
        or cursor < 0
        or not state.get("artifact_run_id")
    ):
        raise _ResearchRunLifecycleConflict(
            "Research Run lifecycle State is internally inconsistent"
        )

    fresh_delta = current_human_count - cursor
    if fresh_delta < 0 or fresh_delta > 1:
        raise _ResearchRunLifecycleConflict(
            "Research Run input occurrence count conflicts with the lifecycle cursor"
        )

    if status is ResearchRunStatus.ACTIVE:
        if fresh_delta != 0:
            raise _ResearchRunLifecycleConflict(
                "Mid-run HumanMessage steering is not supported"
            )
        return {}, False

    if status is ResearchRunStatus.AWAITING_CLARIFICATION:
        if fresh_delta == 0:
            return {}, True
        return {
            "research_run_status": ResearchRunStatus.ACTIVE,
            "research_run_input_cursor": current_human_count,
        }, False

    if status is ResearchRunStatus.FINALIZED:
        if fresh_delta == 0:
            return {}, True
        return (
            _new_research_run_update(
                state=state,
                current_human_count=current_human_count,
                config=config,
                runtime=runtime,
            ),
            False,
        )

    raise _ResearchRunLifecycleConflict("Unknown Research Run lifecycle status")


def _render_evidence_need(evidence_need: EvidenceNeed) -> list[str]:
    """Render one EvidenceNeed into deterministic legacy Markdown lines."""
    labels = (
        ("Evidence types", evidence_need.evidence_types),
        ("Study types", evidence_need.study_types),
        ("Source policy", evidence_need.source_policy),
        ("Date constraints", evidence_need.date_constraints),
        ("Coverage dimensions", evidence_need.coverage_dimensions),
    )
    return [f"  - {label}: {', '.join(values)}" for label, values in labels if values]


def render_medical_research_brief(brief: MedicalResearchBrief) -> str:
    """Render the canonical typed brief as deterministic legacy Markdown.

    Args:
        brief: Structured medical planning contract that remains the source of truth.

    Returns:
        Bounded Markdown for the existing Supervisor message interface.
    """
    lines = [
        "# Medical Research Brief",
        f"- Normalized question: {brief.normalized_question}",
        f"- Question type: {brief.question_type}",
        f"- Research intent: {brief.research_intent}",
    ]
    if brief.clinical_elements:
        lines.append("- Clinical elements:")
        for key in sorted(brief.clinical_elements):
            value = brief.clinical_elements[key]
            rendered_value = ", ".join(value) if isinstance(value, list) else value
            lines.append(f"  - {key}: {rendered_value}")
    lines.append(
        "- Constraints: " + (", ".join(brief.constraints) if brief.constraints else "None")
    )
    lines.append("- Evidence needs:")
    for index, evidence_need in enumerate(brief.evidence_needs, start=1):
        lines.append(f"  {index}.")
        lines.extend(_render_evidence_need(evidence_need))
    return "\n".join(lines)


def render_medical_research_task(task: MedicalResearchTask) -> str:
    """Render a typed delegation as deterministic legacy Researcher input.

    Args:
        task: Host-materialized task contract passed across the subgraph boundary.

    Returns:
        Bounded Markdown for the existing ``research_topic`` compatibility path.
    """
    lines = [
        "# Medical Research Task",
        f"- Task ID: {task.task_id}",
        f"- Research question: {task.research_question}",
        f"- Priority: {task.priority}",
        "- Source preferences: "
        + (", ".join(task.source_preferences) if task.source_preferences else "None"),
        "- Evidence needs:",
    ]
    for index, evidence_need in enumerate(task.evidence_needs, start=1):
        lines.append(f"  {index}.")
        lines.extend(_render_evidence_need(evidence_need))
    return "\n".join(lines)


def _runtime_tool_call_id(
    tool_call: dict[str, Any], research_iteration: int, ordinal: int
) -> str:
    """Return the provider call ID or a deterministic run-local fallback."""
    tool_call_id = str(tool_call.get("id") or "")
    if tool_call_id.strip():
        return tool_call_id
    return f"iteration:{research_iteration}:call:{ordinal}"


def _encode_tool_call_id(value: str) -> str:
    """Encode a provider call ID into an injective task-identity component.

    Percent encoding retains a reversible distinction between provider IDs that a
    lossy character replacement would collapse, while the original ID remains
    unchanged for ToolMessage correlation.

    Args:
        value: Non-blank provider tool-call identity.

    Returns:
        Deterministic percent-encoded identity component.

    Raises:
        ValueError: If the provider identity is blank.
    """
    if not value.strip():
        raise ValueError("Tool call ID cannot produce an empty task identity")
    return quote(value, safe="")


def materialize_medical_research_task(
    tool_call: dict[str, Any], research_iteration: int, ordinal: int
) -> tuple[MedicalResearchTask, str]:
    """Validate one delegation envelope and materialize its domain task contract.

    Args:
        tool_call: LLM tool call containing task semantics but no domain identity.
        research_iteration: Supervisor iteration used by the missing-ID fallback.
        ordinal: One-based call position used by the missing-ID fallback.

    Returns:
        The host-identified MedicalResearchTask and its runtime correlation ID.

    Raises:
        ValidationError: If ConductResearch arguments violate the tool contract.
        ValueError: If a supplied provider call ID cannot form a task identity.
    """
    call_id = _runtime_tool_call_id(tool_call, research_iteration, ordinal)
    provider_call_id = str(tool_call.get("id") or "")
    task_identity = (
        _encode_tool_call_id(call_id) if provider_call_id.strip() else call_id
    )
    request = ConductResearch.model_validate(tool_call.get("args", {}))
    return (
        MedicalResearchTask(
            task_id=f"task:{task_identity}",
            **request.model_dump(),
        ),
        call_id,
    )


class FindingDraft(BaseModel):
    """Carry model-owned finding semantics without authoritative identities."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_evidence_ids(self) -> "FindingDraft":
        """Reject duplicate references before Host finding materialization."""
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("FindingDraft.evidence_ids must be unique")
        return self


class ResearchCompression(BaseModel):
    """Represent structured model semantics consumed by Host compression code."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    summary: str = Field(min_length=1)
    findings: list[FindingDraft] = Field(default_factory=list, max_length=40)
    limitations: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class ProvenancePublicationError(ValueError):
    """Reject a candidate Result whose self-contained provenance is inconsistent."""


class FindingMaterializationError(ValueError):
    """Reject an invalid model semantic batch while preserving valid provenance."""


@dataclass(frozen=True, slots=True)
class _FindingMaterializationOutcome:
    """Published Findings and limitations retained from omitted no-Evidence drafts."""

    findings: tuple[ResearchFinding, ...]
    limitations: tuple[str, ...]


def _materialize_findings(
    *,
    task: MedicalResearchTask,
    compression: ResearchCompression,
    evidence_records: list[EvidenceRecord],
) -> _FindingMaterializationOutcome:
    """Resolve model Evidence references and assign deterministic Finding identities."""
    known_evidence_ids = {record.evidence_id for record in evidence_records}
    findings: list[ResearchFinding] = []
    omitted_limitations: list[str] = []
    for ordinal, draft in enumerate(compression.findings, start=1):
        if not draft.evidence_ids:
            omitted_limitations.append(EVIDENCE_INSUFFICIENT_MARKER)
            omitted_limitations.extend(draft.limitations)
            continue
        unknown = set(draft.evidence_ids) - known_evidence_ids
        if unknown:
            raise FindingMaterializationError(
                "compression_reference_failure: unknown Evidence IDs: "
                f"{sorted(unknown)}"
            )
        identity_payload = json.dumps(
            {
                "version": "p2-s4-finding-v1",
                "task_id": task.task_id,
                "ordinal": ordinal,
                "text": draft.text,
                "evidence_ids": draft.evidence_ids,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        finding_digest = hashlib.sha256(identity_payload.encode("utf-8")).hexdigest()[:24]
        try:
            findings.append(
                ResearchFinding(
                    finding_id=f"finding:sha256:{finding_digest}",
                    task_id=task.task_id,
                    text=draft.text,
                    evidence_ids=draft.evidence_ids,
                    limitations=draft.limitations,
                    conflicts=draft.conflicts,
                )
            )
        except ValidationError as error:
            raise FindingMaterializationError(
                "compression_finding_validation_failure: invalid Finding draft"
            ) from error
    return _FindingMaterializationOutcome(
        findings=tuple(findings),
        limitations=tuple(dict.fromkeys(omitted_limitations)),
    )


def _render_compression_evidence(
    task: MedicalResearchTask, evidence_records: list[EvidenceRecord]
) -> str:
    """Render bounded authoritative Evidence IDs and exact excerpts for compression."""
    lines = [
        "Authoritative Evidence projection for this task:",
        f"Task ID: {task.task_id}",
        f"Research question: {task.research_question}",
    ]
    if not evidence_records:
        lines.append("No authoritative Evidence records were materialized.")
    for record in evidence_records:
        lines.extend(
            (
                "",
                f"[{record.evidence_id}] Source: {record.source_id}",
                record.excerpt,
            )
        )
    return "\n".join(lines)


def render_supervisor_result_projection(
    result: ResearchTaskResult, *, max_chars: int
) -> str:
    """Render a bounded Finding-oriented view without inline provenance ledgers."""
    lines = [
        f"Research task: {result.task_id}",
        f"Status: {result.status.value}",
        "Summary:",
        result.summary,
        "Findings:",
    ]
    if not result.findings:
        lines.append("No structured findings were published.")
    for finding in result.findings:
        lines.extend(
            (
                f"- [{finding.finding_id}] {finding.text}",
                "  Evidence IDs: "
                + (", ".join(finding.evidence_ids) or "none (evidence-insufficient)"),
            )
        )
        if finding.limitations:
            lines.append("  Limitations: " + "; ".join(finding.limitations))
        if finding.conflicts:
            lines.append("  Conflicts: " + "; ".join(finding.conflicts))
    if result.limitations:
        lines.extend(("Task limitations:", *[f"- {item}" for item in result.limitations]))
    if result.conflicts:
        lines.extend(("Task conflicts:", *[f"- {item}" for item in result.conflicts]))
    if result.error:
        lines.extend(("Execution error:", result.error))
    rendered = "\n".join(lines)
    if len(rendered) <= max_chars:
        return rendered
    marker = "\n[Supervisor observation truncated at configured bound.]"
    return rendered[: max_chars - len(marker)].rstrip() + marker


def _failed_research_result(
    task: MedicalResearchTask,
    error: str,
    *,
    source_records: list[SourceRecord] | None = None,
    evidence_records: list[EvidenceRecord] | None = None,
    findings: list[ResearchFinding] | None = None,
    config: RunnableConfig = None,
    artifact_run_id: str | None = None,
) -> ResearchTaskResult:
    """Create a failed result without discarding materialized research artifacts.

    Args:
        task: Materialized task whose execution or result construction failed.
        error: Stable operational error text exposed across the parent boundary.
        source_records: Sources materialized before the failure, if available.
        evidence_records: Evidence materialized before the failure, if available.
        findings: Findings materialized before the failure, if available.

    Returns:
        A FAILED ResearchTaskResult retaining all available valid Source, Evidence,
        and Finding references plus their limitations and conflicts.

    Raises:
        ProvenancePublicationError: If the supplied partial records cannot form a
            valid Researcher-local provenance graph.
    """
    preserved_sources = source_records or []
    preserved_evidence = evidence_records or []
    preserved_findings = findings or []
    return _build_and_publish_research_result(
        task=task,
        config=config,
        artifact_run_id=artifact_run_id,
        status=ResearchTaskStatus.FAILED,
        source_records=preserved_sources,
        evidence_records=preserved_evidence,
        findings=preserved_findings,
        summary=error,
        limitations=list(
            dict.fromkeys(
                limitation
                for finding in preserved_findings
                for limitation in finding.limitations
            )
        ),
        conflicts=list(
            dict.fromkeys(
                conflict
                for finding in preserved_findings
                for conflict in finding.conflicts
            )
        ),
        error=error,
    )


def _validate_research_result_for_publish(
    task: MedicalResearchTask,
    result: ResearchTaskResult,
    *,
    config: RunnableConfig = None,
    artifact_run_id: str | None = None,
) -> ResearchTaskResult:
    """Validate domain, artifact, and configured bounds before Result publication.

    Args:
        task: Delegated task that owns the candidate result.
        result: Candidate cross-subgraph result.
        config: Owning run ArtifactStore namespace and configured Result bounds.

    Returns:
        The unchanged result after its local provenance graph passes validation.

    Raises:
        ProvenancePublicationError: If any candidate reference is dangling or
            inconsistent at the Researcher-local publication boundary.
    """
    try:
        validate_provenance_graph(
            task=task,
            result=result,
        )
        configurable = Configuration.from_runnable_config(config)
        if len(result.source_records) > min(
            configurable.max_sources_per_research_task,
            MAX_RESULT_SOURCE_RECORDS,
        ):
            raise ValueError("Result exceeds the configured Source record bound")
        if len(result.evidence_records) > min(
            configurable.max_evidence_records_per_research_task,
            MAX_RESULT_EVIDENCE_RECORDS,
        ):
            raise ValueError("Result exceeds the configured Evidence record bound")
        if sum(len(record.excerpt) for record in result.evidence_records) > min(
            configurable.max_evidence_excerpt_chars_per_result,
            MAX_RESULT_EVIDENCE_CHARS,
        ):
            raise ValueError("Result exceeds the configured Evidence character bound")
        provenance_payload_size = measure_result_provenance_chars(
            result.source_records,
            result.evidence_records,
        )
        if provenance_payload_size > min(
            configurable.max_result_provenance_chars,
            MAX_RESULT_PROVENANCE_SERIALIZED_CHARS,
        ):
            raise ValueError("Result exceeds the configured provenance payload bound")

        if result.source_records:
            store = artifact_store_from_config(config, artifact_run_id)
            sources_by_id = {
                record.source_id: record for record in result.source_records
            }
            for source in result.source_records:
                validate_source_artifact(source, store)
            for evidence in result.evidence_records:
                validate_evidence_provenance(
                    evidence=evidence,
                    source=sources_by_id[evidence.source_id],
                    artifact_store=store,
                )
    except (ValueError, ValidationError) as error:
        raise ProvenancePublicationError(
            f"provenance_validation_failure: {error}"
        ) from error
    return result


def _build_and_publish_research_result(
    *,
    task: MedicalResearchTask,
    config: RunnableConfig,
    artifact_run_id: str | None,
    status: ResearchTaskStatus,
    source_records: list[SourceRecord],
    evidence_records: list[EvidenceRecord],
    findings: list[ResearchFinding],
    summary: str,
    limitations: list[str],
    conflicts: list[str],
    error: str | None,
) -> ResearchTaskResult:
    """Assemble the D15 carrier atomically and apply the Publication Gate."""
    try:
        result = ResearchTaskResult(
            task_id=task.task_id,
            status=status,
            source_records=source_records,
            evidence_records=evidence_records,
            findings=findings,
            source_ids=[record.source_id for record in source_records],
            evidence_ids=[record.evidence_id for record in evidence_records],
            summary=summary,
            limitations=limitations,
            conflicts=conflicts,
            error=error,
        )
    except ValidationError as validation_error:
        raise ProvenancePublicationError(
            f"provenance_validation_failure: {validation_error}"
        ) from validation_error
    return _validate_research_result_for_publish(
        task,
        result,
        config=config,
        artifact_run_id=artifact_run_id,
    )


async def _invoke_research_task(
    task: MedicalResearchTask,
    config: RunnableConfig,
    artifact_run_id: str,
) -> dict[str, Any]:
    """Adapt one typed task into a Researcher invocation and isolate child failure.

    Args:
        task: Stable Supervisor-to-Researcher task contract.
        config: Runtime configuration forwarded to the Researcher subgraph.

    Returns:
        Researcher output containing the typed result and legacy compatibility text.
        Child exceptions are converted into a task-correlated FAILED result.
    """
    research_topic = render_medical_research_task(task)
    try:
        observation = await researcher_subgraph.ainvoke(
            {
                "task": task,
                "artifact_run_id": artifact_run_id,
                "researcher_messages": [HumanMessage(content=research_topic)],
                "research_topic": research_topic,
                "source_records": [],
                "evidence_records": [],
                "findings": [],
                "execution_issues": [],
                "execution_failure_observed": False,
            },
            config,
        )
        result = ResearchTaskResult.model_validate(observation["research_task_result"])
        if result.task_id != task.task_id:
            raise ValueError("Researcher returned a result for a different task_id")
        await asyncio.to_thread(
            _validate_research_result_for_publish,
            task,
            result,
            config=config,
            artifact_run_id=artifact_run_id,
        )
        return observation
    except Exception as error:
        message = f"execution_failure: {type(error).__name__}"
        return {
            "research_task_result": _failed_research_result(
                task,
                message,
                config=config,
                artifact_run_id=artifact_run_id,
            ),
            "compressed_research": message,
            "raw_notes": [],
        }

async def clarify_with_user(
    state: AgentState,
    config: RunnableConfig,
    runtime: Runtime[Any] | None = None,
) -> Command[Literal["write_research_brief", "__end__"]]:
    """Analyze user messages and ask clarifying questions if the research scope is unclear.
    
    This function determines whether the user's request needs clarification before proceeding
    with research. If clarification is disabled or not needed, it proceeds directly to research.
    
    Args:
        state: Current agent state containing user messages
        config: Runtime configuration with model settings and preferences
        
    Returns:
        Command to either end with a clarifying question or proceed to research brief
    """
    lifecycle_update, should_end = _bootstrap_or_resume_research_run(
        state,
        config,
        runtime,
    )
    if should_end:
        return Command(goto=END)

    # Step 1: Check if clarification is enabled in configuration
    configurable = Configuration.from_runnable_config(config)
    artifact_run_id = lifecycle_update.get(
        "artifact_run_id",
        state.get("artifact_run_id"),
    )
    if not isinstance(artifact_run_id, str):
        raise _ResearchRunLifecycleConflict(
            "Admitted Research Run does not have an Artifact namespace"
        )
    if not configurable.allow_clarification:
        # Skip clarification step and proceed directly to research
        return Command(
            goto="write_research_brief",
            update={
                **lifecycle_update,
                "artifact_run_id": artifact_run_id,
                "research_run_status": ResearchRunStatus.ACTIVE,
            },
        )
    
    # Step 2: Prepare the model for structured clarification analysis
    messages = state["messages"]
    model_config = build_configurable_model_runtime_config(
        model=configurable.research_model,
        max_tokens=configurable.research_model_max_tokens,
        api_key=get_api_key_for_model(configurable.research_model, config),
        enable_thinking=resolve_model_enable_thinking(
            configurable.model_enable_thinking,
            configurable.research_model_enable_thinking,
        ),
    )
    
    # Configure model with structured output and retry logic
    clarification_model = (
        configurable_model
        .with_structured_output(ClarifyWithUser)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(model_config)
    )
    
    # Step 3: Analyze whether clarification is needed
    prompt_content = clarify_with_user_instructions.format(
        messages=get_buffer_string(messages), 
        date=get_today_str()
    )
    response = await clarification_model.ainvoke([HumanMessage(content=prompt_content)])
    
    # Step 4: Route based on clarification analysis
    if response.need_clarification:
        # End with clarifying question for user
        return Command(
            goto=END, 
            update={
                **lifecycle_update,
                "messages": [AIMessage(content=response.question)],
                "artifact_run_id": artifact_run_id,
                "research_run_status": ResearchRunStatus.AWAITING_CLARIFICATION,
            },
        )
    else:
        # Proceed to research with verification message
        return Command(
            goto="write_research_brief", 
            update={
                **lifecycle_update,
                "messages": [AIMessage(content=response.verification)],
                "artifact_run_id": artifact_run_id,
                "research_run_status": ResearchRunStatus.ACTIVE,
            },
        )


async def write_research_brief(state: AgentState, config: RunnableConfig) -> Command[Literal["research_supervisor"]]:
    """Transform user messages into a structured research brief and initialize supervisor.
    
    This function makes MedicalResearchBrief the canonical planning object and derives
    the legacy Markdown view used by the existing Supervisor message interface.
    
    Args:
        state: Current agent state containing user messages
        config: Runtime configuration with model settings
        
    Returns:
        Command to proceed to research supervisor with initialized context
    """
    # Step 1: Set up the research model for structured output
    configurable = Configuration.from_runnable_config(config)
    research_model_config = build_configurable_model_runtime_config(
        model=configurable.research_model,
        max_tokens=configurable.research_model_max_tokens,
        api_key=get_api_key_for_model(configurable.research_model, config),
        enable_thinking=resolve_model_enable_thinking(
            configurable.model_enable_thinking,
            configurable.research_model_enable_thinking,
        ),
    )
    
    # Configure model for structured medical research brief generation
    research_model = (
        configurable_model
        .with_structured_output(MedicalResearchBrief)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )
    
    # Step 2: Generate structured research brief from user messages
    prompt_content = transform_messages_into_research_topic_prompt.format(
        messages=get_buffer_string(state.get("messages", [])),
        date=get_today_str()
    )
    response = await research_model.ainvoke([HumanMessage(content=prompt_content)])
    medical_research_brief = MedicalResearchBrief.model_validate(response)
    # Structured data is authoritative; legacy text is a deterministic migration view.
    legacy_research_brief = render_medical_research_brief(medical_research_brief)
    
    # Step 3: Initialize supervisor with research brief and instructions
    supervisor_system_prompt = lead_researcher_prompt.format(
        date=get_today_str(),
        max_concurrent_research_units=configurable.max_concurrent_research_units,
        max_researcher_iterations=configurable.max_researcher_iterations
    )
    
    return Command(
        goto="research_supervisor", 
        update={
            "medical_research_brief": medical_research_brief,
            "research_brief": legacy_research_brief,
            "supervisor_messages": {
                "type": "override",
                "value": [
                    SystemMessage(content=supervisor_system_prompt),
                    HumanMessage(content=legacy_research_brief)
                ]
            }
        }
    )


async def supervisor(
    state: SupervisorState,
    config: RunnableConfig,
    runtime: Runtime[Any] | None = None,
) -> Command[Literal["supervisor_tools"]]:
    """Lead research supervisor that plans research strategy and delegates to researchers.
    
    The supervisor analyzes the research brief and decides how to break down the research
    into manageable tasks. It can use think_tool for strategic planning, ConductResearch
    to delegate tasks to sub-researchers, or ResearchComplete when satisfied with findings.
    
    Args:
        state: Current supervisor state with messages and research context
        config: Runtime configuration with model settings
        
    Returns:
        Command to proceed to supervisor_tools for tool execution
    """
    # Step 1: Configure the supervisor model with available tools
    configurable = Configuration.from_runnable_config(config)
    artifact_run_id = _artifact_run_id_for_node(
        state.get("artifact_run_id"), config, runtime
    )
    research_model_config = build_configurable_model_runtime_config(
        model=configurable.research_model,
        max_tokens=configurable.research_model_max_tokens,
        api_key=get_api_key_for_model(configurable.research_model, config),
        enable_thinking=resolve_model_enable_thinking(
            configurable.model_enable_thinking,
            configurable.research_model_enable_thinking,
        ),
    )
    
    # Available tools: research delegation, completion signaling, and strategic thinking
    lead_researcher_tools = [ConductResearch, ResearchComplete, think_tool]
    
    # Configure model with tools, retry logic, and model settings
    research_model = (
        configurable_model
        .bind_tools(lead_researcher_tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )
    
    # Step 2: Generate supervisor response based on current context
    supervisor_messages = state.get("supervisor_messages", [])
    response = await research_model.ainvoke(supervisor_messages)
    
    # Step 3: Update state and proceed to tool execution
    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "research_iterations": state.get("research_iterations", 0) + 1,
            "artifact_run_id": artifact_run_id,
        }
    )

async def supervisor_tools(
    state: SupervisorState,
    config: RunnableConfig,
    runtime: Runtime[Any] | None = None,
) -> Command[Literal["supervisor", "__end__"]]:
    """Execute tools called by the supervisor, including research delegation and strategic thinking.
    
    ConductResearch calls are validated and host-materialized here so the model owns
    task semantics while runtime code owns stable identity and failure isolation.

    This function handles three types of supervisor tool calls:
    1. think_tool - Strategic reflection that continues the conversation
    2. ConductResearch - Delegates research tasks to sub-researchers
    3. ResearchComplete - Signals completion of research phase
    
    Args:
        state: Current supervisor state with messages and iteration count
        config: Runtime configuration with research limits and model settings
        
    Returns:
        Command to either continue supervision loop or end research phase
    """
    # Step 1: Extract current state and check exit conditions
    configurable = Configuration.from_runnable_config(config)
    artifact_run_id = _artifact_run_id_for_node(
        state.get("artifact_run_id"), config, runtime
    )
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]
    
    # Define exit criteria for research phase
    exceeded_allowed_iterations = research_iterations > configurable.max_researcher_iterations
    no_tool_calls = not most_recent_message.tool_calls
    research_complete_tool_call = any(
        tool_call["name"] == "ResearchComplete" 
        for tool_call in most_recent_message.tool_calls
    )
    
    # Exit if any termination condition is met
    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        return Command(
            goto=END,
            update={
                "notes": get_notes_from_tool_calls(supervisor_messages),
                "research_brief": state.get("research_brief", ""),
                "artifact_run_id": artifact_run_id,
            }
        )
    
    # Step 2: Process all tool calls together (both think_tool and ConductResearch)
    all_tool_messages = []
    update_payload: dict[str, Any] = {
        "supervisor_messages": [],
        "artifact_run_id": artifact_run_id,
    }
    
    # Handle think_tool calls (strategic reflection)
    think_tool_calls = [
        tool_call for tool_call in most_recent_message.tool_calls 
        if tool_call["name"] == "think_tool"
    ]
    
    for tool_call in think_tool_calls:
        reflection_content = tool_call["args"]["reflection"]
        all_tool_messages.append(ToolMessage(
            content=f"Reflection recorded: {reflection_content}",
            name="think_tool",
            tool_call_id=tool_call["id"]
        ))
    
    # Handle ConductResearch calls (research delegation)
    conduct_research_calls = [
        tool_call for tool_call in most_recent_message.tool_calls 
        if tool_call["name"] == "ConductResearch"
    ]
    
    if conduct_research_calls:
        materialized_calls = []
        for ordinal, tool_call in enumerate(conduct_research_calls, start=1):
            runtime_call_id = _runtime_tool_call_id(
                tool_call, research_iterations, ordinal
            )
            try:
                task, runtime_call_id = materialize_medical_research_task(
                    tool_call, research_iterations, ordinal
                )
            except (ValidationError, ValueError) as error:
                all_tool_messages.append(
                    ToolMessage(
                        content=f"contract_validation_failure: {error}",
                        name="ConductResearch",
                        tool_call_id=runtime_call_id,
                    )
                )
                continue
            materialized_calls.append((tool_call, task, runtime_call_id))

        allowed_calls = materialized_calls[:configurable.max_concurrent_research_units]
        overflow_calls = materialized_calls[configurable.max_concurrent_research_units:]

        tool_results = await asyncio.gather(
            *[
                _invoke_research_task(task, config, artifact_run_id)
                for _, task, _ in allowed_calls
            ]
        )
        research_results = []

        for observation, (tool_call, task, runtime_call_id) in zip(
            tool_results, allowed_calls
        ):
            result = ResearchTaskResult.model_validate(observation["research_task_result"])
            research_results.append(result)
            all_tool_messages.append(
                ToolMessage(
                    content=render_supervisor_result_projection(
                        result,
                        max_chars=configurable.max_supervisor_result_projection_chars,
                    ),
                    name=tool_call["name"],
                    tool_call_id=runtime_call_id,
                )
            )

        for _, task, runtime_call_id in overflow_calls:
            overflow_error = (
                "admission_failure: maximum concurrent research units exceeded; "
                f"limit={configurable.max_concurrent_research_units}"
            )
            research_results.append(
                _failed_research_result(
                    task,
                    overflow_error,
                    config=config,
                    artifact_run_id=artifact_run_id,
                )
            )
            all_tool_messages.append(
                ToolMessage(
                    content=overflow_error,
                    name="ConductResearch",
                    tool_call_id=runtime_call_id,
                )
            )

        if research_results:
            update_payload["research_results"] = research_results

        raw_note_blocks = [
            "\n".join(observation.get("raw_notes", []))
            for observation in tool_results
            if observation.get("raw_notes")
        ]
        raw_notes_concat = "\n".join(raw_note_blocks)
        if raw_notes_concat:
            update_payload["raw_notes"] = [raw_notes_concat]
    
    # Step 3: Return command with all tool results
    update_payload["supervisor_messages"] = all_tool_messages
    return Command(
        goto="supervisor",
        update=update_payload
    ) 

# Supervisor Subgraph Construction
# Creates the supervisor workflow that manages research delegation and coordination
supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)

# Add supervisor nodes for research management
supervisor_builder.add_node("supervisor", supervisor)           # Main supervisor logic
supervisor_builder.add_node("supervisor_tools", supervisor_tools)  # Tool execution handler

# Define supervisor workflow edges
supervisor_builder.add_edge(START, "supervisor")  # Entry point to supervisor

# Compile supervisor subgraph for use in main workflow
supervisor_subgraph = supervisor_builder.compile()

async def researcher(
    state: ResearcherState,
    config: RunnableConfig,
    runtime: Runtime[Any] | None = None,
) -> Command[Literal["researcher_tools"]]:
    """Individual researcher that conducts focused research on specific topics.
    
    This researcher is given a specific research topic by the supervisor and uses
    available tools (search, think_tool, MCP tools) to gather comprehensive information.
    It can use think_tool for strategic planning between searches.
    
    Args:
        state: Current researcher state with messages and topic context
        config: Runtime configuration with model settings and tool availability
        
    Returns:
        Command to proceed to researcher_tools for tool execution
    """
    # Step 1: Load configuration and validate tool availability
    configurable = Configuration.from_runnable_config(config)
    artifact_run_id = _artifact_run_id_for_node(
        state.get("artifact_run_id"), config, runtime
    )
    researcher_messages = state.get("researcher_messages", [])
    
    # Get all available research tools (search, MCP, think_tool)
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError(
            "No tools found to conduct research: Please configure either your "
            "search API or add MCP tools to your configuration."
        )
    
    # Step 2: Configure the researcher model with tools
    research_model_config = build_configurable_model_runtime_config(
        model=configurable.research_model,
        max_tokens=configurable.research_model_max_tokens,
        api_key=get_api_key_for_model(configurable.research_model, config),
        enable_thinking=resolve_model_enable_thinking(
            configurable.model_enable_thinking,
            configurable.research_model_enable_thinking,
        ),
    )
    
    # Prepare system prompt with MCP context if available
    researcher_prompt = research_system_prompt.format(
        mcp_prompt=configurable.mcp_prompt or "", 
        date=get_today_str()
    )
    
    # Configure model with tools, retry logic, and settings
    research_model = (
        configurable_model
        .bind_tools(tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )
    
    # Step 3: Generate researcher response with system context
    messages = [SystemMessage(content=researcher_prompt)] + researcher_messages
    response = await research_model.ainvoke(messages)
    
    # Step 4: Update state and proceed to tool execution
    return Command(
        goto="researcher_tools",
        update={
            "researcher_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
            "artifact_run_id": artifact_run_id,
        }
    )

# Tool Execution Helper Function
@dataclass(frozen=True, slots=True)
class _ToolExecutionObservation:
    """Carry generic tool model content and Host-owned execution issues."""

    model_content: str
    issues: list[ResearchExecutionIssue]


async def execute_tool_safely(
    tool: Any,
    args: dict[str, Any],
    config: RunnableConfig,
    *,
    tool_call_id: str,
) -> _ToolExecutionObservation:
    """Execute a generic tool while retaining failure as a structured Host fact."""
    try:
        result = await tool.ainvoke(args, config)
        return _ToolExecutionObservation(model_content=str(result), issues=[])
    except Exception as error:
        issue = make_research_execution_issue(
            stage=ResearchExecutionStage.TOOL_EXECUTION,
            code="tool_execution_failed",
            severity=ResearchExecutionSeverity.ERROR,
            message=f"Tool execution failed with {type(error).__name__}.",
            tool_call_id=tool_call_id,
            degrades_task_status=True,
            occurrence_key=tool_call_id,
        )
        return _ToolExecutionObservation(
            model_content=issue.message,
            issues=[issue],
        )


async def _execute_researcher_tool(
    *,
    tool_call: dict[str, Any],
    tools_by_name: dict[str, Any],
    research_topic: str,
    config: RunnableConfig,
    artifact_run_id: str,
) -> _ToolExecutionObservation | SearchExecutionResult:
    """Execute Tavily through its structured path and preserve generic tool behavior."""
    tool_name = tool_call["name"]
    if tool_name != "tavily_search":
        return await execute_tool_safely(
            tools_by_name[tool_name],
            tool_call["args"],
            config,
            tool_call_id=tool_call["id"],
        )
    try:
        return await execute_tavily_search_structured(
            **tool_call["args"],
            research_topic=research_topic,
            config=config,
            artifact_run_id=artifact_run_id,
            tool_call_id=tool_call["id"],
        )
    except Exception as error:
        logger.exception("Tavily execution failed")
        issue = make_research_execution_issue(
            stage=ResearchExecutionStage.TOOL_EXECUTION,
            code="tavily_execution_failed",
            severity=ResearchExecutionSeverity.ERROR,
            message=f"Tavily execution failed with {type(error).__name__}.",
            tool_call_id=tool_call["id"],
            degrades_task_status=True,
            occurrence_key=tool_call["id"],
        )
        return SearchExecutionResult(
            model_content=issue.message,
            sources=[],
            evidences=[],
            issues=[issue],
            tool_call_id=tool_call["id"],
        )


def _bounded_search_state_updates(
    *,
    state: ResearcherState,
    observations: list[_ToolExecutionObservation | SearchExecutionResult],
    configurable: Configuration,
) -> tuple[
    list[SourceRecord],
    list[EvidenceRecord],
    list[str | None],
    list[ResearchExecutionIssue],
    bool,
]:
    """Admit structured execution facts under deterministic task-local bounds.

    Exact identity replay is idempotent. Divergent payloads for an existing identity
    remain a contract error, matching the Researcher state reducers. Candidate records
    are considered in stable observation order, Sources before Evidence, and every
    accepted prefix must fit the canonical Result provenance serialization bound.
    """
    ordered_sources = list(state.get("source_records", []))
    ordered_evidence = list(state.get("evidence_records", []))
    known_sources = {record.source_id: record for record in ordered_sources}
    known_evidence = {record.evidence_id: record for record in ordered_evidence}
    provenance_bound = min(
        configurable.max_result_provenance_chars,
        MAX_RESULT_PROVENANCE_SERIALIZED_CHARS,
    )
    if (
        measure_result_provenance_chars(ordered_sources, ordered_evidence)
        > provenance_bound
    ):
        raise ValueError("Existing Researcher provenance state exceeds its bound")
    evidence_counts: dict[str, int] = {}
    for record in known_evidence.values():
        evidence_counts[record.source_id] = evidence_counts.get(record.source_id, 0) + 1
    total_evidence_chars = sum(len(record.excerpt) for record in known_evidence.values())
    admitted_sources: list[SourceRecord] = []
    admitted_evidence: list[EvidenceRecord] = []
    observed_issues: list[ResearchExecutionIssue] = []
    bounded_model_content: list[str | None] = [None for _ in observations]

    def admission_issue(
        observation: SearchExecutionResult,
        *,
        code: str,
        message: str,
        occurrence_key: str,
        source_id: str | None = None,
        candidate_id: str | None = None,
    ) -> ResearchExecutionIssue:
        """Create one deterministic state-admission rejection fact."""
        return make_research_execution_issue(
            stage=ResearchExecutionStage.STATE_ADMISSION,
            code=code,
            severity=ResearchExecutionSeverity.WARNING,
            message=message,
            tool_call_id=observation.tool_call_id,
            source_id=source_id,
            candidate_id=candidate_id,
            degrades_task_status=True,
            occurrence_key=occurrence_key,
        )

    for observation_index, observation in enumerate(observations):
        observed_issues.extend(observation.issues)
        if not isinstance(observation, SearchExecutionResult):
            continue
        visible_sources: list[SourceRecord] = []
        visible_evidence: list[EvidenceRecord] = []
        admission_issues: list[ResearchExecutionIssue] = []
        for source in observation.sources:
            existing = known_sources.get(source.source_id)
            if existing is not None:
                if existing != source:
                    raise ValueError(
                        "Contract conflict for source_id="
                        f"{source.source_id!r}: the same identity has different payloads"
                    )
                visible_sources.append(existing)
                continue
            if len(known_sources) >= configurable.max_sources_per_research_task:
                admission_issues.append(
                    admission_issue(
                        observation,
                        code="source_count_bound",
                        message="One Source record was omitted at the task Source bound.",
                        occurrence_key=f"source:{source.source_id}:count",
                        source_id=source.source_id,
                    )
                )
                continue
            candidate_sources = [*ordered_sources, source]
            if (
                measure_result_provenance_chars(candidate_sources, ordered_evidence)
                > provenance_bound
            ):
                admission_issues.append(
                    admission_issue(
                        observation,
                        code="provenance_payload_bound",
                        message=(
                            "One Source record was omitted at the Result provenance "
                            "payload bound."
                        ),
                        occurrence_key=f"source:{source.source_id}:payload",
                        source_id=source.source_id,
                    )
                )
                continue
            known_sources[source.source_id] = source
            ordered_sources.append(source)
            admitted_sources.append(source)
            visible_sources.append(source)

        for evidence in observation.evidences:
            if evidence.source_id not in known_sources:
                admission_issues.append(
                    admission_issue(
                        observation,
                        code="evidence_source_not_admitted",
                        message=(
                            "One Evidence record was omitted because its Source was not "
                            "admitted."
                        ),
                        occurrence_key=f"evidence:{evidence.evidence_id}:source",
                        source_id=evidence.source_id,
                    )
                )
                continue
            existing = known_evidence.get(evidence.evidence_id)
            if existing is not None:
                if existing != evidence:
                    raise ValueError(
                        "Contract conflict for evidence_id="
                        f"{evidence.evidence_id!r}: the same identity has different payloads"
                    )
                visible_evidence.append(existing)
                continue
            if (
                evidence_counts.get(evidence.source_id, 0)
                >= configurable.max_selected_chunks_per_source
            ):
                admission_issues.append(
                    admission_issue(
                        observation,
                        code="evidence_per_source_bound",
                        message="One Evidence record was omitted at the per-Source bound.",
                        occurrence_key=f"evidence:{evidence.evidence_id}:per-source",
                        source_id=evidence.source_id,
                    )
                )
                continue
            if (
                len(known_evidence)
                >= configurable.max_evidence_records_per_research_task
            ):
                admission_issues.append(
                    admission_issue(
                        observation,
                        code="evidence_count_bound",
                        message="One Evidence record was omitted at the task record bound.",
                        occurrence_key=f"evidence:{evidence.evidence_id}:count",
                        source_id=evidence.source_id,
                    )
                )
                continue
            if (
                total_evidence_chars + len(evidence.excerpt)
                > configurable.max_evidence_excerpt_chars_per_result
            ):
                admission_issues.append(
                    admission_issue(
                        observation,
                        code="evidence_excerpt_chars_bound",
                        message="One Evidence record was omitted at the task character bound.",
                        occurrence_key=f"evidence:{evidence.evidence_id}:chars",
                        source_id=evidence.source_id,
                    )
                )
                continue
            candidate_evidence = [*ordered_evidence, evidence]
            if (
                measure_result_provenance_chars(ordered_sources, candidate_evidence)
                > provenance_bound
            ):
                admission_issues.append(
                    admission_issue(
                        observation,
                        code="provenance_payload_bound",
                        message=(
                            "One Evidence record was omitted at the Result provenance "
                            "payload bound."
                        ),
                        occurrence_key=f"evidence:{evidence.evidence_id}:payload",
                        source_id=evidence.source_id,
                    )
                )
                continue
            known_evidence[evidence.evidence_id] = evidence
            ordered_evidence.append(evidence)
            admitted_evidence.append(evidence)
            visible_evidence.append(evidence)
            evidence_counts[evidence.source_id] = (
                evidence_counts.get(evidence.source_id, 0) + 1
            )
            total_evidence_chars += len(evidence.excerpt)

        observed_issues.extend(admission_issues)
        bounded_model_content[observation_index] = (
            _render_admitted_search_observation(
                sources=visible_sources,
                evidence=visible_evidence,
                issues=[*observation.issues, *admission_issues],
                max_chars=configurable.max_search_tool_message_chars,
            )
            if admission_issues
            else observation.model_content
        )

    admitted_issues = admit_research_execution_issues(
        list(state.get("execution_issues", [])),
        observed_issues,
    )
    return (
        admitted_sources,
        admitted_evidence,
        bounded_model_content,
        admitted_issues,
        any(issue.degrades_task_status for issue in observed_issues),
    )


def _render_admitted_search_observation(
    *,
    sources: list[SourceRecord],
    evidence: list[EvidenceRecord],
    issues: list[ResearchExecutionIssue],
    max_chars: int,
) -> str:
    """Render only records retained by state admission without slicing Evidence."""
    blocks = [
        render_researcher_observation(
            source=source,
            summary="Derived summary omitted after task-bound record filtering.",
            evidence=[record for record in evidence if record.source_id == source.source_id],
        )
        for source in sources
    ]
    if not blocks:
        blocks.append("No structured Source/Evidence records were admitted for this call.")
    if issues:
        blocks.append(
            "Execution warnings (process metadata, not Evidence):\n"
            + "\n".join(f"- {issue.message}" for issue in issues)
        )
    separator = "\n\n---\n\n"
    marker = "[Additional admitted search observations omitted at configured bound.]"
    admitted_blocks: list[str] = []
    for block in blocks:
        candidate = separator.join((*admitted_blocks, block))
        if len(candidate) > max_chars:
            break
        admitted_blocks.append(block)
    if len(admitted_blocks) < len(blocks):
        while admitted_blocks:
            candidate = separator.join((*admitted_blocks, marker))
            if len(candidate) <= max_chars:
                return candidate
            admitted_blocks.pop()
        return marker if len(marker) <= max_chars else ""
    return separator.join(admitted_blocks)


async def researcher_tools(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher", "compress_research"]]:
    """Execute tools called by the researcher, including search tools and strategic thinking.
    
    Status updates describe execution/termination only: normal termination is SUCCESS,
    a budget-bound stop is PARTIAL, and explicit ResearchComplete takes precedence when
    it coincides with the budget boundary.

    This function handles various types of researcher tool calls:
    1. think_tool - Strategic reflection that continues the research conversation
    2. Search tools (tavily_search, web_search) - Information gathering
    3. MCP tools - External tool integrations
    4. ResearchComplete - Signals completion of individual research task
    
    Args:
        state: Current researcher state with messages and iteration count
        config: Runtime configuration with research limits and tool settings
        
    Returns:
        Command to either continue research loop or proceed to compression
    """
    # Step 1: Extract current state and check early exit conditions
    configurable = Configuration.from_runnable_config(config)
    artifact_run_id = _artifact_run_id_for_node(
        state.get("artifact_run_id"), config
    )
    researcher_messages = state.get("researcher_messages", [])
    most_recent_message = researcher_messages[-1]
    
    # Early exit if no tool calls were made (including native web search)
    has_tool_calls = bool(most_recent_message.tool_calls)
    has_native_search = (
        openai_websearch_called(most_recent_message) or 
        anthropic_websearch_called(most_recent_message)
    )
    
    if not has_tool_calls and not has_native_search:
        return Command(
            goto="compress_research",
            update={
                "research_task_status": ResearchTaskStatus.SUCCESS,
                "artifact_run_id": artifact_run_id,
            },
        )
    
    # Step 2: Handle other tool calls (search, MCP tools, etc.)
    tools = await get_all_tools(config)
    tools_by_name = {
        tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool 
        for tool in tools
    }
    
    # Execute all tool calls in parallel
    tool_calls = most_recent_message.tool_calls
    tool_execution_tasks = [
        _execute_researcher_tool(
            tool_call=tool_call,
            tools_by_name=tools_by_name,
            research_topic=state.get("research_topic", ""),
            config=config,
            artifact_run_id=artifact_run_id,
        )
        for tool_call in tool_calls
    ]
    observations = await asyncio.gather(*tool_execution_tasks)
    (
        sources,
        evidences,
        bounded_model_content,
        execution_issues,
        execution_failure_observed,
    ) = _bounded_search_state_updates(
        state=state,
        observations=observations,
        configurable=configurable,
    )

    # Create tool messages from execution results
    tool_outputs = []
    for observation, tool_call, bounded_content in zip(
        observations, tool_calls, bounded_model_content
    ):
        content = bounded_content or observation.model_content
        tool_outputs.append(
            ToolMessage(
                content=content,
                name=tool_call["name"],
                tool_call_id=tool_call["id"],
            )
        )
    
    # Step 3: Check late exit conditions (after processing tools)
    exceeded_iterations = state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls
    research_complete_called = any(
        tool_call["name"] == "ResearchComplete" 
        for tool_call in most_recent_message.tool_calls
    )
    
    if exceeded_iterations or research_complete_called:
        # End research and proceed to compression
        return Command(
            goto="compress_research",
            update={
                "researcher_messages": tool_outputs,
                "source_records": sources,
                "evidence_records": evidences,
                "execution_issues": execution_issues,
                "execution_failure_observed": execution_failure_observed,
                "artifact_run_id": artifact_run_id,
                "research_task_status": (
                    ResearchTaskStatus.SUCCESS
                    if research_complete_called
                    else ResearchTaskStatus.PARTIAL
                ),
            },
        )
    
    # Continue research loop with tool results
    return Command(
        goto="researcher",
        update={
            "researcher_messages": tool_outputs,
            "source_records": sources,
            "evidence_records": evidences,
            "execution_issues": execution_issues,
            "execution_failure_observed": execution_failure_observed,
            "artifact_run_id": artifact_run_id,
        },
    )

async def compress_research(state: ResearcherState, config: RunnableConfig):
    """Create structured Findings, then publish a self-contained D15 Result.

    Args:
        state: Researcher state containing authoritative Source/Evidence ledgers.
        config: Runtime configuration and owning ArtifactStore namespace.

    Returns:
        Published task Result plus the legacy compressed text dual-write.

    Raises:
        ProvenancePublicationError: If the candidate Source/Evidence provenance graph
            cannot pass deterministic Host publication validation.
    """
    configurable = Configuration.from_runnable_config(config)
    task = state["task"]
    artifact_run_id = _artifact_run_id_for_node(
        state.get("artifact_run_id"), config
    )
    source_records = list(state.get("source_records", []))
    evidence_records = list(state.get("evidence_records", []))

    # Gate invalid local provenance before it can enter semantic compression.
    await asyncio.to_thread(
        _build_and_publish_research_result,
        task=task,
        config=config,
        artifact_run_id=artifact_run_id,
        status=ResearchTaskStatus.SUCCESS,
        source_records=source_records,
        evidence_records=evidence_records,
        findings=[],
        summary="Pre-compression provenance validation.",
        limitations=[],
        conflicts=[],
        error=None,
    )

    compression_model_config = build_configurable_model_runtime_config(
        model=configurable.compression_model,
        max_tokens=configurable.compression_model_max_tokens,
        api_key=get_api_key_for_model(configurable.compression_model, config),
        enable_thinking=resolve_model_enable_thinking(
            configurable.model_enable_thinking,
            configurable.compression_model_enable_thinking,
        ),
    )
    synthesizer_model = (
        configurable_model.with_structured_output(ResearchCompression)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(compression_model_config)
    )

    researcher_messages = list(state.get("researcher_messages", []))
    researcher_messages.extend(
        (
            HumanMessage(content=compress_research_simple_human_message),
            HumanMessage(content=_render_compression_evidence(task, evidence_records)),
        )
    )

    synthesis_attempts = 0
    max_attempts = 3
    last_compression_failure = "compression_failure"
    while synthesis_attempts < max_attempts:
        try:
            compression_prompt = compress_research_system_prompt.format(date=get_today_str())
            messages = [SystemMessage(content=compression_prompt)] + researcher_messages
            response = await synthesizer_model.ainvoke(messages)
            compression = ResearchCompression.model_validate(response)
            materialized_findings = _materialize_findings(
                task=task,
                compression=compression,
                evidence_records=evidence_records,
            )
            findings = list(materialized_findings.findings)
            raw_notes_content = "\n".join(
                str(message.content)
                for message in filter_messages(
                    researcher_messages, include_types=["tool", "ai"]
                )
            )

            status = state.get("research_task_status", ResearchTaskStatus.SUCCESS)
            limitations = list(compression.limitations)
            limitations.extend(materialized_findings.limitations)
            limitations.extend(
                limitation for finding in findings for limitation in finding.limitations
            )
            if status is ResearchTaskStatus.PARTIAL:
                limitations.append(
                    "Research stopped after reaching the configured tool-call budget."
                )
            if state.get("execution_failure_observed", False):
                status = ResearchTaskStatus.PARTIAL
                limitations.append(
                    "At least one Host-recorded execution issue degraded this task."
                )
            if any(
                issue.stage is ResearchExecutionStage.STATE_ADMISSION
                for issue in state.get("execution_issues", [])
            ):
                limitations.append(
                    "Some search records were omitted at configured state capacity."
                )
            conflicts = list(compression.conflicts)
            conflicts.extend(conflict for finding in findings for conflict in finding.conflicts)
            result = await asyncio.to_thread(
                _build_and_publish_research_result,
                task=task,
                config=config,
                artifact_run_id=artifact_run_id,
                status=status,
                source_records=source_records,
                evidence_records=evidence_records,
                findings=findings,
                summary=compression.summary,
                limitations=list(dict.fromkeys(limitations)),
                conflicts=list(dict.fromkeys(conflicts)),
                error=None,
            )
            return {
                "research_task_result": result,
                "compressed_research": compression.summary,
                "raw_notes": [raw_notes_content],
            }

        except ProvenancePublicationError:
            raise
        except FindingMaterializationError:
            last_compression_failure = "finding_materialization_failure"
            synthesis_attempts += 1
            continue
        except Exception as error:
            last_compression_failure = "compression_failure"
            synthesis_attempts += 1
            if is_token_limit_exceeded(error, configurable.compression_model):
                researcher_messages = remove_up_to_last_ai_message(researcher_messages)
            continue

    raw_notes_content = "\n".join(
        str(message.content)
        for message in filter_messages(
            researcher_messages, include_types=["tool", "ai"]
        )
    )
    compression_error = f"{last_compression_failure}: maximum retries exceeded"
    failed_result = await asyncio.to_thread(
        _failed_research_result,
        task,
        compression_error,
        source_records=source_records,
        evidence_records=evidence_records,
        findings=state.get("findings", []),
        config=config,
        artifact_run_id=artifact_run_id,
    )
    return {
        "research_task_result": failed_result,
        "compressed_research": "Error synthesizing research report: Maximum retries exceeded",
        "raw_notes": [raw_notes_content],
    }

# Researcher Subgraph Construction
# Creates individual researcher workflow for conducting focused research on specific topics
researcher_builder = StateGraph(
    ResearcherState, 
    output=ResearcherOutputState, 
    config_schema=Configuration
)

# Add researcher nodes for research execution and compression
researcher_builder.add_node("researcher", researcher)                 # Main researcher logic
researcher_builder.add_node("researcher_tools", researcher_tools)     # Tool execution handler
researcher_builder.add_node("compress_research", compress_research)   # Research compression

# Define researcher workflow edges
researcher_builder.add_edge(START, "researcher")           # Entry point to researcher
researcher_builder.add_edge("compress_research", END)      # Exit point after compression

# Compile researcher subgraph for parallel execution by supervisor
researcher_subgraph = researcher_builder.compile()

async def final_report_generation(state: AgentState, config: RunnableConfig):
    """Generate the final comprehensive research report with retry logic for token limits.
    
    This function takes all collected research findings and synthesizes them into a 
    well-structured, comprehensive final report using the configured report generation model.
    
    Args:
        state: Agent state containing research findings and context
        config: Runtime configuration with model settings and API keys
        
    Returns:
        Dictionary containing the final report and cleared state
    """
    # Step 1: Extract research findings and prepare state cleanup
    notes = state.get("notes", [])
    cleared_state = {
        "notes": {"type": "override", "value": []},
        "research_run_status": ResearchRunStatus.FINALIZED,
    }
    findings = "\n".join(notes)
    
    # Step 2: Configure the final report generation model
    configurable = Configuration.from_runnable_config(config)
    writer_model_config = build_configurable_model_runtime_config(
        model=configurable.final_report_model,
        max_tokens=configurable.final_report_model_max_tokens,
        api_key=get_api_key_for_model(configurable.final_report_model, config),
        enable_thinking=resolve_model_enable_thinking(
            configurable.model_enable_thinking,
            configurable.final_report_model_enable_thinking,
        ),
    )
    
    # Step 3: Attempt report generation with token limit retry logic
    max_retries = 3
    current_retry = 0
    findings_token_limit = None
    
    while current_retry <= max_retries:
        try:
            # Create comprehensive prompt with all research context
            final_report_prompt = final_report_generation_prompt.format(
                research_brief=state.get("research_brief", ""),
                messages=get_buffer_string(state.get("messages", [])),
                findings=findings,
                date=get_today_str()
            )
            
            # Generate the final report
            final_report = await configurable_model.with_config(writer_model_config).ainvoke([
                HumanMessage(content=final_report_prompt)
            ])
            
            # Return successful report generation
            return {
                "final_report": final_report.content, 
                "messages": [final_report],
                **cleared_state
            }
            
        except Exception as e:
            # Handle token limit exceeded errors with progressive truncation
            if is_token_limit_exceeded(e, configurable.final_report_model):
                current_retry += 1
                
                if current_retry == 1:
                    # First retry: determine initial truncation limit
                    model_token_limit = get_model_token_limit(configurable.final_report_model)
                    if not model_token_limit:
                        return {
                            "final_report": f"Error generating final report: Token limit exceeded, however, we could not determine the model's maximum context length. Please update the model map in deep_researcher/utils.py with this information. {e}",
                            "messages": [AIMessage(content="Report generation failed due to token limits")],
                            **cleared_state
                        }
                    # Use 4x token limit as character approximation for truncation
                    findings_token_limit = model_token_limit * 4
                else:
                    # Subsequent retries: reduce by 10% each time
                    assert findings_token_limit is not None
                    findings_token_limit = int(findings_token_limit * 0.9)
                
                # Truncate findings and retry
                findings = findings[:findings_token_limit]
                continue
            else:
                # Non-token-limit error: return error immediately
                return {
                    "final_report": f"Error generating final report: {e}",
                    "messages": [AIMessage(content="Report generation failed due to an error")],
                    **cleared_state
                }
    
    # Step 4: Return failure result if all retries exhausted
    return {
        "final_report": "Error generating final report: Maximum retries exceeded",
        "messages": [AIMessage(content="Report generation failed after maximum retries")],
        **cleared_state
    }


async def global_synthesis(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    """Apply one typed global synthesis outcome as a bounded Parent State update."""
    existing_manifest = state.get("grounding_manifest")
    existing_issues = state.get("global_synthesis_issues", [])
    try:
        outcome = await run_global_synthesis(
            medical_research_brief=state.get("medical_research_brief"),
            research_results=state.get("research_results", []),
            artifact_run_id=state.get("artifact_run_id"),
            config=config,
            existing_manifest=existing_manifest,
            existing_shadow_report=state.get("v2_shadow_report"),
            existing_status=state.get("global_synthesis_status"),
            existing_issues=existing_issues,
        )
    except Exception as error:
        logger.exception("Global Synthesis boundary failed")
        outcome = _contained_pipeline_failure(
            error=error,
            existing_manifest=existing_manifest,
            existing_issues=existing_issues,
        )
    update: dict[str, Any] = {
        "global_synthesis_status": outcome.status,
        "global_synthesis_issues": list(outcome.issues),
        "v2_shadow_report": outcome.shadow_report,
    }
    if outcome.manifest is not None:
        update["grounding_manifest"] = outcome.manifest
    return update

# Main Deep Researcher Graph Construction
# Creates the complete deep research workflow from user input to final report
deep_researcher_builder = StateGraph(
    AgentState, 
    input=AgentInputState, 
    config_schema=Configuration
)

# Add main workflow nodes for the complete research process
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)           # User clarification phase
deep_researcher_builder.add_node("write_research_brief", write_research_brief)     # Research planning phase
deep_researcher_builder.add_node("research_supervisor", supervisor_subgraph)       # Research execution phase
deep_researcher_builder.add_node("global_synthesis", global_synthesis)             # V2 shadow synthesis
deep_researcher_builder.add_node("final_report_generation", final_report_generation)  # Report generation phase

# Define main workflow edges for sequential execution
deep_researcher_builder.add_edge(START, "clarify_with_user")                       # Entry point
deep_researcher_builder.add_edge("research_supervisor", "global_synthesis")        # Research to V2 synthesis
deep_researcher_builder.add_edge("global_synthesis", "final_report_generation")    # V2 to V1 report
deep_researcher_builder.add_edge("final_report_generation", END)                   # Final exit point

# Compile the complete deep researcher workflow
deep_researcher = deep_researcher_builder.compile()
