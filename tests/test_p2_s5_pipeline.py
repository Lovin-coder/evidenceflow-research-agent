"""Deterministic end-to-end tests for the typed global synthesis pipeline."""

from __future__ import annotations

import re

import pytest
from test_p2_s5_projection import _brief, _result

import open_deep_research.global_synthesis.pipeline as pipeline_runtime
from open_deep_research.artifact_store import LocalFileArtifactStore
from open_deep_research.configuration import Configuration
from open_deep_research.domain_models import (
    ClaimMateriality,
    EvidenceRef,
    FindingRef,
    GroundingManifest,
)
from open_deep_research.global_synthesis.pipeline import (
    _configured_synthesis_models,
    _SynthesisModels,
    run_global_synthesis,
)
from open_deep_research.global_synthesis.types import (
    ClaimDraft,
    ClaimDraftBatch,
    ClaimEvidenceVerdict,
    ClaimGroundingDraft,
    ReportParagraphDraft,
    ReportSectionDraft,
    ShadowReportDraft,
)
from open_deep_research.prompts import CLAIM_GENERATION_PROMPT
from open_deep_research.state import GlobalSynthesisStatus


class _HappyModels:
    def __init__(self, *, renderer_failure: bool = False) -> None:
        self.calls = {"a": 0, "b": 0, "c": 0}
        self.renderer_failure = renderer_failure

    async def model_a(self, _request):
        self.calls["a"] += 1
        return ClaimDraftBatch(
            claims=[
                ClaimDraft(
                    text="Treatment improves outcomes.",
                    materiality=ClaimMateriality.HIGH,
                    finding_refs=[
                        FindingRef(
                            task_id="task-1", finding_id="shared-finding"
                        )
                    ],
                    scope=None,
                    qualifiers=[],
                )
            ]
        )

    async def model_b(self, _request):
        self.calls["b"] += 1
        return ClaimGroundingDraft(
            verdict=ClaimEvidenceVerdict.SUPPORTED,
            supporting_evidence_refs=[
                EvidenceRef(task_id="task-1", evidence_id="shared-evidence")
            ],
            contradicting_evidence_refs=[],
            reason="Direct support.",
        )

    async def model_c(self, request):
        self.calls["c"] += 1
        if self.renderer_failure:
            raise RuntimeError("renderer unavailable")
        claim_id = re.search(r"claim:sha256:[0-9a-f]+", request[0].content).group(0)
        return ShadowReportDraft(
            sections=[
                ReportSectionDraft(
                    title="Findings",
                    paragraphs=[
                        ReportParagraphDraft(
                            text="Treatment improves outcomes.",
                            claim_ids=[claim_id],
                        )
                    ],
                )
            ]
        )

    def bundle(self) -> _SynthesisModels:
        return _SynthesisModels(self.model_a, self.model_b, self.model_c)


class _RawClaimModels(_HappyModels):
    def __init__(self, claims: list[object]) -> None:
        super().__init__()
        self.claims = claims

    async def model_a(self, _request):
        self.calls["a"] += 1
        return {"claims": self.claims}


def _raw_claim(text: str, *, materiality: str = "high") -> dict[str, object]:
    return {
        "text": text,
        "materiality": materiality,
        "finding_refs": [
            {"task_id": "task-1", "finding_id": "shared-finding"}
        ],
        "scope": None,
        "qualifiers": [],
    }


def test_claim_generation_prompt_matches_claim_draft_wire_contract() -> None:
    for field_name in (
        "text",
        "materiality",
        "finding_refs",
        "scope",
        "qualifiers",
    ):
        assert f"`{field_name}`" in CLAIM_GENERATION_PROMPT

    assert "`task_id` and `finding_id`" in CLAIM_GENERATION_PROMPT
    assert "otherwise use null" in CLAIM_GENERATION_PROMPT
    assert "use a list of strings, or an empty list" in CLAIM_GENERATION_PROMPT
    assert "when no qualifier applies" in CLAIM_GENERATION_PROMPT
    assert "Do not emit `semantics` or any other extra field" in CLAIM_GENERATION_PROMPT
    assert "return an empty `claims` list" in CLAIM_GENERATION_PROMPT
    assert "Return Claim semantics and FindingRefs only" not in CLAIM_GENERATION_PROMPT


def test_configured_synthesis_models_preserve_role_mapping_and_policy(
    monkeypatch,
) -> None:
    """Keep A/C on final-report policy and B on compression policy."""
    monkeypatch.delenv("MODEL_ENABLE_THINKING", raising=False)
    monkeypatch.delenv("FINAL_REPORT_MODEL_ENABLE_THINKING", raising=False)
    monkeypatch.delenv("COMPRESSION_MODEL_ENABLE_THINKING", raising=False)
    calls: list[dict[str, object]] = []

    class CapturingStructuredModel:
        def __init__(self, call: dict[str, object]) -> None:
            self.call = call

        def with_structured_output(self, schema):
            self.call["schema"] = schema
            return self

        async def ainvoke(self, _request):
            raise AssertionError("construction test must not invoke a model")

    def fake_init_chat_model(**kwargs):
        call = dict(kwargs)
        calls.append(call)
        return CapturingStructuredModel(call)

    monkeypatch.setattr(pipeline_runtime, "init_chat_model", fake_init_chat_model)
    monkeypatch.setattr(
        pipeline_runtime,
        "get_api_key_for_model",
        lambda model_name, _config: f"key-for-{model_name}",
    )

    models = _configured_synthesis_models(
        {},
        Configuration(
            model_enable_thinking=False,
            final_report_model="openai:final-role",
            final_report_model_max_tokens=1500,
            final_report_model_enable_thinking=None,
            compression_model="openai:compression-role",
            compression_model_max_tokens=1000,
            compression_model_enable_thinking=True,
        ),
    )

    assert callable(models.claim_generator)
    assert callable(models.grounding_judge)
    assert callable(models.shadow_renderer)
    assert [call["model"] for call in calls] == [
        "openai:final-role",
        "openai:compression-role",
        "openai:final-role",
    ]
    assert [call["max_tokens"] for call in calls] == [1500, 1000, 1500]
    assert [call["extra_body"] for call in calls] == [
        {"enable_thinking": False},
        {"enable_thinking": True},
        {"enable_thinking": False},
    ]
    assert [call["schema"] for call in calls] == [
        ClaimDraftBatch,
        ClaimGroundingDraft,
        ShadowReportDraft,
    ]
    assert all(call["max_retries"] == 0 for call in calls)


@pytest.mark.asyncio
async def test_pipeline_happy_path_publishes_manifest_then_report(tmp_path) -> None:
    models = _HappyModels()
    outcome = await run_global_synthesis(
        medical_research_brief=_brief(),
        research_results=[_result("task-1")],
        artifact_run_id="pipeline-run",
        config={"configurable": {"max_structured_output_retries": 0}},
        artifact_store=LocalFileArtifactStore(tmp_path, "pipeline-run"),
        models=models.bundle(),
    )

    assert outcome.status is GlobalSynthesisStatus.SUCCESS
    assert outcome.manifest is not None
    assert len(outcome.manifest.claims) == 1
    assert len(outcome.manifest.citations) == 1
    assert outcome.shadow_report is not None
    assert models.calls == {"a": 1, "b": 1, "c": 1}


@pytest.mark.asyncio
async def test_schema_invalid_claim_sibling_publishes_partial_manifest(tmp_path) -> None:
    models = _RawClaimModels(
        [
            _raw_claim("Treatment improves outcomes."),
            _raw_claim("Invalid sibling", materiality="critical"),
        ]
    )
    outcome = await run_global_synthesis(
        medical_research_brief=_brief(),
        research_results=[_result("task-1")],
        artifact_run_id="schema-sibling-run",
        config={"configurable": {"max_structured_output_retries": 2}},
        artifact_store=LocalFileArtifactStore(tmp_path, "schema-sibling-run"),
        models=models.bundle(),
    )

    assert outcome.status is GlobalSynthesisStatus.PARTIAL
    assert outcome.manifest is not None
    assert [claim.text for claim in outcome.manifest.claims] == [
        "Treatment improves outcomes."
    ]
    omission = next(
        issue for issue in outcome.issues if issue.code == "CLAIM_SIBLING_OMISSION"
    )
    assert "invalid=1, duplicate=0, capacity=0" in omission.message
    assert "sibling[1]" in omission.message
    assert "materiality" in omission.message
    assert models.calls == {"a": 1, "b": 1, "c": 1}


@pytest.mark.asyncio
async def test_all_schema_invalid_claims_publish_degraded_empty_manifest(tmp_path) -> None:
    models = _RawClaimModels(
        [
            _raw_claim("Invalid enum", materiality="critical"),
            {"materiality": "high"},
        ]
    )
    outcome = await run_global_synthesis(
        medical_research_brief=_brief(),
        research_results=[_result("task-1")],
        artifact_run_id="all-invalid-siblings-run",
        config={"configurable": {"max_structured_output_retries": 2}},
        artifact_store=LocalFileArtifactStore(tmp_path, "all-invalid-siblings-run"),
        models=models.bundle(),
    )

    assert outcome.status is GlobalSynthesisStatus.PARTIAL
    assert outcome.manifest == GroundingManifest(claims=[], groundings=[], citations=[])
    omission = next(
        issue for issue in outcome.issues if issue.code == "CLAIM_SIBLING_OMISSION"
    )
    assert "invalid=2, duplicate=0, capacity=0" in omission.message
    assert "sibling[0]" in omission.message
    assert "sibling[1]" in omission.message
    assert models.calls == {"a": 1, "b": 0, "c": 0}


@pytest.mark.asyncio
async def test_valid_empty_path_skips_all_models_and_publishes_empty_manifest(
    tmp_path,
) -> None:
    models = _HappyModels()
    outcome = await run_global_synthesis(
        medical_research_brief=_brief(),
        research_results=[],
        artifact_run_id="empty-run",
        config={"configurable": {"max_structured_output_retries": 0}},
        artifact_store=LocalFileArtifactStore(tmp_path, "empty-run"),
        models=models.bundle(),
    )

    assert outcome.status is GlobalSynthesisStatus.SUCCESS
    assert outcome.manifest == GroundingManifest(
        claims=[], groundings=[], citations=[]
    )
    assert outcome.shadow_report is not None
    assert models.calls == {"a": 0, "b": 0, "c": 0}


@pytest.mark.asyncio
async def test_pre_gate_failure_has_no_manifest(tmp_path) -> None:
    async def fail(_request):
        raise RuntimeError("generator failed")

    models = _SynthesisModels(fail, fail, fail)
    outcome = await run_global_synthesis(
        medical_research_brief=_brief(),
        research_results=[_result("task-1")],
        artifact_run_id="failed-run",
        config={"configurable": {"max_structured_output_retries": 0}},
        artifact_store=LocalFileArtifactStore(tmp_path, "failed-run"),
        models=models,
    )

    assert outcome.status is GlobalSynthesisStatus.FAILED
    assert outcome.manifest is None
    assert outcome.shadow_report is None


@pytest.mark.asyncio
async def test_post_gate_renderer_failure_preserves_manifest(tmp_path) -> None:
    models = _HappyModels(renderer_failure=True)
    outcome = await run_global_synthesis(
        medical_research_brief=_brief(),
        research_results=[_result("task-1")],
        artifact_run_id="partial-run",
        config={"configurable": {"max_structured_output_retries": 0}},
        artifact_store=LocalFileArtifactStore(tmp_path, "partial-run"),
        models=models.bundle(),
    )

    assert outcome.status is GlobalSynthesisStatus.PARTIAL
    assert outcome.manifest is not None
    assert outcome.shadow_report is None


@pytest.mark.asyncio
async def test_replay_short_circuits_models_and_partial_is_not_repaired(tmp_path) -> None:
    models = _HappyModels()
    manifest = GroundingManifest(claims=[], groundings=[], citations=[])
    complete = await run_global_synthesis(
        medical_research_brief=None,
        research_results=[],
        artifact_run_id=None,
        config={},
        existing_manifest=manifest,
        existing_shadow_report="existing report",
        existing_status=GlobalSynthesisStatus.SUCCESS,
        models=models.bundle(),
    )
    partial = await run_global_synthesis(
        medical_research_brief=None,
        research_results=[],
        artifact_run_id=None,
        config={},
        existing_manifest=manifest,
        existing_shadow_report=None,
        existing_status=GlobalSynthesisStatus.PARTIAL,
        models=models.bundle(),
    )

    assert complete.shadow_report == "existing report"
    assert partial.manifest is manifest and partial.shadow_report is None
    assert models.calls == {"a": 0, "b": 0, "c": 0}


@pytest.mark.asyncio
async def test_invalid_existing_manifest_envelope_is_contained_not_regenerated() -> None:
    models = _HappyModels()
    manifest = GroundingManifest(claims=[], groundings=[], citations=[])

    outcome = await run_global_synthesis(
        medical_research_brief=_brief(),
        research_results=[_result("task-1")],
        artifact_run_id="invalid-replay-run",
        config={},
        existing_manifest=manifest,
        existing_shadow_report=None,
        existing_status=GlobalSynthesisStatus.SUCCESS,
        models=models.bundle(),
    )

    assert outcome.manifest is manifest
    assert outcome.shadow_report is None
    assert outcome.status is GlobalSynthesisStatus.PARTIAL
    assert models.calls == {"a": 0, "b": 0, "c": 0}
