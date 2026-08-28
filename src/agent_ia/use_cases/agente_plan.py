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

SYSTEM_PROMPT_ESTRATEGA = """Eres el AgentePlan de Agent IA, el estratega personal de Miguel.
Miguel quiere lograr una meta, mejorar en algún aspecto académico/personal, o planificar un proyecto complejo.

Tu objetivo es desglosar su meta en un plan estructurado para su Segundo Cerebro en Notion.
Debes proponer exactamente:
1. UN Objetivo principal.
2. UNO O VARIOS Proyectos necesarios para alcanzar ese objetivo.
3. VARIAS Tareas accionables asignadas a cada proyecto.

Responde SIEMPRE en JSON con esta estructura exacta:
{
    "objetivo": {
        "titulo": "Nombre del objetivo (ej. Aprobar Física Electromagnética)",
        "area": "Nombre del área sugerida (ej. Universidad)"
    },
    "proyectos": [
        {
            "titulo": "Nombre del proyecto",
            "tareas": ["Tarea 1", "Tarea 2"]
        }
    ],
    "razon": "Breve explicación motivadora de por qué este plan le ayudará a lograr su meta."
}
"""

SYSTEM_PROMPT_PLAN_CONSULTA = """Eres el AgentePlan de Agent IA, el estratega personal de metas y proyectos de Miguel.
Tu objetivo es presentar de forma clara, motivadora, elegante y bien estructurada los objetivos, proyectos y metas que Miguel tiene en su Segundo Cerebro (Notion).
Habla con tono proactivo, fluido y conversacional.
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

        # 2. ¿Es una consulta de objetivos / metas / proyectos existentes?
        # e.g. "mira mis objetivos", "cuáles son mis metas", "qué metas tengo", "lista mis proyectos"
        es_consulta_objetivos = bool(
            re.search(r'\b(mira|ver|mostrar|cu[aá]les son|qu[eé] (tengo|hay)|lista(r)?|dime|consultar)\b.*\b(objetivos|metas|proyectos|planes)\b', instruccion_lower)
        ) or ("objetivos" in instruccion_lower and not re.search(r'\b(crea|agrega|nuevo|planifica|diseña)\b', instruccion_lower))

        if es_consulta_objetivos:
            return await self._consultar_objetivos_y_metas(instruccion)

        # 3. ¿Es una creación rápida de tarea? (Fast-path sin LLM)
        if re.match(r'^(agrega(r)? (una )?tarea|tarea:|recu[eé]rdame que|a[ñn]ade)', instruccion_lower):
            return await self._creacion_rapida_tarea(instruccion)

        # 4. Planificación estratégica con LLM
        return await self._proponer_plan_estrategico(instruccion)

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

    async def _proponer_plan_estrategico(self, instruccion: str) -> Resultado:
        """Usa el LLM para desglosar la meta en un JSON y espera confirmación."""
        logger.info("AgentePlan iniciando planificación estratégica...")
        
        response = await self._llm.generate(
            prompt=f"El usuario dice: '{instruccion}'. Elabora el plan estratégico.",
            system=SYSTEM_PROMPT_ESTRATEGA,
            temperature=0.4,
        )

        try:
            plan = json.loads(response.content)
        except json.JSONDecodeError:
            logger.error("LLM no devolvió JSON válido en AgentePlan: %s", response.content)
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje="No pude estructurar el plan correctamente. Intenta reformular tu meta.",
                agente=self.nombre,
            )

        # Guardar en propuestas pendientes
        propuesta_id = str(uuid.uuid4())[:8]
        self._propuestas_pendientes[propuesta_id] = plan

        # Formatear la propuesta para mostrársela al usuario
        obj_tit = plan.get("objetivo", {}).get("titulo", "Nuevo Objetivo")
        obj_area = plan.get("objetivo", {}).get("area", "Universidad")
        
        mensaje = f"💡 **Propuesta de Plan Estratégico:**\n\n"
        mensaje += f"*{plan.get('razon', 'Vamos a mejorar en esto.')}*\n\n"
        mensaje += f"🎯 **Objetivo:** {obj_tit} (Área: {obj_area})\n"
        
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
