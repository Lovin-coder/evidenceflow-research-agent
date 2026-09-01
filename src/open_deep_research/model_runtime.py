"""Shared construction helpers for model runtime configuration."""

from typing import Any

from langchain_core.runnables import RunnableConfig


# Model runtime helpers MUST NOT read environment variables directly. Effective Graph
# model policy MUST be resolved through Configuration before model construction.
def resolve_model_enable_thinking(
    global_value: bool | None,
    role_value: bool | None,
) -> bool | None:
    """Resolve a role policy without losing an explicit ``False`` override."""
    return role_value if role_value is not None else global_value


def build_model_runtime_fields(
    *,
    model: str,
    max_tokens: int | None,
    api_key: str | None,
    enable_thinking: bool | None,
) -> dict[str, Any]:
    """Build explicit provider/model fields from already-resolved inputs."""
    fields: dict[str, Any] = {"model": model}
    if max_tokens is not None:
        fields["max_tokens"] = max_tokens
    if api_key is not None:
        fields["api_key"] = api_key
    if enable_thinking is not None:
        fields["extra_body"] = {"enable_thinking": enable_thinking}
    return fields


def build_configurable_model_runtime_config(
    *,
    model: str,
    max_tokens: int | None,
    api_key: str | None,
    enable_thinking: bool | None,
) -> RunnableConfig:
    """Wrap explicit model fields for the shared configurable model."""
    return {
        "configurable": build_model_runtime_fields(
            model=model,
            max_tokens=max_tokens,
            api_key=api_key,
            enable_thinking=enable_thinking,
        ),
        "tags": ["langsmith:nostream"],
    }
