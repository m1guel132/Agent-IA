"""Entidad Tarea — ítem de acción con fecha límite.

Las tareas se sincronizan bidireccionalmente con Todoist (RF6.1)
y con Google Calendar (RF6.2) a través de AgentePlan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class EstadoTarea(StrEnum):
    """Estados posibles de una tarea."""

    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


class PrioridadTarea(StrEnum):
    """Niveles de prioridad (alineados con DINO del SRS)."""

    OBLIGATORIA = "obligatoria"
    IMPORTANTE = "importante"
    DESEABLE = "deseable"


@dataclass
class Tarea:
    """Ítem de acción con seguimiento de estado y fecha límite.

    Attributes:
        id: Identificador único.
        titulo: Descripción de la tarea.
        estado: Estado actual de la tarea.
        prioridad: Nivel de prioridad.
        fecha_limite: Fecha límite para completar.
        area_id: ID del Área a la que pertenece.
        notion_page_id: ID en Notion.
        todoist_id: ID en Todoist (si sincronizada).
        calendar_event_id: ID del evento en Google Calendar (si existe).
        created_at: Fecha de creación.
        updated_at: Última modificación.
    """

    id: str
    titulo: str
    estado: EstadoTarea = EstadoTarea.PENDIENTE
    prioridad: PrioridadTarea = PrioridadTarea.IMPORTANTE
    fecha_limite: date | None = None
    area_id: str | None = None
    notion_page_id: str | None = None
    todoist_id: str | None = None
    calendar_event_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.titulo.strip():
            raise ValueError("El título de la tarea no puede estar vacío")

    @property
    def esta_vencida(self) -> bool:
        """True si la tarea tiene fecha límite y ya venció."""
        if self.fecha_limite is None:
            return False
        return date.today() > self.fecha_limite and self.estado == EstadoTarea.PENDIENTE
