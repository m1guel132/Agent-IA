"""Puerto abstracto para el LLM local.

Define la interfaz que cualquier adaptador de modelo de lenguaje
debe implementar. Por defecto se usa Ollama (RNF2), pero el
puerto permite sustituir por otro backend sin tocar los use_cases.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Respuesta del modelo de lenguaje."""

    content: str
    model: str
    tokens_used: int = 0


class LLMPort(ABC):
    """Interfaz para interactuar con un modelo de lenguaje."""

    @abstractmethod
    async def generate(self, prompt: str, *, system: str = "", temperature: float = 0.7) -> LLMResponse:
        """Genera una respuesta a partir de un prompt.

        Args:
            prompt: El mensaje del usuario.
            system: Prompt de sistema (personalidad/instrucciones).
            temperature: Creatividad de la respuesta (0.0-1.0).

        Returns:
            LLMResponse con el contenido generado.
        """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Genera un vector de embedding para el texto dado.

        Args:
            text: Texto a convertir en embedding.

        Returns:
            Lista de floats representando el vector.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica que el servicio LLM esté activo."""
