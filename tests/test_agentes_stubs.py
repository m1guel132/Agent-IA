"""Tests unitarios para los agentes stub (AgenteSync)."""

from __future__ import annotations

import pytest

from agent_ia.use_cases.agente import EstadoResultado
from agent_ia.use_cases.agente_sync import AgenteSync


@pytest.mark.asyncio
async def test_ejecutar_agenteSync_retornaSinAccion():
    agente = AgenteSync()
    resultado = await agente.ejecutar("Sincroniza Notion con Obsidian")

    assert resultado.estado == EstadoResultado.SIN_ACCION
    assert resultado.agente == "AgenteSync"
    assert "Fase 3" in resultado.mensaje
