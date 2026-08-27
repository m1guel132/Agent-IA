"""AgenteEstudio — gestión del Study Board y repetición espaciada (SM-2).

Responsabilidades (Fase 2):
- Generar tarjetas de repetición espaciada (SM-2) desde notas o temas (RF3.1)
- Consultar y notificar repasos pendientes (RF3.2)
- Generar plantillas de notas Cornell estructuradas (RF3.3)
- Ejecutar sesiones de repaso interactivo y calibrar intervalos SM-2 (RF3.4)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date

from agent_ia.domain.entities.item_estudio import ItemEstudio
from agent_ia.domain.entities.nota import Nota, OrigenNota
from agent_ia.domain.ports.llm_port import LLMPort
from agent_ia.domain.ports.notion_port import NotionPort
from agent_ia.domain.ports.obsidian_port import ObsidianPort
from agent_ia.domain.ports.study_port import StudyPort
from agent_ia.use_cases.agente import Agente, EstadoResultado, Resultado

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_FLASHCARDS = """Eres el AgenteEstudio de Agent IA, experto en técnicas de aprendizaje acelerado y memorización activa.
Tu tarea es extraer conceptos clave de la nota o tema proporcionado y convertirlos en tarjetas de estudio (Flashcards) atómicas y de alto valor conceptual.

Reglas:
1. Genera entre 2 y 5 tarjetas en formato Pregunta / Respuesta concisa.
2. Evita preguntas obvias o de sí/no; formula preguntas que prueben comprensión profunda.

Responde SIEMPRE en JSON con esta estructura exacta:
{
    "tema": "Tema o título de la sesión",
    "tarjetas": [
        {
            "pregunta": "¿Qué es X y cómo funciona?",
            "respuesta": "X es..."
        }
    ],
    "resumen": "Breve explicación pedagógica"
}
"""

SYSTEM_PROMPT_CORNELL = """Eres el AgenteEstudio de Agent IA.
Tu tarea es generar una plantilla de toma de notas con el Método Cornell sobre el tema solicitado.

Estructura requerida en Markdown:
# Cornell Notes: [Tema]
**Fecha:** [Fecha actual] | **Materia/Área:** [Área sugerida]

---

## 📌 Preguntas / Ideas Clave (Cue Column)
- [Pregunta 1]
- [Pregunta 2]
- [Concepto central]

---

## 📝 Notas Detalladas (Notes Column)
- [Desarrollo estructurado punto por punto con viñetas]
- [Explicación técnica clara]

---

## 💡 Resumen Sintético (Summary)
[Resumen de 2 a 3 frases que condensa la idea principal].
"""


class AgenteEstudio(Agente):
    """Agente especializado en Study Board, flashcards y algoritmo SM-2."""

    def __init__(
        self,
        llm: LLMPort,
        study_repo: StudyPort,
        obsidian: ObsidianPort,
        notion: NotionPort | None = None,
    ) -> None:
        super().__init__(nombre="AgenteEstudio", dominio="ItemEstudio, Nota")
        self._llm = llm
        self._study_repo = study_repo
        self._obsidian = obsidian
        self._notion = notion
        self._sesion_activa: dict | None = None

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        """Enruta la instrucción de estudio a su manejador correspondiente."""
        ctx = contexto or {}
        instruccion_lower = instruccion.strip().lower()
        # Normalizar texto (remover acentos para búsqueda robusta)
        clean_text = (
            instruccion_lower.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("¿", "")
            .replace("?", "")
        )

        # 1. ¿Es una calificación de sesión de repaso activa? (ej: 0-5, o palabra clave de evaluación)
        if self._sesion_activa or ctx.get("evaluar_tarjeta"):
            match_calif = re.search(r"\b([0-5])\b", instruccion_lower)
            if match_calif:
                calidad = int(match_calif.group(1))
                return await self._evaluar_repaso(calidad)

        # 2. ¿Es solicitud de plantilla Cornell?
        if "cornell" in clean_text:
            return await self._generar_nota_cornell(instruccion)

        # 3. ¿Es consulta de repasos pendientes?
        if any(p in clean_text for p in ["pendiente", "tengo para repasar", "repasos hoy", "cuantas tarjetas", "estado de estudio"]):
            return await self._consultar_pendientes()

        # 4. ¿Es inicio de sesión de repaso interactivo?
        if any(p in clean_text for p in ["iniciar repaso", "empezar repaso", "repasar", "quiz", "estudiar"]):
            return await self._iniciar_sesion_repaso()

        # 5. Por defecto: Generar flashcards desde texto o tema
        return await self._generar_flashcards(instruccion)

    async def _generar_flashcards(self, instruccion: str) -> Resultado:
        """Genera tarjetas de repetición espaciada usando el LLM y las guarda."""
        prompt = f"Genera tarjetas de estudio para la siguiente nota o instrucción:\n\n{instruccion}"
        try:
            response = await self._llm.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT_FLASHCARDS,
                temperature=0.2,
            )
            data = json.loads(response.content)
        except Exception as e:
            logger.warning("Fallo al parsear JSON de flashcards: %s", e)
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje=f"⚠️ No pude estructurar las flashcards en formato válido: {e}",
                agente=self.nombre,
            )

        tema = data.get("tema", "Tema General")
        tarjetas_data = data.get("tarjetas", [])
        if not tarjetas_data:
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje="No se encontraron conceptos suficientes para generar flashcards.",
                agente=self.nombre,
            )

        tarjetas_creadas = []
        for t in tarjetas_data:
            item = ItemEstudio(
                id=str(uuid.uuid4())[:8],
                nota_id=tema,
                pregunta=t.get("pregunta", ""),
                respuesta=t.get("respuesta", ""),
                sig_repaso=date.today(),
            )
            await self._study_repo.guardar_tarjeta(item)
            tarjetas_creadas.append(item)

        mensaje = f"📚 **¡Se crearon {len(tarjetas_creadas)} flashcards para '{tema}'!**\n\n"
        for i, card in enumerate(tarjetas_creadas, 1):
            mensaje += f"**{i}. Pregunta:** {card.pregunta}\n   **Respuesta:** {card.respuesta}\n\n"

        mensaje += "💡 *Están programadas para su primer repaso hoy. Di 'repasar' cuando quieras iniciar el quiz.*"

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=mensaje,
            agente=self.nombre,
            datos={"tarjetas_creadas": len(tarjetas_creadas), "tema": tema},
        )

    async def _consultar_pendientes(self) -> Resultado:
        """Consulta el total de tarjetas pendientes para hoy."""
        pendientes = await self._study_repo.listar_pendientes(date.today())
        total = len(pendientes)

        if total == 0:
            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje="🎉 **¡Estás al día con tus estudios!** No tienes repasos pendientes para hoy.",
                agente=self.nombre,
                datos={"total_pendientes": 0},
            )

        temas = list({p.nota_id for p in pendientes if p.nota_id})
        mensaje = (
            f"📖 Tienes **{total} tarjeta{'s' if total > 1 else ''} pendiente{'s' if total > 1 else ''}** de repaso hoy.\n\n"
            f"**Temas a repasar:** {', '.join(temas) if temas else 'Varios'}\n\n"
            "Di **'iniciar repaso'** para comenzar la sesión SM-2."
        )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=mensaje,
            agente=self.nombre,
            datos={"total_pendientes": total, "temas": temas},
        )

    async def _iniciar_sesion_repaso(self) -> Resultado:
        """Inicia una sesión de quiz interactivo con la primera tarjeta pendiente."""
        pendientes = await self._study_repo.listar_pendientes(date.today())
        if not pendientes:
            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje="🎉 No hay tarjetas pendientes para repasar hoy. ¡Buen trabajo!",
                agente=self.nombre,
            )

        tarjeta_actual = pendientes[0]
        self._sesion_activa = {
            "tarjeta_id": tarjeta_actual.id,
            "pendientes_restantes": [p.id for p in pendientes[1:]],
            "total_sesion": len(pendientes),
        }

        mensaje = (
            f"🧠 **Sesión de Estudio SM-2 (1/{len(pendientes)})**\n\n"
            f"**Pregunta:** {tarjeta_actual.pregunta}\n\n"
            f"*(Respuesta: {tarjeta_actual.respuesta})*\n\n"
            "**¿Qué tan bien lo recordaste?** Responde con tu calificación:\n"
            "• `0` / `1` : Olvido total\n"
            "• `2` / `3` : Recordé con dificultad\n"
            "• `4` : Buen recuerdo\n"
            "• `5` : Recuerdo perfecto e instantáneo"
        )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=mensaje,
            agente=self.nombre,
            datos={"tarjeta_id": tarjeta_actual.id, "progreso": f"1/{len(pendientes)}"},
        )

    async def _evaluar_repaso(self, calidad: int) -> Resultado:
        """Registra la calificación SM-2 y presenta la siguiente tarjeta o finaliza la sesión."""
        if not self._sesion_activa:
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje="No hay una sesión de repaso activa. Di 'repasar' para iniciar.",
                agente=self.nombre,
            )

        tarjeta_id = self._sesion_activa["tarjeta_id"]
        tarjeta = await self._study_repo.obtener_tarjeta(tarjeta_id)
        if not tarjeta:
            self._sesion_activa = None
            return Resultado(estado=EstadoResultado.ERROR, mensaje="Tarjeta no encontrada.", agente=self.nombre)

        # Aplicar SM-2
        tarjeta.registrar_repaso(calidad=calidad)
        await self._study_repo.guardar_tarjeta(tarjeta)

        restantes = self._sesion_activa.get("pendientes_restantes", [])
        dias = tarjeta.intervalo

        resultado_txt = (
            f"✅ **Repaso registrado** (Calidad {calidad}/5)\n"
            f"📅 Próximo repaso programado en: **{dias} día{'s' if dias != 1 else ''}** (`{tarjeta.sig_repaso.isoformat()}`).\n\n"
        )

        if not restantes:
            self._sesion_activa = None
            resultado_txt += "🎉 **¡Has completado todas las tarjetas de la sesión!**"
            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=resultado_txt,
                agente=self.nombre,
                datos={"sesion_completada": True},
            )

        # Cargar siguiente tarjeta
        sig_id = restantes[0]
        sig_tarjeta = await self._study_repo.obtener_tarjeta(sig_id)
        self._sesion_activa["tarjeta_id"] = sig_id
        self._sesion_activa["pendientes_restantes"] = restantes[1:]

        num_actual = self._sesion_activa["total_sesion"] - len(restantes) + 1
        resultado_txt += (
            f"---\n\n🧠 **Siguiente Tarjeta ({num_actual}/{self._sesion_activa['total_sesion']}):**\n\n"
            f"**Pregunta:** {sig_tarjeta.pregunta if sig_tarjeta else 'Pregunta'}\n\n"
            f"*(Respuesta: {sig_tarjeta.respuesta if sig_tarjeta else ''})*\n\n"
            "Califica tu recuerdo (0 a 5):"
        )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=resultado_txt,
            agente=self.nombre,
            datos={"tarjeta_id": sig_id},
        )

    async def _generar_nota_cornell(self, instruccion: str) -> Resultado:
        """Genera y guarda una nota con formato estructurado Cornell."""
        prompt = f"Genera una nota Cornell detallada sobre:\n\n{instruccion}"
        try:
            response = await self._llm.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT_CORNELL,
                temperature=0.3,
            )
            contenido = response.content
        except Exception as e:
            logger.error("Error al generar nota Cornell: %s", e)
            return Resultado(estado=EstadoResultado.ERROR, mensaje=f"Error al generar nota Cornell: {e}", agente=self.nombre)

        # Extraer título del contenido
        titulo_match = re.search(r"# Cornell Notes:\s*(.+)", contenido)
        titulo = titulo_match.group(1).strip() if titulo_match else "Nota Cornell"

        nota = Nota(
            id=str(uuid.uuid4()),
            titulo=f"Cornell - {titulo}",
            contenido=contenido,
            area_id="Study_Board",
            tags=["cornell", "estudio", "apuntes"],
            origen=OrigenNota.CHAT,
        )

        # Guardar en Obsidian
        filepath = await self._obsidian.escribir_nota(nota)

        # Crear flashcards automáticas asociadas a la nota
        await self._generar_flashcards(f"Genera 3 flashcards del siguiente tema Cornell: {titulo}\n{contenido[:500]}")

        mensaje = (
            f"📝 **¡Nota Cornell creada exitosamente!**\n\n"
            f"📁 **Guardada en:** `{filepath.name}` (Área: `Study_Board`)\n"
            f"🏷️ **Tags:** `#cornell`, `#estudio`\n\n"
            "💡 *Se generaron automáticamente tarjetas de repaso para este tema en tu Study Board.*"
        )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=mensaje,
            agente=self.nombre,
            datos={"obsidian_path": str(filepath)},
        )
