"""Adaptador de Gemini — implementación del puerto LLM en la nube de Google.

Utiliza la API REST oficial de Google AI Studio mediante HTTP asíncrono con httpx.
Soporta:
- Modelos rápidos como gemini-1.5-flash y gemini-2.0-flash
- Enmascaramiento local de datos sensibles con DataMasker
- Fallback automático hacia Ollama local si la API falla o excede cuotas.
"""

from __future__ import annotations

import logging
import re
import httpx

from agent_ia.domain.ports.llm_port import LLMPort, LLMResponse
from agent_ia.infrastructure.config import Settings
from agent_ia.infrastructure.sanitizer import DataMasker

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiAdapter(LLMPort):
    """Adaptador concreto de Gemini para inferencia ultra-rápida y precisa."""

    def __init__(
        self,
        settings: Settings,
        model_override: str | None = None,
        masker: DataMasker | None = None,
        fallback_llm: LLMPort | None = None,
    ) -> None:
        self._settings = settings
        self._api_key = settings.gemini_api_key
        self._model = model_override or settings.gemini_model
        self._masker = masker or DataMasker(enabled=settings.enable_data_masking)
        self._fallback_llm = fallback_llm

    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Genera una respuesta usando la API de Gemini con ofuscación local opcional."""
        if not self._api_key:
            if self._fallback_llm:
                logger.warning("No hay GEMINI_API_KEY configurada. Usando fallback local.")
                return await self._fallback_llm.generate(prompt, system=system, temperature=temperature)
            raise ValueError("GEMINI_API_KEY no está configurada y no hay fallback disponible.")

        # 1. Enmascarar datos sensibles antes de salir a la nube
        mask_result = self._masker.mask(prompt)
        prompt_enviado = mask_result.masked_text

        # 2. Construir payload para Gemini REST API
        generation_config: dict = {
            "temperature": temperature,
        }
        # Desactivar thinking mode en llamadas rápidas para respuesta sub-segundo
        if temperature < 0.5:
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}

        payload: dict = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt_enviado}],
                }
            ],
            "generationConfig": generation_config,
        }

        if system:
            payload["system_instruction"] = {
                "parts": [{"text": system}]
            }

        clean_model = self._model.removeprefix("models/")
        url = f"{GEMINI_BASE_URL}/models/{clean_model}:generateContent?key={self._api_key}"

        max_intentos = 2
        for intento in range(max_intentos):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError(f"Gemini no devolvió candidatos válidos: {data}")

                parts = candidates[0].get("content", {}).get("parts", [])
                raw_content = parts[0].get("text", "") if parts else ""

                # Limpiar bloques markdown ```json ... ``` si el modelo los envolvió
                cleaned_content = self._clean_json_wrapper(raw_content)

                # 3. Desofuscar / Restituir datos originales locales
                final_content = self._masker.unmask(cleaned_content, mask_result.mapping)

                usage = data.get("usageMetadata", {})
                tokens = usage.get("totalTokenCount", 0)

                logger.debug("Gemini generate: %d tokens, model=%s", tokens, self._model)
                return LLMResponse(
                    content=final_content,
                    model=self._model,
                    tokens_used=tokens,
                )

            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as e:
                # Si es un error transitorio de servidor (503, 500, 429) o timeout, reintentar una vez
                if intento < max_intentos - 1:
                    logger.warning("Fallo transitorio en Gemini (%s). Reintentando en 0.5s...", e)
                    import asyncio
                    await asyncio.sleep(0.5)
                    continue

                logger.warning("Gemini no disponible tras reintentos (%s). Activando fallback a LLM local.", e)
                if self._fallback_llm:
                    return await self._fallback_llm.generate(prompt, system=system, temperature=temperature)
                raise
            except Exception as e:
                logger.exception("Error al llamar a Gemini API (%s)", e)
                if self._fallback_llm:
                    logger.warning("Fallo en Gemini. Activando fallback a LLM local.")
                    return await self._fallback_llm.generate(prompt, system=system, temperature=temperature)
                raise

    async def embed(self, text: str) -> list[float]:
        """Genera embeddings usando la API de Gemini o el fallback local."""
        if not self._api_key:
            if self._fallback_llm:
                return await self._fallback_llm.embed(text)
            raise ValueError("GEMINI_API_KEY no configurada.")

        url = f"{GEMINI_BASE_URL}/models/text-embedding-004:embedContent?key={self._api_key}"
        payload = {
            "model": "models/text-embedding-004",
            "content": {
                "parts": [{"text": text}],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            return data["embedding"]["values"]
        except Exception as e:
            logger.warning("Error en embedding de Gemini (%s). Probando fallback local.", e)
            if self._fallback_llm:
                return await self._fallback_llm.embed(text)
            raise

    async def health_check(self) -> bool:
        """Verifica disponibilidad de la API de Gemini."""
        if not self._api_key:
            return False
        try:
            url = f"{GEMINI_BASE_URL}/models/{self._model}?key={self._api_key}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _clean_json_wrapper(text: str) -> str:
        """Extrae el contenido JSON si viene envuelto en markdown ```json ... ```."""
        text_strip = text.strip()
        match = re.search(r"^```(?:json)?\s*\n(.*)\n```$", text_strip, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text_strip
