import logging
import os
from typing import Any

logger = logging.getLogger("acceptance_agent.preflight")


def _is_bigmodel_chat_model(name: str) -> bool:
    value = name.strip().lower()
    return value.startswith("glm-") or value.startswith("chatglm")


def _is_bigmodel_embedding_model(name: str) -> bool:
    value = name.strip().lower()
    return value.startswith("embedding")


def _is_bigmodel_rerank_model(name: str) -> bool:
    value = name.strip().lower()
    return "rerank" in value


def run_startup_preflight() -> dict[str, Any]:
    provider = os.getenv("LLM_PROVIDER", "bigmodel").strip().lower() or "bigmodel"
    warnings: list[str] = []
    errors: list[str] = []
    infos: list[str] = []

    if provider not in {"bigmodel", "openai"}:
        errors.append(
            f"LLM_PROVIDER={provider} is invalid. Allowed values: bigmodel | openai. "
            "Service will fallback to local deterministic mode."
        )

    if provider == "bigmodel":
        api_key = os.getenv("BIGMODEL_API_KEY", "").strip()
        base_url = os.getenv("BIGMODEL_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").strip()
        chat_model = os.getenv("BIGMODEL_CHAT_MODEL", "glm-5-turbo").strip()
        embedding_model = os.getenv("BIGMODEL_EMBEDDING_MODEL", "embedding-3").strip()
        rerank_model = os.getenv("BIGMODEL_RERANK_MODEL", "rerank").strip()

        if not api_key:
            warnings.append(
                "BIGMODEL_API_KEY is empty. LLM calls will run in fallback mode "
                "(no remote model invocation)."
            )
        if not base_url.startswith("http"):
            warnings.append(
                f"BIGMODEL_BASE_URL={base_url!r} does not look like a valid URL. "
                "Expected something like https://open.bigmodel.cn/api/paas/v4."
            )
        if not _is_bigmodel_chat_model(chat_model):
            warnings.append(
                f"BIGMODEL_CHAT_MODEL={chat_model!r} looks unusual for BigModel chat "
                "(expected glm-* family)."
            )
        if not _is_bigmodel_embedding_model(embedding_model):
            warnings.append(
                f"BIGMODEL_EMBEDDING_MODEL={embedding_model!r} looks unusual for BigModel embedding "
                "(expected embedding-*)."
            )
        if not _is_bigmodel_rerank_model(rerank_model):
            warnings.append(
                f"BIGMODEL_RERANK_MODEL={rerank_model!r} looks unusual for BigModel rerank "
                "(expected rerank)."
            )
        infos.append(
            f"provider=bigmodel chat={chat_model} embedding={embedding_model} rerank={rerank_model}"
        )
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini").strip()
        embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        if not api_key:
            warnings.append(
                "OPENAI_API_KEY is empty. LLM calls will run in fallback mode "
                "(no remote model invocation)."
            )
        if not chat_model:
            warnings.append("OPENAI_CHAT_MODEL is empty; fallback model name will be used.")
        if not embedding_model:
            warnings.append("OPENAI_EMBEDDING_MODEL is empty; fallback model name will be used.")
        infos.append(f"provider=openai chat={chat_model} embedding={embedding_model}")

    for info in infos:
        logger.info("[startup-preflight] %s", info)
    for warning in warnings:
        logger.warning("[startup-preflight] %s", warning)
    for error in errors:
        logger.error("[startup-preflight] %s", error)

    return {
        "provider": provider,
        "infos": infos,
        "warnings": warnings,
        "errors": errors,
        "ok": len(errors) == 0,
    }
