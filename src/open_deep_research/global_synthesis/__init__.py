"""Minimal public facade for the EvidenceFlow global synthesis subsystem."""

from open_deep_research.global_synthesis.pipeline import run_global_synthesis
from open_deep_research.global_synthesis.types import GlobalSynthesisOutcome

__all__ = ["GlobalSynthesisOutcome", "run_global_synthesis"]
