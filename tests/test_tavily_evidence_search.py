"""Regression tests for P2-S4 structured Tavily execution."""

from datetime import datetime

import pytest

import open_deep_research.utils as search_runtime
from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.evidence_ingestion import (
    ProvenanceValidationError,
    WebpageSelection,
    parse_locator,
)
from open_deep_research.utils import (
    execute_tavily_search_structured,
    tavily_search,
)


class SelectingModel:
    """Select the first Candidate from each deterministic prompt."""

    async def ainvoke(self, messages):
        """Return only model-owned summary and Candidate identities."""
        prompt = messages[0].content
        return WebpageSelection(
            summary="Derived clinical summary.",
            selected_chunk_ids=["C001"] if "[C001]" in prompt else [],
        )


class SelectiveFailingModel(SelectingModel):
    """Fail one Source selection while allowing a sibling Source to succeed."""

    async def ainvoke(self, messages):
        """Raise only for the source explicitly marked as unavailable."""
        if "fail-selection" in messages[0].content:
            raise RuntimeError("selector unavailable")
        return await super().ainvoke(messages)


class MixedIdentityModel(SelectingModel):
    """Return one valid, one unknown, and one over-bound Candidate identity."""

    async def ainvoke(self, _messages):
        return WebpageSelection(
            summary="Derived mixed selection.",
            selected_chunk_ids=["C001", "C999", "C002"],
        )


class TwoCandidateModel(SelectingModel):
    """Select two known Candidates for per-Candidate failure isolation."""

    async def ainvoke(self, _messages):
        return WebpageSelection(
            summary="Derived two-Candidate selection.",
            selected_chunk_ids=["C001", "C002"],
        )


def provider_response() -> dict:
    """Return one usable deterministic Tavily-like fixture."""
    return {
        "query": "treatment effectiveness",
        "results": [
            {
                "title": "Clinical guideline",
                "url": "https://example.test/guideline?utm_source=search",
                "content": "Provider snippet must not become Evidence.",
                "published_date": "2025-04-18",
                "raw_content": (
                    "Recommendation\r\n\r\nAdults should discuss benefits and harms "
                    "with a clinician before individualized treatment.\r\n\r\n"
                    "The evidence review reported fewer recurrent events without a "
                    "clear difference in serious adverse events."
                ),
            }
        ],
    }


@pytest.mark.asyncio
async def test_structured_tavily_builds_dual_channel_exact_provenance(tmp_path) -> None:
    """Prove usable raw content becomes structured data plus bounded observation."""
    store = LocalFileArtifactStore(tmp_path, "run-one")

    result = await execute_tavily_search_structured(
        ["treatment effectiveness"],
        config={"configurable": {"max_search_tool_message_chars": 4_000}},
        research_topic="Compare clinical benefits and harms.",
        provider_responses=[provider_response()],
        selection_model=SelectingModel(),
        artifact_store=store,
    )

    assert len(result.sources) == len(result.evidences) == 1
    source = result.sources[0]
    evidence = result.evidences[0]
    artifact = store.get_text(source.artifact_ref)
    start, end = parse_locator(evidence.locator)
    assert artifact[start:end] == evidence.excerpt
    assert evidence.source_id == source.source_id
    assert evidence.evidence_id in result.model_content
    assert evidence.excerpt in result.model_content
    assert "Derived clinical summary" in result.model_content
    assert "derived, non-evidence" in result.model_content
    assert "Provider snippet must not become Evidence" not in result.model_content
    assert "\r" not in artifact
    assert result.warnings == []
    assert source.metadata["published_at"] == "2025-04-18"
    retrieved_at = datetime.fromisoformat(source.metadata["retrieved_at"])
    assert retrieved_at.utcoffset() is not None
    assert retrieved_at.utcoffset().total_seconds() == 0
    assert set(source.metadata) == {
        "provider",
        "title",
        "url",
        "retrieved_at",
        "published_at",
    }


@pytest.mark.asyncio
async def test_tavily_metadata_omits_unmapped_and_malformed_fields(tmp_path) -> None:
    """Map only the frozen reliable Tavily surface and reject malformed dates."""
    response = provider_response()
    response["results"][0].update(
        {
            "published_date": "not-a-date",
            "publisher": "Unverified publisher",
            "authors": "Unverified authors",
            "document_type": "Unverified type",
            "retrieval_score": "0.99",
            "images": ["https://example.test/image.png"],
            "favicon": "https://example.test/favicon.ico",
        }
    )

    result = await execute_tavily_search_structured(
        ["treatment effectiveness"],
        provider_responses=[response],
        selection_model=SelectingModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
    )

    assert set(result.sources[0].metadata) == {
        "provider",
        "title",
        "url",
        "retrieved_at",
    }


@pytest.mark.asyncio
async def test_unusable_content_and_query_failure_create_warnings_not_domain_records(
    tmp_path,
) -> None:
    """Keep snippets, provider errors, and missing raw content outside the Domain."""
    response = {
        "query": "missing content",
        "results": [
            {
                "title": "Snippet only",
                "url": "https://example.test/snippet",
                "content": "This provider snippet is not authoritative.",
                "raw_content": None,
            }
        ],
    }

    result = await execute_tavily_search_structured(
        ["missing content", "failed query"],
        provider_responses=[response, RuntimeError("provider unavailable")],
        selection_model=SelectingModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
    )

    assert result.sources == []
    assert result.evidences == []
    assert any("no usable provider raw_content" in item for item in result.warnings)
    assert any(item.code == "provider_query_failed" for item in result.issues)
    assert all("provider unavailable" not in item for item in result.warnings)
    assert "provider snippet is not authoritative" not in result.model_content


@pytest.mark.asyncio
async def test_selector_failure_preserves_source_and_successful_sibling(tmp_path) -> None:
    """Preserve accepted Sources and sibling Evidence after one selector failure."""
    first = provider_response()["results"][0]
    second = {
        **first,
        "title": "Selection unavailable",
        "url": "https://example.test/fail-selection",
        "raw_content": first["raw_content"] + " Additional distinct source text.",
    }
    response = {"query": "treatment", "results": [first, second]}

    result = await execute_tavily_search_structured(
        ["treatment"],
        provider_responses=[response],
        selection_model=SelectiveFailingModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
    )

    assert len(result.sources) == 2
    assert len(result.evidences) == 1
    assert result.evidences[0].source_id == result.sources[0].source_id
    assert any("accepted Source was preserved" in item for item in result.warnings)
    assert "Evidence selection was unavailable" in result.model_content


@pytest.mark.asyncio
async def test_model_projection_omits_whole_evidence_block_at_tight_bound(tmp_path) -> None:
    """Bound context without presenting a truncated excerpt as selected Evidence."""
    response = provider_response()
    response["results"][0]["raw_content"] = "x" * 1_700

    result = await execute_tavily_search_structured(
        ["bounded observation"],
        config={"configurable": {"max_search_tool_message_chars": 1_000}},
        provider_responses=[response],
        selection_model=SelectingModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
    )

    assert len(result.sources) == len(result.evidences) == 1
    assert len(result.model_content) <= 1_000
    assert result.evidences[0].excerpt not in result.model_content
    assert "Additional search observations omitted" in result.model_content


@pytest.mark.asyncio
async def test_different_sources_keep_independent_evidence_identities(tmp_path) -> None:
    """Prevent semantic similarity from merging Evidence across Sources."""
    first = provider_response()["results"][0]
    second = {
        **first,
        "title": "Independent clinical review",
        "url": "https://example.test/independent-review",
    }

    result = await execute_tavily_search_structured(
        ["treatment evidence"],
        provider_responses=[{"query": "treatment evidence", "results": [first, second]}],
        selection_model=SelectingModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
    )

    assert len(result.sources) == len(result.evidences) == 2
    assert [record.source_id for record in result.evidences] == [
        record.source_id for record in result.sources
    ]
    assert result.evidences[0].evidence_id != result.evidences[1].evidence_id


@pytest.mark.asyncio
async def test_invalid_selection_preserves_valid_candidate_evidence(tmp_path) -> None:
    """Reject unknown and over-bound IDs without deleting valid sibling Evidence."""
    long_content = ("First clinical sentence. " * 90) + "\n\n" + (
        "Second clinical sentence. " * 90
    )
    response = provider_response()
    response["results"][0]["raw_content"] = long_content

    result = await execute_tavily_search_structured(
        ["mixed selection"],
        config={"configurable": {"max_selected_chunks_per_source": 1}},
        provider_responses=[response],
        selection_model=MixedIdentityModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
    )

    assert len(result.sources) == len(result.evidences) == 1
    assert any("Unknown Candidate ID was rejected: C999" in item for item in result.warnings)
    assert any("selection bound: C002" in item for item in result.warnings)


@pytest.mark.asyncio
async def test_one_provenance_failure_preserves_valid_candidate_evidence(
    monkeypatch,
    tmp_path,
) -> None:
    """Reject one invalid materialization without erasing a valid sibling Candidate."""
    original_materialize = search_runtime.materialize_evidence

    def selective_materialize(**kwargs):
        selected_id = kwargs["selection"].selected_chunk_ids[0]
        if selected_id == "C002":
            raise ProvenanceValidationError("forced locator mismatch")
        return original_materialize(**kwargs)

    monkeypatch.setattr(search_runtime, "materialize_evidence", selective_materialize)
    response = provider_response()
    response["results"][0]["raw_content"] = (
        ("First clinical sentence. " * 90)
        + "\n\n"
        + ("Second clinical sentence. " * 90)
    )

    result = await execute_tavily_search_structured(
        ["provenance isolation"],
        provider_responses=[response],
        selection_model=TwoCandidateModel(),
        artifact_store=LocalFileArtifactStore(tmp_path, "run-one"),
    )

    assert len(result.evidences) == 1
    assert any("C002 failed provenance materialization" in item for item in result.warnings)


def test_agent_visible_tavily_contract_is_preserved() -> None:
    """Freeze the existing Tool name and model-authored query argument schema."""
    assert tavily_search.name == "tavily_search"
    assert set(tavily_search.args_schema.model_fields) == {
        "queries",
        "max_results",
        "topic",
    }
    assert tavily_search.args_schema.model_fields["queries"].is_required()
