"""Entidad ItemEstudio — tarjeta de repetición espaciada (SM-2).

Conecta el Study Board al Segundo Cerebro: una Nota puede generar
opcionalmente (0..1) un ItemEstudio para repetición espaciada (RF3.1).
El algoritmo SM-2 ajusta facilidad, intervalo y siguiente repaso
según el resultado de cada sesión (RF3.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

# Constantes del algoritmo SM-2
FACILIDAD_MINIMA = 1.3
FACILIDAD_INICIAL = 2.5


@dataclass
class ItemEstudio:
    """Tarjeta de repetición espaciada vinculada a una Nota.

    Attributes:
        id: Identificador único.
        nota_id: ID de la nota fuente.
        pregunta: Pregunta o prompt de la tarjeta.
        respuesta: Respuesta esperada.
        facilidad: Factor de facilidad SM-2 (≥ 1.3).
        intervalo: Días hasta el próximo repaso.
        repeticiones: Número de repasos exitosos consecutivos.
        sig_repaso: Fecha del próximo repaso programado.
        created_at: Fecha de creación.
    """

    id: str
    nota_id: str
    pregunta: str = ""
    respuesta: str = ""
    facilidad: float = FACILIDAD_INICIAL
    intervalo: int = 1
    repeticiones: int = 0
    sig_repaso: date = field(default_factory=date.today)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if self.facilidad < FACILIDAD_MINIMA:
            self.facilidad = FACILIDAD_MINIMA

    @property
    def repaso_pendiente(self) -> bool:
        """True si el repaso está programado para hoy o antes."""
        return date.today() >= self.sig_repaso

    def registrar_repaso(self, calidad: int) -> None:
        """Aplica el algoritmo SM-2 tras un repaso.

        Args:
            calidad: Puntuación de 0-5 (0=fallo total, 5=perfecto).
                     - 0-2: Fallo → resetear repeticiones
                     - 3: Correcto con dificultad
                     - 4: Correcto
                     - 5: Perfecto
        """
        if not 0 <= calidad <= 5:
            raise ValueError(f"La calidad debe estar entre 0 y 5, recibido: {calidad}")

        # Actualizar factor de facilidad
        self.facilidad = max(
            FACILIDAD_MINIMA,
            self.facilidad + (0.1 - (5 - calidad) * (0.08 + (5 - calidad) * 0.02)),
        )

        if calidad < 3:
            # Fallo: resetear
            self.repeticiones = 0
            self.intervalo = 1
        else:
            # Éxito: avanzar
            self.repeticiones += 1
            if self.repeticiones == 1:
                self.intervalo = 1
            elif self.repeticiones == 2:
                self.intervalo = 6
            else:
                self.intervalo = round(self.intervalo * self.facilidad)

        self.sig_repaso = date.today() + timedelta(days=self.intervalo)
