"""Puerto abstracto para la persistencia y estado de sincronización (Fase 3).

Define la interfaz para registrar marcas de tiempo, hashes de contenido y
metadatos de sincronización entre Notion, Obsidian y orígenes externos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SyncPort(ABC):
    """Interfaz para gestionar el estado de sincronización bidireccional."""

    @abstractmethod
    def obtener_estado(self) -> dict:
        """Obtiene el estado completo de sincronización."""

    @abstractmethod
    def guardar_estado(self, estado: dict) -> None:
        """Persiste el estado de sincronización."""

    @abstractmethod
    def registrar_evento(
        self, origen: str, destino: str, entidad: str, accion: str, detalles: dict | None = None
    ) -> None:
        """Registra un evento de sincronización en el historial."""

    @abstractmethod
    def obtener_hash(self, clave: str) -> str | None:
        """Obtiene el hash SHA-256 almacenado para una entidad."""

    @abstractmethod
    def actualizar_hash(self, clave: str, hash_valor: str) -> None:
        """Actualiza el hash SHA-256 de una entidad."""
