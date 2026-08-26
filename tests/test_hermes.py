import re
import pytest
from datetime import datetime

from agent_ia.use_cases.hermes import Hermes, MensajeChat, SYSTEM_PROMPT_CONFIRMACION
from agent_ia.use_cases.agente import Agente, EstadoResultado, Resultado
from agent_ia.domain.ports.llm_port import LLMPort, LLMResponse


class MockLLM(LLMPort):
    """Fake LLM que diferencia explícitamente entre clasificación de confirmación y enrutamiento."""

    async def generate(self, prompt: str, *, system: str = "", temperature: float = 0.7) -> LLMResponse:
        # 1. ¿Es una llamada de clasificación de confirmación? (Hueco 1: inspección explícita de system)
        if "confirmar|rechazar|otro" in system or "confirmación" in system.lower():
            # Extraer respuesta del usuario del prompt
            texto_usuario = prompt.lower()
            if 'respuesta del usuario: "' in texto_usuario:
                texto_usuario = texto_usuario.split('respuesta del usuario: "')[-1].rstrip('"').strip()

            palabras = set(re.findall(r'\b\w+\b', texto_usuario))
            
            # Chequear confirmaciones (palabras o frases como "dale, va")
            if any(w in palabras for w in ["sí", "si", "dale", "va", "confirmo", "adelante", "ok", "yes", "correcto"]):
                content = '{"intencion": "confirmar", "razon": "usuario aprueba la propuesta"}'
            elif any(w in palabras for w in ["no", "cancelar", "cancela", "nope", "rechazar"]):
                content = '{"intencion": "rechazar", "razon": "usuario descarta la propuesta"}'
            else:
                content = '{"intencion": "otro", "razon": "usuario hace una pregunta o cambia de tema"}'
            
            return LLMResponse(content=content, model="mock-fast")

        # 2. Es una llamada de enrutamiento general de Hermes
        mensaje_actual = prompt.split("Mensaje actual de Miguel:")[-1].lower()
        
        if "organiza el inbox" in mensaje_actual:
            content = '{"agente": "curador", "instruccion_para_agente": "organiza el inbox", "razon": "petición explícita"}'
        elif "anota esto" in mensaje_actual or "crear nota" in mensaje_actual:
            content = '{"agente": "curador", "instruccion_para_agente": "anota esto", "razon": "creación de nota"}'
        elif "estudiar redes" in mensaje_actual:
            content = '{"agente": "estudio", "instruccion_para_agente": "generar tarjetas de redes", "razon": "quiere estudiar"}'
        elif "sincronizar" in mensaje_actual:
            content = '{"agente": "sync", "instruccion_para_agente": "sync notion obsidian", "razon": "petición de sync"}'
        else:
            content = '{"agente": "hermes", "instruccion_para_agente": "Hola, soy Hermes", "razon": "conversación general"}'
            
        return LLMResponse(content=content, model="mock-fast")

    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def health_check(self) -> bool:
        return True


class MockAgente(Agente):
    def __init__(
        self,
        nombre: str,
        dominio: str,
        simular_error: bool = False,
        requiere_confirmacion: bool = False,
        titulo_propuesta: str = "Nota de prueba",
    ):
        super().__init__(nombre=nombre, dominio=dominio)
        self.simular_error = simular_error
        self.requiere_confirmacion = requiere_confirmacion
        self.titulo_propuesta = titulo_propuesta
        self.confirmado_con_id: str | None = None

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        if self.simular_error:
            raise RuntimeError("Error simulado en agente")

        ctx = contexto or {}
        if ctx.get("confirmar_propuesta"):
            self.confirmado_con_id = ctx["confirmar_propuesta"]
            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=f"✅ {self.nombre} aplicó propuesta {ctx['confirmar_propuesta']}",
                agente=self.nombre,
            )

        if self.requiere_confirmacion:
            prop_id = f"prop-{self.titulo_propuesta.replace(' ', '_')}"
            return Resultado(
                estado=EstadoResultado.REQUIERE_CONFIRMACION,
                mensaje=f"📋 Propuesta de {self.titulo_propuesta}",
                datos={
                    "propuesta_id": prop_id,
                    "nota": {"titulo": self.titulo_propuesta, "area": "Redes"},
                },
                accion_pendiente=f"Crear nota '{self.titulo_propuesta}'",
                agente=self.nombre,
            )
            
        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=f"{self.nombre} ejecutó: {instruccion}",
            agente=self.nombre,
        )


@pytest.mark.asyncio
async def test_hermes_enrutamiento():
    llm = MockLLM()
    hermes = Hermes(llm=llm)
    
    hermes.registrar_agente("curador", MockAgente("AgenteCurador", "Nota"))
    hermes.registrar_agente("estudio", MockAgente("AgenteEstudio", "Estudio"))
    
    # Prueba 1: Delegar a curador
    res1 = await hermes.procesar_mensaje("Por favor organiza el inbox")
    assert res1.agente == "AgenteCurador"
    assert "ejecutó: organiza el inbox" in res1.mensaje
    
    # Prueba 2: Delegar a estudio
    res2 = await hermes.procesar_mensaje("Quiero estudiar redes")
    assert res2.agente == "AgenteEstudio"
    
    # Prueba 3: Conversación general (lo maneja Hermes)
    res3 = await hermes.procesar_mensaje("Hola ¿cómo estás?")
    assert res3.agente == "Hermes"
    assert res3.mensaje == "Hola, soy Hermes"


@pytest.mark.asyncio
async def test_hermes_falla_aislada():
    llm = MockLLM()
    hermes = Hermes(llm=llm)
    
    # Agente defectuoso
    hermes.registrar_agente("sync", MockAgente("AgenteSync", "Sync", simular_error=True))
    
    # La llamada no debe romper el orquestador
    res = await hermes.procesar_mensaje("sincronizar mis cosas")
    assert res.estado == EstadoResultado.ERROR
    assert res.agente == "AgenteSync"
    assert "encontró un error: Error simulado" in res.mensaje


@pytest.mark.asyncio
async def test_hermes_confirmacion_exacta_si_y_no():
    """Regresión: 'sí' y 'no' literales siguen confirmando y cancelando como siempre."""
    llm = MockLLM()
    hermes = Hermes(llm=llm)
    curador = MockAgente("AgenteCurador", "Nota", requiere_confirmacion=True, titulo_propuesta="Protocolo TCP")
    hermes.registrar_agente("curador", curador)

    # 1. Proponer nota
    res1 = await hermes.procesar_mensaje("anota esto: Protocolo TCP")
    assert res1.estado == EstadoResultado.REQUIERE_CONFIRMACION
    assert hermes._propuesta_activa is not None

    # 2. Confirmar con "sí"
    res2 = await hermes.procesar_mensaje("sí")
    assert res2.estado == EstadoResultado.EXITO
    assert curador.confirmado_con_id == "prop-Protocolo_TCP"
    assert hermes._propuesta_activa is None

    # 3. Proponer otra nota y cancelar con "no"
    curador.titulo_propuesta = "Protocolo UDP"
    await hermes.procesar_mensaje("anota esto: Protocolo UDP")
    assert hermes._propuesta_activa is not None
    res_cancel = await hermes.procesar_mensaje("no")
    assert res_cancel.estado == EstadoResultado.SIN_ACCION
    assert "cancelada" in res_cancel.mensaje.lower()
    assert hermes._propuesta_activa is None


@pytest.mark.asyncio
async def test_hermes_confirmacion_coloquial_llm():
    """Nuevo: respuesta afirmativa coloquial (ej. 'dale, va') confirma vía clasificador LLM."""
    llm = MockLLM()
    hermes = Hermes(llm=llm)
    curador = MockAgente("AgenteCurador", "Nota", requiere_confirmacion=True, titulo_propuesta="Cálculo Vectorial")
    hermes.registrar_agente("curador", curador)

    # 1. Proponer nota
    res1 = await hermes.procesar_mensaje("anota esto: Cálculo Vectorial")
    assert res1.estado == EstadoResultado.REQUIERE_CONFIRMACION

    # 2. Confirmar con frase coloquial
    res2 = await hermes.procesar_mensaje("dale, va")
    assert res2.estado == EstadoResultado.EXITO
    assert "aplicó propuesta prop-Cálculo_Vectorial" in res2.mensaje
    assert hermes._propuesta_activa is None


@pytest.mark.asyncio
async def test_hermes_mensaje_no_relacionado_mantiene_propuesta_y_recuerda():
    """Nuevo: mensaje no relacionado se responde normal, propuesta sigue viva y se añade recordatorio."""
    llm = MockLLM()
    hermes = Hermes(llm=llm)
    curador = MockAgente("AgenteCurador", "Nota", requiere_confirmacion=True, titulo_propuesta="Arquitectura Hexagonal")
    hermes.registrar_agente("curador", curador)

    # 1. Proponer nota
    res1 = await hermes.procesar_mensaje("anota esto: Arquitectura Hexagonal")
    assert res1.estado == EstadoResultado.REQUIERE_CONFIRMACION
    assert hermes._propuesta_activa is not None

    # 2. El usuario hace una pregunta no relacionada
    res2 = await hermes.procesar_mensaje("Hola ¿cómo estás?")
    assert res2.estado == EstadoResultado.EXITO
    assert res2.agente == "Hermes"
    assert "Hola, soy Hermes" in res2.mensaje
    # Validar que incluye el recordatorio con el título de la propuesta pendiente
    assert "Arquitectura Hexagonal" in res2.mensaje
    assert "propuesta pendiente" in res2.mensaje.lower()
    # Validar que la propuesta SIGUE VIVA en Hermes
    assert hermes._propuesta_activa is not None
    assert hermes._propuesta_activa["propuesta_id"] == "prop-Arquitectura_Hexagonal"

    # 3. Tras el desvío, el usuario confirma la propuesta original
    res3 = await hermes.procesar_mensaje("sí, confirmo")
    assert res3.estado == EstadoResultado.EXITO
    assert curador.confirmado_con_id == "prop-Arquitectura_Hexagonal"
    assert hermes._propuesta_activa is None


@pytest.mark.asyncio
async def test_hermes_segunda_propuesta_advierte_reemplazo():
    """Guardia (Hueco 2): si una 2da propuesta reemplaza una pendiente, se advierte en el mensaje."""
    llm = MockLLM()
    hermes = Hermes(llm=llm)
    curador1 = MockAgente("AgenteCurador", "Nota", requiere_confirmacion=True, titulo_propuesta="Nota Uno")
    hermes.registrar_agente("curador", curador1)

    # 1. Primera propuesta
    res1 = await hermes.procesar_mensaje("anota esto: Nota Uno")
    assert res1.estado == EstadoResultado.REQUIERE_CONFIRMACION
    assert hermes._propuesta_activa["propuesta_id"] == "prop-Nota_Uno"

    # 2. Segunda propuesta mientras la primera estaba pendiente
    curador1.titulo_propuesta = "Nota Dos"
    res2 = await hermes.procesar_mensaje("anota esto: Nota Dos")
    assert res2.estado == EstadoResultado.REQUIERE_CONFIRMACION
    # Validar advertencia sobre la nota anterior reemplazada
    assert "Nota Uno" in res2.mensaje
    assert "reemplazada como foco activo" in res2.mensaje
    # El nuevo foco es Nota Dos
    assert hermes._propuesta_activa["propuesta_id"] == "prop-Nota_Dos"
