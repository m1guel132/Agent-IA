"""Ruta /chat — punto de entrada conversacional de Agent IA.

Recibe mensajes del usuario y los enruta a Hermes (orquestador).
Soporta tanto peticiones simples como confirmaciones de propuestas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends

from agent_ia.entrypoints.api.dependencies import get_hermes
from agent_ia.use_cases.hermes import Hermes

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Petición de chat entrante."""

    mensaje: str = Field(..., min_length=1, description="Mensaje del usuario")


class ChatResponse(BaseModel):
    """Respuesta de chat."""

    estado: str
    mensaje: str
    agente: str = ""
    datos: dict = {}
    accion_pendiente: str | None = None


@router.post("/", response_model=ChatResponse)
async def enviar_mensaje(
    request: ChatRequest,
    hermes: Hermes = Depends(get_hermes),
) -> ChatResponse:
    """Envía un mensaje a Hermes y devuelve la respuesta.

    Este endpoint implementa el flujo completo del diagrama de secuencia:
    Miguel → Interfaz → Gateway → Hermes → Agente → (propuesta/resultado)
    """
    resultado = await hermes.procesar_mensaje(request.mensaje)

    return ChatResponse(
        estado=resultado.estado.value,
        mensaje=resultado.mensaje,
        agente=resultado.agente,
        datos=resultado.datos,
        accion_pendiente=resultado.accion_pendiente,
    )


class HistorialResponse(BaseModel):
    """Respuesta con el historial de chat."""

    mensajes: list[dict]


@router.get("/historial", response_model=HistorialResponse)
async def obtener_historial(
    hermes: Hermes = Depends(get_hermes),
) -> HistorialResponse:
    """Devuelve el historial de la conversación actual."""
    return HistorialResponse(mensajes=hermes.obtener_historial())

