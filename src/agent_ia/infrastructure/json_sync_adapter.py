"""Adaptador de persistencia JSON para el estado de sincronización (Fase 3).

Implementa `SyncPort` guardando el historial de eventos, marcas de tiempo y
hashes de contenido en `data/sync_state.json`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent_ia.domain.ports.sync_port import SyncPort


class JsonSyncAdapter(SyncPort):
    """Adaptador de estado de sincronización con almacenamiento JSON local."""

    def __init__(self, file_path: Path | str = "data/sync_state.json") -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._guardar_datos_raw({"hashes": {}, "historial": [], "ultimo_sync": None})

    def _leer_datos_raw(self) -> dict:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"hashes": {}, "historial": [], "ultimo_sync": None}

    def _guardar_datos_raw(self, datos: dict) -> None:
        temp_file = self.file_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        temp_file.replace(self.file_path)

    def obtener_estado(self) -> dict:
        return self._leer_datos_raw()

    def guardar_estado(self, estado: dict) -> None:
        self._guardar_datos_raw(estado)

    def registrar_evento(
        self, origen: str, destino: str, entidad: str, accion: str, detalles: dict | None = None
    ) -> None:
        datos = self._leer_datos_raw()
        ahora_iso = datetime.now(timezone.utc).isoformat()
        evento = {
            "timestamp": ahora_iso,
            "origen": origen,
            "destino": destino,
            "entidad": entidad,
            "accion": accion,
            "detalles": detalles or {},
        }
        historial = datos.get("historial", [])
        historial.append(evento)
        if len(historial) > 100:
            historial = historial[-100:]
        datos["historial"] = historial
        datos["ultimo_sync"] = ahora_iso
        self._guardar_datos_raw(datos)

    def obtener_hash(self, clave: str) -> str | None:
        datos = self._leer_datos_raw()
        return datos.get("hashes", {}).get(clave)

    def actualizar_hash(self, clave: str, hash_valor: str) -> None:
        datos = self._leer_datos_raw()
        hashes = datos.get("hashes", {})
        hashes[clave] = hash_valor
        datos["hashes"] = hashes
        self._guardar_datos_raw(datos)
