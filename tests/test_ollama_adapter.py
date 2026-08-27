"""Tests unitarios para OllamaAdapter con mocks de cliente asíncrono."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent_ia.infrastructure.config import Settings
from agent_ia.infrastructure.ollama_adapter import OllamaAdapter


@pytest.mark.asyncio
async def test_generate_promptValido_retornaLLMResponse():
    settings = Settings(ollama_model="llama3.1:8b")
    adapter = OllamaAdapter(settings)

    mock_chat_resp = MagicMock()
    mock_chat_resp.message.content = "Respuesta generada por Llama"
    mock_chat_resp.eval_count = 20
    mock_chat_resp.prompt_eval_count = 10

    with patch.object(adapter._client, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_chat_resp

        response = await adapter.generate("Explica DNS", system="Eres un tutor", temperature=0.5)

        assert response.content == "Respuesta generada por Llama"
        assert response.model == "llama3.1:8b"
        assert response.tokens_used == 30
        mock_chat.assert_called_once()


@pytest.mark.asyncio
async def test_embed_textoValido_retornaVector():
    settings = Settings(ollama_embed_model="nomic-embed-text")
    adapter = OllamaAdapter(settings)

    mock_embed_resp = MagicMock()
    mock_embed_resp.embeddings = [[0.12, -0.45, 0.78]]

    with patch.object(adapter._client, "embed", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_embed_resp

        vector = await adapter.embed("Texto para vectorizar")

        assert vector == [0.12, -0.45, 0.78]
        mock_embed.assert_called_once_with(model="nomic-embed-text", input="Texto para vectorizar")


@pytest.mark.asyncio
async def test_healthCheck_modeloDisponible_retornaTrue():
    settings = Settings(ollama_model="llama3.1:8b")
    adapter = OllamaAdapter(settings)

    model_1 = MagicMock()
    model_1.model = "llama3.1:8b"
    mock_list_resp = MagicMock()
    mock_list_resp.models = [model_1]

    with patch.object(adapter._client, "list", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_list_resp
        assert await adapter.health_check() is True


@pytest.mark.asyncio
async def test_healthCheck_modeloAusente_retornaFalse():
    settings = Settings(ollama_model="llama3.1:8b")
    adapter = OllamaAdapter(settings)

    model_1 = MagicMock()
    model_1.model = "otro-modelo:7b"
    mock_list_resp = MagicMock()
    mock_list_resp.models = [model_1]

    with patch.object(adapter._client, "list", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_list_resp
        assert await adapter.health_check() is False


@pytest.mark.asyncio
async def test_healthCheck_servicioCaido_retornaFalse():
    settings = Settings(ollama_model="llama3.1:8b")
    adapter = OllamaAdapter(settings)

    with patch.object(adapter._client, "list", side_effect=Exception("Connection refused")):
        assert await adapter.health_check() is False
