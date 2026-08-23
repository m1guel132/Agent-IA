"""Entidad Nota — unidad fundamental de conocimiento.

Una Nota puede vivir en Notion, en Obsidian, o en ambos (sincronizada).
Opcionalmente puede generar un ItemEstudio para repetición espaciada,
conectando el Study Board al Segundo Cerebro sin duplicar datos (RF2.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class OrigenNota(StrEnum):
    """Origen de la nota dentro del sistema."""

    NOTION = "notion"
    OBSIDIAN = "obsidian"
    CHAT = "chat"
    SYNC = "sync"


@dataclass
class Nota:
    """Unidad fundamental de conocimiento del Segundo Cerebro.

    Attributes:
        id: Identificador único.
        titulo: Título de la nota.
        contenido: Contenido en markdown.
        tags: Etiquetas de clasificación.
        area_id: ID del Área a la que pertenece.
        origen: De dónde fue creada la nota.
        notion_page_id: ID de la página en Notion (si existe).
        obsidian_path: Ruta relativa al vault de Obsidian (si existe).
        created_at: Fecha de creación.
        updated_at: Fecha de última modificación.
    """

    id: str
    titulo: str
    contenido: str = ""
    tags: list[str] = field(default_factory=list)
    area_id: str | None = None
    origen: OrigenNota = OrigenNota.CHAT
    notion_page_id: str | None = None
    obsidian_path: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.titulo.strip():
            raise ValueError("El título de la nota no puede estar vacío")

    @property
    def esta_sincronizada(self) -> bool:
        """True si la nota existe tanto en Notion como en Obsidian."""
        return self.notion_page_id is not None and self.obsidian_path is not None
