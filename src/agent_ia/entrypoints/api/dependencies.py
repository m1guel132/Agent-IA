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
from agent_ia.infrastructure.gemini_adapter import GeminiAdapter
from agent_ia.infrastructure.sanitizer import DataMasker
from agent_ia.infrastructure.chroma_adapter import ChromaAdapter
from agent_ia.infrastructure.obsidian_adapter import ObsidianAdapter
from agent_ia.infrastructure.notion_adapter import NotionAdapter
from agent_ia.infrastructure.json_study_adapter import JsonStudyAdapter
from agent_ia.infrastructure.json_sync_adapter import JsonSyncAdapter
from agent_ia.use_cases.agente_curador import AgenteCurador
from agent_ia.use_cases.agente_estudio import AgenteEstudio
from agent_ia.use_cases.agente_sync import AgenteSync
from agent_ia.use_cases.agente_plan import AgentePlan
from agent_ia.use_cases.hermes import Hermes

logger = logging.getLogger(__name__)


@lru_cache
def get_hermes() -> Hermes:
    """Composition root: crea y conecta todos los componentes según el backend configurado."""
    settings = get_settings()

    # Adaptador base local (Ollama)
    llm_local = OllamaAdapter(settings)
    llm_local_rapido = OllamaAdapter(settings, model_override=settings.ollama_model_rapido)

    # Determinar qué backend usar
    if settings.llm_backend in {"gemini", "hybrid"} and settings.gemini_api_key:
        logger.info(
            "Iniciando Agent IA con backend %s (Gemini: %s, Plan: %s, Sanitización: %s)",
            settings.llm_backend.upper(),
            settings.gemini_model,
            settings.gemini_model_plan,
            settings.enable_data_masking,
        )
        masker = DataMasker(enabled=settings.enable_data_masking)
        llm_gemini = GeminiAdapter(
            settings=settings,
            model_override=settings.gemini_model,
            masker=masker,
            fallback_llm=llm_local_rapido,
        )
        llm_gemini_plan = GeminiAdapter(
            settings=settings,
            model_override=settings.gemini_model_plan,
            masker=masker,
            fallback_llm=llm_local,
        )

        llm_principal = llm_gemini
        llm_hermes = llm_gemini
        llm_plan = llm_gemini_plan

        # En modo híbrido, los embeddings y ChromaDB se mantienen 100% locales
        llm_embeddings = llm_local if settings.llm_backend == "hybrid" else llm_gemini
    else:
        logger.info("Iniciando Agent IA con backend 100%% LOCAL (Ollama: %s)", settings.ollama_model)
        llm_principal = llm_local
        llm_hermes = llm_local_rapido
        llm_plan = llm_local
        llm_embeddings = llm_local

    # --- Infrastructure adapters ---
    vector_store = ChromaAdapter(settings, llm_embeddings)
    obsidian = ObsidianAdapter(settings)
    notion = NotionAdapter(settings)
    study_repo = JsonStudyAdapter()
    sync_repo = JsonSyncAdapter()

    # --- Agents ---
    curador = AgenteCurador(
        llm=llm_principal,
        obsidian=obsidian,
        vector_store=vector_store,
        notion=notion,
    )
    estudio = AgenteEstudio(
        llm=llm_principal,
        study_repo=study_repo,
        obsidian=obsidian,
        notion=notion,
    )
    sync = AgenteSync(
        sync_port=sync_repo,
        notion=notion,
        obsidian=obsidian,
        vector_store=vector_store,
        llm=llm_principal,
    )
    plan = AgentePlan(llm=llm_plan, notion=notion)

    # --- Orchestrator ---
    hermes = Hermes(llm=llm_hermes, obsidian=obsidian)
    hermes.registrar_agente("curador", curador)
    hermes.registrar_agente("estudio", estudio)
    hermes.registrar_agente("sync", sync)
    hermes.registrar_agente("plan", plan)

    logger.info("Agent IA inicializado con éxito: Hermes + 4 agentes registrados")
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
