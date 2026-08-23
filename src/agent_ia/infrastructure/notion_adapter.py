"""Adaptador de Notion — implementación del puerto NotionPort.

Usa la librería oficial notion-client para interactuar con la API
de Notion. El token de integración y el database_id se leen
de la configuración centralizada.
"""

from __future__ import annotations

import logging
from datetime import date

from notion_client import AsyncClient as NotionAsyncClient

from agent_ia.domain.entities import Area, Nota, Tarea
from agent_ia.domain.entities.area import TipoArea
from agent_ia.domain.entities.tarea import EstadoTarea
from agent_ia.domain.ports.notion_port import NotionPort
from agent_ia.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class NotionAdapter(NotionPort):
    """Adaptador concreto de la API de Notion."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = NotionAsyncClient(auth=settings.notion_token)
        self._database_id = settings.notion_database_id

    # --- Notas ---

    async def crear_pagina(self, nota: Nota) -> str:
        """Crea una página en Notion a partir de una Nota."""
        properties: dict = {
            "title": {
                "title": [{"text": {"content": nota.titulo}}],
            },
        }

        # Añadir tags si existen
        if nota.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in nota.tags],
            }

        response = await self._client.pages.create(
            parent={"database_id": self._database_id},
            properties=properties,
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": nota.contenido or ""}}],
                    },
                }
            ],
        )

        page_id = response["id"]
        nota.notion_page_id = page_id
        logger.info("Página creada en Notion: %s (id=%s)", nota.titulo, page_id)
        return page_id

    async def obtener_pagina(self, page_id: str) -> dict:
        """Obtiene los datos crudos de una página."""
        return await self._client.pages.retrieve(page_id=page_id)

    async def actualizar_pagina(self, page_id: str, propiedades: dict) -> None:
        """Actualiza propiedades de una página existente."""
        await self._client.pages.update(page_id=page_id, properties=propiedades)
        logger.debug("Página actualizada: %s", page_id)

    # --- Base de datos ---

    async def consultar_database(
        self,
        database_id: str,
        filtro: dict | None = None,
        orden: list[dict] | None = None,
    ) -> list[dict]:
        """Consulta una base de datos con filtros opcionales."""
        kwargs: dict = {"database_id": database_id}
        if filtro:
            kwargs["filter"] = filtro
        if orden:
            kwargs["sorts"] = orden

        resultados = []
        response = await self._client.databases.query(**kwargs)
        resultados.extend(response.get("results", []))

        # Paginación
        while response.get("has_more"):
            response = await self._client.databases.query(
                **kwargs,
                start_cursor=response["next_cursor"],
            )
            resultados.extend(response.get("results", []))

        return resultados

    # --- Áreas ---

    async def listar_areas(self) -> list[Area]:
        """Lista todas las áreas del Segundo Cerebro."""
        resultados = await self.consultar_database(self._database_id)
        areas = []

        for page in resultados:
            try:
                props = page.get("properties", {})
                title_prop = props.get("Name", props.get("title", props.get("Nombre", {})))
                titulo = ""
                if title_prop and "title" in title_prop:
                    titulo = "".join(
                        t.get("plain_text", "") for t in title_prop["title"]
                    )

                areas.append(
                    Area(
                        id=page["id"],
                        nombre=titulo or "Sin nombre",
                        tipo=TipoArea.ACADEMICA,
                        notion_page_id=page["id"],
                    )
                )
            except (KeyError, TypeError) as e:
                logger.warning("Error parseando área de Notion: %s", e)
                continue

        return areas

    # --- Tareas ---

    async def listar_tareas_pendientes(self) -> list[Tarea]:
        """Lista tareas pendientes de Notion."""
        filtro = {
            "property": "Status",
            "status": {"does_not_equal": "Done"},
        }

        try:
            resultados = await self.consultar_database(self._database_id, filtro=filtro)
        except Exception:
            # Si el filtro de status no funciona, consultar sin filtro
            logger.warning("Filtro de status no disponible, consultando sin filtro")
            resultados = await self.consultar_database(self._database_id)

        tareas = []
        for page in resultados:
            try:
                props = page.get("properties", {})
                title_prop = props.get("Name", props.get("title", props.get("Nombre", {})))
                titulo = ""
                if title_prop and "title" in title_prop:
                    titulo = "".join(
                        t.get("plain_text", "") for t in title_prop["title"]
                    )

                # Intentar obtener fecha límite
                fecha_limite = None
                date_prop = props.get("Due", props.get("Fecha", props.get("Date", {})))
                if date_prop and "date" in date_prop and date_prop["date"]:
                    fecha_str = date_prop["date"].get("start", "")
                    if fecha_str:
                        fecha_limite = date.fromisoformat(fecha_str)

                tareas.append(
                    Tarea(
                        id=page["id"],
                        titulo=titulo or "Sin título",
                        estado=EstadoTarea.PENDIENTE,
                        fecha_limite=fecha_limite,
                        notion_page_id=page["id"],
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Error parseando tarea de Notion: %s", e)
                continue

        return tareas

    # --- Health ---

    async def health_check(self) -> bool:
        """Verifica la conexión con Notion."""
        try:
            await self._client.databases.retrieve(database_id=self._database_id)
            return True
        except Exception:
            logger.exception("Notion health check falló")
            return False
