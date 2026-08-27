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


@app.get("/sims", tags=["ui"])
async def sims_view():
    """Visualizador 3D Isométrico de Agentes (The Sims for AI Agents)."""
    sims_path = WEB_DIR / "sims.html"
    if sims_path.exists():
        return FileResponse(str(sims_path))
    return {"error": "Simulador 3D no encontrado"}


@app.get("/health", tags=["system"])
async def health():
    """Health check del sistema completo."""
    from agent_ia.entrypoints.api.dependencies import get_hermes

    hermes = get_hermes()
    return {
        "estado": "activo",
        "agentes": hermes.obtener_estado_agentes(),
    }


@app.post("/sync/ejecutar", tags=["sync"])
async def ejecutar_sync():
    """Dispara una sincronización bidireccional inmediata (Notion ↔ Obsidian + Alertas)."""
    from agent_ia.entrypoints.api.dependencies import get_hermes

    hermes = get_hermes()
    agente_sync = hermes.obtener_agente("sync")
    if not agente_sync:
        return {"estado": "error", "mensaje": "AgenteSync no disponible"}

    resultado = await agente_sync.ejecutar("sincronizar")
    return {
        "estado": resultado.estado.value,
        "mensaje": resultado.mensaje,
        "datos": resultado.datos,
    }


@app.post("/webhook/sync", tags=["sync"])
async def webhook_sync(payload: dict):
    """Endpoint webhook para recibir eventos de n8n, Todoist o automatizaciones externas."""
    from agent_ia.entrypoints.api.dependencies import get_hermes

    hermes = get_hermes()
    agente_sync = hermes.obtener_agente("sync")
    if not agente_sync:
        return {"estado": "error", "mensaje": "AgenteSync no disponible"}

    resultado = await agente_sync.ejecutar("webhook", contexto={"webhook_payload": payload})
    return {
        "estado": resultado.estado.value,
        "mensaje": resultado.mensaje,
        "datos": resultado.datos,
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
