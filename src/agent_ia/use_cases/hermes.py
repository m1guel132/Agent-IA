"""Hermes — orquestador central de Agent IA.

Hermes es el agente orquestador único (RF5.1) que:
- Recibe mensajes del usuario
- Detecta intención usando el LLM
- Delega al agente especializado correcto
- Gestiona la memoria persistente de la conversación
- Maneja el flujo de confirmación (RF5.4)
- Garantiza que una falla en un agente no bloquee a los demás (RF5.2)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from agent_ia.domain.entities import Nota
from agent_ia.domain.ports.llm_port import LLMPort
from agent_ia.domain.ports.obsidian_port import ObsidianPort
from agent_ia.use_cases.agente import Agente, EstadoResultado, Resultado

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_HERMES = """Eres Hermes, el orquestador central y enrutador de intenciones de Agent IA.
Tu tarea es clasificar la intención de Miguel y asignarla al agente especializado correspondiente.

Agentes disponibles:
1. **plan** — Estratega de metas y tareas. Usa este agente cuando Miguel:
   - Pregunte o consulte por sus objetivos, metas, proyectos o planes existentes (ej. "mira mis objetivos", "cuáles son mis metas", "qué proyectos tengo", "mis planes").
   - Quiera crear planes estratégicos o definir nuevas metas de estudio/vida.
   - Pida agregar tareas a Notion (ej. "agrega una tarea: ...").
2. **curador** — Segundo Cerebro (Notas y Conocimiento). Usa este agente cuando Miguel:
   - Quiera capturar o anotar nueva información (ej. "anota esto...", "guarda esta nota...").
   - Quiera consultar, buscar o preguntar sobre notas, conceptos, resúmenes o temas de su Segundo Cerebro (ej. "busca notas de...", "qué tengo sobre X", "consulta de mi segundo cerebro").
   - Pida organizar o limpiar el inbox.
3. **estudio** — Study Board y Repetición Espaciada. Usa SOLO cuando Miguel:
   - Hable de flashcards, tarjetas de estudio, notas Cornell o sesiones de repaso / quiz SM-2.
4. **sync** — Sincronización y alertas. Usa cuando Miguel:
   - Pida sincronizar Notion con Obsidian o verificar consistencia.
   - Pregunte por tareas vencidas o alertas de deadlines.
5. **hermes** — Conversación general, saludos, preguntas de seguimiento, charla libre o consultas reflexivas.

Responde SIEMPRE en JSON con esta estructura exacta:
{
    "agente": "curador|estudio|sync|plan|hermes",
    "instruccion_para_agente": "instrucción procesada para el agente o consulta",
    "razon": "breve explicación de la elección"
}
"""

SYSTEM_PROMPT_HERMES_CONVERSACIONAL = """Eres Hermes, el orquestador inteligente y copiloto personal de Agent IA de Miguel.

Tu personalidad:
- Eres natural, perspicaz, empático, directo y altamente competente.
- Tienes memoria de la conversación y recuerdas lo que Miguel te ha dicho en turnos anteriores para mantener un hilo fluido y coherente.
- Hablas en español con fluidez impecable, usando Markdown claro, legible y profesional.
- Conoces a la perfección el ecosistema de Miguel: su Segundo Cerebro (Notion + Obsidian), su flota de agentes (Curador, Estudio, Sync, Planificador), y sus metas académicas y personales.
- Cuando Miguel dialogue contigo, responde con calidez, inteligencia contextual y claridad, orientándolo proactivamente.
"""

SYSTEM_PROMPT_CONFIRMACION = """Eres Hermes, el orquestador central de Agent IA.
Tu tarea es clasificar la respuesta del usuario ante una propuesta o acción pendiente que requiere confirmación.

Determina cuál es la intención del usuario:
1. "confirmar": El usuario acepta, aprueba o confirma la propuesta pendiente (ej. "sí", "si", "dale", "va", "ok", "confirmo", "adelante", "perfecto", "me parece bien", "hazlo", "yes", "correcto").
2. "rechazar": El usuario rechaza, descarta o cancela la propuesta pendiente (ej. "no", "cancelar", "cancela", "olvídalo", "descarta", "nope", "no quiero").
3. "otro": El usuario no está respondiendo a la propuesta, sino haciendo una nueva pregunta, dando otra instrucción no relacionada, pidiendo organizar algo, o hablando de otro tema (ej. "¿qué es TCP?", "busca notas de redes", "organiza el inbox", "crea una tarea").

Responde SIEMPRE en JSON con esta estructura exacta:
{
    "intencion": "confirmar|rechazar|otro",
    "razon": "breve justificación"
}
"""


@dataclass
class MensajeChat:
    """Mensaje individual en la conversación."""

    role: str  # "user" o "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    agente: str = ""  # Qué agente generó la respuesta


class Hermes:
    """Orquestador central de Agent IA.

    Centraliza la memoria de la conversación, delega a agentes
    especializados y persiste los diálogos en el Segundo Cerebro (Obsidian).
    """

    def __init__(self, llm: LLMPort, obsidian: ObsidianPort | None = None) -> None:
        self._llm = llm
        self._obsidian = obsidian
        self._agentes: dict[str, Agente] = {}
        self._historial: list[MensajeChat] = []
        self._propuesta_activa: dict | None = None

    def registrar_agente(self, clave: str, agente: Agente) -> None:
        """Registra un agente especializado en el orquestador."""
        self._agentes[clave] = agente
        logger.info("Agente registrado: %s → %s", clave, agente)

    def obtener_agente(self, clave: str) -> Agente | None:
        """Obtiene un agente registrado por su clave."""
        return self._agentes.get(clave)

    async def procesar_mensaje(self, mensaje: str) -> Resultado:
        """Procesa un mensaje del usuario, delega al agente y persiste en Obsidian."""
        # Guardar mensaje del usuario en el historial
        self._historial.append(MensajeChat(role="user", content=mensaje))

        # Si hay una propuesta activa y el usuario responde
        if self._propuesta_activa:
            resultado = await self._manejar_confirmacion(mensaje)
        else:
            resultado = await self._procesar_instruccion(mensaje, guardar_en_historial=True)

        # Persistir automáticamente el turno en el Segundo Cerebro (Obsidian)
        await self._persistir_dialogo_obsidian(mensaje, resultado.mensaje, resultado.agente)

        return resultado

    async def _persistir_dialogo_obsidian(self, user_msg: str, bot_msg: str, agente: str) -> None:
        """Persiste automáticamente cada turno en Obsidian bajo la carpeta Conversaciones/."""
        if not self._obsidian:
            return
        try:
            hoy_str = datetime.now().strftime("%Y-%m-%d")
            ahora_hora = datetime.now().strftime("%H:%M:%S")
            ruta_relativa = f"Conversaciones/{hoy_str}.md"

            try:
                contenido_existente = await self._obsidian.leer_nota(ruta_relativa)
            except Exception:
                contenido_existente = (
                    f"# 💬 Diario de Conversaciones — {hoy_str}\n\n"
                    f"Registro automático del Segundo Cerebro (Agent IA).\n\n"
                    f"---\n"
                )

            bloque_dialogo = (
                f"\n### 🕒 {ahora_hora} — Miguel\n"
                f"> {user_msg}\n\n"
                f"### 🤖 {ahora_hora} — {agente}\n"
                f"{bot_msg}\n\n"
                f"---\n"
            )

            nota_actualizada = Nota(
                id=f"chat_{hoy_str}",
                titulo=hoy_str,
                contenido=contenido_existente + bloque_dialogo,
                area_id="Conversaciones",
                tags=["chat", "dialogo", "segundo_cerebro", "hermes"],
            )
            await self._obsidian.escribir_nota(nota_actualizada)
        except Exception as e:
            logger.warning("No se pudo persistir el diálogo en Obsidian: %s", e)

    async def _procesar_instruccion(self, mensaje: str, *, guardar_en_historial: bool = True) -> Resultado:
        """Detecta la intención y ejecuta la instrucción delegando o respondiendo directamente."""
        try:
            routing = await self._detectar_intencion(mensaje)
        except Exception as e:
            logger.exception("Error al detectar intención")
            resultado = self._respuesta_error(f"Error al procesar tu mensaje: {e}")
            if guardar_en_historial:
                self._guardar_respuesta(resultado)
            return resultado

        agente_clave = routing.get("agente", "hermes")
        instruccion = routing.get("instruccion_para_agente", mensaje)

        # Si Hermes responde directamente (conversación natural con memoria)
        if agente_clave == "hermes":
            respuesta_fluida = await self._generar_respuesta_conversacional(mensaje)
            resultado = Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=respuesta_fluida,
                agente="Hermes",
            )
            if guardar_en_historial:
                self._guardar_respuesta(resultado)
            return resultado

        # Delegar al agente correspondiente pasando contexto conversacional
        return await self._delegar(agente_clave, instruccion, mensaje_original=mensaje, guardar_en_historial=guardar_en_historial)

    async def _generar_respuesta_conversacional(self, mensaje: str) -> str:
        """Genera una respuesta conversacional fluida, natural y con memoria de diálogo."""
        historial_reciente = self._historial[-10:]  # Últimos 5 intercambios
        lineas_contexto = []
        for m in historial_reciente[:-1]:  # Excluir el mensaje actual ya presente
            autor = "Miguel" if m.role == "user" else f"Hermes"
            lineas_contexto.append(f"{autor}: {m.content}")

        contexto_dialogo = "\n".join(lineas_contexto) if lineas_contexto else "Inicio de la conversación."

        prompt = (
            f"Historial reciente de la conversación:\n{contexto_dialogo}\n\n"
            f"Mensaje actual de Miguel:\n{mensaje}\n\n"
            f"Responde de forma natural, inteligente, directa y fluida:"
        )

        try:
            response = await self._llm.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT_HERMES_CONVERSACIONAL,
                temperature=0.5,
            )
            return response.content
        except Exception as e:
            logger.warning("Error generando diálogo conversacional: %s", e)
            return f"Hola Miguel, estoy aquí para ayudarte con tu Segundo Cerebro y tus metas. ¿En qué trabajamos hoy?"

    async def _detectar_intencion(self, mensaje: str) -> dict:
        """Usa el LLM para determinar qué agente debe actuar."""
        # Construir contexto con historial reciente
        historial_reciente = self._historial[-6:]  # Últimos 3 intercambios
        contexto = "\n".join(
            f"{'Miguel' if m.role == 'user' else 'Hermes'}: {m.content}"
            for m in historial_reciente[:-1]  # Excluir el mensaje actual
        )

        prompt = f"Historial reciente:\n{contexto}\n\nMensaje actual de Miguel:\n{mensaje}"

        response = await self._llm.generate(
            prompt=prompt,
            system=SYSTEM_PROMPT_HERMES,
            temperature=0.2,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning("LLM no devolvió JSON válido: %s", response.content[:200])
            return {
                "agente": "hermes",
                "instruccion_para_agente": response.content,
                "razon": "Respuesta directa (JSON no válido)",
            }

    async def _delegar(
        self, agente_clave: str, instruccion: str, *, mensaje_original: str = "", guardar_en_historial: bool = True
    ) -> Resultado:
        """Delega la instrucción al agente correspondiente (RF5.2: fallas aisladas)."""
        agente = self._agentes.get(agente_clave)

        if agente is None:
            resultado = Resultado(
                estado=EstadoResultado.ERROR,
                mensaje=f"⚠️ No tengo un agente registrado para '{agente_clave}'.",
                agente="Hermes",
            )
            if guardar_en_historial:
                self._guardar_respuesta(resultado)
            return resultado

        try:
            contexto_delegacion = {
                "historial": self.obtener_historial(),
                "mensaje_original": mensaje_original or instruccion,
            }
            resultado = await agente.ejecutar(instruccion, contexto=contexto_delegacion)
        except Exception as e:
            # RF5.2: falla silenciosa — no bloquea al orquestador
            logger.exception("Error en agente %s", agente_clave)
            resultado = Resultado(
                estado=EstadoResultado.ERROR,
                mensaje=f"⚠️ {agente.nombre} encontró un error: {e}\n"
                "El resto del sistema sigue operativo.",
                agente=agente.nombre,
            )

        # Si el agente requiere confirmación, guardar la propuesta
        if resultado.estado == EstadoResultado.REQUIERE_CONFIRMACION:
            nuevo_propuesta_id = resultado.datos.get("propuesta_id")
            # Guardia: si ya existía otra propuesta activa distinta, advertir reemplazo
            if self._propuesta_activa and self._propuesta_activa.get("propuesta_id") != nuevo_propuesta_id:
                propuesta_ant = self._propuesta_activa
                nota_ant = (
                    propuesta_ant["resultado"].datos.get("nota", {})
                    if propuesta_ant.get("resultado") and propuesta_ant["resultado"].datos
                    else {}
                )
                titulo_ant = (
                    nota_ant.get("titulo")
                    or (propuesta_ant["resultado"].accion_pendiente if propuesta_ant.get("resultado") else None)
                    or "anterior"
                )
                resultado.mensaje += (
                    f"\n\n⚠️ *Aviso:* La propuesta anterior sobre '**{titulo_ant}**' "
                    "fue reemplazada como foco activo de confirmación."
                )

            self._propuesta_activa = {
                "agente_clave": agente_clave,
                "propuesta_id": nuevo_propuesta_id,
                "resultado": resultado,
            }

        if guardar_en_historial:
            self._guardar_respuesta(resultado)
        return resultado

    async def _manejar_confirmacion(self, mensaje: str) -> Resultado:
        """Maneja la respuesta del usuario a una propuesta pendiente usando clasificación LLM."""
        propuesta = self._propuesta_activa
        assert propuesta is not None

        # Clasificar la intención del usuario con el LLM rápido
        prompt_clasif = (
            f"Propuesta pendiente: {propuesta['resultado'].accion_pendiente or 'Acción pendiente'}\n"
            f"Respuesta del usuario: \"{mensaje}\""
        )
        try:
            resp_clasif = await self._llm.generate(
                prompt=prompt_clasif,
                system=SYSTEM_PROMPT_CONFIRMACION,
                temperature=0.0,
            )
            data_clasif = json.loads(resp_clasif.content)
            intencion = data_clasif.get("intencion", "otro").lower().strip()
        except Exception:
            logger.warning("Fallo al clasificar confirmación con LLM, usando fallback por palabras clave")
            mensaje_clean = mensaje.lower().strip()
            if mensaje_clean in {"sí", "si", "confirmar", "confirmo", "ok", "dale", "yes", "correcto", "va", "adelante"}:
                intencion = "confirmar"
            elif mensaje_clean in {"no", "cancelar", "cancela", "nope", "rechazar"}:
                intencion = "rechazar"
            else:
                intencion = "otro"

        if intencion == "confirmar":
            agente = self._agentes.get(propuesta["agente_clave"])
            self._propuesta_activa = None

            if agente:
                resultado = await agente.ejecutar(
                    "confirmar",
                    contexto={"confirmar_propuesta": propuesta["propuesta_id"]},
                )
            else:
                resultado = self._respuesta_error("Agente no disponible")

            self._guardar_respuesta(resultado)
            return resultado

        elif intencion == "rechazar":
            self._propuesta_activa = None
            resultado = Resultado(
                estado=EstadoResultado.SIN_ACCION,
                mensaje="❌ Propuesta cancelada. ¿Qué te gustaría hacer ahora?",
                agente="Hermes",
            )
            self._guardar_respuesta(resultado)
            return resultado

        else:  # intencion == "otro"
            # Procesar el mensaje como una instrucción nueva normal
            propuesta_id_previa = propuesta["propuesta_id"]
            resultado_nuevo = await self._procesar_instruccion(mensaje, guardar_en_historial=False)

            # Si la nueva instrucción no generó una nueva propuesta, añadir recordatorio de la propuesta pendiente
            if (
                self._propuesta_activa
                and self._propuesta_activa.get("propuesta_id") == propuesta_id_previa
            ):
                nota_info = (
                    propuesta["resultado"].datos.get("nota", {})
                    if propuesta.get("resultado") and propuesta["resultado"].datos
                    else {}
                )
                titulo_propuesta = (
                    nota_info.get("titulo")
                    or propuesta["resultado"].accion_pendiente
                    or "propuesta pendiente"
                )
                recordatorio = (
                    f"\n\n📌 *Nota:* Tienes una propuesta pendiente: "
                    f"**{titulo_propuesta}**. Responde *'sí'* para confirmarla o *'no'* para cancelarla."
                )
                resultado_nuevo.mensaje = f"{resultado_nuevo.mensaje}{recordatorio}"

            self._guardar_respuesta(resultado_nuevo)
            return resultado_nuevo

    def _guardar_respuesta(self, resultado: Resultado) -> None:
        """Guarda la respuesta en el historial."""
        self._historial.append(
            MensajeChat(
                role="assistant",
                content=resultado.mensaje,
                agente=resultado.agente,
            )
        )

    @staticmethod
    def _respuesta_error(mensaje: str) -> Resultado:
        return Resultado(
            estado=EstadoResultado.ERROR,
            mensaje=f"❌ {mensaje}",
            agente="Hermes",
        )

    def obtener_historial(self) -> list[dict]:
        """Devuelve el historial de chat formateado."""
        return [
            {
                "role": m.role,
                "content": m.content,
                "agente": m.agente,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in self._historial
        ]

    def obtener_estado_agentes(self) -> dict[str, str]:
        """Devuelve el estado de cada agente registrado."""
        return {
            clave: f"{agente.nombre} ({agente.dominio})"
            for clave, agente in self._agentes.items()
        }
