"""Clase abstracta Agente — base de todos los agentes especializados.

Define la interfaz y el contrato que todo agente debe cumplir.
Vive en domain/ conceptualmente, pero se implementa en use_cases/
porque contiene lógica de negocio (RF5.1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class EstadoResultado(StrEnum):
    """Estado del resultado de una ejecución de agente."""

    EXITO = "exito"
    REQUIERE_CONFIRMACION = "requiere_confirmacion"
    ERROR = "error"
    SIN_ACCION = "sin_accion"


@dataclass
class Resultado:
    """Resultado de la ejecución de un agente.

    Attributes:
        estado: Estado del resultado.
        mensaje: Mensaje descriptivo para el usuario.
        datos: Datos estructurados del resultado.
        accion_pendiente: Descripción de la acción que requiere confirmación.
        agente: Nombre del agente que generó el resultado.
        timestamp: Momento de la ejecución.
    """

    estado: EstadoResultado
    mensaje: str
    datos: dict = field(default_factory=dict)
    accion_pendiente: str | None = None
    agente: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class Agente(ABC):
    """Clase abstracta base para todos los agentes especializados.

    Cada agente opera sobre una porción distinta del modelo de dominio
    y sobreescribe ejecutar() con su lógica específica.
    """

    def __init__(self, nombre: str, dominio: str) -> None:
        """Inicializa el agente.

        Args:
            nombre: Nombre identificador del agente.
            dominio: Descripción de qué parte del dominio opera.
        """
        self.nombre = nombre
        self.dominio = dominio

    @abstractmethod
    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        """Ejecuta una instrucción dentro del dominio del agente.

        Args:
            instruccion: Lo que se le pide al agente (en lenguaje natural).
            contexto: Información adicional para la ejecución.

        Returns:
            Resultado de la ejecución.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(nombre='{self.nombre}', dominio='{self.dominio}')"
