"""Entidad Hábito — seguimiento de hábitos con racha.

El registro de cumplimiento se puede hacer por lenguaje natural
(voz/chat) en vez de edición manual de la base de datos (RF1.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Habito:
    """Hábito con seguimiento de racha y último cumplimiento.

    Attributes:
        id: Identificador único.
        nombre: Nombre del hábito.
        racha: Días consecutivos de cumplimiento.
        area_id: ID del Área a la que pertenece.
        ultimo_cumplimiento: Fecha del último registro.
        activo: Si el hábito está activo.
        notion_page_id: ID en Notion.
        created_at: Fecha de creación.
    """

    id: str
    nombre: str
    racha: int = 0
    area_id: str | None = None
    ultimo_cumplimiento: date | None = None
    activo: bool = True
    notion_page_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ValueError("El nombre del hábito no puede estar vacío")
        if self.racha < 0:
            raise ValueError("La racha no puede ser negativa")

    def registrar_cumplimiento(self) -> None:
        """Registra el cumplimiento del hábito hoy."""
        hoy = date.today()
        if self.ultimo_cumplimiento == hoy:
            return  # Ya registrado hoy

        if self.ultimo_cumplimiento and (hoy - self.ultimo_cumplimiento).days == 1:
            self.racha += 1
        else:
            self.racha = 1  # Racha rota o primer día

        self.ultimo_cumplimiento = hoy

    def verificar_racha(self) -> bool:
        """Verifica si la racha sigue activa (cumplimiento ayer o hoy)."""
        if self.ultimo_cumplimiento is None:
            return False
        dias = (date.today() - self.ultimo_cumplimiento).days
        return dias <= 1
