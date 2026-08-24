"""Puerto abstracto para Notion.

Define la interfaz de acceso a la API de Notion. El sistema descubre
dinámicamente todas las bases de datos dentro de la página raíz y
resuelve relaciones a partir de los schemas reales de Notion.

Comportamiento best-effort: si una relación no se puede resolver
(título ambiguo, base no accesible, etc.), la operación continúa
sin esa relación específica.
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

    # --- Creación de Entidades Dinámicas (Plan Estratégico) ---

    @abstractmethod
    async def crear_proyecto(
        self, titulo: str, relaciones: dict[str, str] | None = None
    ) -> str:
        """Crea un nuevo proyecto en la base de Proyectos.

        Args:
            titulo: Nombre del proyecto.
            relaciones: Diccionario de relaciones, e.g. {"Area": "Ingeniería de Sistemas", "Objetivo": "Aprobar Física"}.

        Returns:
            El page_id de la página creada.
        """

    @abstractmethod
    async def crear_objetivo(
        self, titulo: str, relaciones: dict[str, str] | None = None
    ) -> str:
        """Crea un nuevo objetivo en la base de Objetivos.

        Args:
            titulo: Nombre del objetivo.
            relaciones: Diccionario de relaciones, e.g. {"Area": "Universidad"}.

        Returns:
            El page_id de la página creada.
        """

    # --- Tareas ---

    @abstractmethod
    async def listar_tareas_pendientes(self) -> list[Tarea]:
        """Lista tareas con estado pendiente."""

    @abstractmethod
    async def crear_tarea(
        self,
        titulo: str,
        relaciones: dict[str, str] | None = None,
    ) -> str:
        """Crea una nueva tarea en la base de datos 'Tareas' de Notion.

        El sistema resuelve relaciones dinámicamente contra cualquier base
        relacionada detectada en el schema de Notion, con matching tolerante
        (fuzzy) y comportamiento best-effort: si una relación no se puede
        resolver, la tarea se crea sin esa relación específica (no bloquea).

        Args:
            titulo: Título de la tarea.
            relaciones: Mapeo {nombre_propiedad_relación: título_página_objetivo}.
                        Las propiedades de relación válidas se descubren
                        automáticamente del schema de la base.

        Returns:
            El page_id de la tarea creada en Notion.
        """

    # --- Health ---

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica que la conexión con Notion funcione."""
