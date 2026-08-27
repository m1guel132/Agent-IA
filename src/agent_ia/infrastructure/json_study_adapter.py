"""Adaptador de persistencia JSON para StudyBoard — implementación de StudyPort.

Almacena las tarjetas de estudio e items SM-2 en un archivo JSON local (data/study_board.json).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from agent_ia.domain.entities.item_estudio import ItemEstudio
from agent_ia.domain.ports.study_port import StudyPort

logger = logging.getLogger(__name__)


class JsonStudyAdapter(StudyPort):
    """Adaptador concreto para persistir tarjetas de estudio en disco."""

    def __init__(self, file_path: Path | str = "./data/study_board.json") -> None:
        self._file_path = Path(file_path)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists():
            self._guardar_datos({})

    def _cargar_datos(self) -> dict[str, dict]:
        """Carga el diccionario de tarjetas desde el archivo JSON."""
        try:
            if not self._file_path.exists():
                return {}
            content = self._file_path.read_text(encoding="utf-8")
            if not content.strip():
                return {}
            return json.loads(content)
        except Exception as e:
            logger.error("Error al leer %s: %s", self._file_path, e)
            return {}

    def _guardar_datos(self, datos: dict[str, dict]) -> None:
        """Escribe el diccionario de tarjetas en el archivo JSON."""
        try:
            content = json.dumps(datos, indent=2, ensure_ascii=False)
            self._file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error("Error al guardar %s: %s", self._file_path, e)

    def _serializar_item(self, item: ItemEstudio) -> dict:
        """Convierte una entidad ItemEstudio a un diccionario serializable."""
        return {
            "id": item.id,
            "nota_id": item.nota_id,
            "pregunta": item.pregunta,
            "respuesta": item.respuesta,
            "facilidad": item.facilidad,
            "intervalo": item.intervalo,
            "repeticiones": item.repeticiones,
            "sig_repaso": item.sig_repaso.isoformat(),
            "created_at": item.created_at.isoformat(),
        }

    def _deserializar_item(self, data: dict) -> ItemEstudio:
        """Construye una entidad ItemEstudio desde un diccionario."""
        return ItemEstudio(
            id=data["id"],
            nota_id=data.get("nota_id", ""),
            pregunta=data.get("pregunta", ""),
            respuesta=data.get("respuesta", ""),
            facilidad=float(data.get("facilidad", 2.5)),
            intervalo=int(data.get("intervalo", 1)),
            repeticiones=int(data.get("repeticiones", 0)),
            sig_repaso=date.fromisoformat(data["sig_repaso"]) if "sig_repaso" in data else date.today(),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )

    async def guardar_tarjeta(self, item: ItemEstudio) -> None:
        """Guarda o actualiza una tarjeta."""
        datos = self._cargar_datos()
        datos[item.id] = self._serializar_item(item)
        self._guardar_datos(datos)
        logger.debug("Tarjeta guardada: %s", item.id)

    async def obtener_tarjeta(self, item_id: str) -> ItemEstudio | None:
        """Obtiene una tarjeta por ID."""
        datos = self._cargar_datos()
        data = datos.get(item_id)
        if not data:
            return None
        return self._deserializar_item(data)

    async def listar_pendientes(self, fecha: date | None = None) -> list[ItemEstudio]:
        """Lista tarjetas cuyo próximo repaso sea <= fecha (hoy por defecto)."""
        limite = fecha or date.today()
        todas = await self.listar_todas()
        return [item for item in todas if item.sig_repaso <= limite]

    async def listar_todas(self) -> list[ItemEstudio]:
        """Lista todas las tarjetas."""
        datos = self._cargar_datos()
        return [self._deserializar_item(d) for d in datos.values()]

    async def eliminar_tarjeta(self, item_id: str) -> bool:
        """Elimina una tarjeta del almacenamiento."""
        datos = self._cargar_datos()
        if item_id in datos:
            del datos[item_id]
            self._guardar_datos(datos)
            return True
        return False
