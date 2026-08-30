"""Model A invocation and deterministic Host Claim materialization."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from open_deep_research.domain_models import ClaimMateriality, ClaimRecord, FindingRef
from open_deep_research.global_synthesis.projection import (
    GeneratorProjection,
    TaskQualifiedResolver,
)
from open_deep_research.global_synthesis.types import (
    ClaimDraft,
    ClaimDraftBatch,
    ClaimMaterializationReceipt,
    GlobalSynthesisLimits,
    _invoke_structured_once,
    _invoke_with_host_retry,
    _validate_claim_draft_batch,
)
from open_deep_research.prompts import CLAIM_GENERATION_PROMPT

_MODEL_A_TIMEOUT_SECONDS = 90.0


@dataclass(frozen=True)
class ClaimMaterializationOutcome:
    """Canonical Claims, Gate receipts, and observable sibling omission facts."""

    claims: tuple[ClaimRecord, ...]
    receipts: tuple[ClaimMaterializationReceipt, ...]
    degradation_observed: bool
    invalid_sibling_count: int
    duplicate_count: int
    capacity_omission_count: int


def _canonical_claim_payload(draft: ClaimDraft) -> bytes:
    """Serialize only the validated semantic payload that participates in identity."""
    payload = {
        "text": draft.text,
        "materiality": draft.materiality.value,
        "finding_refs": [ref.model_dump(mode="json") for ref in draft.finding_refs],
        "scope": draft.scope,
        "qualifiers": draft.qualifiers,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _claim_id(original_generator_ordinal: int, canonical_payload: bytes) -> str:
    """Assign a sibling-stable Host identity using original ordinal and semantics."""
    identity = (
        str(original_generator_ordinal).encode("ascii") + b"\x00" + canonical_payload
    )
    return f"claim:sha256:{hashlib.sha256(identity).hexdigest()}"


def _validate_claim_sibling(
    draft: ClaimDraft,
    *,
    resolver: TaskQualifiedResolver,
    visible_refs: set[tuple[str, str]],
    limits: GlobalSynthesisLimits,
) -> bytes:
    """Validate one sibling without changing or repairing its declared semantics."""
    if len(draft.text) > limits.max_claim_text_chars:
        raise ValueError("Claim text exceeds capacity")
    if draft.scope is not None and len(draft.scope) > limits.max_claim_scope_chars:
        raise ValueError("Claim scope exceeds capacity")
    if len(draft.qualifiers) > limits.max_qualifiers_per_claim:
        raise ValueError("Claim qualifier count exceeds capacity")
    if any(not qualifier.strip() for qualifier in draft.qualifiers):
        raise ValueError("Claim qualifiers must not be blank")
    if any(len(qualifier) > limits.max_qualifier_chars for qualifier in draft.qualifiers):
        raise ValueError("Claim qualifier exceeds capacity")
    if not draft.finding_refs:
        raise ValueError("Claim FindingRefs must not be empty")
    if len(draft.finding_refs) > limits.max_finding_refs_per_claim:
        raise ValueError("Claim FindingRef count exceeds capacity")
    coordinates = [(ref.task_id, ref.finding_id) for ref in draft.finding_refs]
    if len(coordinates) != len(set(coordinates)):
        raise ValueError("Claim FindingRefs must be unique")
    for ref, coordinate in zip(draft.finding_refs, coordinates, strict=True):
        resolver.resolve_finding(ref)
        if coordinate not in visible_refs:
            raise ValueError("Claim FindingRef was not visible to Model A")
    return _canonical_claim_payload(draft)


def _parse_claim_sibling(raw_draft: object) -> ClaimDraft:
    """Validate one raw JSON sibling without making it aggregate authority."""
    if isinstance(raw_draft, ClaimDraft):
        return raw_draft
    serialized = json.dumps(
        raw_draft,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ClaimDraft.model_validate_json(serialized)


def _materialize_claims(
    batch: ClaimDraftBatch,
    *,
    resolver: TaskQualifiedResolver,
    generator_visible_finding_refs: Sequence[FindingRef],
    limits: GlobalSynthesisLimits,
) -> ClaimMaterializationOutcome:
    """Salvage valid siblings, deduplicate exactly, and apply one capacity gate."""
    visible_refs = {
        (ref.task_id, ref.finding_id) for ref in generator_visible_finding_refs
    }
    validated: list[tuple[int, ClaimDraft, bytes]] = []
    seen_payloads: set[bytes] = set()
    invalid_count = 0
    duplicate_count = 0

    for ordinal, raw_draft in enumerate(batch.claims):
        try:
            draft = _parse_claim_sibling(raw_draft)
            payload = _validate_claim_sibling(
                draft,
                resolver=resolver,
                visible_refs=visible_refs,
                limits=limits,
            )
        except (TypeError, ValueError):
            invalid_count += 1
            continue
        if payload in seen_payloads:
            duplicate_count += 1
            continue
        seen_payloads.add(payload)
        validated.append((ordinal, draft, payload))

    capacity_omission_count = max(0, len(validated) - limits.max_claims)
    if capacity_omission_count:
        priority = {
            ClaimMateriality.HIGH: 0,
            ClaimMateriality.MEDIUM: 1,
            ClaimMateriality.LOW: 2,
        }
        selected = sorted(
            validated,
            key=lambda item: (priority[item[1].materiality], item[0]),
        )[: limits.max_claims]
        validated = sorted(selected, key=lambda item: item[0])

    claims: list[ClaimRecord] = []
    receipts: list[ClaimMaterializationReceipt] = []
    for ordinal, draft, payload in validated:
        claim_id = _claim_id(ordinal, payload)
        claims.append(
            ClaimRecord(
                claim_id=claim_id,
                text=draft.text,
                materiality=draft.materiality,
                finding_refs=draft.finding_refs,
                scope=draft.scope,
                qualifiers=draft.qualifiers,
            )
        )
        receipts.append(
            ClaimMaterializationReceipt(
                original_generator_ordinal=ordinal,
                canonical_claim_payload=payload,
                expected_claim_id=claim_id,
            )
        )

    return ClaimMaterializationOutcome(
        claims=tuple(claims),
        receipts=tuple(receipts),
        degradation_observed=bool(
            invalid_count or duplicate_count or capacity_omission_count
        ),
        invalid_sibling_count=invalid_count,
        duplicate_count=duplicate_count,
        capacity_omission_count=capacity_omission_count,
    )


async def _invoke_claim_generator(
    invoke: Callable[[list[HumanMessage]], Awaitable[object]],
    *,
    projection: GeneratorProjection,
    max_retries: int,
    limits: GlobalSynthesisLimits,
    sleep: Callable[[float], Awaitable[None]],
) -> ClaimDraftBatch:
    """Invoke Model A under the sole Host retry authority."""
    request = [
        HumanMessage(
            content=CLAIM_GENERATION_PROMPT.format(
                projection=projection.model_dump_json()
            )
        )
    ]

    async def invoke_once() -> object:
        return await _invoke_structured_once(
            invoke,
            request,
            timeout_seconds=_MODEL_A_TIMEOUT_SECONDS,
        )

    def validate(response: object) -> ClaimDraftBatch:
        batch = ClaimDraftBatch.model_validate(response)
        return _validate_claim_draft_batch(batch, limits)

    return await _invoke_with_host_retry(
        invoke_once,
        validate,
        max_retries=max_retries,
        sleep=sleep,
    )
