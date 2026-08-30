"""Deterministic tests for the graph-external P2-S5 faithfulness evaluator."""

from __future__ import annotations

import pytest
from p2_s5_faithfulness_evaluator import (
    FaithfulnessDimension,
    FaithfulnessDimensionResult,
    FaithfulnessEvaluation,
    FaithfulnessEvaluatorInput,
    evaluate_faithfulness,
    evaluate_faithfulness_live,
)

from open_deep_research.domain_models import GroundingManifest
from open_deep_research.state import AgentState


def _evaluation(*, failed: FaithfulnessDimension | None = None):
    dimensions = [
        FaithfulnessDimensionResult(
            dimension=dimension,
            passed=dimension is not failed,
            reason="No violation." if dimension is not failed else "Violation found.",
        )
        for dimension in FaithfulnessDimension
    ]
    return FaithfulnessEvaluation(passed=failed is None, dimensions=dimensions)


def _input():
    return FaithfulnessEvaluatorInput(
        shadow_report="Faithful report.",
        manifest=GroundingManifest(claims=[], groundings=[], citations=[]),
        citation_context=[],
    )


class _Model:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = 0

    async def ainvoke(self, _request):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def with_retry(self, **_kwargs):
        raise AssertionError("Evaluator must not install nested retry")


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [None, *list(FaithfulnessDimension)])
async def test_deterministic_pass_and_each_semantic_fail_are_terminal(failed) -> None:
    model = _Model([_evaluation(failed=failed)])
    result = await evaluate_faithfulness(
        model.ainvoke, _input(), max_retries=3
    )

    assert result.passed is (failed is None)
    assert len(result.dimensions) == 6
    assert model.calls == 1


@pytest.mark.asyncio
async def test_schema_validation_retries_immediately_without_sleep() -> None:
    model = _Model([{"passed": True, "dimensions": []}, _evaluation()])
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)

    result = await evaluate_faithfulness(
        model.ainvoke, _input(), max_retries=1, sleep=sleep
    )
    assert result.passed is True
    assert model.calls == 2
    assert sleeps == []


@pytest.mark.asyncio
async def test_transient_retry_backoff_is_capped_and_bounded() -> None:
    model = _Model(
        [
            TimeoutError("one"),
            RuntimeError("two"),
            RuntimeError("three"),
            RuntimeError("four"),
            _evaluation(),
        ]
    )
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)

    result = await evaluate_faithfulness(
        model.ainvoke, _input(), max_retries=4, sleep=sleep
    )
    assert result.passed is True
    assert model.calls == 5
    assert sleeps == [0.5, 1.0, 2.0, 2.0]


def test_evaluator_is_not_a_runtime_state_or_manifest_field() -> None:
    assert "faithfulness_evaluation" not in AgentState.__annotations__
    assert callable(evaluate_faithfulness_live)
