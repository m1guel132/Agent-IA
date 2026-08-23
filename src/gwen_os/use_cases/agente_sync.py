"""AgenteSync — sincronización bidireccional (stub Fase 3).

Será responsable de:
- Sincronizar Notion ↔ Obsidian (RF1.1)
- Sincronizar tareas con Todoist (RF6.1)
- Sincronizar eventos con Google Calendar (RF6.2)
"""

from __future__ import annotations

from gwen_os.use_cases.agente import Agente, EstadoResultado, Resultado


class AgenteSync(Agente):
    """Stub del AgenteSync — se implementará en Fase 3."""

    def __init__(self) -> None:
        super().__init__(nombre="AgenteSync", dominio="Nota, Área")

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        return Resultado(
            estado=EstadoResultado.SIN_ACCION,
            mensaje="🔄 AgenteSync aún no implementado (Fase 3). "
            "Próximamente: sincronización Notion↔Obsidian, Todoist, "
            "y Google Calendar.",
            agente=self.nombre,
        )
