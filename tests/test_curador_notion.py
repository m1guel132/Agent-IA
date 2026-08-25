"""Tests de integración para AgenteCurador con NotionPort.

Verifica que AgenteCurador (clase real, sin mockear el caso de uso):
1. Propone una nota clasificada por el LLM (modo revisión, RF5.4).
2. Al confirmarse, escribe en Obsidian, llama a notion.crear_pagina(nota),
   asigna nota.notion_page_id e indexa en ChromaDB con dicho ID.
3. Si la llamada a Notion falla, revierte la propuesta al estado pendiente
   y retorna EstadoResultado.ERROR sin dar por completada la operación.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from agent_ia.domain.entities import Area, Nota, Tarea
from agent_ia.domain.ports.llm_port import LLMPort, LLMResponse
from agent_ia.domain.ports.notion_port import NotionPort
from agent_ia.domain.ports.obsidian_port import ObsidianPort
from agent_ia.domain.ports.vector_store_port import SearchResult, VectorStorePort
from agent_ia.use_cases.agente import EstadoResultado
from agent_ia.use_cases.agente_curador import AgenteCurador


class FakeLLM(LLMPort):
    """Fake LLM que responde con clasificaciones JSON predefinidas."""

    def __init__(self, clasificacion_json: str | None = None) -> None:
        self.clasificacion_json = clasificacion_json or (
            '{"area_sugerida": "Redes", "tags": ["redes", "routing"], '
            '"es_posible_duplicado": false, "razon": "Conceptos de redes de datos"}'
        )

    async def generate(
        self, prompt: str, *, system: str = "", temperature: float = 0.7
    ) -> LLMResponse:
        return LLMResponse(content=self.clasificacion_json, model="fake-model")

    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def health_check(self) -> bool:
        return True


class FakeObsidian(ObsidianPort):
    """Fake Obsidian que registra notas escritas en memoria."""

    def __init__(self) -> None:
        self.notas_escritas: list[Nota] = []

    async def escribir_nota(self, nota: Nota) -> Path:
        nota.obsidian_path = f"{nota.area_id or 'inbox'}/{nota.titulo}.md"
        self.notas_escritas.append(nota)
        return Path(f"/vault/{nota.obsidian_path}")

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


class FakeVectorStore(VectorStorePort):
    """Fake VectorStore que captura indexaciones en memoria."""

    def __init__(self) -> None:
        self.indexed_docs: list[dict] = []

    async def indexar(
        self, doc_id: str, content: str, metadata: dict | None = None
    ) -> None:
        self.indexed_docs.append(
            {"doc_id": doc_id, "content": content, "metadata": metadata or {}}
        )

    async def buscar(self, query: str, n_results: int = 5) -> list[SearchResult]:
        return []

    async def eliminar(self, doc_id: str) -> None:
        pass

    async def health_check(self) -> bool:
        return True


class FakeNotion(NotionPort):
    """Fake Notion que registra llamadas a crear_pagina y permite simular errores."""

    def __init__(self, simular_error: bool = False) -> None:
        self.simular_error = simular_error
        self.paginas_creadas: list[Nota] = []

    async def crear_pagina(self, nota: Nota) -> str:
        if self.simular_error:
            raise ConnectionError("No se pudo conectar con la API de Notion")
        page_id = f"notion-page-{len(self.paginas_creadas) + 1}"
        self.paginas_creadas.append(nota)
        return page_id

    async def obtener_pagina(self, page_id: str) -> dict:
        return {}

    async def actualizar_pagina(self, page_id: str, propiedades: dict) -> None:
        pass

    async def consultar_database(
        self,
        database_id: str,
        filtro: dict | None = None,
        orden: list[dict] | None = None,
    ) -> list[dict]:
        return []

    async def listar_areas(self) -> list[Area]:
        return []

    async def crear_proyecto(
        self, titulo: str, relaciones: dict[str, str] | None = None
    ) -> str:
        return "fake-proj-id"

    async def crear_objetivo(
        self, titulo: str, relaciones: dict[str, str] | None = None
    ) -> str:
        return "fake-obj-id"

    async def listar_tareas_pendientes(self) -> list[Tarea]:
        return []

    async def crear_tarea(
        self, titulo: str, relaciones: dict[str, str] | None = None
    ) -> str:
        return "fake-task-id"

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_curador_confirmar_propuesta_crea_pagina_en_notion():
    """Verifica que al confirmar una propuesta, AgenteCurador escribe en Notion con datos correctos."""
    llm = FakeLLM()
    obsidian = FakeObsidian()
    vector_store = FakeVectorStore()
    notion = FakeNotion()

    # Instanciamos el AgenteCurador real
    curador = AgenteCurador(
        llm=llm,
        obsidian=obsidian,
        vector_store=vector_store,
        notion=notion,
    )

    # 1. Proponer nota
    res_propuesta = await curador.ejecutar("anota esto: Protocolo BGP y tablas de enrutamiento")
    assert res_propuesta.estado == EstadoResultado.REQUIERE_CONFIRMACION
    assert "propuesta_id" in res_propuesta.datos
    propuesta_id = res_propuesta.datos["propuesta_id"]

    # Verificar que NO se ha escrito en Notion ni en Obsidian todavía
    assert len(notion.paginas_creadas) == 0
    assert len(obsidian.notas_escritas) == 0

    # 2. Confirmar propuesta
    res_confirmacion = await curador.ejecutar(
        "", contexto={"confirmar_propuesta": propuesta_id}
    )

    # 3. Validar resultados de éxito
    assert res_confirmacion.estado == EstadoResultado.EXITO
    assert "notion_page_id" in res_confirmacion.datos
    assert res_confirmacion.datos["notion_page_id"] == "notion-page-1"

    # 4. Validar que notion.crear_pagina fue invocado con la Nota adecuada
    assert len(notion.paginas_creadas) == 1
    nota_creada = notion.paginas_creadas[0]
    assert nota_creada.titulo == "Protocolo BGP y tablas de enrutamiento"
    assert nota_creada.area_id == "Redes"
    assert "redes" in nota_creada.tags
    assert nota_creada.notion_page_id == "notion-page-1"

    # 5. Validar que ChromaDB fue indexado con el notion_page_id
    assert len(vector_store.indexed_docs) == 1
    doc_indexado = vector_store.indexed_docs[0]
    assert doc_indexado["metadata"]["notion_page_id"] == "notion-page-1"
    assert doc_indexado["metadata"]["obsidian_path"] == "Redes/Protocolo BGP y tablas de enrutamiento.md"
    assert doc_indexado["metadata"]["area"] == "Redes"


@pytest.mark.asyncio
async def test_curador_fallo_notion_revierte_propuesta():
    """Verifica que si Notion falla, la propuesta se devuelve a pendiente y se retorna error."""
    llm = FakeLLM()
    obsidian = FakeObsidian()
    vector_store = FakeVectorStore()
    notion = FakeNotion(simular_error=True)

    curador = AgenteCurador(
        llm=llm,
        obsidian=obsidian,
        vector_store=vector_store,
        notion=notion,
    )

    # 1. Proponer nota
    res_propuesta = await curador.ejecutar("anota esto: Nota que fallara en Notion")
    assert res_propuesta.estado == EstadoResultado.REQUIERE_CONFIRMACION
    propuesta_id = res_propuesta.datos["propuesta_id"]

    # 2. Confirmar propuesta (debe fallar al conectar a Notion)
    res_confirmacion = await curador.ejecutar(
        "", contexto={"confirmar_propuesta": propuesta_id}
    )

    # 3. Validar estado de error
    assert res_confirmacion.estado == EstadoResultado.ERROR
    assert "Error al guardar la nota" in res_confirmacion.mensaje

    # 4. Validar que la propuesta se mantuvo en pendientes (no se perdió)
    assert propuesta_id in curador._propuestas_pendientes
    assert curador._propuestas_pendientes[propuesta_id]["nota"].titulo == "Nota que fallara en Notion"

    # 5. Validar que NO se indexó en ChromaDB debido al fallo previo
    assert len(vector_store.indexed_docs) == 0
