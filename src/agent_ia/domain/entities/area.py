"""Entidad Área — contenedor principal del Segundo Cerebro.

Un Área agrupa notas, tareas y hábitos bajo un mismo dominio temático
(e.g. "Redes", "Cálculo", "Salud"). Corresponde directamente a las
áreas definidas en el Notion del Segundo Cerebro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class TipoArea(StrEnum):
    """Tipos de área soportados en el Segundo Cerebro."""

    ACADEMICA = "academica"
    PERSONAL = "personal"
    PROYECTO = "proyecto"
    HABITO = "habito"


@dataclass
class Area:
    """Contenedor principal del Segundo Cerebro.

    Attributes:
        id: Identificador único (UUID de Notion o generado).
        nombre: Nombre legible del área.
        tipo: Clasificación del área.
        descripcion: Descripción opcional del área.
        notion_page_id: ID de la página/base de datos en Notion (si existe).
        created_at: Fecha de creación.
        updated_at: Fecha de última actualización.
    """

    id: str
    nombre: str
    tipo: TipoArea = TipoArea.ACADEMICA
    descripcion: str = ""
    notion_page_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ValueError("El nombre del área no puede estar vacío")
