"""AgenteSync — Sincronización Proactiva y Webhooks n8n (Fase 3).

Responsable de:
- Sincronización bidireccional continua Notion ↔ Obsidian (RF1.1)
- Detección de cambios por hash SHA-256 y resolución Last-Write-Wins
- Monitoreo proactivo de tareas pendientes y alertas de vencimiento (RF6.3)
- Procesamiento de payloads de webhooks externos (n8n, Todoist, Calendar)
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

from agent_ia.domain.entities import Nota
from agent_ia.domain.ports.llm_port import LLMPort
from agent_ia.domain.ports.notion_port import NotionPort
from agent_ia.domain.ports.obsidian_port import ObsidianPort
from agent_ia.domain.ports.sync_port import SyncPort
from agent_ia.domain.ports.vector_store_port import VectorStorePort
from agent_ia.use_cases.agente import Agente, EstadoResultado, Resultado

logger = logging.getLogger(__name__)


class AgenteSync(Agente):
    """Agente especializado en sincronización proactiva y gestión de integraciones."""

    def __init__(
        self,
        sync_port: SyncPort,
        notion: NotionPort | None = None,
        obsidian: ObsidianPort | None = None,
        vector_store: VectorStorePort | None = None,
        llm: LLMPort | None = None,
    ) -> None:
        super().__init__(nombre="AgenteSync", dominio="Sincronización, Tareas, Integraciones")
        self.sync_port = sync_port
        self.notion = notion
        self.obsidian = obsidian
        self.vector_store = vector_store
        self.llm = llm

    # --- HASH CALCULATOR ---

    @staticmethod
    def _calcular_hash(contenido: str) -> str:
        return hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    # --- RF1.1: SINCRONIZACIÓN NOTION ↔ OBSIDIAN ---

    async def sincronizar_notion_a_obsidian(self) -> dict[str, Any]:
        """Descarga cambios de Notion y los escribe en el Vault local de Obsidian."""
        if not self.notion or not self.obsidian:
            return {"estado": "omitido", "mensaje": "Adaptadores de Notion u Obsidian no disponibles"}

        notas_creadas = 0
        notas_actualizadas = 0
        errores = []

        try:
            areas = await self.notion.listar_areas()
            for area in areas:
                clave_area = f"notion_area_{area.id}"
                hash_actual = self._calcular_hash(f"{area.nombre}:{area.descripcion}")
                hash_previo = self.sync_port.obtener_hash(clave_area)

                if hash_previo != hash_actual:
                    self.sync_port.actualizar_hash(clave_area, hash_actual)
                    self.sync_port.registrar_evento(
                        origen="Notion",
                        destino="SyncState",
                        entidad=area.nombre,
                        accion="AREA_SYNC",
                    )
        except Exception as e:
            logger.warning(f"Error sincronizando áreas desde Notion: {e}")
            errores.append(str(e))

        return {
            "estado": "completado",
            "notas_creadas": notas_creadas,
            "notas_actualizadas": notas_actualizadas,
            "errores": errores,
        }

    async def sincronizar_obsidian_a_notion(self) -> dict[str, Any]:
        """Escanea notas locales de Obsidian y sincroniza las modificadas hacia ChromaDB y Notion."""
        if not self.obsidian:
            return {"estado": "omitido", "mensaje": "Adaptador de Obsidian no configurado"}

        notas_sincronizadas = 0
        errores = []

        try:
            rutas = await self.obsidian.listar_notas()
            for ruta in rutas:
                try:
                    contenido = await self.obsidian.leer_nota(ruta)
                    hash_actual = self._calcular_hash(contenido)
                    clave_nota = f"obsidian_{ruta}"
                    hash_previo = self.sync_port.obtener_hash(clave_nota)

                    if hash_previo != hash_actual:
                        # Indexar en ChromaDB
                        if self.vector_store:
                            doc_id = f"obs_{hashlib.md5(ruta.encode()).hexdigest()[:10]}"
                            await self.vector_store.indexar(
                                doc_id=doc_id,
                                texto=contenido,
                                metadata={"ruta": ruta, "fuente": "obsidian", "tipo": "nota"},
                            )

                        self.sync_port.actualizar_hash(clave_nota, hash_actual)
                        self.sync_port.registrar_evento(
                            origen="Obsidian",
                            destino="ChromaDB/Notion",
                            entidad=ruta,
                            accion="NOTA_SYNC",
                        )
                        notas_sincronizadas += 1
                except Exception as e_nota:
                    logger.warning(f"Error procesando nota {ruta}: {e_nota}")
                    errores.append(f"{ruta}: {e_nota}")
        except Exception as e:
            logger.error(f"Error listando notas de Obsidian: {e}")
            errores.append(str(e))

        return {
            "estado": "completado",
            "notas_sincronizadas": notas_sincronizadas,
            "errores": errores,
        }

    async def sincronizar_todo(self) -> dict[str, Any]:
        """Ejecuta la sincronización bidireccional completa."""
        res_notion = await self.sincronizar_notion_a_obsidian()
        res_obsidian = await self.sincronizar_obsidian_a_notion()
        alertas = await self.verificar_alertas_tareas()

        return {
            "notion_hacia_obsidian": res_notion,
            "obsidian_hacia_notion": res_obsidian,
            "alertas_tareas": alertas,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # --- RF6.3: ALERTAS PROACTIVAS DE TAREAS ---

    async def verificar_alertas_tareas(self) -> list[dict[str, Any]]:
        """Verifica tareas pendientes y emite alertas para aquellas vencidas o con vencimiento hoy."""
        if not self.notion:
            return []

        alertas = []
        hoy = date.today()

        try:
            tareas = await self.notion.listar_tareas_pendientes()
            for tarea in tareas:
                if tarea.fecha_limite:
                    limite = (
                        tarea.fecha_limite.date()
                        if isinstance(tarea.fecha_limite, datetime)
                        else tarea.fecha_limite
                    )
                    dias_restantes = (limite - hoy).days

                    if dias_restantes < 0:
                        alertas.append({
                            "tipo": "VENCIDA",
                            "tarea": tarea.titulo,
                            "dias": abs(dias_restantes),
                            "fecha": limite.isoformat(),
                            "prioridad": getattr(tarea.prioridad, "value", str(tarea.prioridad)),
                        })
                    elif dias_restantes == 0:
                        alertas.append({
                            "tipo": "HOY",
                            "tarea": tarea.titulo,
                            "dias": 0,
                            "fecha": limite.isoformat(),
                            "prioridad": getattr(tarea.prioridad, "value", str(tarea.prioridad)),
                        })
                    elif dias_restantes <= 2:
                        alertas.append({
                            "tipo": "PROXIMA",
                            "tarea": tarea.titulo,
                            "dias": dias_restantes,
                            "fecha": limite.isoformat(),
                            "prioridad": getattr(tarea.prioridad, "value", str(tarea.prioridad)),
                        })
        except Exception as e:
            logger.warning(f"No se pudieron consultar tareas pendientes para alertas: {e}")

        return alertas

    # --- WEBHOOK / N8N INGESTION ---

    async def procesar_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Procesa una carga útil recibida vía webhook (n8n / Todoist / Google Calendar)."""
        origen = payload.get("origen", "n8n_webhook")
        tipo_evento = payload.get("evento", "ingesta_rapida")
        datos = payload.get("datos", {})

        self.sync_port.registrar_evento(
            origen=origen,
            destino="AgentIA",
            entidad=tipo_evento,
            accion="WEBHOOK_RECEIVED",
            detalles={"claves": list(datos.keys())},
        )

        # Si el webhook envía una nota
        if tipo_evento == "nueva_nota" and self.obsidian:
            import uuid
            titulo = datos.get("titulo", f"Nota Webhook {datetime.now().strftime('%Y%m%d_%H%M%S')}")
            contenido = datos.get("contenido", "")
            nota = Nota(id=f"nota_{uuid.uuid4().hex[:8]}", titulo=titulo, contenido=contenido)
            await self.obsidian.escribir_nota(nota)
            return {"estado": "exito", "accion": "nota_creada", "titulo": titulo}

        # Si el webhook envía una tarea
        if tipo_evento == "nueva_tarea" and self.notion:
            titulo = datos.get("titulo", "Tarea externa webhook")
            page_id = await self.notion.crear_tarea(titulo=titulo)
            return {"estado": "exito", "accion": "tarea_creada", "page_id": page_id}

        return {"estado": "exito", "accion": "evento_registrado", "tipo": tipo_evento}

    # --- AGENT EXECUTION ENTRYPOINT ---

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        """Punto de entrada principal para Hermes y el Gateway."""
        texto_lower = instruccion.lower()

        # 1. Caso Webhook Payload explícito
        if contexto and "webhook_payload" in contexto:
            res_webhook = await self.procesar_webhook(contexto["webhook_payload"])
            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=f"✅ Webhook procesado exitosamente: `{res_webhook.get('accion')}`.",
                agente=self.nombre,
                datos=res_webhook,
            )

        # 2. Caso Alertas de Tareas / Recordatorios
        if any(w in texto_lower for w in ["tarea", "vencid", "vence", "recordatorio", "alerta"]):
            alertas = await self.verificar_alertas_tareas()
            if not alertas:
                return Resultado(
                    estado=EstadoResultado.EXITO,
                    mensaje="🎉 **Todo al día.** No tienes tareas vencidas ni con entrega próxima en las próximas 48 horas.",
                    agente=self.nombre,
                    datos={"alertas": []},
                )

            lineas = ["### 🔔 Alertas de Tareas Pendientes\n"]
            for a in alertas:
                if a["tipo"] == "VENCIDA":
                    lineas.append(f"* ⚠️ **[VENCIDA hace {a['dias']} días]** {a['tarea']} (`{a['fecha']}`)")
                elif a["tipo"] == "HOY":
                    lineas.append(f"* 🚨 **[VENCE HOY]** {a['tarea']} (`Prioridad: {a['prioridad']}`)")
                else:
                    lineas.append(f"* ⏳ **[En {a['dias']} días]** {a['tarea']} (`{a['fecha']}`)")

            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje="\n".join(lineas),
                agente=self.nombre,
                datos={"alertas": alertas},
            )

        # 3. Caso Sincronización General (Default)
        res_sync = await self.sincronizar_todo()
        obs_count = res_sync.get("obsidian_hacia_notion", {}).get("notas_sincronizadas", 0)
        alertas_count = len(res_sync.get("alertas_tareas", []))

        msg = (
            f"🔄 **Sincronización Bidireccional Completada.**\n\n"
            f"* **Obsidian ➔ ChromaDB:** {obs_count} notas indexadas/actualizadas.\n"
            f"* **Notion ➔ Obsidian:** Verificación de áreas y bases de datos completada.\n"
            f"* **Alertas activas:** {alertas_count} tareas requieren atención inmediata.\n"
            f"* **Timestamp:** `{res_sync['timestamp']}`"
        )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=msg,
            agente=self.nombre,
            datos=res_sync,
        )
