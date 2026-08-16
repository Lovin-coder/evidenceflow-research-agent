"""Diagnose the LangChain structured-output path used for research briefs."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, get_buffer_string

from open_deep_research.configuration import Configuration
from open_deep_research.domain_models import MedicalResearchBrief
from open_deep_research.prompts import transform_messages_into_research_topic_prompt
from open_deep_research.utils import get_api_key_for_model, get_today_str

MODEL = "openai:qwen3.7-plus-2026-05-26"
DEFAULT_TIMEOUT_SECONDS = 60.0
QUESTION = "For adults with mild primary hypertension, compare ACE inhibitors and ARBs."


def parse_args() -> argparse.Namespace:
    """Parse diagnostic-only timeout and output arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Provider request timeout in seconds.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/qwen37_langchain_structured_off.json"),
        help="Path for the JSON diagnostic result.",
    )
    return parser.parse_args()


def type_name(value: Any) -> str:
    """Return a fully qualified Python type name for diagnostic output."""
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


async def run_diagnostic(timeout: float) -> dict[str, Any]:
    """Invoke only the planning model path and record its typed response."""
    load_dotenv(".env")

    runnable_config = {
        "configurable": {
            "research_model": MODEL,
        }
    }
    configurable = Configuration.from_runnable_config(runnable_config)
    if configurable.research_model != MODEL:
        raise RuntimeError(
            "Resolved RESEARCH_MODEL does not match the diagnostic model: "
            f"{configurable.research_model!r}"
        )

    api_key = get_api_key_for_model(configurable.research_model, runnable_config)
    if api_key is None:
        raise RuntimeError("No API key resolved for the configured research model.")

    request_observation: dict[str, Any] = {
        "request_seen": False,
        "request_count": 0,
        "enable_thinking": None,
        "response_format_type": None,
        "tools_present": False,
    }

    async def observe_request(request: httpx.Request) -> None:
        """Record only non-secret request controls needed by this diagnostic."""
        request_observation["request_seen"] = True
        request_observation["request_count"] += 1
        try:
            payload = json.loads(request.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        request_observation["enable_thinking"] = payload.get("enable_thinking")
        response_format = payload.get("response_format")
        if isinstance(response_format, dict):
            request_observation["response_format_type"] = response_format.get("type")
        request_observation["tools_present"] = bool(payload.get("tools"))

    started = time.perf_counter()
    result: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": configurable.research_model,
        "model_initialization": (
            "langchain.chat_models.init_chat_model"
            "(configurable_fields=('model', 'max_tokens', 'api_key', "
            "'extra_body', 'max_retries', 'timeout'))"
        ),
        "production_configurable_fields": ["model", "max_tokens", "api_key"],
        "diagnostic_only_configurable_fields": [
            "extra_body",
            "max_retries",
            "timeout",
        ],
        "configuration_path": (
            "Configuration.from_runnable_config -> get_api_key_for_model -> "
            "configurable_model.with_config"
        ),
        "structured_output_method": "with_structured_output(MedicalResearchBrief)",
        "thinking_requested": False,
        "sdk_max_retries": 0,
        "runnable_attempts": 1,
    }

    try:
        # Keep the production fields and expose only the transport controls needed
        # by this standalone diagnostic.
        configurable_model = init_chat_model(
            configurable_fields=(
                "model",
                "max_tokens",
                "api_key",
                "extra_body",
                "max_retries",
                "timeout",
            ),
        )
        research_model_config = {
            "model": configurable.research_model,
            "max_tokens": configurable.research_model_max_tokens,
            "api_key": api_key,
            "extra_body": {"enable_thinking": False},
            "max_retries": 0,
            "timeout": timeout,
            "tags": ["langsmith:nostream"],
        }
        research_model = (
            configurable_model.with_structured_output(MedicalResearchBrief)
            .with_retry(stop_after_attempt=1)
            .with_config(research_model_config)
        )

        messages = [HumanMessage(content=QUESTION)]
        prompt_content = transform_messages_into_research_topic_prompt.format(
            messages=get_buffer_string(messages),
            date=get_today_str(),
        )

        original_send = httpx.AsyncClient.send

        async def observed_send(
            client: httpx.AsyncClient,
            request: httpx.Request,
            *args: Any,
            **kwargs: Any,
        ) -> httpx.Response:
            await observe_request(request)
            return await original_send(client, request, *args, **kwargs)

        with patch.object(httpx.AsyncClient, "send", new=observed_send):
            response = await research_model.ainvoke([HumanMessage(content=prompt_content)])

        brief = MedicalResearchBrief.model_validate(response)
        result.update(
            {
                "status": "PASS",
                "returned_python_type": type_name(response),
                "serialized_medical_research_brief": brief.model_dump(mode="json"),
            }
        )
    except Exception as exc:
        result.update(
            {
                "status": "FAIL",
                "exception_type": type_name(exc),
                "exception_message": str(exc),
            }
        )

    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    result["provider_request_observation"] = request_observation
    result["thinking_off_propagated"] = (
        request_observation["request_seen"]
        and request_observation["enable_thinking"] is False
    )
    return result


async def async_main() -> int:
    """Run the diagnostic and persist its secret-free JSON result."""
    args = parse_args()
    result = await run_diagnostic(args.timeout)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    print(rendered)  # noqa: T201
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    print(f"Saved result: {args.output}")  # noqa: T201
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
