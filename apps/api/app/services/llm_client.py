import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

import httpx

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore[assignment]


def _stable_hash_embedding(text: str, dims: int = 128) -> list[float]:
    """Fallback embedding when API key/client is unavailable."""
    vector = [0.0] * dims
    tokens = [token for token in text.lower().replace("\n", " ").split(" ") if token.strip()]
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dims
        sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
        vector[idx] += sign
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [item / norm for item in vector]


def _safe_json_extract(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
    return stripped


@dataclass
class LLMResult:
    text: str
    confidence: float
    trace_id: str
    provider: str = "fallback"
    model: str = "none"
    usage: Optional[dict[str, Any]] = None


class LLMClient:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "bigmodel").strip().lower() or "bigmodel"
        self.timeout_s = float(os.getenv("LLM_TIMEOUT_SECONDS", os.getenv("OPENAI_TIMEOUT_SECONDS", "30")))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", os.getenv("OPENAI_MAX_RETRIES", "2")))

        # OpenAI-compatible config
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self._openai_client = OpenAI(api_key=self.api_key) if self.api_key and OpenAI else None

        # BigModel config
        self.bigmodel_api_key = os.getenv("BIGMODEL_API_KEY", "").strip()
        self.bigmodel_base_url = os.getenv(
            "BIGMODEL_BASE_URL",
            "https://open.bigmodel.cn/api/paas/v4",
        ).rstrip("/")
        self.bigmodel_chat_model = os.getenv("BIGMODEL_CHAT_MODEL", "glm-5-turbo")
        self.bigmodel_embedding_model = os.getenv("BIGMODEL_EMBEDDING_MODEL", "embedding-3")
        self.bigmodel_rerank_model = os.getenv("BIGMODEL_RERANK_MODEL", "rerank")

    @property
    def enabled(self) -> bool:
        if self.provider == "bigmodel":
            return bool(self.bigmodel_api_key)
        if self.provider == "openai":
            return self._openai_client is not None
        return False

    def _fallback_result(self, trace_prefix: str = "fallback", usage: Optional[dict[str, Any]] = None) -> LLMResult:
        return LLMResult(
            text="{}",
            confidence=0.0,
            trace_id=f"{trace_prefix}-{uuid4()}",
            provider="fallback",
            model="none",
            usage=usage,
        )

    def _bigmodel_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bigmodel_api_key}",
            "Content-Type": "application/json",
        }

    def _bigmodel_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.bigmodel_base_url}{path}"
        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(url, headers=self._bigmodel_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}

    def embed_text(self, text: str) -> list[float]:
        payload = text.strip()
        if not payload:
            return _stable_hash_embedding("")
        if not self.enabled:
            return _stable_hash_embedding(payload)

        last_error: Optional[Exception] = None
        for _ in range(max(1, self.max_retries + 1)):
            try:
                if self.provider == "bigmodel":
                    response = self._bigmodel_post(
                        "/embeddings",
                        {
                            "model": self.bigmodel_embedding_model,
                            "input": payload[:8000],
                        },
                    )
                    data = response.get("data")
                    if isinstance(data, list) and data:
                        embedding = data[0].get("embedding")
                        if isinstance(embedding, list):
                            return [float(item) for item in embedding]
                    raise ValueError("Invalid BigModel embedding response")

                if self.provider == "openai" and self._openai_client is not None:
                    response = self._openai_client.embeddings.create(
                        model=self.embedding_model,
                        input=payload[:8000],
                    )
                    embedding = response.data[0].embedding
                    return [float(item) for item in embedding]

                raise ValueError(f"Unsupported provider: {self.provider}")
            except Exception as exc:  # pragma: no cover - network/runtime
                last_error = exc
                time.sleep(0.25)
        # Fail open to deterministic fallback.
        if last_error:
            return _stable_hash_embedding(payload)
        return _stable_hash_embedding(payload)

    def generate_json(self, system_prompt: str, user_prompt: str) -> LLMResult:
        if not self.enabled:
            return self._fallback_result()

        last_error: Optional[Exception] = None
        for _ in range(max(1, self.max_retries + 1)):
            try:
                usage = None
                content = "{}"
                model = "none"
                provider = self.provider
                trace_id = f"{self.provider}-{uuid4()}"

                if self.provider == "bigmodel":
                    response = self._bigmodel_post(
                        "/chat/completions",
                        {
                            "model": self.bigmodel_chat_model,
                            "temperature": 0.1,
                            "response_format": {"type": "json_object"},
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        },
                    )
                    choices = response.get("choices")
                    if isinstance(choices, list) and choices:
                        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
                        content = str((message or {}).get("content") or "{}")
                    usage_raw = response.get("usage")
                    if isinstance(usage_raw, dict):
                        usage = {
                            "prompt_tokens": usage_raw.get("prompt_tokens"),
                            "completion_tokens": usage_raw.get("completion_tokens"),
                            "total_tokens": usage_raw.get("total_tokens"),
                        }
                    model = self.bigmodel_chat_model
                    trace_id = str(response.get("id") or trace_id)
                elif self.provider == "openai" and self._openai_client is not None:
                    response = self._openai_client.chat.completions.create(
                        model=self.chat_model,
                        temperature=0.1,
                        timeout=self.timeout_s,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    )
                    content = response.choices[0].message.content or "{}"
                    if response.usage:
                        usage = {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens,
                        }
                    model = self.chat_model
                    trace_id = f"openai-{uuid4()}"
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")

                return LLMResult(
                    text=_safe_json_extract(content),
                    confidence=0.7,
                    trace_id=trace_id,
                    provider=provider,
                    model=model,
                    usage=usage,
                )
            except Exception as exc:  # pragma: no cover - network/runtime
                last_error = exc
                time.sleep(0.25)

        return self._fallback_result(usage={"error": str(last_error)} if last_error else None)

    def rerank(self, query: str, documents: list[str], top_n: Optional[int] = None) -> list[dict[str, Any]]:
        if not documents:
            return []
        if not self.enabled:
            return [
                {
                    "index": index,
                    "relevance_score": max(0.0, 0.5 - index * 0.02),
                    "reason": "fallback_order",
                }
                for index, _ in enumerate(documents[: (top_n or len(documents))])
            ]

        last_error: Optional[Exception] = None
        for _ in range(max(1, self.max_retries + 1)):
            try:
                if self.provider == "bigmodel":
                    payload: dict[str, Any] = {
                        "model": self.bigmodel_rerank_model,
                        "query": query,
                        "documents": documents,
                    }
                    if top_n is not None:
                        payload["top_n"] = int(top_n)
                    response = self._bigmodel_post("/rerank", payload)
                    data = response.get("results") or response.get("data") or response.get("output")
                    if isinstance(data, list):
                        output: list[dict[str, Any]] = []
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            try:
                                idx = int(item.get("index"))
                            except Exception:
                                continue
                            try:
                                score = float(
                                    item.get("relevance_score")
                                    if item.get("relevance_score") is not None
                                    else item.get("score")
                                )
                            except Exception:
                                score = 0.0
                            output.append(
                                {
                                    "index": idx,
                                    "relevance_score": max(0.0, min(1.0, score)),
                                    "reason": str(item.get("reason") or "bigmodel_rerank"),
                                }
                            )
                        if output:
                            return output
                    raise ValueError("Invalid BigModel rerank response")

                # OpenAI branch: fallback to chat-based json rerank for compatibility.
                if self.provider == "openai":
                    system_prompt = (
                        "你是证据重排器。输出 JSON: {\"scores\":[{\"index\":0,\"relevance_score\":0-1,\"reason\":\"...\"}]}"
                    )
                    user_prompt = json.dumps(
                        {
                            "query": query,
                            "documents": documents,
                            "top_n": top_n,
                        },
                        ensure_ascii=False,
                    )
                    result = self.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
                    payload = json.loads(result.text or "{}")
                    scores = payload.get("scores")
                    output = []
                    if isinstance(scores, list):
                        for item in scores:
                            if not isinstance(item, dict):
                                continue
                            try:
                                idx = int(item.get("index"))
                            except Exception:
                                continue
                            try:
                                score = float(item.get("relevance_score"))
                            except Exception:
                                score = 0.0
                            output.append(
                                {
                                    "index": idx,
                                    "relevance_score": max(0.0, min(1.0, score)),
                                    "reason": str(item.get("reason") or "openai_chat_rerank"),
                                }
                            )
                    if output:
                        return output
                    raise ValueError("Invalid OpenAI chat rerank output")

                raise ValueError(f"Unsupported provider: {self.provider}")
            except Exception as exc:  # pragma: no cover - network/runtime
                last_error = exc
                time.sleep(0.25)

        return [
            {
                "index": index,
                "relevance_score": max(0.0, 0.5 - index * 0.02),
                "reason": f"fallback_order_error:{last_error}",
            }
            for index, _ in enumerate(documents[: (top_n or len(documents))])
        ]


llm_client = LLMClient()
