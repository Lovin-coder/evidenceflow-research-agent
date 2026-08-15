"""Main LangGraph implementation for the Deep Research agent."""

import asyncio
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
from langgraph.types import Command
from pydantic import ValidationError

from open_deep_research.configuration import (
    Configuration,
)
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
    SupervisorState,
)
from open_deep_research.utils import (
    anthropic_websearch_called,
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

# Initialize a configurable model that we will use throughout the agent
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


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


def _failed_research_result(
    task: MedicalResearchTask,
    error: str,
    *,
    source_records: list[SourceRecord] | None = None,
    evidence_records: list[EvidenceRecord] | None = None,
    findings: list[ResearchFinding] | None = None,
) -> ResearchTaskResult:
    """Create a failed result without discarding materialized research artifacts.

    Args:
        task: Materialized task whose execution or result construction failed.
        error: Stable operational error text exposed across the parent boundary.
        source_records: Sources materialized before the failure, if available.
        evidence_records: Evidence materialized before the failure, if available.
        findings: Findings materialized before the failure, if available.

    Returns:
        A FAILED ResearchTaskResult retaining all available Source, Evidence, and
        Finding references plus their limitations and conflicts.
    """
    preserved_sources = source_records or []
    preserved_evidence = evidence_records or []
    preserved_findings = findings or []
    return ResearchTaskResult(
        task_id=task.task_id,
        status=ResearchTaskStatus.FAILED,
        findings=preserved_findings,
        evidence_ids=[record.evidence_id for record in preserved_evidence],
        source_ids=[record.source_id for record in preserved_sources],
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


async def _invoke_research_task(
    task: MedicalResearchTask,
    config: RunnableConfig,
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
                "researcher_messages": [HumanMessage(content=research_topic)],
                "research_topic": research_topic,
                "source_records": [],
                "evidence_records": [],
                "findings": [],
            },
            config,
        )
        result = ResearchTaskResult.model_validate(observation["research_task_result"])
        if result.task_id != task.task_id:
            raise ValueError("Researcher returned a result for a different task_id")
        return observation
    except Exception as error:
        message = f"execution_failure: {type(error).__name__}: {error}"
        return {
            "research_task_result": _failed_research_result(task, message),
            "compressed_research": message,
            "raw_notes": [],
        }

async def clarify_with_user(state: AgentState, config: RunnableConfig) -> Command[Literal["write_research_brief", "__end__"]]:
    """Analyze user messages and ask clarifying questions if the research scope is unclear.
    
    This function determines whether the user's request needs clarification before proceeding
    with research. If clarification is disabled or not needed, it proceeds directly to research.
    
    Args:
        state: Current agent state containing user messages
        config: Runtime configuration with model settings and preferences
        
    Returns:
        Command to either end with a clarifying question or proceed to research brief
    """
    # Step 1: Check if clarification is enabled in configuration
    configurable = Configuration.from_runnable_config(config)
    if not configurable.allow_clarification:
        # Skip clarification step and proceed directly to research
        return Command(goto="write_research_brief")
    
    # Step 2: Prepare the model for structured clarification analysis
    messages = state["messages"]
    model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }
    
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
            update={"messages": [AIMessage(content=response.question)]}
        )
    else:
        # Proceed to research with verification message
        return Command(
            goto="write_research_brief", 
            update={"messages": [AIMessage(content=response.verification)]}
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
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }
    
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


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor_tools"]]:
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
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }
    
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
            "research_iterations": state.get("research_iterations", 0) + 1
        }
    )

async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor", "__end__"]]:
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
                "research_brief": state.get("research_brief", "")
            }
        )
    
    # Step 2: Process all tool calls together (both think_tool and ConductResearch)
    all_tool_messages = []
    update_payload: dict[str, Any] = {"supervisor_messages": []}
    
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
            *[_invoke_research_task(task, config) for _, task, _ in allowed_calls]
        )
        research_results = []

        for observation, (tool_call, task, runtime_call_id) in zip(
            tool_results, allowed_calls
        ):
            result = ResearchTaskResult.model_validate(observation["research_task_result"])
            research_results.append(result)
            all_tool_messages.append(
                ToolMessage(
                    content=observation.get("compressed_research", result.summary),
                    name=tool_call["name"],
                    tool_call_id=runtime_call_id,
                )
            )

        for _, task, runtime_call_id in overflow_calls:
            overflow_error = (
                "admission_failure: maximum concurrent research units exceeded; "
                f"limit={configurable.max_concurrent_research_units}"
            )
            research_results.append(_failed_research_result(task, overflow_error))
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

async def researcher(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher_tools"]]:
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
    researcher_messages = state.get("researcher_messages", [])
    
    # Get all available research tools (search, MCP, think_tool)
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError(
            "No tools found to conduct research: Please configure either your "
            "search API or add MCP tools to your configuration."
        )
    
    # Step 2: Configure the researcher model with tools
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }
    
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
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1
        }
    )

# Tool Execution Helper Function
async def execute_tool_safely(tool, args, config):
    """Safely execute a tool with error handling."""
    try:
        return await tool.ainvoke(args, config)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


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
            update={"research_task_status": ResearchTaskStatus.SUCCESS},
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
        execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config) 
        for tool_call in tool_calls
    ]
    observations = await asyncio.gather(*tool_execution_tasks)
    
    # Create tool messages from execution results
    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"]
        ) 
        for observation, tool_call in zip(observations, tool_calls)
    ]
    
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
        update={"researcher_messages": tool_outputs}
    )

async def compress_research(state: ResearcherState, config: RunnableConfig):
    """Build typed and legacy outputs from the same Researcher execution.
    
    This function takes all the research findings, tool outputs, and AI messages from
    a researcher's work and distills them into a clean, comprehensive summary while
    preserving all important information and findings. If compression cannot complete,
    the FAILED result still retains Source, Evidence, and Finding objects already
    materialized in Researcher-local state.
    
    Args:
        state: Current researcher state with accumulated research messages
        config: Runtime configuration with compression model settings
        
    Returns:
        Dictionary containing ResearchTaskResult, compressed legacy summary, and raw
        legacy notes from the same execution.
    """
    # Step 1: Configure the compression model
    configurable = Configuration.from_runnable_config(config)
    synthesizer_model = configurable_model.with_config({
        "model": configurable.compression_model,
        "max_tokens": configurable.compression_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.compression_model, config),
        "tags": ["langsmith:nostream"]
    })
    
    # Step 2: Prepare messages for compression
    researcher_messages = list(state.get("researcher_messages", []))
    
    # Add instruction to switch from research mode to compression mode
    researcher_messages.append(HumanMessage(content=compress_research_simple_human_message))
    
    # Step 3: Attempt compression with retry logic for token limit issues
    synthesis_attempts = 0
    max_attempts = 3
    
    while synthesis_attempts < max_attempts:
        try:
            # Create system prompt focused on compression task
            compression_prompt = compress_research_system_prompt.format(date=get_today_str())
            messages = [SystemMessage(content=compression_prompt)] + researcher_messages
            
            # Execute compression
            response = await synthesizer_model.ainvoke(messages)
            
            # Extract raw notes from all tool and AI messages
            raw_notes_content = "\n".join([
                str(message.content) 
                for message in filter_messages(researcher_messages, include_types=["tool", "ai"])
            ])
            
            summary = str(response.content)
            status = state.get("research_task_status", ResearchTaskStatus.SUCCESS)
            limitations = [
                limitation
                for finding in state.get("findings", [])
                for limitation in finding.limitations
            ]
            if status is ResearchTaskStatus.PARTIAL:
                limitations.append(
                    "Research stopped after reaching the configured tool-call budget."
                )
            tool_execution_failed = any(
                isinstance(message, ToolMessage)
                and str(message.content).startswith("Error executing tool:")
                for message in researcher_messages
            )
            if tool_execution_failed:
                status = ResearchTaskStatus.PARTIAL
                limitations.append(
                    "At least one research tool failed during this task execution."
                )
            conflicts = [
                conflict
                for finding in state.get("findings", [])
                for conflict in finding.conflicts
            ]
            result = ResearchTaskResult(
                task_id=state["task"].task_id,
                status=status,
                findings=state.get("findings", []),
                evidence_ids=[
                    record.evidence_id for record in state.get("evidence_records", [])
                ],
                source_ids=[
                    record.source_id for record in state.get("source_records", [])
                ],
                summary=summary,
                limitations=list(dict.fromkeys(limitations)),
                conflicts=list(dict.fromkeys(conflicts)),
                error=None,
            )

            # One execution feeds both paths; legacy text never replaces typed provenance.
            return {
                "research_task_result": result,
                "compressed_research": summary,
                "raw_notes": [raw_notes_content],
            }
            
        except Exception as e:
            synthesis_attempts += 1
            
            # Handle token limit exceeded by removing older messages
            if is_token_limit_exceeded(e, configurable.research_model):
                researcher_messages = remove_up_to_last_ai_message(researcher_messages)
                continue
            
            # For other errors, continue retrying
            continue
    
    # Step 4: Return error result if all attempts failed
    raw_notes_content = "\n".join([
        str(message.content) 
        for message in filter_messages(researcher_messages, include_types=["tool", "ai"])
    ])
    
    error = "compression_failure: maximum retries exceeded"
    # Compression failure must not erase structured work already present in local state.
    return {
        "research_task_result": _failed_research_result(
            state["task"],
            error,
            source_records=state.get("source_records", []),
            evidence_records=state.get("evidence_records", []),
            findings=state.get("findings", []),
        ),
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
    cleared_state = {"notes": {"type": "override", "value": []}}
    findings = "\n".join(notes)
    
    # Step 2: Configure the final report generation model
    configurable = Configuration.from_runnable_config(config)
    writer_model_config = {
        "model": configurable.final_report_model,
        "max_tokens": configurable.final_report_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.final_report_model, config),
        "tags": ["langsmith:nostream"]
    }
    
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
deep_researcher_builder.add_node("final_report_generation", final_report_generation)  # Report generation phase

# Define main workflow edges for sequential execution
deep_researcher_builder.add_edge(START, "clarify_with_user")                       # Entry point
deep_researcher_builder.add_edge("research_supervisor", "final_report_generation") # Research to report
deep_researcher_builder.add_edge("final_report_generation", END)                   # Final exit point

# Compile the complete deep researcher workflow
deep_researcher = deep_researcher_builder.compile()
