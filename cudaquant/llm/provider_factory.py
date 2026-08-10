"""LLM provider factory — builds OpenAI-compatible clients from settings.

Supports any OpenAI-compatible API (DeepSeek, OpenAI, etc.) via
settings.LLM_BASE_URL + settings.LLM_MODEL + settings.LLM_API_KEY.
"""

import logging

logger = logging.getLogger(__name__)


def build_llm_provider():
    """Build an OpenAI-compatible client from settings.

    Returns None if LLM_API_KEY is not configured.
    """
    from cudaquant.config.settings import settings

    if not settings.LLM_API_KEY:
        logger.info("LLM_API_KEY not set — LLM will use local fallback")
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed — LLM will use local fallback")
        return None

    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )

    # Wrap in a simple adapter that matches the LLMProvider ABC interface
    class OpenAICompatibleProvider:
        def __init__(self, client, model):
            self._client = client
            self._model = model

        def generate(self, prompt: str, **kwargs) -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", 1000),
                temperature=kwargs.get("temperature", 0.7),
            )
            return response.choices[0].message.content or ""

    logger.info("LLM provider built: model=%s base=%s", settings.LLM_MODEL, settings.LLM_BASE_URL)
    return OpenAICompatibleProvider(client, settings.LLM_MODEL)
