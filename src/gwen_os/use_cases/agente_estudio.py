"""AgenteEstudio — gestión del Study Board (stub Fase 2).

Será responsable de:
- Generar tarjetas de repetición espaciada (SM-2) desde las notas (RF3.1)
- Notificar repasos pendientes (RF3.2)
- Plantillas Cornell (RF3.3)
- Registrar resultados de repasos (RF3.4)
"""

from __future__ import annotations

from gwen_os.use_cases.agente import Agente, EstadoResultado, Resultado


class AgenteEstudio(Agente):
    """Stub del AgenteEstudio — se implementará en Fase 2."""

    def __init__(self) -> None:
        super().__init__(nombre="AgenteEstudio", dominio="ItemEstudio")

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        return Resultado(
            estado=EstadoResultado.SIN_ACCION,
            mensaje="📚 AgenteEstudio aún no implementado (Fase 2). "
            "Próximamente: repetición espaciada SM-2, tarjetas de repaso, "
            "y plantillas Cornell.",
            agente=self.nombre,
        )
