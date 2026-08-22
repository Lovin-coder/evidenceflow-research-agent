"""Graph state definitions and data structures for the Deep Research agent."""

import hashlib
import json
import operator
import re
from enum import Enum
from typing import Annotated, Optional, TypeVar

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict

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

IdentityModel = TypeVar("IdentityModel")
MAX_RESEARCH_EXECUTION_ISSUES = 100
MAX_RESEARCH_EXECUTION_ISSUE_MESSAGE_CHARS = 512
MAX_RESEARCH_EXECUTION_ISSUES_SERIALIZED_CHARS = 192_000


###################
# Structured Outputs
###################
class ConductResearch(BaseModel):
    """Request one research delegation; the host assigns its stable task ID."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    research_question: str = Field(
        min_length=1,
        description="A focused, self-contained medical research question.",
    )
    evidence_needs: list[EvidenceNeed] = Field(
        min_length=1,
        description="The evidence requirements this delegated task must address.",
    )
    source_preferences: list[str] = Field(
        description="Non-binding source or provider preferences for this task.",
    )
    priority: int = Field(
        ge=0,
        description="Relative task priority; it does not guarantee execution order.",
    )

class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""

class Summary(BaseModel):
    """Research summary with key findings."""
    
    summary: str
    key_excerpts: str

class ClarifyWithUser(BaseModel):
    """Model for user clarification requests."""
    
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )

class ResearchQuestion(BaseModel):
    """Research question and brief for guiding research."""
    
    research_brief: str = Field(
        description="A research question that will be used to guide the research.",
    )


class ResearchExecutionStage(str, Enum):
    """Identify the internal runtime boundary that observed an execution issue."""

    PROVIDER = "provider"
    CONTENT_GATE = "content_gate"
    SELECTION = "selection"
    MATERIALIZATION = "materialization"
    STATE_ADMISSION = "state_admission"
    TOOL_EXECUTION = "tool_execution"
    COMPRESSION = "compression"


class ResearchExecutionSeverity(str, Enum):
    """Classify internal issues without deriving meaning from diagnostic text."""

    WARNING = "warning"
    ERROR = "error"


class ResearchExecutionIssue(BaseModel):
    """Carry bounded Host-owned execution facts outside model-facing messages."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    issue_id: str = Field(min_length=1, max_length=96)
    stage: ResearchExecutionStage
    code: str = Field(min_length=1, max_length=96)
    severity: ResearchExecutionSeverity
    message: str = Field(
        min_length=1,
        max_length=MAX_RESEARCH_EXECUTION_ISSUE_MESSAGE_CHARS,
    )
    tool_call_id: str | None = Field(default=None, max_length=256)
    source_id: str | None = Field(default=None, max_length=256)
    candidate_id: str | None = Field(default=None, max_length=256)
    degrades_task_status: bool


def make_research_execution_issue(
    *,
    stage: ResearchExecutionStage,
    code: str,
    severity: ResearchExecutionSeverity,
    message: str,
    degrades_task_status: bool,
    tool_call_id: str | None = None,
    source_id: str | None = None,
    candidate_id: str | None = None,
    occurrence_key: str = "",
) -> ResearchExecutionIssue:
    """Construct a deterministic, bounded issue without retaining raw payloads."""
    bounded_tool_call_id = tool_call_id[:256] if tool_call_id else None
    bounded_source_id = source_id[:256] if source_id else None
    bounded_candidate_id = candidate_id[:256] if candidate_id else None
    bounded_occurrence_key = occurrence_key[:512]
    normalized_message = re.sub(r"\s+", " ", message).strip()
    bounded_message = normalized_message[:MAX_RESEARCH_EXECUTION_ISSUE_MESSAGE_CHARS]
    identity_payload = json.dumps(
        {
            "version": "p2-s4-execution-issue-v1",
            "stage": stage.value,
            "code": code,
            "severity": severity.value,
            "message": bounded_message,
            "tool_call_id": bounded_tool_call_id,
            "source_id": bounded_source_id,
            "candidate_id": bounded_candidate_id,
            "degrades_task_status": degrades_task_status,
            "occurrence_key": bounded_occurrence_key,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity_payload.encode("utf-8")).hexdigest()[:32]
    return ResearchExecutionIssue(
        issue_id=f"issue:sha256:{digest}",
        stage=stage,
        code=code,
        severity=severity,
        message=bounded_message,
        tool_call_id=bounded_tool_call_id,
        source_id=bounded_source_id,
        candidate_id=bounded_candidate_id,
        degrades_task_status=degrades_task_status,
    )


###################
# State Definitions
###################

def override_reducer(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


def _merge_identity_models(
    current_value: list[IdentityModel],
    new_value: list[IdentityModel],
    identity_field: str,
) -> list[IdentityModel]:
    """Merge immutable contract objects using their stable identity.

    Args:
        current_value: Contract objects already present in the state channel.
        new_value: Contract objects supplied by the current partial update.
        identity_field: Stable model field used to detect replay and conflicts.

    Returns:
        Existing objects followed by newly observed identities in arrival order.

    Raises:
        ValueError: If the same identity is associated with a different payload.
    """
    merged = list(current_value)
    by_identity = {getattr(item, identity_field): item for item in merged}
    for item in new_value:
        identity = getattr(item, identity_field)
        existing = by_identity.get(identity)
        if existing is None:
            by_identity[identity] = item
            merged.append(item)
        elif existing != item:
            # Exact replay is idempotent; divergent immutable content is a contract error.
            raise ValueError(
                f"Contract conflict for {identity_field}={identity!r}: "
                "the same identity has different payloads"
            )
    return merged


def research_results_reducer(
    current_value: list[ResearchTaskResult],
    new_value: list[ResearchTaskResult],
) -> list[ResearchTaskResult]:
    """Append task results while making exact task replay idempotent."""
    return _merge_identity_models(current_value, new_value, "task_id")


def source_records_reducer(
    current_value: list[SourceRecord], new_value: list[SourceRecord]
) -> list[SourceRecord]:
    """Append SourceRecords while making exact source replay idempotent."""
    return _merge_identity_models(current_value, new_value, "source_id")


def evidence_records_reducer(
    current_value: list[EvidenceRecord], new_value: list[EvidenceRecord]
) -> list[EvidenceRecord]:
    """Append EvidenceRecords while making exact evidence replay idempotent."""
    return _merge_identity_models(current_value, new_value, "evidence_id")


def findings_reducer(
    current_value: list[ResearchFinding], new_value: list[ResearchFinding]
) -> list[ResearchFinding]:
    """Append ResearchFindings while making exact finding replay idempotent."""
    return _merge_identity_models(current_value, new_value, "finding_id")


def measure_research_execution_issues_chars(
    issues: list[ResearchExecutionIssue],
) -> int:
    """Measure the deterministic JSON projection used by the issue-state bound."""
    return len(
        json.dumps(
            [issue.model_dump(mode="json") for issue in issues],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def execution_issues_reducer(
    current_value: list[ResearchExecutionIssue],
    new_value: list[ResearchExecutionIssue],
) -> list[ResearchExecutionIssue]:
    """Merge issues idempotently and reject identity conflicts or bound overflow."""
    merged = _merge_identity_models(current_value, new_value, "issue_id")
    if len(merged) > MAX_RESEARCH_EXECUTION_ISSUES:
        raise ValueError("Research execution issue count exceeds the state bound")
    if (
        measure_research_execution_issues_chars(merged)
        > MAX_RESEARCH_EXECUTION_ISSUES_SERIALIZED_CHARS
    ):
        raise ValueError("Research execution issue payload exceeds the state bound")
    return merged


def admit_research_execution_issues(
    current_value: list[ResearchExecutionIssue],
    new_value: list[ResearchExecutionIssue],
) -> list[ResearchExecutionIssue]:
    """Return the deterministic new subset that can enter bounded issue state.

    One count slot is reserved from non-degrading diagnostics so a later task-
    degrading fact can still be represented. The separate sticky failure channel
    preserves Host status authority even after the issue ledger reaches capacity.
    """
    known = {issue.issue_id: issue for issue in current_value}
    merged = list(current_value)
    admitted: list[ResearchExecutionIssue] = []
    for issue in new_value:
        existing = known.get(issue.issue_id)
        if existing is not None:
            if existing != issue:
                raise ValueError(
                    f"Execution issue conflict for issue_id={issue.issue_id!r}"
                )
            continue
        count_limit = (
            MAX_RESEARCH_EXECUTION_ISSUES
            if issue.degrades_task_status
            else MAX_RESEARCH_EXECUTION_ISSUES - 1
        )
        candidate = [*merged, issue]
        if len(candidate) > count_limit:
            continue
        if (
            measure_research_execution_issues_chars(candidate)
            > MAX_RESEARCH_EXECUTION_ISSUES_SERIALIZED_CHARS
        ):
            continue
        known[issue.issue_id] = issue
        merged.append(issue)
        admitted.append(issue)
    return admitted


def boolean_or_reducer(current_value: bool, new_value: bool) -> bool:
    """Preserve a Host-observed degrading execution fact across later success."""
    return current_value or new_value
    
class AgentInputState(MessagesState):
    """InputState is only 'messages'."""

class AgentState(MessagesState):
    """Parent graph state carrying structured results and legacy report channels."""
    
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    artifact_run_id: Optional[str]
    medical_research_brief: Optional[MedicalResearchBrief]
    research_brief: Optional[str]
    research_results: Annotated[list[ResearchTaskResult], research_results_reducer]
    raw_notes: Annotated[list[str], override_reducer]
    notes: Annotated[list[str], override_reducer]
    final_report: str

class SupervisorState(TypedDict):
    """Supervisor-local planning state with bounded task-result observations."""
    
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    artifact_run_id: str
    medical_research_brief: MedicalResearchBrief
    research_brief: str
    research_results: Annotated[list[ResearchTaskResult], research_results_reducer]
    notes: Annotated[list[str], override_reducer]
    research_iterations: int
    raw_notes: Annotated[list[str], override_reducer]

class ResearcherState(TypedDict):
    """Researcher-local process state for one MedicalResearchTask invocation."""
    
    task: MedicalResearchTask
    artifact_run_id: str
    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int
    research_topic: str
    source_records: Annotated[list[SourceRecord], source_records_reducer]
    evidence_records: Annotated[list[EvidenceRecord], evidence_records_reducer]
    findings: Annotated[list[ResearchFinding], findings_reducer]
    execution_issues: Annotated[
        list[ResearchExecutionIssue], execution_issues_reducer
    ]
    execution_failure_observed: Annotated[bool, boolean_or_reducer]
    research_task_status: ResearchTaskStatus
    compressed_research: str
    research_task_result: ResearchTaskResult
    raw_notes: Annotated[list[str], override_reducer]

class ResearcherOutputState(BaseModel):
    """Project the stable task result plus temporary legacy compatibility outputs."""
    
    research_task_result: ResearchTaskResult
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = Field(default_factory=list)
