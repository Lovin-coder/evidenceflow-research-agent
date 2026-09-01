"""Focused tests for Model A and deterministic Host Claim materialization."""

from __future__ import annotations

import asyncio
import warnings
from dataclasses import replace

import pytest
from test_p2_s5_projection import _brief, _result

from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.domain_models import ClaimMateriality, FindingRef
from open_deep_research.global_synthesis.claims import (
    _invalid_sibling_diagnostic,
    _invoke_claim_generator,
    _materialize_claims,
)
from open_deep_research.global_synthesis.projection import (
    GeneratorProjection,
    TaskQualifiedResolver,
)
from open_deep_research.global_synthesis.types import (
    ClaimDraft,
    ClaimDraftBatch,
    GlobalSynthesisLimits,
)


def _draft(
    text: str,
    *,
    materiality: ClaimMateriality = ClaimMateriality.HIGH,
    finding_id: str = "shared-finding",
) -> ClaimDraft:
    return ClaimDraft(
        text=text,
        materiality=materiality,
        finding_refs=[FindingRef(task_id="task-1", finding_id=finding_id)],
        scope=None,
        qualifiers=[],
    )


def _raw_draft(
    text: str,
    *,
    materiality: str = "high",
    finding_id: str = "shared-finding",
) -> dict[str, object]:
    return {
        "text": text,
        "materiality": materiality,
        "finding_refs": [{"task_id": "task-1", "finding_id": finding_id}],
        "scope": None,
        "qualifiers": [],
    }


def _materialize_batch(tmp_path, batch: ClaimDraftBatch, *, limits=None):
    result = _result("task-1")
    resolver = TaskQualifiedResolver(
        [result], LocalFileArtifactStore(tmp_path, "claim-run")
    )
    return _materialize_claims(
        batch,
        resolver=resolver,
        generator_visible_finding_refs=[
            FindingRef(task_id="task-1", finding_id="shared-finding")
        ],
        limits=limits or GlobalSynthesisLimits(),
    )


def _materialize(tmp_path, drafts: list[object], *, limits=None):
    return _materialize_batch(
        tmp_path,
        ClaimDraftBatch(claims=drafts),
        limits=limits,
    )


def test_claim_batch_exposes_draft_schema_and_serializes_raw_siblings() -> None:
    schema = ClaimDraftBatch.model_json_schema()
    item_schema = schema["properties"]["claims"]["items"]
    if "$ref" in item_schema:
        definition_name = item_schema["$ref"].removeprefix("#/$defs/")
        item_schema = schema["$defs"][definition_name]

    assert set(item_schema["properties"]) == {
        "text",
        "materiality",
        "finding_refs",
        "scope",
        "qualifiers",
    }
    assert item_schema["additionalProperties"] is False

    raw_claims = [
        _raw_draft("Valid claim"),
        {"semantics": "invalid sibling"},
        7,
    ]
    batch = ClaimDraftBatch.model_validate({"claims": raw_claims})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dumped = batch.model_dump(mode="json")

    assert dumped == {"claims": raw_claims}
    assert caught == []


@pytest.mark.parametrize(
    "error",
    [
        TypeError("secret model payload"),
        ValueError("secret model payload"),
    ],
)
def test_ordinary_sibling_errors_do_not_echo_model_payload(error) -> None:
    diagnostic = _invalid_sibling_diagnostic(2, error)

    assert "secret model payload" not in diagnostic
    assert "sibling[2]" in diagnostic


def test_invalid_sibling_is_dropped_without_losing_valid_sibling(tmp_path) -> None:
    outcome = _materialize(
        tmp_path,
        [_draft("Valid claim"), _draft("Invalid claim", finding_id="unseen")],
    )

    assert [claim.text for claim in outcome.claims] == ["Valid claim"]
    assert outcome.invalid_sibling_count == 1
    assert outcome.degradation_observed is True


def test_exact_duplicate_only_and_near_duplicate_survives(tmp_path) -> None:
    first = _draft("Treatment improves outcomes.")
    outcome = _materialize(
        tmp_path,
        [first, first.model_copy(deep=True), _draft("Treatment improves outcomes")],
    )

    assert [claim.text for claim in outcome.claims] == [
        "Treatment improves outcomes.",
        "Treatment improves outcomes",
    ]
    assert outcome.duplicate_count == 1


def test_claim_identity_uses_original_ordinal_not_survivor_ordinal(tmp_path) -> None:
    valid = _draft("Stable claim")
    first = _materialize(
        tmp_path, [_draft("Invalid", finding_id="unseen"), valid]
    )
    second = _materialize(
        tmp_path, [_draft("Different invalid", finding_id="unseen"), valid]
    )

    assert first.claims[0].claim_id == second.claims[0].claim_id
    assert first.receipts[0].original_generator_ordinal == 1


def test_schema_invalid_middle_sibling_preserves_original_ordinals(tmp_path) -> None:
    raw_claims = [
        _raw_draft("Claim A"),
        _raw_draft("Invalid", materiality="critical"),
        _raw_draft("Claim B"),
    ]
    batch = ClaimDraftBatch.model_validate({"claims": raw_claims})

    assert all(type(claim) is dict for claim in batch.claims)
    assert not any(isinstance(claim, ClaimDraft) for claim in batch.claims)

    first = _materialize_batch(tmp_path, batch)
    replay = _materialize(
        tmp_path,
        [
            _raw_draft("Claim A"),
            {"text": "Different invalid sibling"},
            _raw_draft("Claim B"),
        ],
    )

    assert [claim.text for claim in first.claims] == ["Claim A", "Claim B"]
    assert [receipt.original_generator_ordinal for receipt in first.receipts] == [0, 2]
    assert [claim.claim_id for claim in first.claims] == [
        claim.claim_id for claim in replay.claims
    ]
    assert first.invalid_sibling_count == 1
    assert first.degradation_observed is True


def test_capacity_prioritizes_materiality_then_restores_generator_order(tmp_path) -> None:
    outcome = _materialize(
        tmp_path,
        [
            _draft("low-first", materiality=ClaimMateriality.LOW),
            _draft("high-middle", materiality=ClaimMateriality.HIGH),
            _draft("medium-last", materiality=ClaimMateriality.MEDIUM),
        ],
        limits=replace(GlobalSynthesisLimits(), max_claims=2),
    )

    assert [claim.text for claim in outcome.claims] == [
        "high-middle",
        "medium-last",
    ]
    assert outcome.capacity_omission_count == 1


def test_all_invalid_and_valid_empty_batch_are_legal(tmp_path) -> None:
    invalid = _materialize(tmp_path, [_draft("Invalid", finding_id="unseen")])
    empty = _materialize(tmp_path, [])

    assert invalid.claims == ()
    assert invalid.degradation_observed is True
    assert empty.claims == ()
    assert empty.degradation_observed is False


class _SequenceModel:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def ainvoke(self, _request: object) -> object:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def with_retry(self, **_kwargs):
        raise AssertionError("S5 must not install a nested retry layer")


def _projection() -> GeneratorProjection:
    return GeneratorProjection(medical_research_brief=_brief(), results=[])


@pytest.mark.parametrize(
    "invalid_batch",
    [
        {"claims": "not-a-list"},
        ClaimDraftBatch(claims=[{}] * 65),
    ],
)
@pytest.mark.asyncio
async def test_aggregate_validation_retries_immediately_without_sleep(
    invalid_batch,
) -> None:
    model = _SequenceModel([invalid_batch, ClaimDraftBatch(claims=[])])
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    batch = await _invoke_claim_generator(
        model.ainvoke,
        projection=_projection(),
        max_retries=1,
        limits=GlobalSynthesisLimits(),
        sleep=sleep,
    )

    assert batch.claims == []
    assert model.calls == 2
    assert sleeps == []


@pytest.mark.asyncio
async def test_schema_invalid_sibling_does_not_retry_valid_batch(tmp_path) -> None:
    model = _SequenceModel(
        [
            {
                "claims": [
                    _raw_draft("Valid claim"),
                    _raw_draft("Invalid claim", materiality="critical"),
                ]
            }
        ]
    )
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    batch = await _invoke_claim_generator(
        model.ainvoke,
        projection=_projection(),
        max_retries=2,
        limits=GlobalSynthesisLimits(),
        sleep=sleep,
    )
    outcome = _materialize_batch(tmp_path, batch)

    assert [claim.text for claim in outcome.claims] == ["Valid claim"]
    assert outcome.invalid_sibling_count == 1
    assert outcome.degradation_observed is True
    assert model.calls == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_all_schema_invalid_siblings_do_not_retry_outer_batch(tmp_path) -> None:
    model = _SequenceModel(
        [
            {
                "claims": [
                    _raw_draft("Invalid enum", materiality="critical"),
                    {"materiality": "high"},
                ]
            }
        ]
    )

    batch = await _invoke_claim_generator(
        model.ainvoke,
        projection=_projection(),
        max_retries=2,
        limits=GlobalSynthesisLimits(),
        sleep=asyncio.sleep,
    )
    outcome = _materialize_batch(tmp_path, batch)

    assert outcome.claims == ()
    assert outcome.invalid_sibling_count == 2
    assert outcome.degradation_observed is True
    assert model.calls == 1


@pytest.mark.asyncio
async def test_provider_failures_use_backoff_and_request_bound() -> None:
    model = _SequenceModel(
        [TimeoutError("one"), RuntimeError("two"), ClaimDraftBatch(claims=[])]
    )
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    await _invoke_claim_generator(
        model.ainvoke,
        projection=_projection(),
        max_retries=2,
        limits=GlobalSynthesisLimits(),
        sleep=sleep,
    )

    assert model.calls == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.asyncio
async def test_timeout_and_cancellation_are_host_bounded(monkeypatch) -> None:
    observed_timeout: list[float] = []

    async def fake_wait_for(awaitable, timeout):
        observed_timeout.append(timeout)
        return await awaitable

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    model = _SequenceModel([ClaimDraftBatch(claims=[])])
    await _invoke_claim_generator(
        model.ainvoke,
        projection=_projection(),
        max_retries=0,
        limits=GlobalSynthesisLimits(),
        sleep=asyncio.sleep,
    )
    assert observed_timeout == [90.0]

    cancelled = _SequenceModel([asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        await _invoke_claim_generator(
            cancelled.ainvoke,
            projection=_projection(),
            max_retries=3,
            limits=GlobalSynthesisLimits(),
            sleep=asyncio.sleep,
        )
