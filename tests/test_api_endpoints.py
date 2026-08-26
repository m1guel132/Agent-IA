import pytest
from starlette.testclient import TestClient
from agent_ia.entrypoints.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_root_serves_html_or_json(client):
    response = client.get("/")
    assert response.status_code == 200
    # Should serve HTML or JSON status
    assert "text/html" in response.headers.get("content-type", "") or "application/json" in response.headers.get("content-type", "")


def test_app_endpoint_serves_html(client):
    response = client.get("/app")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Agent IA" in response.text
    assert "Hermes Fleet" in response.text


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
