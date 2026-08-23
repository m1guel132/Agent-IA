"""Adaptador de ChromaDB — implementación del puerto VectorStore.

Usa ChromaDB local con embeddings generados por Ollama (nomic-embed-text).
Los documentos se persisten en disco para sobrevivir reinicios.
"""

from __future__ import annotations

import logging

import chromadb

from gwen_os.domain.ports.llm_port import LLMPort
from gwen_os.domain.ports.vector_store_port import SearchResult, VectorStorePort
from gwen_os.infrastructure.config import Settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "gwen_os_knowledge"


class ChromaAdapter(VectorStorePort):
    """Adaptador concreto de ChromaDB para búsqueda semántica."""

    def __init__(self, settings: Settings, llm: LLMPort) -> None:
        self._settings = settings
        self._llm = llm  # Para generar embeddings vía Ollama

        # Crear directorio de persistencia si no existe
        persist_dir = settings.chroma_path
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Base de conocimiento de Gwen OS"},
        )
        logger.info("ChromaDB inicializado en %s", persist_dir)

    async def indexar(self, doc_id: str, content: str, metadata: dict | None = None) -> None:
        """Indexa un documento generando su embedding con Ollama."""
        embedding = await self._llm.embed(content)

        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata or {}],
        )
        logger.debug("Indexado documento %s (%d chars)", doc_id, len(content))

    async def buscar(self, query: str, n_results: int = 5) -> list[SearchResult]:
        """Busca documentos por similitud semántica."""
        query_embedding = await self._llm.embed(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                search_results.append(
                    SearchResult(
                        id=doc_id,
                        content=results["documents"][0][i] if results["documents"] else "",
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        score=1.0 - (results["distances"][0][i] if results["distances"] else 0.0),
                    )
                )

        return search_results

    async def eliminar(self, doc_id: str) -> None:
        """Elimina un documento del índice."""
        self._collection.delete(ids=[doc_id])
        logger.debug("Eliminado documento %s del índice", doc_id)

    async def health_check(self) -> bool:
        """Verifica que ChromaDB esté operativo."""
        try:
            count = self._collection.count()
            logger.debug("ChromaDB health check OK: %d documentos indexados", count)
            return True
        except Exception:
            logger.exception("ChromaDB health check falló")
            return False
