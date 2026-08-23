"""Puerto abstracto para el vector store.

Define la interfaz para indexación y búsqueda semántica.
El adaptador por defecto usa ChromaDB con embeddings de
nomic-embed-text vía Ollama.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Resultado de una búsqueda semántica."""

    id: str
    content: str
    metadata: dict
    score: float


class VectorStorePort(ABC):
    """Interfaz para el vector store (búsqueda semántica)."""

    @abstractmethod
    async def indexar(self, doc_id: str, content: str, metadata: dict | None = None) -> None:
        """Indexa un documento en el vector store.

        Args:
            doc_id: Identificador único del documento.
            content: Texto a indexar.
            metadata: Metadatos asociados (área, tipo, tags, etc.).
        """

    @abstractmethod
    async def buscar(self, query: str, n_results: int = 5) -> list[SearchResult]:
        """Busca documentos semánticamente similares a la query.

        Args:
            query: Texto de búsqueda.
            n_results: Número máximo de resultados.

        Returns:
            Lista de SearchResult ordenados por relevancia.
        """

    @abstractmethod
    async def eliminar(self, doc_id: str) -> None:
        """Elimina un documento del índice."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica que el vector store esté operativo."""
