"""Opt-in real-provider smoke for the P2-S5 runtime and external evaluator."""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from dotenv import load_dotenv
from p2_s5_faithfulness_evaluator import (
    build_faithfulness_input,
    evaluate_faithfulness_live,
)

from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.configuration import Configuration
from open_deep_research.domain_models import (
    EvidenceNeed,
    EvidenceRecord,
    GroundingManifest,
    GroundingStatus,
    MedicalResearchBrief,
    ResearchFinding,
    ResearchTaskResult,
    ResearchTaskStatus,
    SourceRecord,
)
from open_deep_research.global_synthesis.pipeline import (
    _configured_synthesis_models,
    _SynthesisModels,
    run_global_synthesis,
)
from open_deep_research.global_synthesis.projection import TaskQualifiedResolver
from open_deep_research.global_synthesis.renderer import (
    SourceDisplayEntry,
    build_source_display_entries,
)
from open_deep_research.model_runtime import resolve_model_enable_thinking
from open_deep_research.state import GlobalSynthesisStatus

_RUN_PROVIDER_SMOKE = os.getenv("EVIDENCEFLOW_RUN_PROVIDER_SMOKE") == "1"


def _parse_optional_bool(value: str | None, *, name: str) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true"}:
        return True
    if normalized in {"0", "false"}:
        return False
    raise ValueError(f"{name} must be one of: 1, true, 0, false")


def _resolve_evaluator_model(configured_value: str | None, fallback: str) -> str:
    return configured_value or fallback


async def _run_evaluator_smoke(
    *,
    enabled: bool,
    shadow_report: str,
    manifest: GroundingManifest,
    display_entries: list[SourceDisplayEntry],
    model_name: str,
    enable_thinking_value: str | None,
) -> tuple[str, str | None, bool | None]:
    if not enabled:
        return "NOT_EXECUTED", None, None
    try:
        enable_thinking = _parse_optional_bool(
            enable_thinking_value,
            name="EVIDENCEFLOW_EVALUATOR_ENABLE_THINKING",
        )
        evaluator_input = build_faithfulness_input(
            shadow_report=shadow_report,
            manifest=manifest,
            display_entries=display_entries,
        )
        evaluator_result = await evaluate_faithfulness_live(
            evaluator_input,
            model_name=model_name,
            enable_thinking=enable_thinking,
            max_retries=1,
        )
        return (
            "EXECUTED",
            "PASS" if evaluator_result.passed else "FAIL",
            enable_thinking,
        )
    except Exception as error:
        return f"OPERATIONAL_FAILURE:{type(error).__name__}", None, None


def _provider_fixture(
    store: LocalFileArtifactStore,
) -> tuple[MedicalResearchBrief, ResearchTaskResult]:
    excerpt = (
        "In a randomized trial of adults with hypertension, the intervention group "
        "had a mean systolic blood-pressure reduction of 8 mm Hg compared with "
        "control at twelve weeks."
    )
    artifact_ref = store.put_text(excerpt)
    source = SourceRecord(
        source_id="source-smoke-1",
        artifact_ref=artifact_ref,
        metadata={
            "url": "https://example.test/p2-s5-provider-smoke",
            "title": "Controlled P2-S5 provider smoke fixture",
            "provider": "persisted-fixture",
            "retrieved_at": "2026-08-29T00:00:00Z",
            "document_type": "randomized trial",
        },
    )
    evidence = EvidenceRecord(
        evidence_id="evidence-smoke-1",
        source_id=source.source_id,
        locator=f"char:0-{len(excerpt)}",
        excerpt=excerpt,
        hash="sha256:" + "1" * 64,
    )
    result = ResearchTaskResult(
        task_id="task-smoke-1",
        status=ResearchTaskStatus.SUCCESS,
        source_records=[source],
        evidence_records=[evidence],
        findings=[
            ResearchFinding(
                finding_id="finding-smoke-1",
                task_id="task-smoke-1",
                text=(
                    "The intervention reduced mean systolic blood pressure by 8 mm "
                    "Hg relative to control at twelve weeks in the reported trial."
                ),
                evidence_ids=[evidence.evidence_id],
                limitations=["The fixture describes one trial and one follow-up point."],
                conflicts=[],
            )
        ],
        evidence_ids=[evidence.evidence_id],
        source_ids=[source.source_id],
        summary="One persisted trial finding with exact supporting Evidence.",
        limitations=["The fixture is intentionally small."],
        conflicts=[],
    )
    brief = MedicalResearchBrief(
        normalized_question=(
            "What effect did the intervention have on systolic blood pressure at "
            "twelve weeks in the supplied trial?"
        ),
        question_type="therapy",
        clinical_elements=None,
        constraints=["Use only the supplied persisted ResearchTaskResult."],
        research_intent="Summarize the reported comparative blood-pressure outcome.",
        evidence_needs=[
            EvidenceNeed(
                evidence_types=["comparative clinical outcome"],
                study_types=["randomized trial"],
                coverage_dimensions=["effect size", "follow-up time"],
            )
        ],
    )
    return brief, result


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("1", True), ("true", True), ("0", False), ("FALSE", False)],
)
def test_evaluator_thinking_env_parser_preserves_explicit_values(
    value: str | None,
    expected: bool | None,
) -> None:
    assert _parse_optional_bool(
        value,
        name="EVIDENCEFLOW_EVALUATOR_ENABLE_THINKING",
    ) is expected


def test_evaluator_model_falls_back_to_final_report_role() -> None:
    assert _resolve_evaluator_model(None, "openai:final-role") == "openai:final-role"
    assert _resolve_evaluator_model("judge-model", "openai:final-role") == "judge-model"


@pytest.mark.asyncio
async def test_evaluator_smoke_requires_independent_opt_in(monkeypatch) -> None:
    async def forbidden_evaluator(*_args, **_kwargs):
        raise AssertionError("evaluator request must not be made")

    monkeypatch.setattr(
        sys.modules[__name__],
        "evaluate_faithfulness_live",
        forbidden_evaluator,
    )
    status, verdict, thinking = await _run_evaluator_smoke(
        enabled=False,
        shadow_report="report",
        manifest=GroundingManifest(claims=[], groundings=[], citations=[]),
        display_entries=[],
        model_name="openai:test-model",
        enable_thinking_value="false",
    )

    assert (status, verdict, thinking) == ("NOT_EXECUTED", None, None)


@pytest.mark.asyncio
async def test_evaluator_smoke_passes_explicit_independent_policy(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_input(**_kwargs):
        return object()

    async def fake_evaluator(
        _evaluator_input,
        *,
        model_name,
        enable_thinking,
        max_retries,
    ):
        captured.update(
            model_name=model_name,
            enable_thinking=enable_thinking,
            max_retries=max_retries,
        )

        class PassingResult:
            passed = True

        return PassingResult()

    monkeypatch.setattr(sys.modules[__name__], "build_faithfulness_input", fake_build_input)
    monkeypatch.setattr(sys.modules[__name__], "evaluate_faithfulness_live", fake_evaluator)
    status, verdict, thinking = await _run_evaluator_smoke(
        enabled=True,
        shadow_report="report",
        manifest=GroundingManifest(claims=[], groundings=[], citations=[]),
        display_entries=[],
        model_name="openai:test-model",
        enable_thinking_value="false",
    )

    assert (status, verdict, thinking) == ("EXECUTED", "PASS", False)
    assert captured == {
        "model_name": "openai:test-model",
        "enable_thinking": False,
        "max_retries": 1,
    }


def _measured_models(
    configured: _SynthesisModels,
) -> tuple[_SynthesisModels, dict[str, int], dict[str, list[float]]]:
    counts = {"model_a": 0, "model_b": 0, "model_c": 0}
    latencies: dict[str, list[float]] = {
        "model_a": [],
        "model_b": [],
        "model_c": [],
    }

    def measure(
        role: str, invoke: Callable[[object], Awaitable[object]]
    ) -> Callable[[object], Awaitable[object]]:
        async def measured(request: object) -> object:
            counts[role] += 1
            started = time.monotonic()
            try:
                return await invoke(request)
            finally:
                latencies[role].append(round(time.monotonic() - started, 3))

        return measured

    return (
        _SynthesisModels(
            claim_generator=measure("model_a", configured.claim_generator),
            grounding_judge=measure("model_b", configured.grounding_judge),
            shadow_renderer=measure("model_c", configured.shadow_renderer),
        ),
        counts,
        latencies,
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _RUN_PROVIDER_SMOKE,
    reason="set EVIDENCEFLOW_RUN_PROVIDER_SMOKE=1 to run real-provider smoke",
)
async def test_p2_s5_real_provider_smoke(tmp_path: Path, monkeypatch) -> None:
    load_dotenv()
    missing = [
        name
        for name in ("OPENAI_API_KEY", "OPENAI_API_BASE")
        if not os.getenv(name)
    ]
    if missing:
        pytest.skip("provider environment unavailable: missing " + ", ".join(missing))

    for name in (
        "MODEL_ENABLE_THINKING",
        "FINAL_REPORT_MODEL_ENABLE_THINKING",
        "COMPRESSION_MODEL_ENABLE_THINKING",
        "FINAL_REPORT_MODEL_MAX_TOKENS",
        "COMPRESSION_MODEL_MAX_TOKENS",
        "MAX_STRUCTURED_OUTPUT_RETRIES",
        "MAX_CONCURRENT_GROUNDING_JUDGMENTS",
    ):
        monkeypatch.delenv(name, raising=False)
    config = {
        "configurable": {
            "artifact_store_root": str(tmp_path),
            "model_enable_thinking": False,
            "final_report_model_max_tokens": 1500,
            "compression_model_max_tokens": 1000,
            "max_structured_output_retries": 1,
            "max_concurrent_grounding_judgments": 1,
        }
    }
    configurable = Configuration.from_runnable_config(config)
    configured_models = _configured_synthesis_models(config, configurable)
    models, request_counts, role_latencies = _measured_models(configured_models)
    run_id = "p2-s5-real-provider-smoke"
    store = LocalFileArtifactStore(tmp_path, run_id)
    brief, result = _provider_fixture(store)

    outcome = await run_global_synthesis(
        medical_research_brief=brief,
        research_results=[result],
        artifact_run_id=run_id,
        config=config,
        artifact_store=store,
        models=models,
    )

    assert outcome.manifest is not None, "Manifest Gate did not publish"
    assert outcome.shadow_report is not None, "renderer did not produce an output"
    assert outcome.status in {
        GlobalSynthesisStatus.SUCCESS,
        GlobalSynthesisStatus.PARTIAL,
    }
    assert request_counts["model_a"] >= 1

    grounding_counts = {
        status.value: sum(
            grounding.status is status for grounding in outcome.manifest.groundings
        )
        for status in GroundingStatus
    }
    eligible_count = sum(
        grounding.status
        in {GroundingStatus.SUPPORTED, GroundingStatus.SUPPORTED_WITH_CONFLICT}
        for grounding in outcome.manifest.groundings
    )
    if outcome.manifest.claims:
        assert request_counts["model_b"] >= len(outcome.manifest.claims)
    else:
        assert request_counts["model_b"] == 0
    if eligible_count:
        assert request_counts["model_c"] >= 1
    else:
        assert request_counts["model_c"] == 0
    expected_request_counts = {
        "model_a": 1,
        "model_b": len(outcome.manifest.claims),
        "model_c": 1 if eligible_count else 0,
    }
    retry_counts = {
        role: max(0, request_counts[role] - expected_count)
        for role, expected_count in expected_request_counts.items()
    }

    operational_failure_codes = {
        "GLOBAL_SYNTHESIS_PRE_GATE_FAILURE",
        "GROUNDING_UNASSESSED",
        "SHADOW_RENDERER_FAILURE",
    }
    assert not operational_failure_codes.intersection(
        issue.code for issue in outcome.issues
    )

    resolver = TaskQualifiedResolver([result], store)
    display_entries = build_source_display_entries(
        outcome.manifest.citations,
        resolver=resolver,
        artifact_run_id=run_id,
        artifact_store=store,
    )
    evaluator_enabled = os.getenv("EVIDENCEFLOW_RUN_EVALUATOR_SMOKE") == "1"
    evaluator_model = _resolve_evaluator_model(
        os.getenv("EVIDENCEFLOW_EVALUATOR_MODEL"),
        configurable.final_report_model,
    )
    evaluator_status, evaluator_verdict, evaluator_thinking = (
        await _run_evaluator_smoke(
            enabled=evaluator_enabled,
            shadow_report=outcome.shadow_report,
            manifest=outcome.manifest,
            display_entries=display_entries,
            model_name=evaluator_model,
            enable_thinking_value=os.getenv(
                "EVIDENCEFLOW_EVALUATOR_ENABLE_THINKING"
            ),
        )
    )
    final_report_thinking = resolve_model_enable_thinking(
        configurable.model_enable_thinking,
        configurable.final_report_model_enable_thinking,
    )
    compression_thinking = resolve_model_enable_thinking(
        configurable.model_enable_thinking,
        configurable.compression_model_enable_thinking,
    )
    thinking_policy: dict[str, bool | None] = {
        "model_a": final_report_thinking,
        "model_b": compression_thinking,
        "model_c": final_report_thinking,
    }
    if evaluator_enabled:
        thinking_policy["evaluator"] = evaluator_thinking

    sys.stdout.write(
        json.dumps(
            {
                "claim_count": len(outcome.manifest.claims),
                "grounding_status_counts": grounding_counts,
                "citation_count": len(outcome.manifest.citations),
                "manifest_gate": "PASS",
                "renderer": (
                    "MODEL_C_PASS" if eligible_count else "ZERO_ELIGIBLE_HOST_PASS"
                ),
                "global_synthesis_status": outcome.status.value,
                "issues": [
                    issue.model_dump(mode="json") for issue in outcome.issues
                ],
                "model_mapping": {
                    "model_a": configurable.final_report_model,
                    "model_b": configurable.compression_model,
                    "model_c": configurable.final_report_model,
                },
                "thinking_policy": thinking_policy,
                "max_output_tokens": {
                    "model_a": configurable.final_report_model_max_tokens,
                    "model_b": configurable.compression_model_max_tokens,
                    "model_c": configurable.final_report_model_max_tokens,
                },
                "request_counts": request_counts,
                "retry_counts": retry_counts,
                "role_latencies_seconds": role_latencies,
                "evaluator_status": evaluator_status,
                "evaluator_verdict": evaluator_verdict,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
