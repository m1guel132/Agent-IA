"""Puerto abstracto para Obsidian (vault local).

Define la interfaz de lectura/escritura de archivos .md en el vault.
El vault es un directorio local, sin API; el adaptador opera
directamente sobre el sistema de archivos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from gwen_os.domain.entities import Nota


class ObsidianPort(ABC):
    """Interfaz para interactuar con el vault de Obsidian."""

    @abstractmethod
    async def escribir_nota(self, nota: Nota) -> Path:
        """Escribe una nota como archivo .md en el vault.

        Returns:
            Path absoluto del archivo creado/actualizado.
        """

    @abstractmethod
    async def leer_nota(self, ruta_relativa: str) -> str:
        """Lee el contenido de un archivo .md del vault.

        Args:
            ruta_relativa: Ruta relativa al vault root.

        Returns:
            Contenido del archivo como string.
        """

    @abstractmethod
    async def listar_notas(self, directorio: str = "") -> list[str]:
        """Lista todas las notas (.md) en un directorio del vault.

        Args:
            directorio: Subdirectorio dentro del vault (vacío = raíz).

        Returns:
            Lista de rutas relativas al vault.
        """

    @abstractmethod
    async def buscar_notas(self, query: str) -> list[str]:
        """Busca notas cuyo nombre o contenido coincida con la query.

        Returns:
            Lista de rutas relativas que coinciden.
        """

    @abstractmethod
    async def eliminar_nota(self, ruta_relativa: str) -> bool:
        """Elimina un archivo .md del vault.

        Returns:
            True si se eliminó, False si no existía.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica que el vault exista y sea accesible."""
