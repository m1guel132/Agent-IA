"""Tests unitarios para AgentePlan."""

from __future__ import annotations

import json
import pytest

from agent_ia.domain.ports.llm_port import LLMPort, LLMResponse
from agent_ia.domain.ports.notion_port import NotionPort
from agent_ia.use_cases.agente import EstadoResultado
from agent_ia.use_cases.agente_plan import AgentePlan


class DummyLLM(LLMPort):
    def __init__(self, response_text: str = "") -> None:
        self.response_text = response_text

    async def generate(self, prompt: str, *, system: str = "", temperature: float = 0.7) -> LLMResponse:
        return LLMResponse(content=self.response_text, model="test-model")

    async def embed(self, text: str) -> list[float]:
        return [0.0]

    async def health_check(self) -> bool:
        return True


class DummyNotion(NotionPort):
    def __init__(self) -> None:
        self.tareas_creadas: list[dict] = []
        self.objetivos_creados: list[dict] = []
        self.proyectos_creados: list[dict] = []

    async def crear_pagina(self, nota) -> str:
        return "page-id"

    async def obtener_pagina(self, page_id: str) -> dict:
        return {}

    async def actualizar_pagina(self, page_id: str, propiedades: dict) -> None:
        pass

    async def consultar_database(self, database_id: str, filtro=None, orden=None) -> list[dict]:
        return []

    async def listar_areas(self) -> list:
        return []

    async def listar_objetivos(self) -> list:
        return [{"id": "obj-1", "titulo": "Aprobar Redes", "area": "Universidad"}]

    async def listar_proyectos(self) -> list:
        return [{"id": "proj-1", "titulo": "Laboratorio Raft"}]

    async def listar_tareas_pendientes(self) -> list:
        return []

    async def crear_tarea(self, titulo: str, relaciones: dict[str, str] | None = None) -> str:
        self.tareas_creadas.append({"titulo": titulo, "relaciones": relaciones})
        return f"tarea-{len(self.tareas_creadas)}"

    async def crear_objetivo(self, titulo: str, relaciones: dict[str, str] | None = None) -> str:
        self.objetivos_creados.append({"titulo": titulo, "relaciones": relaciones})
        return f"obj-{len(self.objetivos_creados)}"

    async def crear_proyecto(self, titulo: str, relaciones: dict[str, str] | None = None) -> str:
        self.proyectos_creados.append({"titulo": titulo, "relaciones": relaciones})
        return f"proj-{len(self.proyectos_creados)}"

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_ejecutar_creacionRapidaTarea_agregaTareaDirecta():
    notion = DummyNotion()
    llm = DummyLLM()
    agente = AgentePlan(llm=llm, notion=notion)

    resultado = await agente.ejecutar("agrega una tarea: Terminar informe de redes")

    assert resultado.estado == EstadoResultado.EXITO
    assert len(notion.tareas_creadas) == 1
    assert notion.tareas_creadas[0]["titulo"] == "Terminar informe de redes"
    assert "notion_page_id" in resultado.datos


@pytest.mark.asyncio
async def test_ejecutar_creacionRapidaTareaSinTitulo_retornaError():
    notion = DummyNotion()
    llm = DummyLLM()
    agente = AgentePlan(llm=llm, notion=notion)

    resultado = await agente.ejecutar("tarea:")

    assert resultado.estado == EstadoResultado.ERROR
    assert len(notion.tareas_creadas) == 0
    assert "Por favor indícame" in resultado.mensaje


@pytest.mark.asyncio
async def test_ejecutar_planEstrategico_proponePlanConObjetivoYProyectos():
    notion = DummyNotion()
    plan_json = json.dumps({
        "objetivo": {
            "titulo": "Aprobar Redes de Computadores",
            "area": "Universidad"
        },
        "proyectos": [
            {
                "titulo": "Laboratorio 1",
                "tareas": ["Configurar routers", "Capturar paquetes"]
            }
        ],
        "razon": "Un enfoque práctico aumentará tu dominio técnico."
    })
    llm = DummyLLM(response_text=plan_json)
    agente = AgentePlan(llm=llm, notion=notion)

    resultado = await agente.ejecutar("Quiero planear cómo sacar 5 en Redes este semestre")

    assert resultado.estado == EstadoResultado.REQUIERE_CONFIRMACION
    assert resultado.accion_pendiente is not None
    assert "Aprobar Redes de Computadores" in resultado.mensaje
    assert "Laboratorio 1" in resultado.mensaje
    assert "Configurar routers" in resultado.mensaje


@pytest.mark.asyncio
async def test_ejecutar_planEstrategicoTextoLibre_retornaRespuestaConversacional():
    """Verifica que si el LLM responde con análisis o plan en texto libre, se entregue como respuesta fluida."""
    notion = DummyNotion()
    llm = DummyLLM(response_text="Aquí tienes una hoja de ruta estratégica en 3 fases para tus objetivos...")
    agente = AgentePlan(llm=llm, notion=notion)

    resultado = await agente.ejecutar("puedes hacer un plan para cumplir esos objetivos")

    assert resultado.estado == EstadoResultado.EXITO
    assert "hoja de ruta estratégica" in resultado.mensaje
    assert resultado.agente == "AgentePlan"


@pytest.mark.asyncio
async def test_ejecutar_confirmarPropuestaExitosa_creaObjetivoProyectosYTareasEnNotion():
    notion = DummyNotion()
    plan_json = json.dumps({
        "objetivo": {"titulo": "Dominar FastAPI", "area": "Tecnología"},
        "proyectos": [
            {"titulo": "API REST", "tareas": ["Definir esquemas Pydantic", "Conectar base de datos"]}
        ],
        "razon": "Te dará fundamentos sólidos."
    })
    llm = DummyLLM(response_text=plan_json)
    agente = AgentePlan(llm=llm, notion=notion)

    # 1. Proponer plan
    res_propuesta = await agente.ejecutar("Quiero aprender FastAPI")
    propuesta_id = res_propuesta.accion_pendiente

    # 2. Confirmar plan
    res_confirmacion = await agente.ejecutar(
        "sí", contexto={"confirmar_propuesta": propuesta_id}
    )

    assert res_confirmacion.estado == EstadoResultado.EXITO
    assert len(notion.objetivos_creados) == 1
    assert notion.objetivos_creados[0]["titulo"] == "Dominar FastAPI"
    assert len(notion.proyectos_creados) == 1
    assert len(notion.tareas_creadas) == 2
    assert "Plan implementado en Notion con éxito" in res_confirmacion.mensaje


@pytest.mark.asyncio
async def test_ejecutar_confirmarPropuestaNoEncontrada_retornaError():
    notion = DummyNotion()
    llm = DummyLLM()
    agente = AgentePlan(llm=llm, notion=notion)

    resultado = await agente.ejecutar(
        "sí", contexto={"confirmar_propuesta": "id-inexistente"}
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert "no existe" in resultado.mensaje.lower() or "expir" in resultado.mensaje.lower()


@pytest.mark.asyncio
async def test_ejecutar_consultar_objetivos_existentes():
    """Verifica que el agente consulte y presente los objetivos de Notion."""
    notion = DummyNotion()
    llm = DummyLLM(response_text="🎯 **Tus Objetivos Actuales:**\n- Aprobar Redes")
    agente = AgentePlan(llm=llm, notion=notion)

    resultado = await agente.ejecutar("mira mis objetivos de mi segundo cerebro")

    assert resultado.estado == EstadoResultado.EXITO
    assert "Aprobar Redes" in resultado.mensaje
    assert len(resultado.datos["objetivos"]) == 1
