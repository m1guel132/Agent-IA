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

from agent_ia.domain.ports.llm_port import LLMPort
from agent_ia.use_cases.agente import Agente, EstadoResultado, Resultado

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_HERMES = """Eres Hermes, el orquestador central de Agent IA, el copiloto personal de gestión de conocimiento y estudio de Miguel.

Tu personalidad:
- Eres directo, eficiente y amigable.
- Hablas en español por defecto, pero puedes cambiar a inglés si Miguel lo prefiere.
- Siempre explicas qué agente se encargará de cada tarea.

Tu trabajo es analizar los mensajes de Miguel y decidir qué agente debe actuar.
Los agentes disponibles son:
1. **AgenteCurador** — Organiza el Segundo Cerebro: notas, áreas, tags, inbox. Usa este agente cuando Miguel quiera anotar algo, organizar notas, buscar en su conocimiento, o cuando mencione el Segundo Cerebro.
2. **AgenteEstudio** — Study Board y repetición espaciada. Usa SOLO cuando Miguel hable de repasar tarjetas, cuestionarios, o técnicas de estudio (ej. Cornell).
3. **AgenteSync** — Sincronización entre plataformas (Notion, Obsidian, Todoist, Calendar). Usa cuando pida sincronizar o verificar consistencia.
4. **AgentePlan** — Estratega de metas y planificación. Usa cuando hable de tareas, deadlines, o de CREAR PLANES para mejorar académicamente o personalmente, definiendo objetivos y proyectos.

Si el mensaje es una conversación general (saludo, pregunta sobre el sistema, etc.), responde tú directamente sin delegar.

Responde SIEMPRE en JSON con esta estructura exacta:
{
    "agente": "curador|estudio|sync|plan|hermes",
    "instruccion_para_agente": "instrucción procesada para el agente, o tu respuesta directa si agente=hermes",
    "razon": "por qué elegiste ese agente"
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

    Centraliza la memoria de la conversación y delega a agentes
    especializados según la intención del usuario.
    """

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm
        self._agentes: dict[str, Agente] = {}
        self._historial: list[MensajeChat] = []
        self._propuesta_activa: dict | None = None

    def registrar_agente(self, clave: str, agente: Agente) -> None:
        """Registra un agente especializado en el orquestador."""
        self._agentes[clave] = agente
        logger.info("Agente registrado: %s → %s", clave, agente)

    async def procesar_mensaje(self, mensaje: str) -> Resultado:
        """Procesa un mensaje del usuario y delega al agente correcto.

        Este es el punto de entrada principal del sistema.
        """
        # Guardar mensaje del usuario en el historial
        self._historial.append(MensajeChat(role="user", content=mensaje))

        # Si hay una propuesta activa y el usuario confirma
        if self._propuesta_activa:
            return await self._manejar_confirmacion(mensaje)

        # Detectar intención con el LLM
        try:
            routing = await self._detectar_intencion(mensaje)
        except Exception as e:
            logger.exception("Error al detectar intención")
            return self._respuesta_error(f"Error al procesar tu mensaje: {e}")

        agente_clave = routing.get("agente", "hermes")
        instruccion = routing.get("instruccion_para_agente", mensaje)

        # Si Hermes responde directamente
        if agente_clave == "hermes":
            resultado = Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=instruccion,
                agente="Hermes",
            )
            self._guardar_respuesta(resultado)
            return resultado

        # Delegar al agente correspondiente
        return await self._delegar(agente_clave, instruccion)

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
            # Fallback: intentar responder directamente
            return {
                "agente": "hermes",
                "instruccion_para_agente": response.content,
                "razon": "Respuesta directa (JSON no válido)",
            }

    async def _delegar(self, agente_clave: str, instruccion: str) -> Resultado:
        """Delega la instrucción al agente correspondiente (RF5.2: fallas aisladas)."""
        agente = self._agentes.get(agente_clave)

        if agente is None:
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje=f"⚠️ No tengo un agente registrado para '{agente_clave}'.",
                agente="Hermes",
            )

        try:
            resultado = await agente.ejecutar(instruccion)
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
            self._propuesta_activa = {
                "agente_clave": agente_clave,
                "propuesta_id": resultado.datos.get("propuesta_id"),
                "resultado": resultado,
            }

        self._guardar_respuesta(resultado)
        return resultado

    async def _manejar_confirmacion(self, mensaje: str) -> Resultado:
        """Maneja la respuesta del usuario a una propuesta pendiente."""
        propuesta = self._propuesta_activa
        assert propuesta is not None

        mensaje_lower = mensaje.lower().strip()
        afirmaciones = {"sí", "si", "confirmar", "confirmo", "ok", "dale", "yes", "correcto"}
        negaciones = {"no", "cancelar", "cancela", "ajustar", "cambiar", "nope"}

        if mensaje_lower in afirmaciones:
            # Confirmar la propuesta
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

        elif mensaje_lower in negaciones:
            self._propuesta_activa = None
            resultado = Resultado(
                estado=EstadoResultado.SIN_ACCION,
                mensaje="❌ Propuesta cancelada. ¿Qué te gustaría ajustar?",
                agente="Hermes",
            )
            self._guardar_respuesta(resultado)
            return resultado

        else:
            # No se entendió la respuesta
            resultado = Resultado(
                estado=EstadoResultado.REQUIERE_CONFIRMACION,
                mensaje="🤔 No entendí tu respuesta. ¿Confirmas la propuesta? (Sí/No)",
                datos=propuesta["resultado"].datos,
                agente="Hermes",
            )
            self._guardar_respuesta(resultado)
            return resultado

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
