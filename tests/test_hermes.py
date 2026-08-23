import pytest
from datetime import datetime

from agent_ia.use_cases.hermes import Hermes, MensajeChat
from agent_ia.use_cases.agente import Agente, EstadoResultado, Resultado
from agent_ia.domain.ports.llm_port import LLMPort, LLMResponse


class MockLLM(LLMPort):
    async def generate(self, prompt: str, *, system: str = "", temperature: float = 0.7) -> LLMResponse:
        # Extraer el mensaje actual del prompt (después de "Mensaje actual de Miguel:")
        mensaje_actual = prompt.split("Mensaje actual de Miguel:")[-1].lower()
        
        # Responder con JSON simulando a Hermes
        if "organiza el inbox" in mensaje_actual:
            content = '{"agente": "curador", "instruccion_para_agente": "organiza el inbox", "razon": "petición explícita"}'
        elif "estudiar redes" in mensaje_actual:
            content = '{"agente": "estudio", "instruccion_para_agente": "generar tarjetas de redes", "razon": "quiere estudiar"}'
        elif "sincronizar" in mensaje_actual:
            content = '{"agente": "sync", "instruccion_para_agente": "sync notion obsidian", "razon": "petición de sync"}'
        else:
            content = '{"agente": "hermes", "instruccion_para_agente": "Hola, soy Hermes", "razon": "conversación general"}'
            
        return LLMResponse(content=content, model="mock")

    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def health_check(self) -> bool:
        return True


class MockAgente(Agente):
    def __init__(self, nombre: str, dominio: str, simular_error: bool = False):
        super().__init__(nombre=nombre, dominio=dominio)
        self.simular_error = simular_error

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        if self.simular_error:
            raise RuntimeError("Error simulado en agente")
            
        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=f"{self.nombre} ejecutó: {instruccion}",
            agente=self.nombre
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
