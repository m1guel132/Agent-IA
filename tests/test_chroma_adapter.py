"""Tests unitarios para ChromaAdapter."""

from __future__ import annotations

import pytest
from pathlib import Path

from agent_ia.domain.ports.llm_port import LLMPort, LLMResponse
from agent_ia.infrastructure.config import Settings
from agent_ia.infrastructure.chroma_adapter import ChromaAdapter


class DummyEmbedder(LLMPort):
    async def generate(self, prompt: str, *, system: str = "", temperature: float = 0.7) -> LLMResponse:
        return LLMResponse(content="", model="dummy")

    async def embed(self, text: str) -> list[float]:
        # Generar embedding sintético basado en longitud del texto
        val = float(len(text) % 10) / 10.0
        return [val, val + 0.1, val + 0.2]

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_chroma_indexar_buscar_y_eliminar(tmp_path: Path):
    settings = Settings(chroma_persist_dir=str(tmp_path / "chroma_db"))
    llm = DummyEmbedder()
    adapter = ChromaAdapter(settings, llm)

    # 1. Health check inicial
    assert await adapter.health_check() is True

    # 2. Indexar documentos
    await adapter.indexar("doc-1", "Contenido sobre redes TCP y UDP", {"area": "Redes"})
    await adapter.indexar("doc-2", "Contenido sobre cálculo diferencial", {"area": "Matemáticas"})

    # 3. Buscar
    resultados = await adapter.buscar("redes", n_results=2)
    assert len(resultados) >= 1
    assert any(r.id == "doc-1" for r in resultados)

    # 4. Eliminar
    await adapter.eliminar("doc-1")
    resultados_post_delete = await adapter.buscar("redes", n_results=2)
    assert all(r.id != "doc-1" for r in resultados_post_delete)
