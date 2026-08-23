"""Puerto abstracto para Notion.

Define la interfaz de acceso a la API de Notion. El AgenteCurador
y AgenteSync son los principales consumidores de este puerto.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_ia.domain.entities import Area, Nota, Tarea


class NotionPort(ABC):
    """Interfaz para interactuar con la API de Notion."""

    # --- Notas ---

    @abstractmethod
    async def crear_pagina(self, nota: Nota) -> str:
        """Crea una página en Notion a partir de una Nota.

        Returns:
            El page_id de la página creada en Notion.
        """

    @abstractmethod
    async def obtener_pagina(self, page_id: str) -> dict:
        """Obtiene los datos crudos de una página de Notion."""

    @abstractmethod
    async def actualizar_pagina(self, page_id: str, propiedades: dict) -> None:
        """Actualiza las propiedades de una página existente."""

    # --- Base de datos ---

    @abstractmethod
    async def consultar_database(
        self,
        database_id: str,
        filtro: dict | None = None,
        orden: list[dict] | None = None,
    ) -> list[dict]:
        """Consulta una base de datos de Notion con filtros opcionales.

        Returns:
            Lista de resultados crudos de la API de Notion.
        """

    # --- Áreas ---

    @abstractmethod
    async def listar_areas(self) -> list[Area]:
        """Lista todas las áreas del Segundo Cerebro."""

    # --- Tareas ---

    @abstractmethod
    async def listar_tareas_pendientes(self) -> list[Tarea]:
        """Lista tareas con estado pendiente."""

    # --- Health ---

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica que la conexión con Notion funcione."""
