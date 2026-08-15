"""Graph state definitions and data structures for the Deep Research agent."""

import operator
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

IdentityModel = TypeVar(
    "IdentityModel", SourceRecord, EvidenceRecord, ResearchFinding, ResearchTaskResult
)


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
    """Append distinct identities, deduplicate replays, and reject conflicts."""
    merged = list(current_value)
    by_identity = {getattr(item, identity_field): item for item in merged}
    for item in new_value:
        identity = getattr(item, identity_field)
        existing = by_identity.get(identity)
        if existing is None:
            by_identity[identity] = item
            merged.append(item)
        elif existing != item:
            raise ValueError(
                f"Contract conflict for {identity_field}={identity!r}: "
                "the same identity has different payloads"
            )
    return merged


def research_results_reducer(
    current_value: list[ResearchTaskResult],
    new_value: list[ResearchTaskResult],
) -> list[ResearchTaskResult]:
    """Aggregate immutable task results by task identity."""
    return _merge_identity_models(current_value, new_value, "task_id")


def source_records_reducer(
    current_value: list[SourceRecord], new_value: list[SourceRecord]
) -> list[SourceRecord]:
    """Aggregate immutable source records by source identity."""
    return _merge_identity_models(current_value, new_value, "source_id")


def evidence_records_reducer(
    current_value: list[EvidenceRecord], new_value: list[EvidenceRecord]
) -> list[EvidenceRecord]:
    """Aggregate immutable evidence records by evidence identity."""
    return _merge_identity_models(current_value, new_value, "evidence_id")


def findings_reducer(
    current_value: list[ResearchFinding], new_value: list[ResearchFinding]
) -> list[ResearchFinding]:
    """Aggregate immutable findings by finding identity."""
    return _merge_identity_models(current_value, new_value, "finding_id")
    
class AgentInputState(MessagesState):
    """InputState is only 'messages'."""

class AgentState(MessagesState):
    """Main agent state containing messages and research data."""
    
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    medical_research_brief: Optional[MedicalResearchBrief]
    research_brief: Optional[str]
    research_results: Annotated[list[ResearchTaskResult], research_results_reducer]
    raw_notes: Annotated[list[str], override_reducer]
    notes: Annotated[list[str], override_reducer]
    final_report: str

class SupervisorState(TypedDict):
    """State for the supervisor that manages research tasks."""
    
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    medical_research_brief: MedicalResearchBrief
    research_brief: str
    research_results: Annotated[list[ResearchTaskResult], research_results_reducer]
    notes: Annotated[list[str], override_reducer]
    research_iterations: int
    raw_notes: Annotated[list[str], override_reducer]

class ResearcherState(TypedDict):
    """State for individual researchers conducting research."""
    
    task: MedicalResearchTask
    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int
    research_topic: str
    source_records: Annotated[list[SourceRecord], source_records_reducer]
    evidence_records: Annotated[list[EvidenceRecord], evidence_records_reducer]
    findings: Annotated[list[ResearchFinding], findings_reducer]
    research_task_status: ResearchTaskStatus
    compressed_research: str
    research_task_result: ResearchTaskResult
    raw_notes: Annotated[list[str], override_reducer]

class ResearcherOutputState(BaseModel):
    """Output state from individual researchers."""
    
    research_task_result: ResearchTaskResult
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = Field(default_factory=list)
