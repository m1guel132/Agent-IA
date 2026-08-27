"""Tests unitarios para AgenteSync y JsonSyncAdapter (Fase 3).

Sigue el estándar Given-When-Then de unit-tests-skills.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_ia.domain.entities import Area, Nota, Tarea
from agent_ia.domain.entities.tarea import EstadoTarea, PrioridadTarea
from agent_ia.infrastructure.json_sync_adapter import JsonSyncAdapter
from agent_ia.use_cases.agente import EstadoResultado
from agent_ia.use_cases.agente_sync import AgenteSync


# ====================================================================
# TEST 1: JsonSyncAdapter CRUD & Eventos
# ====================================================================

def test_json_sync_adapter_crud_y_eventos():
    # Given: Un archivo temporal para el estado de sincronización
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_path = Path(tf.name)

    try:
        adapter = JsonSyncAdapter(file_path=temp_path)

        # When: Se registra un evento y se actualizan hashes
        adapter.actualizar_hash("test_key", "sha256_dummy_hash")
        adapter.registrar_evento(
            origen="Obsidian",
            destino="ChromaDB",
            entidad="Notas/Sistemas.md",
            accion="NOTA_SYNC",
            detalles={"test": True},
        )

        # Then: Los datos persisten correctamente
        assert adapter.obtener_hash("test_key") == "sha256_dummy_hash"
        estado = adapter.obtener_estado()
        assert len(estado["historial"]) == 1
        assert estado["historial"][0]["accion"] == "NOTA_SYNC"
        assert estado["ultimo_sync"] is not None
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ====================================================================
# TEST 2: Sincronización Bidireccional Completa
# ====================================================================

@pytest.mark.asyncio
async def test_agente_sync_ejecutar_sincronizacion_bidireccional():
    # Given: Un adapter de estado y mocks de Notion, Obsidian y VectorStore
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_path = Path(tf.name)

    try:
        sync_adapter = JsonSyncAdapter(file_path=temp_path)

        mock_notion = AsyncMock()
        mock_notion.listar_areas.return_value = [
            Area(id="a1", nombre="Sistemas", descripcion="Área técnica")
        ]
        mock_notion.listar_tareas_pendientes.return_value = []

        mock_obsidian = AsyncMock()
        mock_obsidian.listar_notas.return_value = ["Sistemas/Redes.md"]
        mock_obsidian.leer_nota.return_value = "# Redes\nProtocolos TCP/IP"

        mock_vector = AsyncMock()

        agente = AgenteSync(
            sync_port=sync_adapter,
            notion=mock_notion,
            obsidian=mock_obsidian,
            vector_store=mock_vector,
        )

        # When: Se ejecuta la instrucción de sincronización
        resultado = await agente.ejecutar("Sincroniza mis notas de Notion con Obsidian")

        # Then: La sincronización es exitosa y se indexa en ChromaDB
        assert resultado.estado == EstadoResultado.EXITO
        assert resultado.agente == "AgenteSync"
        assert "Sincronización Bidireccional Completada" in resultado.mensaje
        mock_vector.indexar.assert_called_once()
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ====================================================================
# TEST 3: Alertas Proactivas de Tareas (Vencidas, Hoy, Próximas)
# ====================================================================

@pytest.mark.asyncio
async def test_agente_sync_alertas_tareas_vencidas():
    # Given: Tareas con distintas fechas límite
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_path = Path(tf.name)

    try:
        sync_adapter = JsonSyncAdapter(file_path=temp_path)
        mock_notion = AsyncMock()

        ayer = datetime.now(timezone.utc) - timedelta(days=2)
        hoy = datetime.now(timezone.utc)

        mock_notion.listar_tareas_pendientes.return_value = [
            Tarea(
                id="t1",
                titulo="Entrega Proyecto Final",
                estado=EstadoTarea.PENDIENTE,
                prioridad=PrioridadTarea.OBLIGATORIA,
                fecha_limite=ayer,
            ),
            Tarea(
                id="t2",
                titulo="Revisar Flashcards Redes",
                estado=EstadoTarea.PENDIENTE,
                prioridad=PrioridadTarea.IMPORTANTE,
                fecha_limite=hoy,
            ),
        ]

        agente = AgenteSync(
            sync_port=sync_adapter,
            notion=mock_notion,
        )

        # When: Se consultan las alertas de tareas
        resultado = await agente.ejecutar("¿Qué tareas tengo vencidas o por vencer?")

        # Then: Se genera el reporte con alertas detalladas
        assert resultado.estado == EstadoResultado.EXITO
        assert "Alertas de Tareas Pendientes" in resultado.mensaje
        assert "VENCIDA" in resultado.mensaje
        assert "VENCE HOY" in resultado.mensaje
        assert len(resultado.datos["alertas"]) == 2
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ====================================================================
# TEST 4: Procesamiento de Webhook n8n
# ====================================================================

@pytest.mark.asyncio
async def test_agente_sync_procesar_webhook_payload():
    # Given: Un payload recibido de n8n para crear una nota
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_path = Path(tf.name)

    try:
        sync_adapter = JsonSyncAdapter(file_path=temp_path)
        mock_obsidian = AsyncMock()

        agente = AgenteSync(
            sync_port=sync_adapter,
            obsidian=mock_obsidian,
        )

        payload = {
            "origen": "n8n",
            "evento": "nueva_nota",
            "datos": {
                "titulo": "Nota desde Telegram Webhook",
                "contenido": "Contenido capturado automáticamente",
            },
        }

        # When: Se ejecuta la ingesta vía webhook
        resultado = await agente.ejecutar("webhook", contexto={"webhook_payload": payload})

        # Then: Se procesa y se escribe en Obsidian
        assert resultado.estado == EstadoResultado.EXITO
        assert "Webhook procesado exitosamente" in resultado.mensaje
        mock_obsidian.escribir_nota.assert_called_once()
    finally:
        if temp_path.exists():
            temp_path.unlink()
