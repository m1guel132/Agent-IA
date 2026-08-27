"""Puerto abstracto para la persistencia del Study Board y repetición espaciada.

Define la interfaz para guardar, recuperar y listar tarjetas de estudio (ItemEstudio).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from agent_ia.domain.entities.item_estudio import ItemEstudio


class StudyPort(ABC):
    """Interfaz para persistencia de tarjetas de estudio e items SM-2."""

    @abstractmethod
    async def guardar_tarjeta(self, item: ItemEstudio) -> None:
        """Guarda o actualiza una tarjeta de estudio en el repositorio."""

    @abstractmethod
    async def obtener_tarjeta(self, item_id: str) -> ItemEstudio | None:
        """Obtiene una tarjeta de estudio por su identificador único."""

    @abstractmethod
    async def listar_pendientes(self, fecha: date | None = None) -> list[ItemEstudio]:
        """Lista todas las tarjetas cuyo repaso esté pendiente a la fecha dada (hoy por defecto)."""

    @abstractmethod
    async def listar_todas(self) -> list[ItemEstudio]:
        """Lista todas las tarjetas registradas en el Study Board."""

    @abstractmethod
    async def eliminar_tarjeta(self, item_id: str) -> bool:
        """Elimina una tarjeta de estudio por su ID."""
