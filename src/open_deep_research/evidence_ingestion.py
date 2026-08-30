"""Deterministic Source normalization, chunking, and Evidence materialization."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field, model_validator

from open_deep_research.artifact_store import ArtifactStore
from open_deep_research.domain_models import (
    MAX_EVIDENCE_EXCERPT_CHARS,
    EvidenceRecord,
    SourceRecord,
)
from open_deep_research.prompts import select_webpage_evidence_prompt

CHUNKING_VERSION = "p2-s4-char-v1"
TARGET_CANDIDATE_CHARS = 1_200
MAX_CANDIDATE_CHARS = 1_800
MIN_TAIL_CHARS = 275
MAX_SELECTED_CHUNKS_PER_SOURCE = 4
MIN_USABLE_SOURCE_CHARS = 20
_MAX_OPTIONAL_SOURCE_METADATA_CHARS = 1_000
_MAX_PUBLISHED_AT_CHARS = 128
_LOCATOR_PATTERN = re.compile(r"char:(?P<start>\d+)-(?P<end>\d+)\Z")
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}

if MAX_CANDIDATE_CHARS > MAX_EVIDENCE_EXCERPT_CHARS:
    raise RuntimeError("Candidate chunks cannot exceed the Evidence excerpt contract")


class EvidenceIngestionError(ValueError):
    """Report a deterministic Source/Evidence ingestion contract failure."""


class SelectionValidationError(EvidenceIngestionError):
    """Reject an invalid model-selected Candidate identity set."""


class ProvenanceValidationError(EvidenceIngestionError):
    """Reject Evidence that cannot be replayed exactly from its Source artifact."""


@dataclass(frozen=True, slots=True)
class CandidateChunk:
    """Represent one internal contiguous Candidate in normalized artifact coordinates."""

    chunk_id: str
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class SelectionRejection:
    """Describe one deterministic Host rejection of a model-selected Candidate."""

    code: str
    message: str
    candidate_id: str


class WebpageSelection(BaseModel):
    """Carry derived summary text and model-selected internal Candidate IDs."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    summary: str = Field(min_length=1)
    selected_chunk_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_candidate_ids(self) -> WebpageSelection:
        """Reject duplicate selections before Evidence materialization."""
        if len(self.selected_chunk_ids) != len(set(self.selected_chunk_ids)):
            raise ValueError("selected_chunk_ids must be unique")
        return self


def normalize_source_text(raw_content: str) -> str:
    """Create the deterministic normalized coordinate space used by ArtifactStore."""
    if not isinstance(raw_content, str):
        raise TypeError("raw_content must be a string")
    normalized = raw_content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(
        character
        for character in normalized
        if character in {"\n", "\t"} or unicodedata.category(character) != "Cc"
    )
    normalized = "\n".join(line.rstrip(" \t") for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def is_usable_source_content(raw_content: object) -> bool:
    """Return whether provider content can enter the authoritative Source path."""
    if not isinstance(raw_content, str):
        return False
    normalized = normalize_source_text(raw_content)
    return len(normalized) >= MIN_USABLE_SOURCE_CHARS and any(
        character.isalnum() for character in normalized
    )


def chunk_source_text(
    normalized_text: str,
    *,
    target_chars: int = TARGET_CANDIDATE_CHARS,
    max_chars: int = MAX_CANDIDATE_CHARS,
    min_tail_chars: int | None = None,
) -> list[CandidateChunk]:
    """Split normalized text into stable paragraph-first contiguous Candidates."""
    if not normalized_text:
        return []
    if normalized_text != normalized_text.strip():
        raise EvidenceIngestionError(
            "normalized_text must not contain leading or trailing whitespace"
        )
    if not 0 < target_chars <= max_chars <= MAX_EVIDENCE_EXCERPT_CHARS:
        raise EvidenceIngestionError("Candidate size configuration is invalid")
    effective_min_tail_chars = (
        min(MIN_TAIL_CHARS, max_chars)
        if min_tail_chars is None
        else min_tail_chars
    )
    if not 0 <= effective_min_tail_chars <= max_chars:
        raise EvidenceIngestionError("Candidate tail configuration is invalid")

    atomic_spans: list[tuple[int, int]] = []
    for start, end in _logical_block_spans(normalized_text):
        if end - start <= max_chars:
            atomic_spans.append((start, end))
        else:
            atomic_spans.extend(
                _split_oversized_span(
                    normalized_text,
                    start,
                    end,
                    target_chars=target_chars,
                    max_chars=max_chars,
                )
            )

    packed: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for span in atomic_spans:
        if current is None:
            current = span
            continue
        combined_length = span[1] - current[0]
        current_length = current[1] - current[0]
        if current_length < target_chars and combined_length <= max_chars:
            current = (current[0], span[1])
        else:
            packed.append(current)
            current = span
    if current is not None:
        packed.append(current)

    if (
        len(packed) > 1
        and packed[-1][1] - packed[-1][0] < effective_min_tail_chars
    ):
        merged = (packed[-2][0], packed[-1][1])
        if merged[1] - merged[0] <= max_chars:
            packed[-2:] = [merged]

    candidates = [
        CandidateChunk(
            chunk_id=f"C{index:03d}",
            start=start,
            end=end,
            text=normalized_text[start:end],
        )
        for index, (start, end) in enumerate(packed, start=1)
    ]
    for candidate in candidates:
        if candidate.text != normalized_text[candidate.start : candidate.end]:
            raise ProvenanceValidationError("Candidate locator does not reproduce text")
        if candidate.text != candidate.text.strip():
            raise ProvenanceValidationError("Candidate boundaries include edge whitespace")
        if len(candidate.text) > max_chars:
            raise ProvenanceValidationError("Candidate exceeds the configured maximum")
    return candidates


def validate_selected_candidates(
    selection: WebpageSelection,
    candidates: list[CandidateChunk],
    *,
    max_selected: int = MAX_SELECTED_CHUNKS_PER_SOURCE,
) -> list[CandidateChunk]:
    """Resolve a bounded model selection to authoritative Host Candidates."""
    if len(selection.selected_chunk_ids) > max_selected:
        raise SelectionValidationError(
            f"selected_chunk_ids exceeds the configured limit of {max_selected}"
        )
    by_id = {candidate.chunk_id: candidate for candidate in candidates}
    unknown = [
        chunk_id
        for chunk_id in selection.selected_chunk_ids
        if chunk_id not in by_id
    ]
    if unknown:
        raise SelectionValidationError(f"Unknown Candidate IDs: {unknown}")
    return [by_id[chunk_id] for chunk_id in selection.selected_chunk_ids]


async def select_webpage_chunks(
    model: BaseChatModel,
    *,
    research_topic: str,
    query: str,
    title: str,
    url: str,
    candidates: list[CandidateChunk],
    max_selected: int = MAX_SELECTED_CHUNKS_PER_SOURCE,
    validate_ids: bool = True,
) -> WebpageSelection:
    """Ask the model for semantic Candidate IDs and validate only their structure."""
    candidate_text = "\n\n".join(
        f"[{candidate.chunk_id}]\n{candidate.text}" for candidate in candidates
    )
    prompt = select_webpage_evidence_prompt.format(
        research_topic=research_topic,
        query=query,
        title=title,
        url=url,
        max_selected=max_selected,
        candidates=candidate_text,
    )
    response = await model.ainvoke([HumanMessage(content=prompt)])
    selection = WebpageSelection.model_validate(response)
    if validate_ids:
        validate_selected_candidates(selection, candidates, max_selected=max_selected)
    return selection


def sanitize_candidate_selection(
    selection: WebpageSelection,
    candidates: list[CandidateChunk],
    *,
    max_selected: int = MAX_SELECTED_CHUNKS_PER_SOURCE,
) -> tuple[WebpageSelection, list[SelectionRejection]]:
    """Reject invalid IDs while preserving valid selections in deterministic order."""
    known_ids = {candidate.chunk_id for candidate in candidates}
    accepted_ids: list[str] = []
    rejections: list[SelectionRejection] = []
    for chunk_id in selection.selected_chunk_ids:
        if chunk_id not in known_ids:
            rejections.append(
                SelectionRejection(
                    code="unknown_candidate_id",
                    message=f"Unknown Candidate ID was rejected: {chunk_id}",
                    candidate_id=chunk_id,
                )
            )
            continue
        if len(accepted_ids) >= max_selected:
            rejections.append(
                SelectionRejection(
                    code="candidate_selection_bound",
                    message=(
                        "Candidate ID was rejected at the selection bound: "
                        f"{chunk_id}"
                    ),
                    candidate_id=chunk_id,
                )
            )
            continue
        accepted_ids.append(chunk_id)
    return (
        WebpageSelection(
            summary=selection.summary,
            selected_chunk_ids=accepted_ids,
        ),
        rejections,
    )


def build_source_record(
    *,
    url: str,
    title: str,
    provider: str,
    artifact_ref: str,
    normalized_text: str,
    retrieved_at: datetime | None = None,
    published_at: object = None,
    publisher: object = None,
    authors: object = None,
    document_type: object = None,
) -> SourceRecord:
    """Build a stable compact Source only after usable content is persisted."""
    if not normalized_text or not artifact_ref:
        raise EvidenceIngestionError(
            "A SourceRecord requires persisted usable normalized content"
        )
    canonical_url = canonicalize_source_url(url)
    identity_material = "\0".join(
        ("p2-s4-source-v1", canonical_url or evidence_hash(normalized_text))
    )
    source_digest = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()[:24]
    metadata = {
        "provider": provider,
        "title": title.strip() or canonical_url or "Untitled source",
        "retrieved_at": _serialize_retrieval_timestamp(retrieved_at),
    }
    if canonical_url:
        metadata["url"] = canonical_url
    optional_metadata = {
        "published_at": _validated_published_at(published_at),
        "publisher": _validated_optional_metadata_value(publisher),
        "authors": _validated_optional_metadata_value(authors),
        "document_type": _validated_optional_metadata_value(document_type),
    }
    metadata.update(
        {key: value for key, value in optional_metadata.items() if value is not None}
    )
    return SourceRecord(
        source_id=f"source:sha256:{source_digest}",
        artifact_ref=artifact_ref,
        metadata=metadata,
    )


def _serialize_retrieval_timestamp(retrieved_at: datetime | None) -> str:
    """Serialize one Host-owned retrieval timestamp in UTC."""
    timestamp = retrieved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise EvidenceIngestionError("retrieved_at must be timezone-aware")
    return timestamp.astimezone(timezone.utc).isoformat()


def _validated_optional_metadata_value(value: object) -> str | None:
    """Admit only compact provider strings without inventing missing metadata."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > _MAX_OPTIONAL_SOURCE_METADATA_CHARS
        or any(ord(character) < 32 for character in normalized)
    ):
        return None
    return normalized


def _validated_published_at(value: object) -> str | None:
    """Preserve a compact provider publication date only when it parses reliably."""
    normalized = _validated_optional_metadata_value(value)
    if normalized is None or len(normalized) > _MAX_PUBLISHED_AT_CHARS:
        return None
    try:
        date.fromisoformat(normalized)
    except ValueError:
        try:
            datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsedate_to_datetime(normalized)
            except (TypeError, ValueError, OverflowError):
                return None
    return normalized


def materialize_evidence(
    *,
    source: SourceRecord,
    candidates: list[CandidateChunk],
    selection: WebpageSelection,
    artifact_store: ArtifactStore,
    max_selected: int = MAX_SELECTED_CHUNKS_PER_SOURCE,
) -> list[EvidenceRecord]:
    """Materialize model-selected IDs as exact Host-owned Evidence records."""
    if not source.artifact_ref:
        raise ProvenanceValidationError("SourceRecord.artifact_ref is required")
    artifact_text = artifact_store.get_text(source.artifact_ref)
    selected = validate_selected_candidates(
        selection, candidates, max_selected=max_selected
    )
    records: list[EvidenceRecord] = []
    for candidate in selected:
        excerpt = artifact_text[candidate.start : candidate.end]
        if excerpt != candidate.text:
            raise ProvenanceValidationError(
                f"Candidate {candidate.chunk_id!r} does not resolve against the artifact"
            )
        locator = format_locator(candidate.start, candidate.end)
        content_hash = evidence_hash(excerpt)
        identity_material = "\0".join(
            (CHUNKING_VERSION, source.source_id, locator, content_hash)
        )
        evidence_digest = hashlib.sha256(
            identity_material.encode("utf-8")
        ).hexdigest()[:24]
        record = EvidenceRecord(
            evidence_id=f"evidence:sha256:{evidence_digest}",
            source_id=source.source_id,
            locator=locator,
            excerpt=excerpt,
            hash=content_hash,
        )
        validate_evidence_provenance(
            evidence=record,
            source=source,
            artifact_store=artifact_store,
        )
        records.append(record)
    return records


def validate_source_artifact(
    source: SourceRecord, artifact_store: ArtifactStore
) -> str:
    """Resolve a published Source artifact and reject missing references."""
    if not source.artifact_ref:
        raise ProvenanceValidationError(
            f"SourceRecord {source.source_id!r} has no artifact_ref"
        )
    return artifact_store.get_text(source.artifact_ref)


def validate_evidence_provenance(
    *,
    evidence: EvidenceRecord,
    source: SourceRecord,
    artifact_store: ArtifactStore,
) -> None:
    """Replay locator, excerpt, and hash deterministically against Source text."""
    if evidence.source_id != source.source_id:
        raise ProvenanceValidationError("Evidence is bound to a different SourceRecord")
    artifact_text = validate_source_artifact(source, artifact_store)
    start, end = parse_locator(evidence.locator)
    if not 0 <= start < end <= len(artifact_text):
        raise ProvenanceValidationError("Evidence locator is outside the Source artifact")
    resolved = artifact_text[start:end]
    if resolved != evidence.excerpt:
        raise ProvenanceValidationError(
            "Evidence excerpt does not equal the authoritative artifact slice"
        )
    if evidence_hash(resolved) != evidence.hash:
        raise ProvenanceValidationError("Evidence hash does not match its excerpt")


def render_researcher_observation(
    *,
    source: SourceRecord,
    summary: str,
    evidence: list[EvidenceRecord],
    warnings: list[str] | None = None,
    max_summary_chars: int = 2_000,
) -> str:
    """Render a bounded Evidence-aware model view without raw Source artifacts."""
    title = source.metadata.get("title", "Untitled source")
    url = source.metadata.get("url", "unavailable")
    blocks = [
        f"Source: [{source.source_id}]",
        f"Title: {title}",
        f"URL: {url}",
        "",
        "Summary (derived, non-evidence):",
        summary[:max_summary_chars],
        "",
        "Selected Evidence (authoritative source-derived excerpts):",
    ]
    if evidence:
        for record in evidence:
            blocks.extend((f"[{record.evidence_id}]", record.excerpt, ""))
    else:
        blocks.append("No Evidence candidates were materialized from this Source.")
    if warnings:
        blocks.extend(("", "Ingestion warnings (process metadata, not Evidence):"))
        blocks.extend(f"- {warning}" for warning in warnings)
    return "\n".join(blocks).strip()


def format_locator(start: int, end: int) -> str:
    """Encode one inclusive-start, exclusive-end character interval."""
    if not 0 <= start < end:
        raise ProvenanceValidationError("Locator requires 0 <= start < end")
    return f"char:{start}-{end}"


def parse_locator(locator: str) -> tuple[int, int]:
    """Parse the frozen inclusive-start, exclusive-end character locator."""
    match = _LOCATOR_PATTERN.fullmatch(locator)
    if match is None:
        raise ProvenanceValidationError(f"Invalid Evidence locator: {locator!r}")
    return int(match.group("start")), int(match.group("end"))


def evidence_hash(excerpt: str) -> str:
    """Return the canonical SHA-256 hash encoding for an exact Evidence passage."""
    return f"sha256:{hashlib.sha256(excerpt.encode('utf-8')).hexdigest()}"


def canonicalize_source_url(url: str) -> str:
    """Canonicalize a provider URL for deterministic run-local Source identity."""
    if not url or not url.strip():
        return ""
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not scheme or not hostname:
        return url.strip()
    port = parsed.port
    default_port = (scheme == "http" and port == 80) or (
        scheme == "https" and port == 443
    )
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    path = parsed.path or "/"
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY_KEYS
        and not key.lower().startswith("utm_")
    ]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(query_items)), ""))


def _logical_block_spans(text: str) -> list[tuple[int, int]]:
    """Return paragraph spans while retaining offsets in normalized text."""
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"(?:\A|\n\n)(.*?)(?=\n\n|\Z)", text, re.DOTALL):
        start, end = match.span(1)
        start, end = _trim_span(text, start, end)
        if start < end:
            spans.append((start, end))
    return spans


def _split_oversized_span(
    text: str,
    start: int,
    end: int,
    *,
    target_chars: int,
    max_chars: int,
) -> list[tuple[int, int]]:
    """Split one oversized block using sentence, whitespace, then hard boundaries."""
    spans: list[tuple[int, int]] = []
    cursor = start
    while end - cursor > max_chars:
        hard_end = cursor + max_chars
        preferred = min(cursor + target_chars, hard_end)
        floor = min(cursor + max(1, target_chars // 2), hard_end)
        cut = _nearest_sentence_boundary(text, floor, hard_end, preferred)
        if cut is None:
            cut = _nearest_whitespace_boundary(text, floor, hard_end, preferred)
        if cut is None or cut <= cursor:
            cut = hard_end
        chunk_start, chunk_end = _trim_span(text, cursor, cut)
        if chunk_start < chunk_end:
            spans.append((chunk_start, chunk_end))
        cursor = cut
        while cursor < end and text[cursor].isspace():
            cursor += 1
    tail_start, tail_end = _trim_span(text, cursor, end)
    if tail_start < tail_end:
        spans.append((tail_start, tail_end))
    return spans


def _nearest_sentence_boundary(
    text: str, floor: int, ceiling: int, preferred: int
) -> int | None:
    """Choose the closest deterministic sentence-like boundary to the target."""
    candidates: list[int] = []
    for match in re.finditer(r"[.!?。！？](?:[\"'”’\)\]]*)", text[floor:ceiling]):
        position = floor + match.end()
        if position == len(text) or text[position].isspace():
            candidates.append(position)
    return _closest_boundary(candidates, preferred)


def _nearest_whitespace_boundary(
    text: str, floor: int, ceiling: int, preferred: int
) -> int | None:
    """Choose a whitespace cut when no sentence boundary is available."""
    candidates = [
        position
        for position in range(floor, ceiling)
        if text[position].isspace()
    ]
    return _closest_boundary(candidates, preferred)


def _closest_boundary(candidates: list[int], preferred: int) -> int | None:
    """Choose the nearest boundary, preferring the earlier one on a tie."""
    if not candidates:
        return None
    return min(candidates, key=lambda position: (abs(position - preferred), position))


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Remove meaningless separator whitespace from Candidate outer boundaries."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
