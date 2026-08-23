"""API Gateway de Agent IA — FastAPI en :8000.

Punto de entrada HTTP del sistema. Todas las interfaces
(HUD, CLI, Telegram) se comunican con el sistema a través
de este gateway.
"""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_ia.entrypoints.api.routes.chat import router as chat_router
from agent_ia.infrastructure.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-30s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title="Agent IA — API Gateway",
    description=(
        "Copiloto personal de gestión de conocimiento y estudio. "
        "API Gateway que conecta todas las interfaces con Hermes (orquestador)."
    ),
    version="0.1.0",
)

# CORS para el HUD (Streamlit en otro puerto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(chat_router)


@app.get("/", tags=["system"])
async def root():
    """Endpoint raíz — verificación rápida de que el API está activo."""
    return {
        "sistema": "Agent IA",
        "version": "0.1.0",
        "estado": "activo",
        "mensaje": "API Gateway operativo. Usa POST /chat/ para conversar con Hermes.",
    }


@app.get("/health", tags=["system"])
async def health():
    """Health check del sistema completo."""
    from agent_ia.entrypoints.api.dependencies import get_hermes

    hermes = get_hermes()
    return {
        "estado": "activo",
        "agentes": hermes.obtener_estado_agentes(),
    }


def start() -> None:
    """Entry point para el script `agent-api`."""
    settings = get_settings()
    uvicorn.run(
        "agent_ia.entrypoints.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    start()
