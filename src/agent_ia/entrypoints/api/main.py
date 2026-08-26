"""API Gateway de Agent IA — FastAPI en :8000.

Punto de entrada HTTP del sistema. Todas las interfaces
(HUD, CLI, Telegram) se comunican con el sistema a través
de este gateway.
"""

from __future__ import annotations

import logging

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent_ia.entrypoints.api.routes.chat import router as chat_router
from agent_ia.infrastructure.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-30s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)

WEB_DIR = Path(__file__).parent.parent / "web"

app = FastAPI(
    title="Agent IA — API Gateway",
    description=(
        "Copiloto personal de gestión de conocimiento y estudio. "
        "API Gateway que conecta todas las interfaces con Hermes (orquestador)."
    ),
    version="0.1.0",
)

# CORS para el HUD o frontend externo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar estáticos si existe la carpeta web
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# Rutas
app.include_router(chat_router)


@app.get("/", tags=["ui"])
async def root():
    """Sirve la interfaz web moderna si está disponible, o el estado del API."""
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "sistema": "Agent IA",
        "version": "0.1.0",
        "estado": "activo",
        "mensaje": "API Gateway operativo. Usa POST /chat/ para conversar con Hermes.",
    }


@app.get("/app", tags=["ui"])
async def web_app():
    """Acceso directo a la interfaz web moderna."""
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"error": "Interfaz web no encontrada"}


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
