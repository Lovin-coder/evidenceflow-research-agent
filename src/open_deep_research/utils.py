"""Utility functions and helpers for the Deep Research agent."""

import asyncio
import logging
import os
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional

import aiohttp
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    MessageLikeRepresentation,
    filter_messages,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import (
    BaseTool,
    InjectedToolArg,
    StructuredTool,
    ToolException,
    tool,
)
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.config import get_store
from mcp import McpError
from tavily import AsyncTavilyClient

from open_deep_research.artifact_store import (
    ArtifactStore,
    artifact_store_from_config,
)
from open_deep_research.configuration import Configuration, SearchAPI
from open_deep_research.domain_models import EvidenceRecord, SourceRecord
from open_deep_research.evidence_ingestion import (
    WebpageSelection,
    build_source_record,
    canonicalize_source_url,
    chunk_source_text,
    is_usable_source_content,
    materialize_evidence,
    normalize_source_text,
    render_researcher_observation,
    sanitize_candidate_selection,
    select_webpage_chunks,
)
from open_deep_research.prompts import summarize_webpage_prompt
from open_deep_research.state import (
    ResearchComplete,
    ResearchExecutionIssue,
    ResearchExecutionSeverity,
    ResearchExecutionStage,
    make_research_execution_issue,
)

##########################
# Tavily Search Tool Utils
##########################
TAVILY_SEARCH_DESCRIPTION = (
    "A search engine optimized for comprehensive, accurate, and trusted results. "
    "Useful for when you need to answer questions about current events."
)


@dataclass(frozen=True, slots=True)
class SearchExecutionResult:
    """Carry authoritative search data separately from bounded model content."""

    model_content: str
    sources: list[SourceRecord]
    evidences: list[EvidenceRecord]
    issues: list[ResearchExecutionIssue]
    tool_call_id: str | None = None

    @property
    def warnings(self) -> list[str]:
        """Project diagnostic messages for compatibility, never Host status logic."""
        return [issue.message for issue in self.issues]


@dataclass(frozen=True, slots=True)
class _ProcessedSearchResult:
    """Carry one accepted provider result through the structured executor."""

    source: SourceRecord
    evidences: list[EvidenceRecord]
    model_content: str
    issues: list[ResearchExecutionIssue]


@tool(description=TAVILY_SEARCH_DESCRIPTION)
async def tavily_search(
    queries: List[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
    config: RunnableConfig = None
) -> str:
    """Fetch and summarize search results from Tavily search API.

    Args:
        queries: List of search queries to execute
        max_results: Maximum number of results to return per query
        topic: Topic filter for search results (general, news, or finance)
        config: Runtime configuration for API keys and model settings

    Returns:
        Formatted string containing summarized search results
    """
    result = await execute_tavily_search_structured(
        queries,
        max_results=max_results,
        topic=topic,
        config=config,
    )
    return result.model_content


async def execute_tavily_search_structured(
    queries: List[str],
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    config: RunnableConfig = None,
    *,
    research_topic: str = "",
    provider_responses: list[dict[str, Any] | BaseException] | None = None,
    selection_model: Any | None = None,
    artifact_store: ArtifactStore | None = None,
    artifact_run_id: str | None = None,
    tool_call_id: str | None = None,
) -> SearchExecutionResult:
    """Execute Tavily and split structured provenance from bounded model context.

    Provider snippets are never used as authoritative Source content. Each usable
    ``raw_content`` result is normalized, persisted, chunked, selected, and Host-
    materialized independently so one result failure cannot erase valid siblings.

    Args:
        queries: Existing agent-visible search queries.
        max_results: Existing per-query provider result limit.
        topic: Existing Tavily topic filter.
        config: Runtime and EvidenceFlow bounds configuration.
        research_topic: Researcher-local task context for semantic selection.
        provider_responses: Optional deterministic provider fixture for tests.
        selection_model: Optional deterministic structured selector for tests.
        artifact_store: Optional run-scoped Store override for tests.
        artifact_run_id: Internal owning-run namespace when no Store is injected.
        tool_call_id: Runtime correlation ID copied into structured execution issues.

    Returns:
        Structured records, issues, and a bounded Evidence-aware model projection.
    """
    search_results = provider_responses
    if search_results is None:
        search_results = await tavily_search_async(
            queries,
            max_results=max_results,
            topic=topic,
            include_raw_content=True,
            config=config,
        )
    retrieved_at = datetime.now(timezone.utc)

    configurable = Configuration.from_runnable_config(config)
    store = artifact_store or artifact_store_from_config(config, artifact_run_id)
    if selection_model is None:
        model_api_key = get_api_key_for_model(configurable.summarization_model, config)
        selection_model = (
            init_chat_model(
                model=configurable.summarization_model,
                max_tokens=configurable.summarization_model_max_tokens,
                api_key=model_api_key,
                tags=["langsmith:nostream"],
            )
            .with_structured_output(WebpageSelection)
            .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        )

    issues_found: list[ResearchExecutionIssue] = []

    def issue(
        *,
        stage: ResearchExecutionStage,
        code: str,
        severity: ResearchExecutionSeverity,
        message: str,
        degrades_task_status: bool,
        occurrence_key: str,
        source_id: str | None = None,
        candidate_id: str | None = None,
    ) -> ResearchExecutionIssue:
        """Build one bounded issue correlated to this search execution."""
        return make_research_execution_issue(
            stage=stage,
            code=code,
            severity=severity,
            message=message,
            degrades_task_status=degrades_task_status,
            tool_call_id=tool_call_id,
            source_id=source_id,
            candidate_id=candidate_id,
            occurrence_key=occurrence_key,
        )

    unique_results: dict[str, dict[str, Any]] = {}
    for response_index, response in enumerate(search_results, start=1):
        if isinstance(response, BaseException):
            issues_found.append(
                issue(
                    stage=ResearchExecutionStage.PROVIDER,
                    code="provider_query_failed",
                    severity=ResearchExecutionSeverity.ERROR,
                    message=(
                        f"Tavily query {response_index} failed with "
                        f"{type(response).__name__}."
                    ),
                    degrades_task_status=True,
                    occurrence_key=f"query:{response_index}",
                )
            )
            continue
        query = str(response.get("query", ""))
        results = response.get("results", [])
        if not isinstance(results, list):
            issues_found.append(
                issue(
                    stage=ResearchExecutionStage.PROVIDER,
                    code="invalid_provider_results_payload",
                    severity=ResearchExecutionSeverity.ERROR,
                    message=(
                        f"Tavily query {response_index} returned an invalid results payload."
                    ),
                    degrades_task_status=True,
                    occurrence_key=f"query:{response_index}",
                )
            )
            continue
        for result_index, provider_result in enumerate(results, start=1):
            if not isinstance(provider_result, dict):
                issues_found.append(
                    issue(
                        stage=ResearchExecutionStage.PROVIDER,
                        code="invalid_provider_result",
                        severity=ResearchExecutionSeverity.ERROR,
                        message=(
                            f"Tavily result {response_index}.{result_index} was not an object."
                        ),
                        degrades_task_status=True,
                        occurrence_key=f"result:{response_index}:{result_index}",
                    )
                )
                continue
            url = str(provider_result.get("url") or "")
            dedup_key = canonicalize_source_url(url) or (
                f"missing-url:{response_index}:{result_index}"
            )
            if dedup_key not in unique_results:
                unique_results[dedup_key] = {**provider_result, "query": query}

    model_level_issues = list(issues_found)

    async def process_result(
        ordinal: int, provider_result: dict[str, Any]
    ) -> _ProcessedSearchResult | ResearchExecutionIssue:
        raw_content = provider_result.get("raw_content")
        title = str(provider_result.get("title") or "Untitled source")
        url = str(provider_result.get("url") or "")
        label = url or f"result {ordinal}"
        if not is_usable_source_content(raw_content):
            return issue(
                stage=ResearchExecutionStage.CONTENT_GATE,
                code="unusable_provider_content",
                severity=ResearchExecutionSeverity.WARNING,
                message=f"Skipped {label}: no usable provider raw_content.",
                degrades_task_status=False,
                occurrence_key=f"result:{ordinal}:raw",
            )
        assert isinstance(raw_content, str)
        result_issues: list[ResearchExecutionIssue] = []
        bounded_raw_content = raw_content[: configurable.max_content_length]
        if len(raw_content) > configurable.max_content_length:
            result_issues.append(
                issue(
                    stage=ResearchExecutionStage.CONTENT_GATE,
                    code="source_content_bounded",
                    severity=ResearchExecutionSeverity.WARNING,
                    message=(
                        "Source content was bounded to "
                        f"{configurable.max_content_length} characters before normalization."
                    ),
                    degrades_task_status=False,
                    occurrence_key=f"result:{ordinal}:content-bound",
                )
            )
        normalized_text = normalize_source_text(bounded_raw_content)
        if not is_usable_source_content(normalized_text):
            return issue(
                stage=ResearchExecutionStage.CONTENT_GATE,
                code="unusable_normalized_content",
                severity=ResearchExecutionSeverity.WARNING,
                message=f"Skipped {label}: normalized raw_content was not usable.",
                degrades_task_status=False,
                occurrence_key=f"result:{ordinal}:normalized",
            )
        artifact_ref = store.put_text(normalized_text)
        source = build_source_record(
            url=url,
            title=title,
            provider="tavily",
            artifact_ref=artifact_ref,
            normalized_text=normalized_text,
            retrieved_at=retrieved_at,
            published_at=provider_result.get("published_date"),
        )
        candidates = chunk_source_text(normalized_text)
        try:
            selection = await asyncio.wait_for(
                select_webpage_chunks(
                    selection_model,
                    research_topic=research_topic or "General web research",
                    query=str(provider_result.get("query") or ""),
                    title=title,
                    url=url,
                    candidates=candidates,
                    max_selected=configurable.max_selected_chunks_per_source,
                    validate_ids=False,
                ),
                timeout=60.0,
            )
            selection, selection_rejections = sanitize_candidate_selection(
                selection,
                candidates,
                max_selected=configurable.max_selected_chunks_per_source,
            )
            result_issues.extend(
                issue(
                    stage=ResearchExecutionStage.SELECTION,
                    code=rejection.code,
                    severity=ResearchExecutionSeverity.WARNING,
                    message=rejection.message,
                    degrades_task_status=True,
                    occurrence_key=f"result:{ordinal}:{rejection.candidate_id}",
                    source_id=source.source_id,
                    candidate_id=rejection.candidate_id,
                )
                for rejection in selection_rejections
            )
            evidences = []
            for selected_chunk_id in selection.selected_chunk_ids:
                single_selection = WebpageSelection(
                    summary=selection.summary,
                    selected_chunk_ids=[selected_chunk_id],
                )
                try:
                    evidences.extend(
                        materialize_evidence(
                            source=source,
                            candidates=candidates,
                            selection=single_selection,
                            artifact_store=store,
                            max_selected=1,
                        )
                    )
                except Exception as evidence_error:
                    result_issues.append(
                        issue(
                            stage=ResearchExecutionStage.MATERIALIZATION,
                            code="evidence_materialization_failed",
                            severity=ResearchExecutionSeverity.ERROR,
                            message=(
                                f"Candidate {selected_chunk_id} failed provenance "
                                "materialization and was rejected with "
                                f"{type(evidence_error).__name__}."
                            ),
                            degrades_task_status=True,
                            occurrence_key=(
                                f"result:{ordinal}:candidate:{selected_chunk_id}"
                            ),
                            source_id=source.source_id,
                            candidate_id=selected_chunk_id,
                        )
                    )
            summary = selection.summary
        except Exception as error:
            result_issues.append(
                issue(
                    stage=ResearchExecutionStage.SELECTION,
                    code="evidence_selection_failed",
                    severity=ResearchExecutionSeverity.ERROR,
                    message=(
                        "Evidence selection/materialization failed; accepted Source was "
                        f"preserved ({type(error).__name__})."
                    ),
                    degrades_task_status=True,
                    occurrence_key=f"result:{ordinal}:selection",
                    source_id=source.source_id,
                )
            )
            evidences = []
            summary = "Evidence selection was unavailable for this accepted Source."
        model_content = render_researcher_observation(
            source=source,
            summary=summary,
            evidence=evidences,
            warnings=[item.message for item in result_issues],
        )
        return _ProcessedSearchResult(
            source=source,
            evidences=evidences,
            model_content=model_content,
            issues=result_issues,
        )

    processed_or_errors = await asyncio.gather(
        *(
            process_result(index, provider_result)
            for index, provider_result in enumerate(unique_results.values(), start=1)
        ),
        return_exceptions=True,
    )
    processed: list[_ProcessedSearchResult] = []
    for index, item in enumerate(processed_or_errors, start=1):
        if isinstance(item, BaseException):
            ingestion_issue = issue(
                stage=ResearchExecutionStage.MATERIALIZATION,
                code="result_ingestion_failed",
                severity=ResearchExecutionSeverity.ERROR,
                message=(
                    f"Tavily result {index} failed ingestion with "
                    f"{type(item).__name__}."
                ),
                degrades_task_status=True,
                occurrence_key=f"result:{index}:ingestion",
            )
            issues_found.append(ingestion_issue)
            model_level_issues.append(ingestion_issue)
        elif isinstance(item, ResearchExecutionIssue):
            issues_found.append(item)
            model_level_issues.append(item)
        else:
            processed.append(item)
            issues_found.extend(item.issues)

    sources = [item.source for item in processed]
    evidences = [record for item in processed for record in item.evidences]
    model_blocks = [item.model_content for item in processed]
    if not model_blocks:
        model_blocks.append("No authoritative Sources or Evidence were accepted.")
    if model_level_issues:
        model_blocks.extend(
            (
                "Ingestion warnings (process metadata, not Evidence):",
                *(f"- {item.message}" for item in model_level_issues),
            )
        )
    model_content = _join_bounded_model_blocks(
        model_blocks,
        max_chars=configurable.max_search_tool_message_chars,
    )
    return SearchExecutionResult(
        model_content=model_content,
        sources=sources,
        evidences=evidences,
        issues=issues_found,
        tool_call_id=tool_call_id,
    )


def _join_bounded_model_blocks(blocks: list[str], *, max_chars: int) -> str:
    """Keep whole Evidence-aware blocks while enforcing the model-context bound."""
    separator = "\n\n---\n\n"
    marker = "[Additional search observations omitted at configured bound.]"
    admitted: list[str] = []
    current_length = 0
    for block in blocks:
        added_length = len(block) + (len(separator) if admitted else 0)
        if current_length + added_length > max_chars:
            break
        admitted.append(block)
        current_length += added_length
    if len(admitted) == len(blocks):
        return separator.join(admitted)
    marker_length = len(marker) + (len(separator) if admitted else 0)
    while admitted and current_length + marker_length > max_chars:
        removed = admitted.pop()
        current_length -= len(removed)
        if admitted:
            current_length -= len(separator)
        marker_length = len(marker) + (len(separator) if admitted else 0)
    if marker_length <= max_chars:
        admitted.append(marker)
    return separator.join(admitted)

async def tavily_search_async(
    search_queries, 
    max_results: int = 5, 
    topic: Literal["general", "news", "finance"] = "general", 
    include_raw_content: bool = True, 
    config: RunnableConfig = None
):
    """Execute multiple Tavily search queries asynchronously.
    
    Args:
        search_queries: List of search query strings to execute
        max_results: Maximum number of results per query
        topic: Topic category for filtering results
        include_raw_content: Whether to include full webpage content
        config: Runtime configuration for API key access
        
    Returns:
        List of search result dictionaries from Tavily API
    """
    # Initialize the Tavily client with API key from config
    tavily_client = AsyncTavilyClient(api_key=get_tavily_api_key(config))
    
    # Create search tasks for parallel execution
    search_tasks = [
        tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic
        )
        for query in search_queries
    ]
    
    # Preserve successful sibling queries when one provider request fails.
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    return search_results

async def summarize_webpage(model: BaseChatModel, webpage_content: str) -> str:
    """Summarize webpage content using AI model with timeout protection.
    
    Args:
        model: The chat model configured for summarization
        webpage_content: Raw webpage content to be summarized
        
    Returns:
        Formatted summary, or a bounded non-Evidence failure observation.
    """
    try:
        # Create prompt with current date context
        prompt_content = summarize_webpage_prompt.format(
            webpage_content=webpage_content, 
            date=get_today_str()
        )
        
        # Execute summarization with timeout to prevent hanging
        summary = await asyncio.wait_for(
            model.ainvoke([HumanMessage(content=prompt_content)]),
            timeout=60.0  # 60 second timeout for summarization
        )
        
        # Format the summary with structured sections
        formatted_summary = (
            f"<summary>\n{summary.summary}\n</summary>\n\n"
            f"<key_excerpts>\n{summary.key_excerpts}\n</key_excerpts>"
        )
        
        return formatted_summary
        
    except asyncio.TimeoutError:
        logging.warning("Summarization timed out after 60 seconds")
        return "Webpage summarization unavailable; no Evidence was materialized."
    except Exception as e:
        logging.warning(f"Summarization failed with error: {str(e)}")
        return "Webpage summarization unavailable; no Evidence was materialized."

##########################
# Reflection Tool Utils
##########################

@tool(description="Strategic reflection tool for research planning")
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"

##########################
# MCP Utils
##########################

async def get_mcp_access_token(
    supabase_token: str,
    base_mcp_url: str,
) -> Optional[Dict[str, Any]]:
    """Exchange Supabase token for MCP access token using OAuth token exchange.
    
    Args:
        supabase_token: Valid Supabase authentication token
        base_mcp_url: Base URL of the MCP server
        
    Returns:
        Token data dictionary if successful, None if failed
    """
    try:
        # Prepare OAuth token exchange request data
        form_data = {
            "client_id": "mcp_default",
            "subject_token": supabase_token,
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "resource": base_mcp_url.rstrip("/") + "/mcp",
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        }
        
        # Execute token exchange request
        async with aiohttp.ClientSession() as session:
            token_url = base_mcp_url.rstrip("/") + "/oauth/token"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            async with session.post(token_url, headers=headers, data=form_data) as response:
                if response.status == 200:
                    # Successfully obtained token
                    token_data = await response.json()
                    return token_data
                else:
                    # Log error details for debugging
                    response_text = await response.text()
                    logging.error(f"Token exchange failed: {response_text}")
                    
    except Exception as e:
        logging.error(f"Error during token exchange: {e}")
    
    return None

async def get_tokens(config: RunnableConfig):
    """Retrieve stored authentication tokens with expiration validation.
    
    Args:
        config: Runtime configuration containing thread and user identifiers
        
    Returns:
        Token dictionary if valid and not expired, None otherwise
    """
    store = get_store()
    
    # Extract required identifiers from config
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        return None
        
    user_id = config.get("metadata", {}).get("owner")
    if not user_id:
        return None
    
    # Retrieve stored tokens
    tokens = await store.aget((user_id, "tokens"), "data")
    if not tokens:
        return None
    
    # Check token expiration
    expires_in = tokens.value.get("expires_in")  # seconds until expiration
    created_at = tokens.created_at  # datetime of token creation
    current_time = datetime.now(timezone.utc)
    expiration_time = created_at + timedelta(seconds=expires_in)
    
    if current_time > expiration_time:
        # Token expired, clean up and return None
        await store.adelete((user_id, "tokens"), "data")
        return None

    return tokens.value

async def set_tokens(config: RunnableConfig, tokens: dict[str, Any]):
    """Store authentication tokens in the configuration store.
    
    Args:
        config: Runtime configuration containing thread and user identifiers
        tokens: Token dictionary to store
    """
    store = get_store()
    
    # Extract required identifiers from config
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        return
        
    user_id = config.get("metadata", {}).get("owner")
    if not user_id:
        return
    
    # Store the tokens
    await store.aput((user_id, "tokens"), "data", tokens)

async def fetch_tokens(config: RunnableConfig) -> dict[str, Any]:
    """Fetch and refresh MCP tokens, obtaining new ones if needed.
    
    Args:
        config: Runtime configuration with authentication details
        
    Returns:
        Valid token dictionary, or None if unable to obtain tokens
    """
    # Try to get existing valid tokens first
    current_tokens = await get_tokens(config)
    if current_tokens:
        return current_tokens
    
    # Extract Supabase token for new token exchange
    supabase_token = config.get("configurable", {}).get("x-supabase-access-token")
    if not supabase_token:
        return None
    
    # Extract MCP configuration
    mcp_config = config.get("configurable", {}).get("mcp_config")
    if not mcp_config or not mcp_config.get("url"):
        return None
    
    # Exchange Supabase token for MCP tokens
    mcp_tokens = await get_mcp_access_token(supabase_token, mcp_config.get("url"))
    if not mcp_tokens:
        return None

    # Store the new tokens and return them
    await set_tokens(config, mcp_tokens)
    return mcp_tokens

def wrap_mcp_authenticate_tool(tool: StructuredTool) -> StructuredTool:
    """Wrap MCP tool with comprehensive authentication and error handling.
    
    Args:
        tool: The MCP structured tool to wrap
        
    Returns:
        Enhanced tool with authentication error handling
    """
    original_coroutine = tool.coroutine
    
    async def authentication_wrapper(**kwargs):
        """Enhanced coroutine with MCP error handling and user-friendly messages."""
        
        def _find_mcp_error_in_exception_chain(exc: BaseException) -> McpError | None:
            """Recursively search for MCP errors in exception chains."""
            if isinstance(exc, McpError):
                return exc
            
            # Handle ExceptionGroup (Python 3.11+) by checking attributes
            if hasattr(exc, 'exceptions'):
                for sub_exception in exc.exceptions:
                    if found_error := _find_mcp_error_in_exception_chain(sub_exception):
                        return found_error
            return None
        
        try:
            # Execute the original tool functionality
            return await original_coroutine(**kwargs)
            
        except BaseException as original_error:
            # Search for MCP-specific errors in the exception chain
            mcp_error = _find_mcp_error_in_exception_chain(original_error)
            if not mcp_error:
                # Not an MCP error, re-raise the original exception
                raise original_error
            
            # Handle MCP-specific error cases
            error_details = mcp_error.error
            error_code = getattr(error_details, "code", None)
            error_data = getattr(error_details, "data", None) or {}
            
            # Check for authentication/interaction required error
            if error_code == -32003:  # Interaction required error code
                message_payload = error_data.get("message", {})
                error_message = "Required interaction"
                
                # Extract user-friendly message if available
                if isinstance(message_payload, dict):
                    error_message = message_payload.get("text") or error_message
                
                # Append URL if provided for user reference
                if url := error_data.get("url"):
                    error_message = f"{error_message} {url}"
                
                raise ToolException(error_message) from original_error
            
            # For other MCP errors, re-raise the original
            raise original_error
    
    # Replace the tool's coroutine with our enhanced version
    tool.coroutine = authentication_wrapper
    return tool

async def load_mcp_tools(
    config: RunnableConfig,
    existing_tool_names: set[str],
) -> list[BaseTool]:
    """Load and configure MCP (Model Context Protocol) tools with authentication.
    
    Args:
        config: Runtime configuration containing MCP server details
        existing_tool_names: Set of tool names already in use to avoid conflicts
        
    Returns:
        List of configured MCP tools ready for use
    """
    configurable = Configuration.from_runnable_config(config)
    
    # Step 1: Handle authentication if required
    if configurable.mcp_config and configurable.mcp_config.auth_required:
        mcp_tokens = await fetch_tokens(config)
    else:
        mcp_tokens = None
    
    # Step 2: Validate configuration requirements
    config_valid = (
        configurable.mcp_config and 
        configurable.mcp_config.url and 
        configurable.mcp_config.tools and 
        (mcp_tokens or not configurable.mcp_config.auth_required)
    )
    
    if not config_valid:
        return []
    
    # Step 3: Set up MCP server connection
    server_url = configurable.mcp_config.url.rstrip("/") + "/mcp"
    
    # Configure authentication headers if tokens are available
    auth_headers = None
    if mcp_tokens:
        auth_headers = {"Authorization": f"Bearer {mcp_tokens['access_token']}"}
    
    mcp_server_config = {
        "server_1": {
            "url": server_url,
            "headers": auth_headers,
            "transport": "streamable_http"
        }
    }
    # TODO: When Multi-MCP Server support is merged in OAP, update this code
    
    # Step 4: Load tools from MCP server
    try:
        client = MultiServerMCPClient(mcp_server_config)
        available_mcp_tools = await client.get_tools()
    except Exception:
        # If MCP server connection fails, return empty list
        return []
    
    # Step 5: Filter and configure tools
    configured_tools = []
    for mcp_tool in available_mcp_tools:
        # Skip tools with conflicting names
        if mcp_tool.name in existing_tool_names:
            warnings.warn(
                f"MCP tool '{mcp_tool.name}' conflicts with existing tool name - skipping"
            )
            continue
        
        # Only include tools specified in configuration
        if mcp_tool.name not in set(configurable.mcp_config.tools):
            continue
        
        # Wrap tool with authentication handling and add to list
        enhanced_tool = wrap_mcp_authenticate_tool(mcp_tool)
        configured_tools.append(enhanced_tool)
    
    return configured_tools


##########################
# Tool Utils
##########################

async def get_search_tool(search_api: SearchAPI):
    """Configure and return search tools based on the specified API provider.
    
    Args:
        search_api: The search API provider to use (Anthropic, OpenAI, Tavily, or None)
        
    Returns:
        List of configured search tool objects for the specified provider
    """
    if search_api == SearchAPI.ANTHROPIC:
        # Anthropic's native web search with usage limits
        return [{
            "type": "web_search_20250305", 
            "name": "web_search", 
            "max_uses": 5
        }]
        
    elif search_api == SearchAPI.OPENAI:
        # OpenAI's web search preview functionality
        return [{"type": "web_search_preview"}]
        
    elif search_api == SearchAPI.TAVILY:
        # Configure Tavily search tool with metadata
        search_tool = tavily_search
        search_tool.metadata = {
            **(search_tool.metadata or {}), 
            "type": "search", 
            "name": "web_search"
        }
        return [search_tool]
        
    elif search_api == SearchAPI.NONE:
        # No search functionality configured
        return []
        
    # Default fallback for unknown search API types
    return []
    
async def get_all_tools(config: RunnableConfig):
    """Assemble complete toolkit including research, search, and MCP tools.
    
    Args:
        config: Runtime configuration specifying search API and MCP settings
        
    Returns:
        List of all configured and available tools for research operations
    """
    # Start with core research tools
    tools = [tool(ResearchComplete), think_tool]
    
    # Add configured search tools
    configurable = Configuration.from_runnable_config(config)
    search_api = SearchAPI(get_config_value(configurable.search_api))
    search_tools = await get_search_tool(search_api)
    tools.extend(search_tools)
    
    # Track existing tool names to prevent conflicts
    existing_tool_names = {
        tool.name if hasattr(tool, "name") else tool.get("name", "web_search") 
        for tool in tools
    }
    
    # Add MCP tools if configured
    mcp_tools = await load_mcp_tools(config, existing_tool_names)
    tools.extend(mcp_tools)
    
    return tools

def get_notes_from_tool_calls(messages: list[MessageLikeRepresentation]):
    """Extract notes from tool call messages."""
    return [tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")]

##########################
# Model Provider Native Websearch Utils
##########################

def anthropic_websearch_called(response):
    """Detect if Anthropic's native web search was used in the response.
    
    Args:
        response: The response object from Anthropic's API
        
    Returns:
        True if web search was called, False otherwise
    """
    try:
        # Navigate through the response metadata structure
        usage = response.response_metadata.get("usage")
        if not usage:
            return False
        
        # Check for server-side tool usage information
        server_tool_use = usage.get("server_tool_use")
        if not server_tool_use:
            return False
        
        # Look for web search request count
        web_search_requests = server_tool_use.get("web_search_requests")
        if web_search_requests is None:
            return False
        
        # Return True if any web search requests were made
        return web_search_requests > 0
        
    except (AttributeError, TypeError):
        # Handle cases where response structure is unexpected
        return False

def openai_websearch_called(response):
    """Detect if OpenAI's web search functionality was used in the response.
    
    Args:
        response: The response object from OpenAI's API
        
    Returns:
        True if web search was called, False otherwise
    """
    # Check for tool outputs in the response metadata
    tool_outputs = response.additional_kwargs.get("tool_outputs")
    if not tool_outputs:
        return False
    
    # Look for web search calls in the tool outputs
    for tool_output in tool_outputs:
        if tool_output.get("type") == "web_search_call":
            return True
    
    return False


##########################
# Token Limit Exceeded Utils
##########################

def is_token_limit_exceeded(exception: Exception, model_name: str = None) -> bool:
    """Determine if an exception indicates a token/context limit was exceeded.
    
    Args:
        exception: The exception to analyze
        model_name: Optional model name to optimize provider detection
        
    Returns:
        True if the exception indicates a token limit was exceeded, False otherwise
    """
    error_str = str(exception).lower()
    
    # Step 1: Determine provider from model name if available
    provider = None
    if model_name:
        model_str = str(model_name).lower()
        if model_str.startswith('openai:'):
            provider = 'openai'
        elif model_str.startswith('anthropic:'):
            provider = 'anthropic'
        elif model_str.startswith('gemini:') or model_str.startswith('google:'):
            provider = 'gemini'
    
    # Step 2: Check provider-specific token limit patterns
    if provider == 'openai':
        return _check_openai_token_limit(exception, error_str)
    elif provider == 'anthropic':
        return _check_anthropic_token_limit(exception, error_str)
    elif provider == 'gemini':
        return _check_gemini_token_limit(exception, error_str)
    
    # Step 3: If provider unknown, check all providers
    return (
        _check_openai_token_limit(exception, error_str) or
        _check_anthropic_token_limit(exception, error_str) or
        _check_gemini_token_limit(exception, error_str)
    )

def _check_openai_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates OpenAI token limit exceeded."""
    # Analyze exception metadata
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')
    
    # Check if this is an OpenAI exception
    is_openai_exception = (
        'openai' in exception_type.lower() or 
        'openai' in module_name.lower()
    )
    
    # Check for typical OpenAI token limit error types
    is_request_error = class_name in ['BadRequestError', 'InvalidRequestError']
    
    if is_openai_exception and is_request_error:
        # Look for token-related keywords in error message
        token_keywords = ['token', 'context', 'length', 'maximum context', 'reduce']
        if any(keyword in error_str for keyword in token_keywords):
            return True
    
    # Check for specific OpenAI error codes
    if hasattr(exception, 'code') and hasattr(exception, 'type'):
        error_code = getattr(exception, 'code', '')
        error_type = getattr(exception, 'type', '')
        
        if (error_code == 'context_length_exceeded' or
            error_type == 'invalid_request_error'):
            return True
    
    return False

def _check_anthropic_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates Anthropic token limit exceeded."""
    # Analyze exception metadata
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')
    
    # Check if this is an Anthropic exception
    is_anthropic_exception = (
        'anthropic' in exception_type.lower() or 
        'anthropic' in module_name.lower()
    )
    
    # Check for Anthropic-specific error patterns
    is_bad_request = class_name == 'BadRequestError'
    
    if is_anthropic_exception and is_bad_request:
        # Anthropic uses specific error messages for token limits
        if 'prompt is too long' in error_str:
            return True
    
    return False

def _check_gemini_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates Google/Gemini token limit exceeded."""
    # Analyze exception metadata
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')
    
    # Check if this is a Google/Gemini exception
    is_google_exception = (
        'google' in exception_type.lower() or 
        'google' in module_name.lower()
    )
    
    # Check for Google-specific resource exhaustion errors
    is_resource_exhausted = class_name in [
        'ResourceExhausted', 
        'GoogleGenerativeAIFetchError'
    ]
    
    if is_google_exception and is_resource_exhausted:
        return True
    
    # Check for specific Google API resource exhaustion patterns
    if 'google.api_core.exceptions.resourceexhausted' in exception_type.lower():
        return True
    
    return False

# NOTE: This may be out of date or not applicable to your models. Please update this as needed.
MODEL_TOKEN_LIMITS = {
    "openai:gpt-4.1-mini": 1047576,
    "openai:gpt-4.1-nano": 1047576,
    "openai:gpt-4.1": 1047576,
    "openai:gpt-4o-mini": 128000,
    "openai:gpt-4o": 128000,
    "openai:o4-mini": 200000,
    "openai:o3-mini": 200000,
    "openai:o3": 200000,
    "openai:o3-pro": 200000,
    "openai:o1": 200000,
    "openai:o1-pro": 200000,
    "anthropic:claude-opus-4": 200000,
    "anthropic:claude-sonnet-4": 200000,
    "anthropic:claude-3-7-sonnet": 200000,
    "anthropic:claude-3-5-sonnet": 200000,
    "anthropic:claude-3-5-haiku": 200000,
    "google:gemini-1.5-pro": 2097152,
    "google:gemini-1.5-flash": 1048576,
    "google:gemini-pro": 32768,
    "cohere:command-r-plus": 128000,
    "cohere:command-r": 128000,
    "cohere:command-light": 4096,
    "cohere:command": 4096,
    "mistral:mistral-large": 32768,
    "mistral:mistral-medium": 32768,
    "mistral:mistral-small": 32768,
    "mistral:mistral-7b-instruct": 32768,
    "ollama:codellama": 16384,
    "ollama:llama2:70b": 4096,
    "ollama:llama2:13b": 4096,
    "ollama:llama2": 4096,
    "ollama:mistral": 32768,
    "bedrock:us.amazon.nova-premier-v1:0": 1000000,
    "bedrock:us.amazon.nova-pro-v1:0": 300000,
    "bedrock:us.amazon.nova-lite-v1:0": 300000,
    "bedrock:us.amazon.nova-micro-v1:0": 128000,
    "bedrock:us.anthropic.claude-3-7-sonnet-20250219-v1:0": 200000,
    "bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0": 200000,
    "bedrock:us.anthropic.claude-opus-4-20250514-v1:0": 200000,
    "anthropic.claude-opus-4-1-20250805-v1:0": 200000,
}

def get_model_token_limit(model_string):
    """Look up the token limit for a specific model.
    
    Args:
        model_string: The model identifier string to look up
        
    Returns:
        Token limit as integer if found, None if model not in lookup table
    """
    # Search through known model token limits
    for model_key, token_limit in MODEL_TOKEN_LIMITS.items():
        if model_key in model_string:
            return token_limit
    
    # Model not found in lookup table
    return None

def remove_up_to_last_ai_message(messages: list[MessageLikeRepresentation]) -> list[MessageLikeRepresentation]:
    """Truncate message history by removing up to the last AI message.
    
    This is useful for handling token limit exceeded errors by removing recent context.
    
    Args:
        messages: List of message objects to truncate
        
    Returns:
        Truncated message list up to (but not including) the last AI message
    """
    # Search backwards through messages to find the last AI message
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            # Return everything up to (but not including) the last AI message
            return messages[:i]
    
    # No AI messages found, return original list
    return messages

##########################
# Misc Utils
##########################

def get_today_str() -> str:
    """Get current date formatted for display in prompts and outputs.
    
    Returns:
        Human-readable date string in format like 'Mon Jan 15, 2024'
    """
    now = datetime.now()
    return f"{now:%a} {now:%b} {now.day}, {now:%Y}"

def get_config_value(value):
    """Extract value from configuration, handling enums and None values."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    elif isinstance(value, dict):
        return value
    else:
        return value.value

def get_api_key_for_model(model_name: str, config: RunnableConfig):
    """Get API key for a specific model from environment or config."""
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    model_name = model_name.lower()
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        if model_name.startswith("openai:"):
            return api_keys.get("OPENAI_API_KEY")
        elif model_name.startswith("anthropic:"):
            return api_keys.get("ANTHROPIC_API_KEY")
        elif model_name.startswith("google"):
            return api_keys.get("GOOGLE_API_KEY")
        return None
    else:
        if model_name.startswith("openai:"): 
            return os.getenv("OPENAI_API_KEY")
        elif model_name.startswith("anthropic:"):
            return os.getenv("ANTHROPIC_API_KEY")
        elif model_name.startswith("google"):
            return os.getenv("GOOGLE_API_KEY")
        return None

def get_tavily_api_key(config: RunnableConfig):
    """Get Tavily API key from environment or config."""
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        return api_keys.get("TAVILY_API_KEY")
    else:
        return os.getenv("TAVILY_API_KEY")
