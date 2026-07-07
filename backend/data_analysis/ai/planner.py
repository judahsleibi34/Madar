from __future__ import annotations

import json
from typing import Any

from data_analysis.ai.prompts import (
    CODE_GENERATOR_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    build_code_generation_prompt,
    build_planner_prompt,
)
from data_analysis.ai.settings import (
    AIModelConfig,
    get_model_config_for_plan,
    get_provider_api_key,
)


class AIPlannerError(RuntimeError):
    pass


def parse_json_response(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise AIPlannerError("AI response was empty")

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()

        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIPlannerError(f"AI response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise AIPlannerError("AI response JSON must be an object")

    return parsed


def ask_planner(
    compact_profile: dict[str, Any],
    allowed_columns: list[str] | set[str] | tuple[str, ...],
    user_message: str,
    user_plan: str | None = "free",
) -> dict[str, Any]:
    model_config = get_model_config_for_plan(user_plan)

    prompt = build_planner_prompt(
        compact_profile=compact_profile,
        allowed_columns=allowed_columns,
        user_message=user_message,
    )

    return _call_provider_json(
        model_config=model_config,
        system_prompt=PLANNER_SYSTEM_PROMPT,
        user_prompt=prompt,
    )


def ask_code_generator(
    full_profile: dict[str, Any],
    approved_columns: list[str] | set[str] | tuple[str, ...],
    analysis_goal: str,
    assumptions: list[str] | None = None,
    user_plan: str | None = "free",
) -> dict[str, Any]:
    model_config = get_model_config_for_plan(user_plan)

    prompt = build_code_generation_prompt(
        full_profile=full_profile,
        approved_columns=approved_columns,
        analysis_goal=analysis_goal,
        assumptions=assumptions or [],
    )

    return _call_provider_json(
        model_config=model_config,
        system_prompt=CODE_GENERATOR_SYSTEM_PROMPT,
        user_prompt=prompt,
    )


def _call_provider_json(
    model_config: AIModelConfig,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    if model_config.provider == "gemini":
        return _call_gemini_json(
            model=model_config.model,
            max_output_tokens=model_config.max_output_tokens,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    if model_config.provider == "openai":
        raise AIPlannerError("OpenAI provider is not implemented yet")

    if model_config.provider == "deepseek":
        raise AIPlannerError("DeepSeek provider is not implemented yet")

    raise AIPlannerError(f"Unsupported AI provider: {model_config.provider}")


def _call_gemini_json(
    model: str,
    max_output_tokens: int,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise AIPlannerError("google-genai is not installed") from exc

    api_key = get_provider_api_key("gemini")
    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
            ),
        )
    except Exception as exc:
        raise AIPlannerError(f"Gemini request failed: {exc}") from exc

    text = getattr(response, "text", None)

    if not text:
        raise AIPlannerError("Gemini returned empty response")

    return parse_json_response(text)
