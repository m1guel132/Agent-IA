"""AgentePlan — planificación y gestión de tareas (stub Fase 3).

Será responsable de:
- Recordatorios proactivos de tareas próximas (RF6.3)
- Planificación semanal/diaria
- Coordinación con Todoist y Calendar
"""

from __future__ import annotations

from gwen_os.use_cases.agente import Agente, EstadoResultado, Resultado


class AgentePlan(Agente):
    """Stub del AgentePlan — se implementará en Fase 3."""

    def __init__(self) -> None:
        super().__init__(nombre="AgentePlan", dominio="Tarea")

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        return Resultado(
            estado=EstadoResultado.SIN_ACCION,
            mensaje="📅 AgentePlan aún no implementado (Fase 3). "
            "Próximamente: planificación, recordatorios proactivos, "
            "y coordinación con Todoist + Calendar.",
            agente=self.nombre,
        )
