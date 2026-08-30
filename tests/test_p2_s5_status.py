"""Focused tests for P2-S5 issue reconciliation and process status."""

from open_deep_research.domain_models import GroundingManifest
from open_deep_research.global_synthesis.pipeline import (
    _derive_global_synthesis_status,
    _make_global_synthesis_issue,
    _reconcile_global_synthesis_issues,
)
from open_deep_research.global_synthesis.types import (
    GlobalSynthesisLimits,
    GlobalSynthesisStage,
)
from open_deep_research.state import (
    GlobalSynthesisSeverity,
    GlobalSynthesisStatus,
)


def _issue(*, message: str = "First wording", degrades: bool = False):
    return _make_global_synthesis_issue(
        stage=GlobalSynthesisStage.CLAIM_MATERIALIZATION,
        code="CLAIM_OMITTED",
        severity=GlobalSynthesisSeverity.WARNING,
        message=message,
        degrades_global_status=degrades,
        claim_id="claim:1",
        occurrence_key="claim:1",
    )


def test_message_only_divergence_retains_first_without_escalation() -> None:
    first = _issue(message="First wording")
    second = _issue(message="Different diagnostic wording")

    outcome = _reconcile_global_synthesis_issues(
        [first], [second], degradation_observed=False
    )

    assert outcome.issues == (first,)
    assert outcome.degradation_observed is False


def test_semantic_divergence_retains_first_and_emits_deterministic_conflict() -> None:
    first = _issue()
    divergent = first.model_copy(
        update={"severity": GlobalSynthesisSeverity.ERROR, "message": "Divergent"}
    )

    one = _reconcile_global_synthesis_issues(
        [first], [divergent], degradation_observed=False
    )
    two = _reconcile_global_synthesis_issues(
        [first], [divergent], degradation_observed=False
    )

    assert one == two
    assert one.issues[0] == first
    assert one.issues[1].code == "ISSUE_PAYLOAD_CONFLICT"
    assert one.degradation_observed is True


def test_late_degradation_survives_a_full_issue_ledger() -> None:
    retained = _issue()
    late = _issue(degrades=True).model_copy(update={"issue_id": "issue:late"})
    limits = GlobalSynthesisLimits(max_global_synthesis_issues=1)

    outcome = _reconcile_global_synthesis_issues(
        [retained], [late], degradation_observed=False, limits=limits
    )

    assert outcome.issues == (retained,)
    assert outcome.degradation_observed is True


def test_severity_does_not_imply_degradation() -> None:
    severe = _issue().model_copy(update={"severity": GlobalSynthesisSeverity.ERROR})

    outcome = _reconcile_global_synthesis_issues(
        [], [severe], degradation_observed=False
    )

    assert outcome.degradation_observed is False


def test_status_uses_manifest_renderer_and_sticky_degradation_only() -> None:
    empty_manifest = GroundingManifest(claims=[], groundings=[], citations=[])

    assert _derive_global_synthesis_status(
        manifest=None, degradation_observed=False, renderer_succeeded=True
    ) is GlobalSynthesisStatus.FAILED
    assert _derive_global_synthesis_status(
        manifest=empty_manifest,
        degradation_observed=False,
        renderer_succeeded=True,
    ) is GlobalSynthesisStatus.SUCCESS
    assert _derive_global_synthesis_status(
        manifest=empty_manifest,
        degradation_observed=True,
        renderer_succeeded=True,
    ) is GlobalSynthesisStatus.PARTIAL
    assert _derive_global_synthesis_status(
        manifest=empty_manifest,
        degradation_observed=False,
        renderer_succeeded=False,
    ) is GlobalSynthesisStatus.PARTIAL
