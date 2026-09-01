"""Graph-external P2-S5 faithfulness evaluator and opt-in live entry."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from enum import Enum

from langchain_openai import ChatOpenAI
from pydantic import Field, model_validator

from open_deep_research.domain_models import (
    Citation,
    ContractModel,
    GroundingManifest,
)
from open_deep_research.global_synthesis.renderer import SourceDisplayEntry
from open_deep_research.global_synthesis.types import (
    _invoke_structured_once,
    _invoke_with_host_retry,
    _StructuredValidationError,
)
from open_deep_research.model_runtime import build_model_runtime_fields

_EVALUATOR_TIMEOUT_SECONDS = 90.0
_MAX_EVALUATOR_INPUT_CHARS = 256_000


class FaithfulnessDimension(str, Enum):
    UNSUPPORTED_FACTUAL_PROPOSITION = "unsupported_factual_proposition"
    SCOPE_EXPANSION = "scope_expansion"
    QUALIFIER_LOSS = "qualifier_loss"
    CONFLICT_OMISSION = "conflict_omission"
    CLAIM_MISREPRESENTATION = "claim_misrepresentation"
    CITATION_CLAIM_PLACEMENT_MISMATCH = "citation_claim_placement_mismatch"


_DIMENSION_ORDER = tuple(FaithfulnessDimension)


class FaithfulnessDimensionResult(ContractModel):
    dimension: FaithfulnessDimension
    passed: bool
    reason: str = Field(min_length=1, max_length=1_000)


class FaithfulnessEvaluation(ContractModel):
    passed: bool
    dimensions: list[FaithfulnessDimensionResult] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def require_complete_consistent_rubric(self) -> "FaithfulnessEvaluation":
        if tuple(result.dimension for result in self.dimensions) != _DIMENSION_ORDER:
            raise ValueError("Faithfulness dimensions must appear once in frozen order")
        if self.passed != all(result.passed for result in self.dimensions):
            raise ValueError("Overall faithfulness PASS must equal all dimension PASS")
        return self


class FaithfulnessCitationView(ContractModel):
    citation: Citation
    label: str = Field(min_length=1, max_length=32)
    bibliography: str = Field(max_length=4_000)


class FaithfulnessEvaluatorInput(ContractModel):
    shadow_report: str = Field(min_length=1, max_length=30_000)
    manifest: GroundingManifest
    citation_context: list[FaithfulnessCitationView] = Field(max_length=512)


def build_faithfulness_input(
    *,
    shadow_report: str,
    manifest: GroundingManifest,
    display_entries: tuple[SourceDisplayEntry, ...],
) -> FaithfulnessEvaluatorInput:
    label_by_citation = {
        citation_id: (entry.label, entry.bibliography)
        for entry in display_entries
        for citation_id in entry.citation_ids
    }
    context = []
    for citation in manifest.citations:
        try:
            label, bibliography = label_by_citation[citation.citation_id]
        except KeyError as error:
            raise _StructuredValidationError(
                "Evaluator Citation has no display context"
            ) from error
        context.append(
            FaithfulnessCitationView(
                citation=citation,
                label=label,
                bibliography=bibliography,
            )
        )
    value = FaithfulnessEvaluatorInput(
        shadow_report=shadow_report,
        manifest=manifest,
        citation_context=context,
    )
    serialized = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(serialized) > _MAX_EVALUATOR_INPUT_CHARS:
        raise _StructuredValidationError("Faithfulness evaluator input exceeds capacity")
    return value


_FAITHFULNESS_PROMPT = """Evaluate the shadow report only against the supplied
authoritative Claim/Manifest and Citation display projection. Return exactly the six
rubric dimensions in the given order. PASS a dimension only if no violation exists.
Do not repair the report and do not provide hidden reasoning.

Dimensions: unsupported factual proposition; scope expansion; qualifier loss;
conflict omission; Claim misrepresentation; Citation/Claim placement mismatch.

Input:
{input}
"""


async def evaluate_faithfulness(
    invoke: Callable[[object], Awaitable[object]],
    evaluator_input: FaithfulnessEvaluatorInput,
    *,
    max_retries: int,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> FaithfulnessEvaluation:
    request = [
        {
            "role": "user",
            "content": _FAITHFULNESS_PROMPT.format(
                input=evaluator_input.model_dump_json()
            ),
        }
    ]

    async def invoke_once() -> object:
        return await _invoke_structured_once(
            invoke, request, timeout_seconds=_EVALUATOR_TIMEOUT_SECONDS
        )

    def validate(response: object) -> FaithfulnessEvaluation:
        return FaithfulnessEvaluation.model_validate(response)

    return await _invoke_with_host_retry(
        invoke_once,
        validate,
        max_retries=max_retries,
        sleep=sleep,
    )


async def evaluate_faithfulness_live(
    evaluator_input: FaithfulnessEvaluatorInput,
    *,
    model_name: str = "gpt-4.1",
    enable_thinking: bool | None = None,
    max_retries: int = 3,
) -> FaithfulnessEvaluation:
    """Callable opt-in live smoke path; deterministic tests never invoke it."""
    chat_openai_model_name = (
        model_name.removeprefix("openai:")
        if model_name.startswith("openai:")
        else model_name
    )
    model_fields = build_model_runtime_fields(
        model=chat_openai_model_name,
        max_tokens=None,
        api_key=None,
        enable_thinking=enable_thinking,
    )
    model = ChatOpenAI(max_retries=0, **model_fields)
    structured = model.with_structured_output(FaithfulnessEvaluation)
    return await evaluate_faithfulness(
        structured.ainvoke,
        evaluator_input,
        max_retries=max_retries,
    )
