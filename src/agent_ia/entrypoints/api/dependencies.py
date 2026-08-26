"""Dependency injection — inicialización de componentes de Agent IA.

Crea y cachea las instancias de todos los adaptadores, agentes y
el orquestador Hermes. Sigue el patrón de composición root de
arquitectura hexagonal.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from agent_ia.infrastructure.config import get_settings
from agent_ia.infrastructure.ollama_adapter import OllamaAdapter
from agent_ia.infrastructure.chroma_adapter import ChromaAdapter
from agent_ia.infrastructure.obsidian_adapter import ObsidianAdapter
from agent_ia.infrastructure.notion_adapter import NotionAdapter
from agent_ia.use_cases.agente_curador import AgenteCurador
from agent_ia.use_cases.agente_estudio import AgenteEstudio
from agent_ia.use_cases.agente_sync import AgenteSync
from agent_ia.use_cases.agente_plan import AgentePlan
from agent_ia.use_cases.hermes import Hermes

logger = logging.getLogger(__name__)


@lru_cache
def get_hermes() -> Hermes:
    """Composition root: crea y conecta todos los componentes."""
    settings = get_settings()

    # --- Infrastructure adapters ---
    llm = OllamaAdapter(settings)
    llm_rapido = OllamaAdapter(settings, model_override=settings.ollama_model_rapido)
    vector_store = ChromaAdapter(settings, llm)
    obsidian = ObsidianAdapter(settings)
    notion = NotionAdapter(settings)

    # --- Agents ---
    curador = AgenteCurador(
        llm=llm,
        obsidian=obsidian,
        vector_store=vector_store,
        notion=notion,
    )
    estudio = AgenteEstudio()
    sync = AgenteSync()
    plan = AgentePlan(llm=llm, notion=notion)

    # --- Orchestrator ---
    hermes = Hermes(llm=llm_rapido)
    hermes.registrar_agente("curador", curador)
    hermes.registrar_agente("estudio", estudio)
    hermes.registrar_agente("sync", sync)
    hermes.registrar_agente("plan", plan)

    logger.info("Agent IA inicializado: Hermes + 4 agentes registrados")
    return hermes


@lru_cache
def get_system_status() -> dict:
    """Devuelve información del estado del sistema (para el HUD)."""
    settings = get_settings()
    return {
        "ollama_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "vault_path": str(settings.vault_path),
        "n8n_url": settings.n8n_base_url,
    }
