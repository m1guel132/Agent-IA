"""Tests de integración para los endpoints de la API FastAPI."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from agent_ia.entrypoints.api.main import app
from agent_ia.entrypoints.api.dependencies import get_hermes
from agent_ia.use_cases.agente import EstadoResultado, Resultado


class DummyHermes:
    def obtener_historial(self) -> list[dict]:
        return [
            {"role": "user", "content": "Hola", "agente": "", "timestamp": "2026-08-27T10:00:00"},
            {"role": "assistant", "content": "Hola Miguel", "agente": "Hermes", "timestamp": "2026-08-27T10:00:01"},
        ]

    async def procesar_mensaje(self, mensaje: str) -> Resultado:
        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=f"Eco: {mensaje}",
            agente="Hermes",
            datos={"test": True},
        )


@pytest.fixture
def client():
    app.dependency_overrides[get_hermes] = lambda: DummyHermes()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_root_serves_html_or_json(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "") or "application/json" in response.headers.get("content-type", "")


def test_app_endpoint_serves_html(client):
    response = client.get("/app")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Agent IA" in response.text


def test_static_files_accessible(client):
    res_css = client.get("/static/styles.css")
    assert res_css.status_code == 200
    assert "--agent-hermes" in res_css.text

    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "sendMessage" in res_js.text


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "activo"
    assert "agentes" in data


def test_chat_enviar_mensaje_endpoint(client):
    response = client.post("/chat/", json={"mensaje": "Hola Hermes"})
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "exito"
    assert data["mensaje"] == "Eco: Hola Hermes"
    assert data["agente"] == "Hermes"
    assert data["datos"]["test"] is True


def test_chat_historial_endpoint(client):
    response = client.get("/chat/historial")
    assert response.status_code == 200
    data = response.json()
    assert "mensajes" in data
    assert len(data["mensajes"]) == 2
    assert data["mensajes"][0]["content"] == "Hola"
