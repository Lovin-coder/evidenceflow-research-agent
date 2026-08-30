"""Reader-facing Source display and shadow report rendering helpers."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeAlias
from urllib.parse import urlsplit

from langchain_core.messages import HumanMessage

from open_deep_research.artifact_store import ArtifactStore
from open_deep_research.domain_models import (
    Citation,
    EvidenceRef,
    GroundingManifest,
    GroundingStatus,
)
from open_deep_research.global_synthesis.projection import (
    RendererProjectionOutcome,
    TaskQualifiedResolver,
)
from open_deep_research.global_synthesis.types import (
    GlobalSynthesisLimits,
    ShadowReportDraft,
    _invoke_structured_once,
    _invoke_with_host_retry,
    _StructuredValidationError,
    _validate_shadow_report_draft,
)
from open_deep_research.prompts import SHADOW_RENDERER_PROMPT

_MODEL_C_TIMEOUT_SECONDS = 90.0
_CONFLICT_MARKER = "存在与该结论方向不一致的重要证据。"
_ZERO_ELIGIBLE_REPORT = "暂无通过全局证据锚定、可纳入影子报告的主张。"


@dataclass(frozen=True)
class TaskSourceDisplayKey:
    """Fallback display identity scoped to one canonical task Source."""

    task_id: str
    source_id: str


@dataclass(frozen=True)
class UrlArtifactDisplayKey:
    """Cross-task display identity proven inside one current Artifact Run."""

    artifact_run_id: str
    stored_url: str
    artifact_ref: str


SourceDisplayKey: TypeAlias = TaskSourceDisplayKey | UrlArtifactDisplayKey


@dataclass(frozen=True)
class SourceDisplayMetadata:
    """Whitelisted first-write-wins presentation metadata."""

    title: str | None = None
    publisher: str | None = None
    authors: str | None = None
    published_at: str | None = None
    document_type: str | None = None
    provider: str | None = None


@dataclass(frozen=True)
class SourceDisplayEntry:
    """One labeled display group without changing canonical provenance records."""

    key: SourceDisplayKey
    source_refs: tuple[TaskSourceDisplayKey, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    citation_ids: tuple[str, ...]
    metadata: SourceDisplayMetadata
    label: str
    bibliography: str


def _is_valid_stored_url(value: str | None) -> bool:
    """Validate an exact stored URL without returning a normalized replacement."""
    if value is None or value != value.strip():
        return False
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _display_key(
    *,
    task_id: str,
    source_id: str,
    stored_url: str | None,
    artifact_ref: str | None,
    artifact_run_id: str,
    artifact_store: ArtifactStore,
) -> SourceDisplayKey:
    """Select a cross-task key only when URL and current-run Artifact both resolve."""
    if (
        stored_url is not None
        and _is_valid_stored_url(stored_url)
        and artifact_ref is not None
    ):
        try:
            artifact_store.get_text(artifact_ref)
        except ValueError:
            pass
        else:
            return UrlArtifactDisplayKey(
                artifact_run_id=artifact_run_id,
                stored_url=stored_url,
                artifact_ref=artifact_ref,
            )
    return TaskSourceDisplayKey(task_id=task_id, source_id=source_id)


def _merge_metadata(
    current: SourceDisplayMetadata,
    incoming: dict[str, str],
) -> SourceDisplayMetadata:
    """Retain the first validated non-empty value for each display field."""
    values: dict[str, str | None] = {}
    for field in SourceDisplayMetadata.__dataclass_fields__:
        prior = getattr(current, field)
        candidate = incoming.get(field)
        values[field] = prior or (
            candidate if candidate is not None and candidate.strip() else None
        )
    return SourceDisplayMetadata(**values)


def _format_bibliography(
    key: SourceDisplayKey, metadata: SourceDisplayMetadata
) -> str:
    """Format a deterministic best-effort GB/T 7714-style display string."""
    segments: list[str] = []
    if metadata.authors:
        segments.append(metadata.authors)
    if metadata.title:
        title = metadata.title
        if metadata.document_type:
            title = f"{title}[{metadata.document_type}]"
        segments.append(title)
    elif metadata.document_type:
        segments.append(f"[{metadata.document_type}]")
    if metadata.publisher:
        segments.append(metadata.publisher)
    if metadata.published_at:
        segments.append(metadata.published_at)
    if metadata.provider:
        segments.append(metadata.provider)
    if isinstance(key, UrlArtifactDisplayKey):
        segments.append(key.stored_url)
    return ". ".join(segments)


@dataclass
class _MutableDisplayEntry:
    key: SourceDisplayKey
    source_refs: list[TaskSourceDisplayKey]
    evidence_refs: list[EvidenceRef]
    citation_ids: list[str]
    metadata: SourceDisplayMetadata


def build_source_display_entries(
    citations: list[Citation] | tuple[Citation, ...],
    *,
    resolver: TaskQualifiedResolver,
    artifact_run_id: str,
    artifact_store: ArtifactStore,
) -> tuple[SourceDisplayEntry, ...]:
    """Group display Sources in canonical Citation traversal and assign labels."""
    entries: list[_MutableDisplayEntry] = []
    by_key: dict[SourceDisplayKey, _MutableDisplayEntry] = {}
    for citation in citations:
        evidence = resolver.resolve_evidence(citation.evidence_ref)
        source = resolver.resolve_source(citation.evidence_ref)
        source_ref = TaskSourceDisplayKey(
            task_id=citation.evidence_ref.task_id,
            source_id=evidence.source_id,
        )
        key = _display_key(
            task_id=source_ref.task_id,
            source_id=source_ref.source_id,
            stored_url=source.metadata.get("url"),
            artifact_ref=source.artifact_ref,
            artifact_run_id=artifact_run_id,
            artifact_store=artifact_store,
        )
        entry = by_key.get(key)
        if entry is None:
            entry = _MutableDisplayEntry(
                key=key,
                source_refs=[],
                evidence_refs=[],
                citation_ids=[],
                metadata=SourceDisplayMetadata(),
            )
            by_key[key] = entry
            entries.append(entry)
        if source_ref not in entry.source_refs:
            entry.source_refs.append(source_ref)
        if citation.evidence_ref not in entry.evidence_refs:
            entry.evidence_refs.append(citation.evidence_ref)
        entry.citation_ids.append(citation.citation_id)
        entry.metadata = _merge_metadata(entry.metadata, source.metadata)

    return tuple(
        SourceDisplayEntry(
            key=entry.key,
            source_refs=tuple(entry.source_refs),
            evidence_refs=tuple(entry.evidence_refs),
            citation_ids=tuple(entry.citation_ids),
            metadata=entry.metadata,
            label=f"[{index}]",
            bibliography=_format_bibliography(entry.key, entry.metadata),
        )
        for index, entry in enumerate(entries, start=1)
    )


def _validate_renderer_draft(
    draft: ShadowReportDraft,
    *,
    eligible_claim_ids: tuple[str, ...],
    limits: GlobalSynthesisLimits,
) -> ShadowReportDraft:
    """Validate Model-owned structure, bindings, occurrence limits, and coverage."""
    _validate_shadow_report_draft(draft, limits)
    eligible = set(eligible_claim_ids)
    occurrences = {claim_id: 0 for claim_id in eligible_claim_ids}
    for section in draft.sections:
        for paragraph in section.paragraphs:
            if len(paragraph.claim_ids) != len(set(paragraph.claim_ids)):
                raise _StructuredValidationError(
                    "Renderer paragraph Claim IDs must be unique"
                )
            if any(claim_id not in eligible for claim_id in paragraph.claim_ids):
                raise _StructuredValidationError(
                    "Renderer paragraph references an ineligible Claim"
                )
            for claim_id in paragraph.claim_ids:
                occurrences[claim_id] += 1
                if occurrences[claim_id] > limits.max_claim_occurrences_per_claim:
                    raise _StructuredValidationError(
                        "Renderer Claim occurrence exceeds capacity"
                    )
    if any(count == 0 for count in occurrences.values()):
        raise _StructuredValidationError("Renderer draft does not cover every Claim")
    return draft


def _citation_label_map(
    entries: tuple[SourceDisplayEntry, ...],
) -> dict[str, str]:
    return {
        citation_id: entry.label
        for entry in entries
        for citation_id in entry.citation_ids
    }


def _finalize_shadow_report(
    draft: ShadowReportDraft,
    *,
    manifest: GroundingManifest,
    display_entries: tuple[SourceDisplayEntry, ...],
    limits: GlobalSynthesisLimits,
) -> str:
    """Inject minimum conflict disclosure, Citation labels, and bibliography."""
    grounding_by_claim = {
        grounding.claim_id: grounding for grounding in manifest.groundings
    }
    label_by_citation = _citation_label_map(display_entries)
    conflict_marked: set[str] = set()
    used_labels: set[str] = set()
    lines: list[str] = []
    for section in draft.sections:
        lines.append(f"## {section.title}")
        lines.append("")
        for paragraph in section.paragraphs:
            text = paragraph.text
            for claim_id in paragraph.claim_ids:
                grounding = grounding_by_claim[claim_id]
                if (
                    grounding.status is GroundingStatus.SUPPORTED_WITH_CONFLICT
                    and claim_id not in conflict_marked
                ):
                    text = f"{text} {_CONFLICT_MARKER}"
                    conflict_marked.add(claim_id)
            paragraph_claim_ids = set(paragraph.claim_ids)
            labels: list[str] = []
            for citation in manifest.citations:
                if citation.claim_id not in paragraph_claim_ids:
                    continue
                try:
                    label = label_by_citation[citation.citation_id]
                except KeyError as error:
                    raise _StructuredValidationError(
                        "Citation has no reader-facing display label"
                    ) from error
                if label not in labels:
                    labels.append(label)
                    used_labels.add(label)
            if labels:
                text = f"{text} {' '.join(labels)}"
            lines.extend((text, ""))

    bibliography_entries = [
        entry for entry in display_entries if entry.label in used_labels
    ]
    if bibliography_entries:
        lines.extend(("## 参考文献", ""))
        for entry in bibliography_entries:
            lines.append(f"{entry.label} {entry.bibliography}")
    report = "\n".join(lines).strip()
    if len(report) > limits.max_shadow_report_chars:
        raise _StructuredValidationError("Final shadow report exceeds capacity")
    return report


async def _render_shadow_report(
    invoke: Callable[[list[HumanMessage]], Awaitable[object]],
    *,
    projection: RendererProjectionOutcome,
    manifest: GroundingManifest,
    display_entries: tuple[SourceDisplayEntry, ...],
    max_retries: int,
    limits: GlobalSynthesisLimits,
    sleep: Callable[[float], Awaitable[None]],
) -> str:
    """Run Model C and Host finalization under one shared logical retry budget."""
    if not projection.claims:
        return _ZERO_ELIGIBLE_REPORT
    projection_payload = json.dumps(
        [claim.model_dump(mode="json") for claim in projection.claims],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    request = [
        HumanMessage(
            content=SHADOW_RENDERER_PROMPT.format(projection=projection_payload)
        )
    ]
    eligible_claim_ids = tuple(claim.claim_id for claim in projection.claims)

    async def invoke_once() -> object:
        return await _invoke_structured_once(
            invoke, request, timeout_seconds=_MODEL_C_TIMEOUT_SECONDS
        )

    def validate(response: object) -> str:
        draft = ShadowReportDraft.model_validate(response)
        _validate_renderer_draft(
            draft,
            eligible_claim_ids=eligible_claim_ids,
            limits=limits,
        )
        return _finalize_shadow_report(
            draft,
            manifest=manifest,
            display_entries=display_entries,
            limits=limits,
        )

    return await _invoke_with_host_retry(
        invoke_once,
        validate,
        max_retries=max_retries,
        sleep=sleep,
    )
