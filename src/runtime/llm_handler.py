from __future__ import annotations

import os
from typing import Any

import httpx


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _model_from_step(step: dict[str, Any]) -> str:
    node_cfg = step.get("node_config") or {}
    if isinstance(node_cfg, dict) and node_cfg.get("model"):
        return str(node_cfg["model"])

    cfg = step.get("tool_config") or {}
    if isinstance(cfg, dict) and cfg.get("model"):
        return str(cfg["model"])
    # 2) env
    return _env("LLM_MODEL", "gpt-4o-mini") or "gpt-4o-mini"


def _prompt_from_step(step: dict[str, Any], ctx: dict[str, Any]) -> str:
    # Базовый демо-промпт: берём текст из ctx
    prompt = ctx.get("prompt") or ctx.get("input") or ctx.get("text")
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    # fallback: описание шага
    return str(step.get("description") or step.get("step") or "Hello")


async def llm_chat_handler(step: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Реальный LLM вызов через OpenAI-compatible endpoint.

    ENV:
      - LLM_BASE_URL (default: https://api.openai.com)
      - LLM_API_KEY  (required)
      - LLM_MODEL    (default: gpt-4o-mini)
    """
    node_cfg = step.get("node_config") or {}
    if not isinstance(node_cfg, dict):
        node_cfg = {}

    base_url = str(node_cfg.get("base_url") or _env("LLM_BASE_URL", "https://api.openai.com") or "https://api.openai.com")
    api_key = str(node_cfg.get("api_key") or _env("LLM_API_KEY") or "")
    if not api_key.strip():
        raise RuntimeError("LLM API key is not set (node_config.api_key or LLM_API_KEY)")

    model = _model_from_step(step)
    user_prompt = _prompt_from_step(step, ctx)
    system_prompt = str(node_cfg.get("system_prompt") or _env("LLM_SYSTEM_PROMPT", "") or "").strip() or None

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    timeout_s = float(node_cfg.get("timeout_s") or _env("LLM_TIMEOUT_S", "30") or "30")

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": float(node_cfg.get("temperature") or _env("LLM_TEMPERATURE", "0.2") or "0.2"),
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    content = (
        (data.get("choices") or [{}])[0]
        .get("message", {})
        .get("content")
    )
    return {
        "ok": True,
        "tool": "llm",
        "model": model,
        "prompt": user_prompt,
        "content": content,
        "raw": data,
    }

