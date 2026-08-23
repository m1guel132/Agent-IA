"""Adaptador de Obsidian — implementación del puerto ObsidianPort.

Opera directamente sobre el sistema de archivos del vault local.
No hay API; todo es lectura/escritura de archivos .md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agent_ia.domain.entities import Nota
from agent_ia.domain.ports.obsidian_port import ObsidianPort
from agent_ia.infrastructure.config import Settings

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Limpia un nombre para usarlo como nombre de archivo."""
    # Remover caracteres no válidos para nombres de archivo en Windows
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip()


class ObsidianAdapter(ObsidianPort):
    """Adaptador concreto para el vault de Obsidian (sistema de archivos)."""

    def __init__(self, settings: Settings) -> None:
        self._vault_path = settings.vault_path
        if not self._vault_path.exists():
            logger.warning("Vault de Obsidian no encontrado: %s", self._vault_path)

    async def escribir_nota(self, nota: Nota) -> Path:
        """Escribe una nota como archivo .md en el vault."""
        # Determinar la carpeta de destino (por área o raíz)
        if nota.area_id:
            carpeta = self._vault_path / _sanitize_filename(nota.area_id)
        else:
            carpeta = self._vault_path / "inbox"

        carpeta.mkdir(parents=True, exist_ok=True)

        filename = _sanitize_filename(nota.titulo) + ".md"
        filepath = carpeta / filename

        # Construir contenido con frontmatter YAML
        frontmatter = [
            "---",
            f"id: {nota.id}",
            f"titulo: {nota.titulo}",
            f"area: {nota.area_id or 'sin_area'}",
            f"tags: [{', '.join(nota.tags)}]",
            f"origen: {nota.origen}",
            f"created: {nota.created_at.isoformat()}",
            "---",
            "",
        ]
        content = "\n".join(frontmatter) + nota.contenido

        filepath.write_text(content, encoding="utf-8")

        # Actualizar la ruta en la nota
        nota.obsidian_path = str(filepath.relative_to(self._vault_path))

        logger.info("Nota escrita en vault: %s", filepath)
        return filepath

    async def leer_nota(self, ruta_relativa: str) -> str:
        """Lee el contenido de un archivo .md del vault."""
        filepath = self._vault_path / ruta_relativa
        if not filepath.exists():
            raise FileNotFoundError(f"Nota no encontrada: {filepath}")
        return filepath.read_text(encoding="utf-8")

    async def listar_notas(self, directorio: str = "") -> list[str]:
        """Lista todas las notas (.md) en un directorio del vault."""
        search_path = self._vault_path / directorio if directorio else self._vault_path
        if not search_path.exists():
            return []

        return [
            str(p.relative_to(self._vault_path))
            for p in search_path.rglob("*.md")
            if not p.name.startswith(".")
        ]

    async def buscar_notas(self, query: str) -> list[str]:
        """Busca notas cuyo nombre o contenido contenga la query."""
        resultados = []
        query_lower = query.lower()

        for md_file in self._vault_path.rglob("*.md"):
            if md_file.name.startswith("."):
                continue

            # Buscar en el nombre del archivo
            if query_lower in md_file.stem.lower():
                resultados.append(str(md_file.relative_to(self._vault_path)))
                continue

            # Buscar en el contenido
            try:
                contenido = md_file.read_text(encoding="utf-8").lower()
                if query_lower in contenido:
                    resultados.append(str(md_file.relative_to(self._vault_path)))
            except (UnicodeDecodeError, PermissionError):
                continue

        return resultados

    async def eliminar_nota(self, ruta_relativa: str) -> bool:
        """Elimina un archivo .md del vault."""
        filepath = self._vault_path / ruta_relativa
        if filepath.exists():
            filepath.unlink()
            logger.info("Nota eliminada: %s", filepath)
            return True
        return False

    async def health_check(self) -> bool:
        """Verifica que el vault exista y sea accesible."""
        return self._vault_path.exists() and self._vault_path.is_dir()
