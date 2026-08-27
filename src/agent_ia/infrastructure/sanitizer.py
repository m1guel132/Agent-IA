"""Módulo de sanitización y ofuscación de datos locales (DataMasker).

Protege la privacidad del usuario enmascarando entidades sensibles
(credenciales, emails, números telefónicos, montos monetarios, etc.)
antes de enviar texto a modelos en la nube (como Gemini API).
Luego restituye los datos originales en las respuestas recibidas.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MaskResult:
    """Resultado del proceso de enmascaramiento."""

    masked_text: str
    mapping: dict[str, str] = field(default_factory=dict)


class DataMasker:
    """Detecta y enmascara información privada con identificadores sintéticos."""

    # Expresiones regulares para detección de entidades sensibles
    PATTERNS: list[tuple[str, re.Pattern]] = [
        # Claves API, tokens y contraseñas explícitas
        (
            "SECRET",
            re.compile(
                r"(?i)\b(?:api[_-]?key|token|password|clave|secreto|contrase[ñn]a)\s*[:=]\s*([A-Za-z0-9_\-\.]{8,})",
            ),
        ),
        # Emails
        (
            "EMAIL",
            re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            ),
        ),
        # Números telefónicos (internacionales o locales de 7 a 15 dígitos)
        (
            "PHONE",
            re.compile(
                r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}\b",
            ),
        ),
        # Cantidades de dinero / moneda (ej: $5,000 USD, 1500 €, €50, etc.)
        (
            "AMOUNT",
            re.compile(
                r"(?:\$|€|£|USD|EUR|COP|MXN|ARS)\s*[\d,.]+(?:\s*(?:mil|millones|k|USD|EUR|COP|MXN|ARS))?|\b\d[\d,.]*\s*(?:USD|EUR|COP|MXN|d[oó]lares|pesos|euros)\b",
                re.IGNORECASE,
            ),
        ),
    ]

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def mask(self, text: str) -> MaskResult:
        """Enmascara datos sensibles en el texto dado y devuelve el mapeo para restauración."""
        if not self.enabled or not text:
            return MaskResult(masked_text=text, mapping={})

        current_text = text
        mapping: dict[str, str] = {}
        counters: dict[str, int] = {}

        for entity_type, pattern in self.PATTERNS:
            def _replace_match(match: re.Match) -> str:
                # Si el patrón tiene grupos de captura (ej: secret), enmascaramos solo el valor
                if match.groups():
                    val = match.group(1)
                    full_match = match.group(0)
                else:
                    val = match.group(0)
                    full_match = val

                # Verificar si ya tenemos un token para este valor exacto
                for placeholder, original in mapping.items():
                    if original == val:
                        return full_match.replace(val, placeholder)

                counters[entity_type] = counters.get(entity_type, 0) + 1
                placeholder = f"<{entity_type}_{counters[entity_type]}>"
                mapping[placeholder] = val
                return full_match.replace(val, placeholder)

            current_text = pattern.sub(_replace_match, current_text)

        if mapping:
            logger.debug("DataMasker aplicó %d sustituciones: %s", len(mapping), list(mapping.keys()))

        return MaskResult(masked_text=current_text, mapping=mapping)

    def unmask(self, text: str, mapping: dict[str, str]) -> str:
        """Restituye los valores originales en el texto reemplazando los placeholders."""
        if not self.enabled or not text or not mapping:
            return text

        result = text
        for placeholder, original in mapping.items():
            result = result.replace(placeholder, original)

        return result
