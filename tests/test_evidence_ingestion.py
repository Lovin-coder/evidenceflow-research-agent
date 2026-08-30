"""Deterministic regression tests for the P2-S4 Evidence ingestion boundary."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from open_deep_research.artifact_store import (
    ArtifactStoreError,
    LocalFileArtifactStore,
)
from open_deep_research.evidence_ingestion import (
    MAX_CANDIDATE_CHARS,
    CandidateChunk,
    ProvenanceValidationError,
    SelectionValidationError,
    WebpageSelection,
    build_source_record,
    chunk_source_text,
    evidence_hash,
    is_usable_source_content,
    materialize_evidence,
    normalize_source_text,
    parse_locator,
    sanitize_candidate_selection,
    select_webpage_chunks,
    validate_evidence_provenance,
    validate_selected_candidates,
)


class SelectionModel:
    """Return one fixed structured selection without invoking an external model."""

    def __init__(self, selection: WebpageSelection) -> None:
        self.selection = selection
        self.messages = []

    async def ainvoke(self, messages):
        """Capture the prompt and return the configured selection."""
        self.messages = messages
        return self.selection


def medical_document() -> str:
    """Build a representative paragraph-oriented medical Source fixture."""
    return (
        "# Guideline recommendation\n\n"
        "Adults with the condition should receive individualized treatment after "
        "benefits and harms are discussed. The recommendation is conditional.\n\n"
        "A randomized trial reported fewer recurrent events in the intervention "
        "group, while serious adverse events were similar between groups.\n\n"
        "The guideline notes uncertainty for adults older than eighty years."
    )


def test_normalization_is_deterministic_and_defines_usable_content() -> None:
    """Freeze newline, control-character, whitespace, and usability handling."""
    raw = "  Heading\r\nLine with spaces   \r\n\r\n\r\nBody\x00 text.  "

    first = normalize_source_text(raw)
    second = normalize_source_text(raw)

    assert first == second == "Heading\nLine with spaces\n\nBody text."
    assert is_usable_source_content(raw)
    assert not is_usable_source_content(None)
    assert not is_usable_source_content("  \n\n short ")


def test_chunker_is_paragraph_first_contiguous_bounded_and_deterministic() -> None:
    """Protect Candidate order, exact offsets, paragraph packing, and zero overlap."""
    normalized = normalize_source_text(medical_document())

    first = chunk_source_text(normalized, target_chars=180, max_chars=260, min_tail_chars=60)
    second = chunk_source_text(normalized, target_chars=180, max_chars=260, min_tail_chars=60)

    assert first == second
    assert [chunk.chunk_id for chunk in first] == [
        f"C{index:03d}" for index in range(1, len(first) + 1)
    ]
    assert all(chunk.text == normalized[chunk.start : chunk.end] for chunk in first)
    assert all(chunk.text == chunk.text.strip() for chunk in first)
    assert all(len(chunk.text) <= 260 for chunk in first)
    assert all(left.end <= right.start for left, right in zip(first, first[1:]))
    assert "\n\n" in first[0].text


def test_chunker_uses_deterministic_sentence_whitespace_and_hard_fallbacks() -> None:
    """Keep oversized logical blocks bounded even when preferred boundaries vanish."""
    sentence_block = " ".join(
        f"Sentence {index} contains a clinically relevant observation."
        for index in range(80)
    )
    huge_token = "x" * (MAX_CANDIDATE_CHARS * 2 + 333)

    sentence_chunks = chunk_source_text(sentence_block)
    hard_chunks = chunk_source_text(huge_token)

    assert len(sentence_chunks) > 1
    assert all(chunk.text.endswith(('.', '!', '?')) for chunk in sentence_chunks[:-1])
    assert [len(chunk.text) for chunk in hard_chunks] == [
        MAX_CANDIDATE_CHARS,
        MAX_CANDIDATE_CHARS,
        333,
    ]
    assert all(chunk.text == huge_token[chunk.start : chunk.end] for chunk in hard_chunks)


def test_chunker_empty_short_and_small_tail_boundaries_are_exact() -> None:
    """Cover empty, single-block, and explicit small-tail merge slice invariants."""
    assert chunk_source_text("") == []

    short = "Short clinically meaningful source block."
    short_chunks = chunk_source_text(short, target_chars=50, max_chars=120)
    assert [(chunk.start, chunk.end, chunk.text) for chunk in short_chunks] == [
        (0, len(short), short)
    ]

    normalized = ("a" * 100) + "\n\n" + ("b" * 10)
    merged = chunk_source_text(
        normalized,
        target_chars=50,
        max_chars=120,
        min_tail_chars=20,
    )
    assert len(merged) == 1
    assert merged[0].text == normalized[merged[0].start : merged[0].end]
    assert (merged[0].start, merged[0].end) == (0, len(normalized))


def test_artifact_store_round_trip_is_exact_safe_and_run_scoped(tmp_path) -> None:
    """Keep normalized artifacts outside State and resolvable for the owning run."""
    text = normalize_source_text(medical_document())
    first_call = LocalFileArtifactStore(tmp_path, "run-one")
    later_call = LocalFileArtifactStore(tmp_path, "run-one")
    other_run = LocalFileArtifactStore(tmp_path, "run-two")

    artifact_ref = first_call.put_text(text)

    assert first_call.put_text(text) == artifact_ref
    assert later_call.get_text(artifact_ref) == text
    with pytest.raises(ArtifactStoreError, match="does not exist"):
        other_run.get_text(artifact_ref)
    with pytest.raises(ArtifactStoreError, match="Invalid artifact reference"):
        first_call.get_text("artifact:sha256:../../escape")


def test_structured_selection_validates_ids_duplicates_and_limit() -> None:
    """Allow semantic ID choice while retaining Host authority over Candidates."""
    normalized = normalize_source_text(medical_document())
    candidates = chunk_source_text(normalized, target_chars=120, max_chars=180)
    valid = WebpageSelection(
        summary="Derived summary.",
        selected_chunk_ids=[candidates[0].chunk_id],
    )

    assert validate_selected_candidates(valid, candidates, max_selected=1) == [
        candidates[0]
    ]
    with pytest.raises(SelectionValidationError, match="Unknown Candidate"):
        validate_selected_candidates(
            WebpageSelection(summary="Derived.", selected_chunk_ids=["C999"]),
            candidates,
        )
    with pytest.raises(SelectionValidationError, match="configured limit"):
        validate_selected_candidates(
            WebpageSelection(
                summary="Derived.",
                selected_chunk_ids=[candidate.chunk_id for candidate in candidates[:2]],
            ),
            candidates,
            max_selected=1,
        )
    with pytest.raises(ValidationError, match="must be unique"):
        WebpageSelection(
            summary="Derived.",
            selected_chunk_ids=[candidates[0].chunk_id, candidates[0].chunk_id],
        )

    sanitized, rejections = sanitize_candidate_selection(
        WebpageSelection(
            summary="Derived.",
            selected_chunk_ids=[candidates[0].chunk_id, "C999", candidates[1].chunk_id],
        ),
        candidates,
        max_selected=1,
    )
    assert sanitized.selected_chunk_ids == [candidates[0].chunk_id]
    assert [rejection.code for rejection in rejections] == [
        "unknown_candidate_id",
        "candidate_selection_bound",
    ]


@pytest.mark.asyncio
async def test_selection_model_receives_candidates_but_owns_no_evidence_fields() -> None:
    """Keep structured model output limited to summary and Candidate identities."""
    normalized = normalize_source_text(medical_document())
    candidates = chunk_source_text(normalized)
    expected = WebpageSelection(
        summary="Derived summary.", selected_chunk_ids=[candidates[0].chunk_id]
    )
    model = SelectionModel(expected)

    actual = await select_webpage_chunks(
        model,
        research_topic="Compare benefits and harms.",
        query="treatment randomized trial",
        title="Guideline",
        url="https://example.test/guideline",
        candidates=candidates,
    )

    assert actual == expected
    prompt = model.messages[0].content
    assert f"[{candidates[0].chunk_id}]" in prompt
    assert "Do not\nreturn excerpts, locators, Source IDs, Evidence IDs" in prompt


def test_host_materializes_exact_deterministic_evidence_and_empty_selection(tmp_path) -> None:
    """Prove Evidence content, locator, identity, and hash come only from Host data."""
    normalized = normalize_source_text(medical_document())
    store = LocalFileArtifactStore(tmp_path, "run-one")
    artifact_ref = store.put_text(normalized)
    source = build_source_record(
        url="HTTPS://EXAMPLE.TEST/guideline?utm_source=test&b=2&a=1#section",
        title="Guideline",
        provider="tavily",
        artifact_ref=artifact_ref,
        normalized_text=normalized,
    )
    replayed_source = build_source_record(
        url="https://example.test/guideline?a=1&b=2",
        title="Guideline",
        provider="tavily",
        artifact_ref=artifact_ref,
        normalized_text=normalized,
    )
    candidates = chunk_source_text(normalized, target_chars=180, max_chars=260)
    selection = WebpageSelection(
        summary="The model may not author Evidence text.",
        selected_chunk_ids=[candidates[0].chunk_id],
    )

    first = materialize_evidence(
        source=source,
        candidates=candidates,
        selection=selection,
        artifact_store=store,
    )
    second = materialize_evidence(
        source=source,
        candidates=candidates,
        selection=selection,
        artifact_store=store,
    )

    assert source.source_id == replayed_source.source_id
    assert first == second
    assert len(first) == 1
    start, end = parse_locator(first[0].locator)
    assert first[0].excerpt == candidates[0].text == normalized[start:end]
    assert first[0].hash == evidence_hash(first[0].excerpt)
    assert materialize_evidence(
        source=source,
        candidates=candidates,
        selection=WebpageSelection(summary="No useful Evidence.", selected_chunk_ids=[]),
        artifact_store=store,
    ) == []


def test_source_metadata_enrichment_is_validated_and_identity_neutral(tmp_path) -> None:
    """Keep best-effort metadata compact without changing Source provenance identity."""
    normalized = normalize_source_text(medical_document())
    store = LocalFileArtifactStore(tmp_path, "run-one")
    artifact_ref = store.put_text(normalized)
    retrieved_at = datetime(2026, 8, 29, 12, 30, tzinfo=timezone.utc)

    enriched = build_source_record(
        url="https://example.test/guideline",
        title="Guideline",
        provider="tavily",
        artifact_ref=artifact_ref,
        normalized_text=normalized,
        retrieved_at=retrieved_at,
        published_at="2025-04-18",
        publisher="  Clinical Society  ",
        authors="A. Researcher; B. Reviewer",
        document_type="Clinical guideline",
    )
    minimal = build_source_record(
        url="https://example.test/guideline",
        title="Guideline",
        provider="tavily",
        artifact_ref=artifact_ref,
        normalized_text=normalized,
        retrieved_at=retrieved_at,
    )

    assert enriched.metadata == {
        "provider": "tavily",
        "title": "Guideline",
        "retrieved_at": "2026-08-29T12:30:00+00:00",
        "url": "https://example.test/guideline",
        "published_at": "2025-04-18",
        "publisher": "Clinical Society",
        "authors": "A. Researcher; B. Reviewer",
        "document_type": "Clinical guideline",
    }
    assert enriched.source_id == minimal.source_id
    assert enriched.artifact_ref == minimal.artifact_ref
    assert "retrieval_score" not in enriched.metadata


def test_source_metadata_omits_malformed_optional_provider_values(tmp_path) -> None:
    """Omit invalid provider metadata rather than fabricating semantic repairs."""
    normalized = normalize_source_text(medical_document())
    store = LocalFileArtifactStore(tmp_path, "run-one")
    source = build_source_record(
        url="https://example.test/guideline",
        title="Guideline",
        provider="tavily",
        artifact_ref=store.put_text(normalized),
        normalized_text=normalized,
        retrieved_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
        published_at="not-a-date",
        publisher=42,
        authors=" ",
        document_type="x" * 1_001,
    )

    assert source.metadata == {
        "provider": "tavily",
        "title": "Guideline",
        "retrieved_at": "2026-08-29T00:00:00+00:00",
        "url": "https://example.test/guideline",
    }


def test_provenance_validator_rejects_wrong_source_excerpt_and_hash(tmp_path) -> None:
    """Fail deterministic replay instead of using semantic matching."""
    normalized = normalize_source_text(medical_document())
    store = LocalFileArtifactStore(tmp_path, "run-one")
    source = build_source_record(
        url="https://example.test/guideline",
        title="Guideline",
        provider="tavily",
        artifact_ref=store.put_text(normalized),
        normalized_text=normalized,
    )
    candidate = CandidateChunk("C001", 0, 10, normalized[:10])
    record = materialize_evidence(
        source=source,
        candidates=[candidate],
        selection=WebpageSelection(summary="Derived.", selected_chunk_ids=["C001"]),
        artifact_store=store,
    )[0]
    other_source = source.model_copy(update={"source_id": "source:other"})

    with pytest.raises(ProvenanceValidationError, match="different SourceRecord"):
        validate_evidence_provenance(
            evidence=record, source=other_source, artifact_store=store
        )
    with pytest.raises(ProvenanceValidationError, match="hash"):
        validate_evidence_provenance(
            evidence=record.model_copy(update={"hash": "sha256:wrong"}),
            source=source,
            artifact_store=store,
        )
