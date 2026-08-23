"""Adaptador de Ollama — implementación del puerto LLM.

Usa la librería oficial de Ollama para chat/generate y embeddings.
Respeta RNF2 (todo local) y RNF3 (keep_alive para evitar cold-starts).
"""

from __future__ import annotations

import logging

from ollama import AsyncClient

from gwen_os.domain.ports.llm_port import LLMPort, LLMResponse
from gwen_os.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class OllamaAdapter(LLMPort):
    """Adaptador concreto de Ollama para generación y embeddings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncClient(host=settings.ollama_base_url)
        self._model = settings.ollama_model
        self._embed_model = settings.ollama_embed_model
        self._keep_alive = settings.ollama_keep_alive

    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Genera una respuesta usando Ollama chat API."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat(
            model=self._model,
            messages=messages,
            options={"temperature": temperature},
            keep_alive=self._keep_alive,
        )

        content = response.message.content or ""
        tokens = (response.eval_count or 0) + (response.prompt_eval_count or 0)

        logger.debug("Ollama generate: %d tokens, model=%s", tokens, self._model)

        return LLMResponse(
            content=content,
            model=self._model,
            tokens_used=tokens,
        )

    async def embed(self, text: str) -> list[float]:
        """Genera embeddings usando nomic-embed-text."""
        response = await self._client.embed(
            model=self._embed_model,
            input=text,
        )
        return response.embeddings[0]

    async def health_check(self) -> bool:
        """Verifica que Ollama esté corriendo y el modelo disponible."""
        try:
            models = await self._client.list()
            model_names = [m.model for m in models.models]
            return self._model in model_names
        except Exception:
            logger.exception("Ollama health check falló")
            return False
