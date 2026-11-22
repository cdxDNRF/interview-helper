import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator
from urllib.parse import urlparse

import httpx

from app.config import AppRuntimeConfig, StageLLMSettings
from app.services.pricing import estimate_cost_cny


@dataclass
class LLMCallResult:
    content: str
    model: str
    prompt_tokens: int
    cached_tokens: int
    completion_tokens: int
    latency_ms: int
    estimated_cost_cny: float
    raw_usage: dict[str, Any]


def _is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _build_httpx_client(base_url: str, timeout: float = 90.0) -> httpx.AsyncClient:
    """Bypass system HTTP(S)_PROXY for local loopback relays like 127.0.0.1:8790."""
    use_env_proxy = not _is_loopback_url(base_url)
    return httpx.AsyncClient(timeout=timeout, trust_env=use_env_proxy)


def extract_cached_tokens(usage: dict[str, Any]) -> int:
    if not usage:
        return 0
    if isinstance(usage.get("prompt_cache_hit_tokens"), int):
        return int(usage["prompt_cache_hit_tokens"])
    details = usage.get("prompt_tokens_details") or {}
    if isinstance(details, dict) and isinstance(details.get("cached_tokens"), int):
        return int(details["cached_tokens"])
    if isinstance(usage.get("cached_tokens"), int):
        return int(usage["cached_tokens"])
    return 0


def strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _build_tool_ack_messages(
    base_messages: list[dict[str, Any]],
    assistant_content: str,
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append assistant tool_calls + deterministic ack messages without mutating prefix."""
    next_messages: list[dict[str, Any]] = list(base_messages)
    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "tool_calls": tool_calls,
    }
    if assistant_content:
        assistant_msg["content"] = assistant_content
    else:
        assistant_msg["content"] = ""
    next_messages.append(assistant_msg)

    for idx, tc in enumerate(tool_calls):
        fn = tc.get("function") or {}
        tc_id = tc.get("id") or f"call_obs_{idx}"
        tc_name = fn.get("name") or "record_observation"
        next_messages.append(
            {
                "role": "tool",
                "tool_call_id": tc_id,
                "name": tc_name,
                "content": json.dumps({"ok": True, "recorded": True}),
            }
        )
    return next_messages


async def fetch_available_models(base_url: str, api_key: str = "") -> list[str]:
    clean_base = base_url.rstrip("/")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with _build_httpx_client(clean_base, timeout=15.0) as client:
        resp = await client.get(f"{clean_base}/models", headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    items = payload.get("data") or []
    return [str(item["id"]) for item in items if isinstance(item, dict) and "id" in item]


async def chat_completion(
    stage_cfg: StageLLMSettings,
    runtime_cfg: AppRuntimeConfig,
    messages: list[dict[str, Any]],
    *,
    response_format: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMCallResult:
    clean_base = stage_cfg.base_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {stage_cfg.api_key or 'sk-local'}",
    }

    working_messages = list(messages)
    working_tools = tools
    body: dict[str, Any] = {
        "model": stage_cfg.model,
        "messages": working_messages,
        "temperature": stage_cfg.temperature if temperature is None else temperature,
        "max_tokens": stage_cfg.max_tokens if max_tokens is None else max_tokens,
    }
    if response_format is not None:
        body["response_format"] = response_format
    if working_tools is not None:
        body["tools"] = working_tools

    t0 = time.perf_counter()
    last_error: Exception | None = None
    total_prompt_tokens = 0
    total_cached_tokens = 0
    total_completion_tokens = 0
    last_usage: dict[str, Any] = {}
    model_used = stage_cfg.model
    handled_tool_round = False

    async with _build_httpx_client(clean_base, timeout=120.0) as client:
        for attempt in range(4):
            body["messages"] = working_messages
            if working_tools is not None:
                body["tools"] = working_tools
            else:
                body.pop("tools", None)

            resp = await client.post(f"{clean_base}/chat/completions", headers=headers, json=body)
            # Downgrade json_schema -> json_object automatically for relays/models that reject strict schema
            if resp.status_code in {400, 422} and body.get("response_format", {}).get("type") == "json_schema":
                body["response_format"] = {"type": "json_object"}
                resp = await client.post(f"{clean_base}/chat/completions", headers=headers, json=body)
            if resp.status_code in {400, 422} and body.get("response_format", {}).get("type") == "json_object":
                body.pop("response_format", None)
                resp = await client.post(f"{clean_base}/chat/completions", headers=headers, json=body)

            if resp.status_code == 429 and attempt < 3:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            if resp.status_code >= 400:
                last_error = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}: {resp.text[:400]}",
                    request=resp.request,
                    response=resp,
                )
                if attempt < 3 and resp.status_code >= 500:
                    await asyncio.sleep(1.0)
                    continue
                raise last_error

            data = resp.json()
            if data.get("error"):
                raise RuntimeError(f"上游模型返回异常: {str(data['error'])[:300]}")

            choice = (data.get("choices") or [{}])[0]
            finish_reason = choice.get("finish_reason")
            msg = choice.get("message") or {}
            content = (msg.get("content") or "").strip()
            msg_tool_calls = msg.get("tool_calls") or []

            usage = data.get("usage") or {}
            total_prompt_tokens += int(usage.get("prompt_tokens") or 0)
            total_cached_tokens += extract_cached_tokens(usage)
            total_completion_tokens += int(usage.get("completion_tokens") or 0)
            last_usage = usage
            model_used = str(data.get("model") or stage_cfg.model)

            # Handle upstream returning a tool call instead of text
            if msg_tool_calls and not content and not handled_tool_round:
                handled_tool_round = True
                working_messages = _build_tool_ack_messages(
                    working_messages, content, list(msg_tool_calls)
                )
                working_tools = None
                continue

            if (
                finish_reason == "length"
                and attempt < 3
                and body["max_tokens"] < 12288
                and (
                    not content
                    or response_format is not None
                    or body.get("response_format") is not None
                )
            ):
                body["max_tokens"] = min(16384, max(2048, int(body["max_tokens"]) * 2))
                continue

            latency_ms = int((time.perf_counter() - t0) * 1000)
            cost_cny = estimate_cost_cny(
                model_used,
                total_prompt_tokens,
                total_cached_tokens,
                total_completion_tokens,
                runtime_cfg,
            )
            return LLMCallResult(
                content=content,
                model=model_used,
                prompt_tokens=total_prompt_tokens,
                cached_tokens=total_cached_tokens,
                completion_tokens=total_completion_tokens,
                latency_ms=latency_ms,
                estimated_cost_cny=cost_cny,
                raw_usage=last_usage,
            )

    if last_error:
        raise last_error
    raise RuntimeError("Unexpected chat_completion failure")


async def _run_single_stream(
    client: httpx.AsyncClient,
    clean_base: str,
    headers: dict[str, str],
    body: dict[str, Any],
) -> AsyncGenerator[dict[str, Any], None]:
    async with client.stream(
        "POST", f"{clean_base}/chat/completions", headers=headers, json=body
    ) as resp:
        if resp.status_code in {400, 422} and "stream_options" in body:
            await resp.aread()
            retry_body = dict(body)
            retry_body.pop("stream_options", None)
            async with client.stream(
                "POST", f"{clean_base}/chat/completions", headers=headers, json=retry_body
            ) as resp2:
                if resp2.status_code >= 400:
                    err_body2 = await resp2.aread()
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp2.status_code}: {err_body2.decode('utf-8', errors='replace')[:400]}",
                        request=resp2.request,
                        response=resp2,
                    )
                async for event in _parse_sse_stream(resp2):
                    yield event
        else:
            if resp.status_code >= 400:
                err_body = await resp.aread()
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}: {err_body.decode('utf-8', errors='replace')[:400]}",
                    request=resp.request,
                    response=resp,
                )
            async for event in _parse_sse_stream(resp):
                yield event


async def stream_chat_completion(
    stage_cfg: StageLLMSettings,
    runtime_cfg: AppRuntimeConfig,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Streams deltas and yields final usage event:
    - {"type": "delta", "text": "..."}
    - {"type": "done", "result": LLMCallResult}
    Handles tool_calls transparently so callers always receive spoken text if a model calls a tool.
    """
    clean_base = stage_cfg.base_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {stage_cfg.api_key or 'sk-local'}",
    }

    t0 = time.perf_counter()
    full_chunks: list[str] = []
    total_prompt_tokens = 0
    total_cached_tokens = 0
    total_completion_tokens = 0
    last_usage: dict[str, Any] = {}
    model_used = stage_cfg.model

    working_messages: list[dict[str, Any]] = list(messages)
    working_tools = tools

    async with _build_httpx_client(clean_base, timeout=120.0) as client:
        for round_idx in range(2):
            body: dict[str, Any] = {
                "model": stage_cfg.model,
                "messages": working_messages,
                "temperature": stage_cfg.temperature,
                "max_tokens": stage_cfg.max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if working_tools is not None:
                body["tools"] = working_tools

            round_chunks: list[str] = []
            round_usage: dict[str, Any] = {}
            tool_calls_acc: dict[int, dict[str, Any]] = {}

            async for event in _run_single_stream(client, clean_base, headers, body):
                if event["type"] == "delta":
                    round_chunks.append(event["text"])
                    full_chunks.append(event["text"])
                    yield event
                elif event["type"] == "tool_call_delta":
                    tc_list = event["tool_calls"]
                    for tc in tc_list:
                        idx = int(tc.get("index", 0))
                        entry = tool_calls_acc.setdefault(
                            idx,
                            {
                                "id": tc.get("id") or f"call_{round_idx}_{idx}",
                                "type": tc.get("type") or "function",
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        if tc.get("id"):
                            entry["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            entry["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            entry["function"]["arguments"] += fn["arguments"]
                elif event["type"] == "meta":
                    if event.get("usage"):
                        round_usage = event["usage"]
                    if event.get("model"):
                        model_used = event["model"]

            total_prompt_tokens += int(round_usage.get("prompt_tokens") or 0)
            total_cached_tokens += extract_cached_tokens(round_usage)
            total_completion_tokens += int(round_usage.get("completion_tokens") or 0)
            if round_usage:
                last_usage = round_usage

            # If the model answered with tool_calls and emitted no spoken text, reply to the tool call and stream text
            if tool_calls_acc and not "".join(round_chunks).strip() and round_idx == 0:
                ordered_calls = [tool_calls_acc[k] for k in sorted(tool_calls_acc.keys())]
                working_messages = _build_tool_ack_messages(
                    working_messages, "".join(round_chunks).strip(), ordered_calls
                )
                working_tools = None
                continue
            break

    latency_ms = int((time.perf_counter() - t0) * 1000)
    full_text = "".join(full_chunks).strip()
    if total_completion_tokens == 0 and full_text:
        total_completion_tokens = max(1, len(full_text) // 2)
    cost_cny = estimate_cost_cny(
        model_used,
        total_prompt_tokens,
        total_cached_tokens,
        total_completion_tokens,
        runtime_cfg,
    )
    yield {
        "type": "done",
        "result": LLMCallResult(
            content=full_text,
            model=model_used,
            prompt_tokens=total_prompt_tokens,
            cached_tokens=total_cached_tokens,
            completion_tokens=total_completion_tokens,
            latency_ms=latency_ms,
            estimated_cost_cny=cost_cny,
            raw_usage=last_usage,
        ),
    }


async def _parse_sse_stream(resp: httpx.Response) -> AsyncGenerator[dict[str, Any], None]:
    async for raw_line in resp.aiter_lines():
        line = raw_line.strip()
        if not line or not line.startswith("data:"):
            continue
        data_str = line[5:].strip()
        if not data_str or data_str == "[DONE]":
            continue
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        if isinstance(chunk, dict) and chunk.get("error"):
            err_obj = chunk["error"]
            msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
            raise RuntimeError(f"流式模型上游报错: {str(msg)[:300]}")
        meta_usage = chunk.get("usage")
        meta_model = chunk.get("model")
        if meta_usage or meta_model:
            yield {"type": "meta", "usage": meta_usage, "model": meta_model}
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        text_part = delta.get("content")
        if text_part:
            yield {"type": "delta", "text": text_part}
        if delta.get("tool_calls"):
            yield {"type": "tool_call_delta", "tool_calls": delta["tool_calls"]}
