"""AgentePlan — planificación y gestión de tareas y metas.

Será responsable de:
- Creación de tareas rápidas en Notion (vía comandos)
- Planificación estratégica conversacional (crea Objetivos, Proyectos y Tareas)
- Propone planes y espera confirmación antes de impactar el Segundo Cerebro
"""

from __future__ import annotations

import json
import logging
import uuid
import re

from agent_ia.use_cases.agente import Agente, EstadoResultado, Resultado
from agent_ia.domain.ports.llm_port import LLMPort
from agent_ia.domain.ports.notion_port import NotionPort

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_ESTRATEGA = """Eres el AgentePlan de Agent IA, el estratega senior de metas, productividad y proyectos de Miguel.

Tu misión es transformar ambiciones y metas en planes realistas, estructurados y de alto impacto.

Directrices de razonamiento:
1. Contexto y memoria: Conoces los objetivos que Miguel ya tiene en su Segundo Cerebro (Notion) y recuerdas la conversación reciente.
2. Si Miguel pide un plan de acción, priorización o estrategia para metas ya existentes o múltiples objetivos:
   - Actúa como un asesor estratégico: evita la sobrecarga cognitiva de hacer 7 cosas a la vez.
   - Agrupa en Fases cronológicas de ejecución (ej. Fase 1: Victorias Rápidas, Fase 2: Enfoque Académico/Profesional, Fase 3: Hábitos y Consistencia).
   - Detalla prioridades inmediatas, métricas de éxito y próximos pasos accionables.
   - Responde en Markdown estructurado, fluido y profesional.
3. Si Miguel pide planificar una META NUEVA o proyecto específico para guardarlo en Notion:
   - Desglósalo en 1 Objetivo, 1-3 Proyectos y Tareas concretas respondiendo en JSON:
   {
       "objetivo": {
           "titulo": "Nombre del objetivo",
           "area": "Área sugerida"
       },
       "proyectos": [
           {
               "titulo": "Nombre del proyecto",
               "tareas": ["Tarea 1", "Tarea 2"]
           }
       ],
       "razon": "Explicación estratégica"
   }
"""

SYSTEM_PROMPT_PLAN_CONSULTA = """Eres el AgentePlan de Agent IA, el estratega personal de metas y proyectos de Miguel.
Tu objetivo es presentar de forma clara, motivadora, elegante y bien estructurada los objetivos, proyectos y metas que Miguel tiene en su Segundo Cerebro (Notion).
Habla con tono proactivo, fluido y conversacional.
"""


SYSTEM_PROMPT_UPDATE_OBJETIVOS = """Eres el AgentePlan de Agent IA.
Miguel quiere actualizar propiedades reales de sus objetivos en Notion (ej. asignar fechas límite / Deadline para activar el Countdown, cambiar Status, etc.).

Hoy es {fecha_hoy}.
Dado el listado de objetivos de Miguel y su instrucción:
1. Calcula la fecha exacta en formato ISO "YYYY-MM-DD" para cada objetivo según los días o meses solicitados (sumando los días a la fecha de hoy {fecha_hoy}).
2. Opcionalmente asigna el Status ("No empezado", "En progreso", "Completado") si aplica.

Responde SIEMPRE en JSON con esta estructura exacta:
{
    "actualizaciones": [
        {
            "id": "id_del_objetivo",
            "titulo": "titulo corto del objetivo",
            "deadline": "YYYY-MM-DD",
            "dias_countdown": 30,
            "status": "En progreso|No empezado|null"
        }
    ],
    "resumen": "Breve explicación de los plazos calculados e impactados en Notion."
}
"""


class AgentePlan(Agente):
    """AgentePlan — planificación y gestión estratégica en Notion."""

    def __init__(self, llm: LLMPort, notion: NotionPort) -> None:
        super().__init__(nombre="AgentePlan", dominio="Tarea, Proyecto, Objetivo")
        self._llm = llm
        self._notion = notion
        self._propuestas_pendientes: dict[str, dict] = {}

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        ctx = contexto or {}
        instruccion_lower = instruccion.strip().lower()

        # 1. ¿Es una confirmación de un plan pendiente?
        if ctx.get("confirmar_propuesta"):
            return await self._aplicar_propuesta(ctx["confirmar_propuesta"])

        # 2. ¿Es una solicitud de ACTUALIZACIÓN / CRUD de propiedades (ej. countdown, deadline, fechas, status)?
        # e.g. "actualizale el countdown", "ponle fecha limite", "asigna deadlines", "actualiza el status"
        es_mutacion_propiedades = bool(
            re.search(r'\b(actualiza(r|le)?|asigna(r|le)?|pon(er|le)?|cambia(r|le)?|agrega(r|le)?)\b.*\b(countdown|deadline|fecha|plazo|status|estado)\b', instruccion_lower)
        )
        if es_mutacion_propiedades:
            return await self._mutar_propiedades_objetivos(instruccion, contexto=ctx)

        # 3. ¿Es una consulta simple de listado de objetivos / metas existentes?
        es_consulta_simple = bool(
            re.match(r'^(mira|ver|mostrar|cu[aá]les son|qu[eé] (tengo|hay)|lista(r)?|dime|consultar)\b.*\b(objetivos|metas|proyectos|planes)\b', instruccion_lower)
        )

        if es_consulta_simple:
            return await self._consultar_objetivos_y_metas(instruccion)

        # 4. ¿Es una creación rápida de tarea? (Fast-path sin LLM)
        if re.match(r'^(agrega(r)? (una )?tarea|tarea:|recu[eé]rdame que|a[ñn]ade)', instruccion_lower):
            return await self._creacion_rapida_tarea(instruccion)

        # 5. Planificación y estrategia con LLM (con contexto de metas e historial)
        return await self._proponer_plan_estrategico(instruccion, contexto=ctx)

    async def _mutar_propiedades_objetivos(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        """Calcula y aplica mutaciones CRUD directas a las páginas de Notion (ej. Deadlines para activar Countdowns)."""
        from datetime import date
        hoy_str = date.today().isoformat()

        objetivos = []
        try:
            if hasattr(self._notion, "listar_objetivos"):
                objetivos = await self._notion.listar_objetivos()
        except Exception as e:
            logger.warning("Error consultando Notion para mutar objetivos: %s", e)

        if not objetivos:
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje="No encontré objetivos activos en Notion para actualizar.",
                agente=self.nombre,
            )

        contexto_notion = "Objetivos actuales en Notion:\n" + "\n".join(
            f"- ID: `{o['id']}` | Título: {o['titulo']}" for o in objetivos
        )

        # Extraer historial reciente
        ctx = contexto or {}
        historial = ctx.get("historial", [])
        lineas_hist = []
        if isinstance(historial, list):
            for m in historial[-6:]:
                rol = getattr(m, "role", "") or (m.get("role", "") if isinstance(m, dict) else "")
                contenido = getattr(m, "content", "") or (m.get("content", "") if isinstance(m, dict) else "")
                lineas_hist.append(f"{rol}: {contenido}")
        hist_str = "\n".join(lineas_hist) if lineas_hist else ""

        prompt = (
            f"{contexto_notion}\n\n"
            f"Historial reciente del plan conversado:\n{hist_str}\n\n"
            f"Solicitud de Miguel:\n'{instruccion}'\n\n"
            f"Determina el JSON de actualizaciones exactas con fecha ISO (YYYY-MM-DD):"
        )

        system_prompt = SYSTEM_PROMPT_UPDATE_OBJETIVOS.replace("{fecha_hoy}", hoy_str)

        response = await self._llm.generate(
            prompt=prompt,
            system=system_prompt,
            temperature=0.2,
        )

        try:
            # Parsear JSON de actualizaciones
            raw = response.content
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(1)
            elif not raw.strip().startswith("{"):
                brace_match = re.search(r'(\{[\s\S]*"actualizaciones"[\s\S]*\})', raw)
                if brace_match:
                    raw = brace_match.group(1)

            data = json.loads(raw)
            actualizaciones = data.get("actualizaciones", [])
        except Exception as e:
            logger.warning("Error parseando mutaciones de objetivos: %s (content: %s)", e, response.content[:150])
            actualizaciones = []

        if not actualizaciones:
            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=response.content,
                agente=self.nombre,
            )

        # Ejecutar mutaciones reales en la API de Notion
        exitos = 0
        lineas_resumen = []
        for act in actualizaciones:
            page_id = act.get("id")
            deadline = act.get("deadline")
            status = act.get("status") if act.get("status") != "null" else None
            titulo = act.get("titulo", "Objetivo")

            if not page_id:
                # Buscar por match aproximado de título
                for o in objetivos:
                    if o["titulo"].lower().startswith(titulo.lower()[:20]):
                        page_id = o["id"]
                        break

            if page_id and (deadline or status):
                try:
                    await self._notion.actualizar_objetivo(
                        page_id=page_id,
                        deadline=deadline,
                        status=status,
                    )
                    exitos += 1
                    countdown_dias = act.get("dias_countdown", "")
                    cd_txt = f" (Countdown: ~{countdown_dias} días)" if countdown_dias else ""
                    lineas_resumen.append(f"• **{titulo[:60]}...** $\\rightarrow$ Deadline: `{deadline}`{cd_txt}")
                except Exception as e:
                    logger.warning("Error al actualizar objetivo %s: %s", page_id, e)

        mensaje_final = (
            f"⚡ **Propiedades actualizadas directamente en Notion ({exitos}/{len(actualizaciones)} objetivos):**\n\n"
            + "\n".join(lineas_resumen)
            + "\n\n✨ *Las fórmulas de `Countdown` y `Quarter` en tus tarjetas de Notion se han recalculado automáticamente.*"
        )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=mensaje_final,
            datos={"actualizados": exitos, "detalles": actualizaciones},
            agente=self.nombre,
        )

    async def _consultar_objetivos_y_metas(self, instruccion: str) -> Resultado:
        """Consulta los objetivos y proyectos registrados en Notion y los resume conversacionalmente."""
        try:
            objetivos = await self._notion.listar_objetivos() if hasattr(self._notion, "listar_objetivos") else []
            proyectos = await self._notion.listar_proyectos() if hasattr(self._notion, "listar_proyectos") else []
        except Exception as e:
            logger.warning("Error consultando Notion para objetivos: %s", e)
            objetivos, proyectos = [], []

        if not objetivos and not proyectos:
            mensaje = (
                "🎯 **Tus Objetivos en el Segundo Cerebro:**\n\n"
                "Actualmente no tienes objetivos activos registrados en tu base de Notion.\n\n"
                "💡 *¿Te gustaría que diseñemos un plan estratégico para alguna meta académica o personal?* "
                "Solo dime, por ejemplo: *'Quiero preparar mi examen de Redes'* o *'Crear un plan para dominar Rust'*."
            )
            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=mensaje,
                datos={"objetivos": [], "proyectos": []},
                agente=self.nombre,
            )

        contexto_notion = "Objetivos registrados en Notion:\n" + "\n".join(
            f"- 🎯 {o['titulo']} (Área: {o.get('area', 'General')})" for o in objetivos
        )
        if proyectos:
            contexto_notion += "\n\nProyectos activos vinculados:\n" + "\n".join(
                f"- 📁 {p['titulo']}" for p in proyectos
            )

        prompt = (
            f"{contexto_notion}\n\n"
            f"Pregunta de Miguel: {instruccion}\n\n"
            f"Presenta a Miguel sus objetivos y proyectos de forma clara, motivadora y estructurada:"
        )

        try:
            response = await self._llm.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT_PLAN_CONSULTA,
                temperature=0.3,
            )
            mensaje = response.content
        except Exception:
            mensaje = "🎯 **Tus Objetivos en el Segundo Cerebro:**\n\n" + "\n".join(
                f"• **{o['titulo']}** (Área: `{o.get('area', 'General')}`)" for o in objetivos
            )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=mensaje,
            datos={"objetivos": objetivos, "proyectos": proyectos},
            agente=self.nombre,
        )

    async def _creacion_rapida_tarea(self, instruccion: str) -> Resultado:
        """Modo antiguo: crea una tarea directamente usando regex/parsing simple."""
        titulo = instruccion.strip()
        prefijos = [
            "agrega una tarea en mi notion", "agrega una tarea", "agrega la tarea",
            "tarea:", "recuérdame que", "recuerdame que", "añade",
        ]

        for p in prefijos:
            if titulo.lower().startswith(p):
                titulo = titulo[len(p):].strip()
                break

        if titulo.startswith(":") or titulo.startswith("que"):
            titulo = titulo[1:].strip()

        if not titulo:
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje="Por favor indícame cuál es la tarea que quieres agregar.",
                agente=self.nombre,
            )

        try:
            page_id = await self._notion.crear_tarea(titulo=titulo, relaciones=None)
            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=f"Tarea agregada exitosamente a Notion\n'{titulo}'",
                datos={"notion_page_id": page_id},
                agente=self.nombre,
            )
        except Exception as e:
            logger.exception("Error agregando tarea a Notion")
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje=f"Ocurrió un error al intentar guardar la tarea en Notion:\n{e}",
                agente=self.nombre,
            )

    async def _proponer_plan_estrategico(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        """Usa el LLM con memoria conversacional y objetivos existentes para elaborar una estrategia."""
        logger.info("AgentePlan iniciando planificación estratégica...")
        ctx = contexto or {}

        # 1. Recuperar objetivos existentes de Notion para contexto
        objetivos = []
        try:
            if hasattr(self._notion, "listar_objetivos"):
                objetivos = await self._notion.listar_objetivos()
        except Exception:
            pass

        # 2. Extraer historial reciente si está disponible
        historial = ctx.get("historial", [])
        lineas_historial = []
        if isinstance(historial, list):
            for m in historial[-6:]:
                rol = getattr(m, "role", "") or (m.get("role", "") if isinstance(m, dict) else "")
                contenido = getattr(m, "content", "") or (m.get("content", "") if isinstance(m, dict) else "")
                autor = "Miguel" if rol == "user" else "AgentePlan"
                lineas_historial.append(f"{autor}: {contenido}")
        contexto_historial = "\n".join(lineas_historial) if lineas_historial else ""

        bloque_objetivos = (
            "\n".join(f"- 🎯 {o['titulo']} (Área: {o.get('area', 'General')})" for o in objetivos)
            if objetivos
            else "Sin objetivos previos registrados."
        )

        prompt = (
            f"Objetivos actualmente registrados en el Segundo Cerebro de Miguel:\n{bloque_objetivos}\n\n"
            f"Historial reciente del diálogo:\n{contexto_historial}\n\n"
            f"Petición actual de Miguel:\n'{instruccion}'\n\n"
            f"Elabora el plan estratégico o respuesta correspondiente:"
        )

        response = await self._llm.generate(
            prompt=prompt,
            system=SYSTEM_PROMPT_ESTRATEGA,
            temperature=0.4,
        )

        # 3. Intentar extraer JSON si el LLM generó una propuesta estructurada de creación para Notion
        plan = None
        try:
            plan = json.loads(response.content)
        except Exception:
            # Buscar bloque JSON dentro de markdown o llaves
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response.content, re.DOTALL)
            if json_match:
                try:
                    plan = json.loads(json_match.group(1))
                except Exception:
                    pass
            if not plan:
                brace_match = re.search(r'(\{[\s\S]*"objetivo"[\s\S]*\})', response.content)
                if brace_match:
                    try:
                        plan = json.loads(brace_match.group(1))
                    except Exception:
                        pass

        # Si es un plan JSON estructurado para persistir en Notion (1 objetivo + proyectos)
        if plan and isinstance(plan, dict) and "objetivo" in plan and isinstance(plan["objetivo"], dict):
            propuesta_id = str(uuid.uuid4())[:8]
            self._propuestas_pendientes[propuesta_id] = plan

            obj_tit = plan.get("objetivo", {}).get("titulo", "Nuevo Objetivo")
            obj_area = plan.get("objetivo", {}).get("area", "Universidad")

            mensaje = f"💡 **Propuesta de Plan Estratégico para Notion:**\n\n"
            mensaje += f"*{plan.get('razon', 'Vamos a estructurar esta meta.')}*\n\n"
            mensaje += f"🎯 **Objetivo:** {obj_tit} (Área: `{obj_area}`)\n"

            for p in plan.get("proyectos", []):
                mensaje += f"\n📁 **Proyecto:** {p.get('titulo')}\n"
                for t in p.get("tareas", []):
                    mensaje += f"  - [ ] {t}\n"

            mensaje += "\n¿Quieres que implemente este plan en tu Segundo Cerebro? (Responde 'sí' para confirmar)."

            return Resultado(
                estado=EstadoResultado.REQUIERE_CONFIRMACION,
                mensaje=mensaje,
                accion_pendiente=propuesta_id,
                agente=self.nombre,
            )

        # Si el LLM devolvió una hoja de ruta o análisis estratégico conversacional en Markdown:
        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=response.content,
            agente=self.nombre,
        )

    async def _aplicar_propuesta(self, propuesta_id: str) -> Resultado:
        """Aplica un plan estratégico previamente generado insertándolo en Notion."""
        plan = self._propuestas_pendientes.get(propuesta_id)
        if not plan:
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje="La propuesta expiró o no existe. Por favor, solicítala de nuevo.",
                agente=self.nombre,
            )

        try:
            obj_info = plan.get("objetivo", {})
            obj_tit = obj_info.get("titulo", "Objetivo sin título")
            area = obj_info.get("area")
            
            # 1. Crear el Objetivo
            rel_obj = {"Area": area} if area else None
            obj_id = await self._notion.crear_objetivo(titulo=obj_tit, relaciones=rel_obj)

            # 2. Crear los Proyectos y sus Tareas
            resumen_creados = []
            
            for p in plan.get("proyectos", []):
                proj_tit = p.get("titulo", "Proyecto sin título")
                # Relacionamos el proyecto con el objetivo recién creado
                rel_proj = {"Objetivo": obj_tit}
                if area:
                    rel_proj["Area"] = area
                    
                await self._notion.crear_proyecto(titulo=proj_tit, relaciones=rel_proj)
                resumen_creados.append(f"📁 {proj_tit}")
                
                # 3. Crear las tareas del proyecto
                for t in p.get("tareas", []):
                    # Relacionamos la tarea con el proyecto recién creado
                    rel_tarea = {"Proyecto": proj_tit}
                    if area:
                        rel_tarea["Area"] = area
                        
                    await self._notion.crear_tarea(titulo=t, relaciones=rel_tarea)
                    resumen_creados.append(f"  - {t}")

            del self._propuestas_pendientes[propuesta_id]

            mensaje_final = "✅ **¡Plan implementado en Notion con éxito!**\n\n"
            mensaje_final += f"🎯 **Objetivo:** {obj_tit}\n" + "\n".join(resumen_creados)

            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=mensaje_final,
                agente=self.nombre,
            )
            
        except Exception as e:
            logger.exception("Error aplicando plan estratégico en Notion")
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje=f"Error al implementar el plan en Notion: {e}",
                agente=self.nombre,
            )
