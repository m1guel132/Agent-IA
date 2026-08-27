"""Tests unitarios para AgenteEstudio, StudyBoard y repetición espaciada SM-2."""

from __future__ import annotations

import json
import pytest
from datetime import date, timedelta
from pathlib import Path

from agent_ia.domain.entities.item_estudio import ItemEstudio
from agent_ia.domain.entities.nota import Nota
from agent_ia.domain.ports.llm_port import LLMPort, LLMResponse
from agent_ia.domain.ports.obsidian_port import ObsidianPort
from agent_ia.infrastructure.json_study_adapter import JsonStudyAdapter
from agent_ia.use_cases.agente import EstadoResultado
from agent_ia.use_cases.agente_estudio import AgenteEstudio


class DummyLLM(LLMPort):
    def __init__(self, response_text: str = "") -> None:
        self.response_text = response_text

    async def generate(self, prompt: str, *, system: str = "", temperature: float = 0.7) -> LLMResponse:
        return LLMResponse(content=self.response_text, model="test-llm")

    async def embed(self, text: str) -> list[float]:
        return [0.0]

    async def health_check(self) -> bool:
        return True


class DummyObsidian(ObsidianPort):
    def __init__(self) -> None:
        self.notas_escritas: list[Nota] = []

    async def escribir_nota(self, nota: Nota) -> Path:
        self.notas_escritas.append(nota)
        return Path(f"/vault/{nota.area_id}/{nota.titulo}.md")

    async def leer_nota(self, ruta_relativa: str) -> str:
        return ""

    async def listar_notas(self, directorio: str = "") -> list[str]:
        return []

    async def buscar_notas(self, query: str) -> list[str]:
        return []

    async def eliminar_nota(self, ruta_relativa: str) -> bool:
        return True

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_json_study_adapter_crud(tmp_path: Path):
    file_path = tmp_path / "study_board.json"
    adapter = JsonStudyAdapter(file_path=file_path)

    # 1. Guardar tarjeta
    item = ItemEstudio(
        id="card-1",
        nota_id="Redes",
        pregunta="¿Qué es MTU?",
        respuesta="Maximum Transmission Unit",
        sig_repaso=date.today(),
    )
    await adapter.guardar_tarjeta(item)

    # 2. Obtener tarjeta
    recuperada = await adapter.obtener_tarjeta("card-1")
    assert recuperada is not None
    assert recuperada.pregunta == "¿Qué es MTU?"
    assert recuperada.respuesta == "Maximum Transmission Unit"

    # 3. Listar pendientes
    pendientes = await adapter.listar_pendientes(date.today())
    assert len(pendientes) == 1

    # 4. Eliminar tarjeta
    eliminado = await adapter.eliminar_tarjeta("card-1")
    assert eliminado is True
    assert await adapter.obtener_tarjeta("card-1") is None


@pytest.mark.asyncio
async def test_generar_flashcards_exito(tmp_path: Path):
    adapter = JsonStudyAdapter(file_path=tmp_path / "study.json")
    obsidian = DummyObsidian()
    cards_json = json.dumps({
        "tema": "Protocolo Raft",
        "tarjetas": [
            {
                "pregunta": "¿Cuál es el rol del líder en Raft?",
                "respuesta": "Gestionar la replicación del log y coordinar consenso."
            },
            {
                "pregunta": "¿Qué ocurre en una partición de red?",
                "respuesta": "La mayoría mantiene el quorum y la minoría no puede confirmar escrituras."
            }
        ],
        "resumen": "Conceptos clave del algoritmo Raft."
    })
    llm = DummyLLM(response_text=cards_json)
    agente = AgenteEstudio(llm=llm, study_repo=adapter, obsidian=obsidian)

    resultado = await agente.ejecutar("Genera flashcards de mi nota de Raft")

    assert resultado.estado == EstadoResultado.EXITO
    assert "Se crearon 2 flashcards" in resultado.mensaje
    assert "Protocolo Raft" in resultado.mensaje

    guardadas = await adapter.listar_todas()
    assert len(guardadas) == 2


@pytest.mark.asyncio
async def test_consultar_pendientes_y_sesion_quiz(tmp_path: Path):
    adapter = JsonStudyAdapter(file_path=tmp_path / "study.json")
    obsidian = DummyObsidian()
    llm = DummyLLM()
    agente = AgenteEstudio(llm=llm, study_repo=adapter, obsidian=obsidian)

    # 1. Consulta inicial vacía
    res_vacio = await agente.ejecutar("¿Qué tengo para repasar?")
    assert "¡Estás al día" in res_vacio.mensaje

    # 2. Agregar tarjeta para hoy
    card = ItemEstudio(
        id="card-100",
        nota_id="Cálculo",
        pregunta="¿Derivada de e^x?",
        respuesta="e^x",
        sig_repaso=date.today(),
    )
    await adapter.guardar_tarjeta(card)

    # 3. Consulta con tarjeta pendiente
    res_pend = await agente.ejecutar("repasos pendientes")
    assert "1 tarjeta pendiente" in res_pend.mensaje
    assert "Cálculo" in res_pend.mensaje

    # 4. Iniciar sesión de repaso
    res_inicio = await agente.ejecutar("iniciar repaso")
    assert "Sesión de Estudio SM-2" in res_inicio.mensaje
    assert "¿Derivada de e^x?" in res_inicio.mensaje

    # 5. Evaluar respuesta con calificación 5
    res_eval = await agente.ejecutar("5")
    assert "Repaso registrado" in res_eval.mensaje
    assert "Calidad 5/5" in res_eval.mensaje
    assert "¡Has completado todas las tarjetas" in res_eval.mensaje

    card_actualizada = await adapter.obtener_tarjeta("card-100")
    assert card_actualizada.repeticiones == 1
    assert card_actualizada.intervalo == 1


@pytest.mark.asyncio
async def test_generar_nota_cornell(tmp_path: Path):
    adapter = JsonStudyAdapter(file_path=tmp_path / "study.json")
    obsidian = DummyObsidian()
    cornell_md = """# Cornell Notes: Enrutamiento BGP
**Fecha:** 2026-08-27 | **Materia/Área:** Redes

---

## 📌 Preguntas / Ideas Clave
- ¿Qué es un Sistema Autónomo (AS)?

---

## 📝 Notas Detalladas
- BGP es un protocolo de vector de rutas (Path Vector Protocol).

---

## 💡 Resumen Sintético
BGP conecta sistemas autónomos en Internet mediante políticas de enrutamiento.
"""
    llm = DummyLLM(response_text=cornell_md)
    agente = AgenteEstudio(llm=llm, study_repo=adapter, obsidian=obsidian)

    resultado = await agente.ejecutar("Crea una nota Cornell sobre Enrutamiento BGP")

    assert resultado.estado == EstadoResultado.EXITO
    assert "Nota Cornell creada exitosamente" in resultado.mensaje
    assert len(obsidian.notas_escritas) >= 1
    assert "Cornell - Enrutamiento BGP" in obsidian.notas_escritas[0].titulo
