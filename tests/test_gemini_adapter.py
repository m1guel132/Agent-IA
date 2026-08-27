"""Tests para el adaptador de Gemini con mocks de HTTP."""

from __future__ import annotations

import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from agent_ia.infrastructure.config import Settings
from agent_ia.infrastructure.gemini_adapter import GeminiAdapter
from agent_ia.infrastructure.sanitizer import DataMasker
from agent_ia.domain.ports.llm_port import LLMPort, LLMResponse


class DummyLocalLLM(LLMPort):
    async def generate(self, prompt: str, *, system: str = "", temperature: float = 0.7) -> LLMResponse:
        return LLMResponse(content='{"agente": "curador", "fallback": true}', model="llama-local")

    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_gemini_generate_success():
    settings = Settings(gemini_api_key="fake-test-key", gemini_model="gemini-2.0-flash")
    adapter = GeminiAdapter(settings=settings)

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({"agente": "curador", "instruccion": "organizar notas"})
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {
            "totalTokenCount": 42
        }
    }

    mock_response = httpx.Response(
        status_code=200,
        json=mock_gemini_response,
        request=httpx.Request("POST", "https://test.url")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        response = await adapter.generate(
            prompt="Anota esto en el Segundo Cerebro",
            system="Eres Hermes",
            temperature=0.2,
        )

        assert response.model == "gemini-2.0-flash"
        assert response.tokens_used == 42
        data = json.loads(response.content)
        assert data["agente"] == "curador"


@pytest.mark.asyncio
async def test_gemini_generate_with_masking():
    settings = Settings(
        gemini_api_key="fake-test-key",
        gemini_model="gemini-2.0-flash",
        enable_data_masking=True,
    )
    masker = DataMasker(enabled=True)
    adapter = GeminiAdapter(settings=settings, masker=masker)

    def side_effect_post(url, json=None):
        sent_text = json["contents"][0]["parts"][0]["text"]
        # Validar que al endpoint de Google NO le llega el email real
        assert "miguel@empresa.com" not in sent_text
        assert "<EMAIL_1>" in sent_text

        # Gemini responde mencionando el placeholder
        mock_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"accion": "enviar", "destinatario": "<EMAIL_1>"}'
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {"totalTokenCount": 25}
        }
        return httpx.Response(200, json=mock_data, request=httpx.Request("POST", url))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = side_effect_post

        response = await adapter.generate(
            prompt="Enviar email a miguel@empresa.com con los resultados",
        )

        # El contenido final desofuscado DEBE contener el email original restaurado
        assert "miguel@empresa.com" in response.content
        data = json.loads(response.content)
        assert data["destinatario"] == "miguel@empresa.com"


@pytest.mark.asyncio
async def test_gemini_fallback_on_error():
    fallback_llm = DummyLocalLLM()
    settings = Settings(gemini_api_key="fake-key", gemini_model="gemini-2.0-flash")
    adapter = GeminiAdapter(settings=settings, fallback_llm=fallback_llm)

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection failed")):
        response = await adapter.generate("Test prompt")
        assert response.model == "llama-local"
        assert "fallback" in response.content
