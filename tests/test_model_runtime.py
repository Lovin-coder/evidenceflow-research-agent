"""Deterministic tests for shared model runtime policy construction."""

import ast
import inspect

import pytest

from open_deep_research import model_runtime
from open_deep_research.configuration import Configuration
from open_deep_research.model_runtime import (
    build_configurable_model_runtime_config,
    build_model_runtime_fields,
    resolve_model_enable_thinking,
)


@pytest.mark.parametrize(
    ("global_value", "role_value", "expected"),
    [
        (False, None, False),
        (False, True, True),
        (True, False, False),
        (None, None, None),
    ],
)
def test_resolve_model_enable_thinking_preserves_precedence(
    global_value: bool | None,
    role_value: bool | None,
    expected: bool | None,
) -> None:
    assert resolve_model_enable_thinking(global_value, role_value) is expected


@pytest.mark.parametrize("enable_thinking", [False, True])
def test_build_model_runtime_fields_includes_explicit_thinking_policy(
    enable_thinking: bool,
) -> None:
    assert build_model_runtime_fields(
        model="openai:test-model",
        max_tokens=321,
        api_key="test-key",
        enable_thinking=enable_thinking,
    ) == {
        "model": "openai:test-model",
        "max_tokens": 321,
        "api_key": "test-key",
        "extra_body": {"enable_thinking": enable_thinking},
    }


def test_build_model_runtime_fields_omits_optional_provider_fields() -> None:
    fields = build_model_runtime_fields(
        model="openai:test-model",
        max_tokens=None,
        api_key=None,
        enable_thinking=None,
    )

    assert fields == {"model": "openai:test-model"}
    assert "extra_body" not in fields


def test_build_configurable_model_runtime_config_wraps_shared_fields() -> None:
    runtime_config = build_configurable_model_runtime_config(
        model="openai:test-model",
        max_tokens=123,
        api_key=None,
        enable_thinking=False,
    )

    assert runtime_config == {
        "configurable": {
            "model": "openai:test-model",
            "max_tokens": 123,
            "extra_body": {"enable_thinking": False},
        },
        "tags": ["langsmith:nostream"],
    }


def test_configuration_defaults_preserve_provider_thinking_policy() -> None:
    configurable = Configuration()

    assert configurable.model_enable_thinking is None
    assert configurable.summarization_model_enable_thinking is None
    assert configurable.research_model_enable_thinking is None
    assert configurable.compression_model_enable_thinking is None
    assert configurable.final_report_model_enable_thinking is None


def test_model_runtime_module_has_no_configuration_source_access() -> None:
    tree = ast.parse(inspect.getsource(model_runtime))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    accessed_attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }

    assert "os" not in imported_names
    assert "dotenv" not in imported_modules
    assert "open_deep_research.configuration" not in imported_modules
    assert "load_dotenv" not in called_names
    assert "getenv" not in accessed_attributes
    assert "environ" not in accessed_attributes
    assert "from_runnable_config" not in accessed_attributes
