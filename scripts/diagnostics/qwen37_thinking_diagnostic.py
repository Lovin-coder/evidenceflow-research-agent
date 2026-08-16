"""Diagnose Qwen3.7 thinking and structured-output latency.

This script intentionally bypasses LangChain, LangGraph, and EvidenceFlow
runtime code. It talks directly to the OpenAI-compatible provider endpoint.

The diagnostic isolates:
1. Plain completion with thinking disabled.
2. Plain completion with bounded thinking.
3. JSON Schema structured output with thinking disabled.
4. JSON Schema structured output with bounded thinking.
5. Streaming thinking progress without printing reasoning content.
6. Streaming JSON Schema structured output with bounded thinking.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_MODEL = "qwen3.7-plus-2026-05-26"
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_THINKING_BUDGET = 256

CASES = (
    "plain-off",
    "plain-on",
    "structured-off",
    "structured-on",
    "stream-thinking",
    "structured-stream-on",
)


MINIMAL_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "diagnostic_medical_brief",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "normalized_question": {
                    "type": "string",
                    "description": "Normalized medical research question.",
                },
                "question_type": {
                    "type": "string",
                    "description": "High-level type of the medical question.",
                },
            },
            "required": [
                "normalized_question",
                "question_type",
            ],
            "additionalProperties": False,
        },
    },
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for one isolated diagnostic case."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--case",
        choices=CASES,
        required=True,
        help="Diagnostic case to execute.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Provider model ID.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=DEFAULT_THINKING_BUDGET,
        help="Maximum reasoning tokens for thinking-mode cases.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path for the JSON diagnostic result.",
    )

    return parser.parse_args()


def load_provider_config() -> tuple[str, str]:
    """Load API key and base URL without changing project configuration."""
    load_dotenv(".env")

    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    base_url = (
        os.getenv("OPENAI_API_BASE")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("DASHSCOPE_BASE_URL")
    )

    if not api_key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY or DASHSCOPE_API_KEY."
        )

    if not base_url:
        raise RuntimeError(
            "Missing OPENAI_API_BASE / OPENAI_BASE_URL / "
            "DASHSCOPE_BASE_URL."
        )

    return api_key, base_url.rstrip("/")


def build_client(
    api_key: str,
    base_url: str,
    timeout: float,
) -> OpenAI:
    """Create a direct client with retries disabled for clean diagnosis."""
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=0,
    )


def safe_model_dump(value: Any) -> Any:
    """Convert SDK objects to JSON-compatible diagnostic output."""
    if value is None:
        return None

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if isinstance(value, (str, int, float, bool, list, dict)):
        return value

    return str(value)


def extract_reasoning_content(message: Any) -> str:
    """Read provider-specific reasoning content without printing it."""
    reasoning = getattr(message, "reasoning_content", None)

    if reasoning is None:
        model_extra = getattr(message, "model_extra", None) or {}
        reasoning = model_extra.get("reasoning_content")

    return reasoning or ""


def print_result_summary(result: dict[str, Any]) -> None:
    """Print only latency, usage, and response metadata."""
    print("\n" + "=" * 72)
    print(f"case:             {result['case']}")
    print(f"model:            {result['model']}")
    print(f"status:           {result['status']}")
    print(f"elapsed_seconds:  {result['elapsed_seconds']}")

    if result.get("response_id"):
        print(f"response_id:      {result['response_id']}")

    if result.get("finish_reason"):
        print(f"finish_reason:    {result['finish_reason']}")

    if "content_chars" in result:
        print(f"content_chars:    {result['content_chars']}")

    if "reasoning_chars" in result:
        print(f"reasoning_chars:  {result['reasoning_chars']}")

    if result.get("first_reasoning_seconds") is not None:
        print(
            "first_reasoning:  "
            f"{result['first_reasoning_seconds']} s"
        )

    if result.get("first_content_seconds") is not None:
        print(
            "first_content:    "
            f"{result['first_content_seconds']} s"
        )

    if result.get("usage") is not None:
        print("usage:")
        print(
            json.dumps(
                result["usage"],
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    if result.get("error"):
        print(f"error_type:       {result['error_type']}")
        print(f"error:            {result['error']}")

    print("=" * 72)


def run_non_streaming_case(
    *,
    client: OpenAI,
    case: str,
    model: str,
    enable_thinking: bool,
    thinking_budget: int | None,
    structured: bool,
) -> dict[str, Any]:
    """Run one non-streaming provider request and record timing/usage."""
    messages = [
        {
            "role": "user",
            "content": (
                "For an adult with mild primary hypertension and no "
                "chronic kidney disease, compare ACE inhibitors and ARBs. "
                "Return only the requested concise result."
            ),
        }
    ]

    extra_body: dict[str, Any] = {
        "enable_thinking": enable_thinking,
    }

    if enable_thinking and thinking_budget is not None:
        extra_body["thinking_budget"] = thinking_budget

    request: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "extra_body": extra_body,
    }

    if structured:
        request["response_format"] = MINIMAL_JSON_SCHEMA

    started = time.perf_counter()

    try:
        completion = client.chat.completions.create(**request)
        elapsed = time.perf_counter() - started

        choice = completion.choices[0]
        message = choice.message

        content = message.content or ""
        reasoning = extract_reasoning_content(message)

        result = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "case": case,
            "model": model,
            "status": "PASS",
            "elapsed_seconds": round(elapsed, 3),
            "response_id": completion.id,
            "finish_reason": choice.finish_reason,
            "content_chars": len(content),
            "reasoning_chars": len(reasoning),
            "content_preview": content[:500],
            "usage": safe_model_dump(completion.usage),
        }

        if structured:
            try:
                result["parsed_json"] = json.loads(content)
                result["json_parse"] = "PASS"
            except json.JSONDecodeError as exc:
                result["json_parse"] = "FAIL"
                result["json_error"] = str(exc)

        return result

    except Exception as exc:
        elapsed = time.perf_counter() - started

        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "case": case,
            "model": model,
            "status": "FAIL",
            "elapsed_seconds": round(elapsed, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def run_streaming_thinking_case(
    *,
    client: OpenAI,
    model: str,
    thinking_budget: int,
) -> dict[str, Any]:
    """Measure when reasoning and final-answer chunks first arrive."""
    started = time.perf_counter()

    first_chunk_seconds: float | None = None
    first_reasoning_seconds: float | None = None
    first_content_seconds: float | None = None

    reasoning_chars = 0
    content_chars = 0
    usage: Any = None

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Briefly compare ACE inhibitors and ARBs for "
                        "mild primary hypertension."
                    ),
                }
            ],
            extra_body={
                "enable_thinking": True,
                "thinking_budget": thinking_budget,
            },
            stream=True,
            stream_options={
                "include_usage": True,
            },
        )

        for chunk in stream:
            now = time.perf_counter()

            if first_chunk_seconds is None:
                first_chunk_seconds = now - started

            if getattr(chunk, "usage", None) is not None:
                usage = safe_model_dump(chunk.usage)

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning is None:
                model_extra = getattr(delta, "model_extra", None) or {}
                reasoning = model_extra.get("reasoning_content")

            if reasoning:
                if first_reasoning_seconds is None:
                    first_reasoning_seconds = now - started
                    print(
                        "First reasoning chunk received at "
                        f"{first_reasoning_seconds:.3f}s"
                    )

                reasoning_chars += len(reasoning)

            content = getattr(delta, "content", None)

            if content:
                if first_content_seconds is None:
                    first_content_seconds = now - started
                    print(
                        "First final-content chunk received at "
                        f"{first_content_seconds:.3f}s"
                    )

                content_chars += len(content)

        elapsed = time.perf_counter() - started

        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "case": "stream-thinking",
            "model": model,
            "status": "PASS",
            "elapsed_seconds": round(elapsed, 3),
            "first_chunk_seconds": (
                round(first_chunk_seconds, 3)
                if first_chunk_seconds is not None
                else None
            ),
            "first_reasoning_seconds": (
                round(first_reasoning_seconds, 3)
                if first_reasoning_seconds is not None
                else None
            ),
            "first_content_seconds": (
                round(first_content_seconds, 3)
                if first_content_seconds is not None
                else None
            ),
            "reasoning_chars": reasoning_chars,
            "content_chars": content_chars,
            "usage": usage,
        }

    except Exception as exc:
        elapsed = time.perf_counter() - started

        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "case": "stream-thinking",
            "model": model,
            "status": "FAIL",
            "elapsed_seconds": round(elapsed, 3),
            "first_chunk_seconds": first_chunk_seconds,
            "first_reasoning_seconds": first_reasoning_seconds,
            "first_content_seconds": first_content_seconds,
            "reasoning_chars": reasoning_chars,
            "content_chars": content_chars,
            "usage": usage,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def run_streaming_structured_case(
    *,
    client: OpenAI,
    model: str,
    thinking_budget: int,
) -> dict[str, Any]:
    """Stream structured output while recording reasoning size and timing."""
    started = time.perf_counter()

    first_chunk_seconds: float | None = None
    first_reasoning_seconds: float | None = None
    first_content_seconds: float | None = None

    reasoning_chars = 0
    content_parts: list[str] = []
    usage: Any = None

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "For an adult with mild primary hypertension and no "
                        "chronic kidney disease, compare ACE inhibitors and ARBs. "
                        "Return only the requested concise result."
                    ),
                }
            ],
            extra_body={
                "enable_thinking": True,
                "thinking_budget": thinking_budget,
            },
            response_format=MINIMAL_JSON_SCHEMA,
            stream=True,
            stream_options={
                "include_usage": True,
            },
        )

        for chunk in stream:
            now = time.perf_counter()

            if first_chunk_seconds is None:
                first_chunk_seconds = now - started

            if getattr(chunk, "usage", None) is not None:
                usage = safe_model_dump(chunk.usage)

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning is None:
                model_extra = getattr(delta, "model_extra", None) or {}
                reasoning = model_extra.get("reasoning_content")

            if reasoning:
                if first_reasoning_seconds is None:
                    first_reasoning_seconds = now - started
                reasoning_chars += len(reasoning)

            content = getattr(delta, "content", None)

            if content:
                if first_content_seconds is None:
                    first_content_seconds = now - started
                content_parts.append(content)

        elapsed = time.perf_counter() - started
        content = "".join(content_parts)

        result = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "case": "structured-stream-on",
            "model": model,
            "status": "PASS",
            "elapsed_seconds": round(elapsed, 3),
            "first_chunk_seconds": (
                round(first_chunk_seconds, 3)
                if first_chunk_seconds is not None
                else None
            ),
            "first_reasoning_seconds": (
                round(first_reasoning_seconds, 3)
                if first_reasoning_seconds is not None
                else None
            ),
            "first_content_seconds": (
                round(first_content_seconds, 3)
                if first_content_seconds is not None
                else None
            ),
            "reasoning_chars": reasoning_chars,
            "content_chars": len(content),
            "usage": usage,
        }

        try:
            result["parsed_json"] = json.loads(content)
            result["json_parse"] = "PASS"
        except json.JSONDecodeError as exc:
            result["json_parse"] = "FAIL"
            result["json_error"] = str(exc)

        return result

    except Exception as exc:
        elapsed = time.perf_counter() - started

        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "case": "structured-stream-on",
            "model": model,
            "status": "FAIL",
            "elapsed_seconds": round(elapsed, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> int:
    """Execute exactly one diagnostic case."""
    args = parse_args()

    api_key, base_url = load_provider_config()

    print("Qwen provider diagnostic")
    print(f"model:            {args.model}")
    print(f"base_url:         {base_url}")
    print(f"case:             {args.case}")
    print(f"timeout:          {args.timeout}s")
    print(f"thinking_budget:  {args.thinking_budget}")
    print("max_retries:      0")
    print("API key:          [hidden]")

    client = build_client(
        api_key=api_key,
        base_url=base_url,
        timeout=args.timeout,
    )

    if args.case == "plain-off":
        result = run_non_streaming_case(
            client=client,
            case=args.case,
            model=args.model,
            enable_thinking=False,
            thinking_budget=None,
            structured=False,
        )

    elif args.case == "plain-on":
        result = run_non_streaming_case(
            client=client,
            case=args.case,
            model=args.model,
            enable_thinking=True,
            thinking_budget=args.thinking_budget,
            structured=False,
        )

    elif args.case == "structured-off":
        result = run_non_streaming_case(
            client=client,
            case=args.case,
            model=args.model,
            enable_thinking=False,
            thinking_budget=None,
            structured=True,
        )

    elif args.case == "structured-on":
        result = run_non_streaming_case(
            client=client,
            case=args.case,
            model=args.model,
            enable_thinking=True,
            thinking_budget=args.thinking_budget,
            structured=True,
        )

    elif args.case == "structured-stream-on":
        result = run_streaming_structured_case(
            client=client,
            model=args.model,
            thinking_budget=args.thinking_budget,
        )

    else:
        result = run_streaming_thinking_case(
            client=client,
            model=args.model,
            thinking_budget=args.thinking_budget,
        )

    print_result_summary(result)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"\nSaved result: {args.output}")

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
