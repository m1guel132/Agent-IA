"""HUD de Agent IA — Interfaz web local con Streamlit.

Implementa el wireframe del SRS: chat con Hermes a la izquierda,
panel de agentes + sistema + próximo repaso a la derecha.
Se comunica con el sistema a través del API Gateway (:8000).
"""

from __future__ import annotations

import httpx
import streamlit as st

# ──────────────────────────────────────────────────────────────
# Configuración de página
# ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Agent IA",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "http://localhost:8000"


# ──────────────────────────────────────────────────────────────
# Estilos CSS personalizados
# ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    /* Variables de color */
    :root {
        --gwen-teal: #0a5041;
        --gwen-teal-bg: #e1f5ee;
        --gwen-blue: #0c447c;
        --gwen-blue-bg: #e6f1fb;
        --gwen-amber-bg: #faeeda;
        --gwen-purple-bg: #eeedfe;
    }

    /* Header personalizado */
    .gwen-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 1rem;
        background: linear-gradient(135deg, #0a5041 0%, #0c447c 100%);
        border-radius: 8px;
        margin-bottom: 1rem;
        color: white;
    }
    .gwen-header h1 {
        margin: 0;
        font-size: 1.4rem;
        color: white;
    }
    .gwen-header .status {
        font-size: 0.85rem;
        opacity: 0.9;
    }

    /* Burbujas de chat */
    .chat-user {
        background-color: #f1efe8;
        padding: 0.7rem 1rem;
        border-radius: 12px 12px 4px 12px;
        margin: 0.5rem 0;
        margin-left: 20%;
        text-align: left;
    }
    .chat-assistant {
        background-color: #e6f1fb;
        padding: 0.7rem 1rem;
        border-radius: 12px 12px 12px 4px;
        margin: 0.5rem 0;
        margin-right: 10%;
    }
    .chat-agent-tag {
        font-size: 0.7rem;
        color: #666;
        margin-bottom: 0.3rem;
    }

    /* Panel lateral */
    .panel-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 0.8rem;
        margin-bottom: 0.8rem;
    }
    .panel-card h4 {
        margin: 0 0 0.5rem 0;
        font-size: 0.9rem;
    }

    /* Ocultar footer de Streamlit */
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────
# Estado de sesión
# ──────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_status" not in st.session_state:
    st.session_state.api_status = "desconocido"


# ──────────────────────────────────────────────────────────────
# Funciones de comunicación con la API
# ──────────────────────────────────────────────────────────────

def send_message(mensaje: str) -> dict:
    """Envía un mensaje al API Gateway y devuelve la respuesta."""
    try:
        response = httpx.post(
            f"{API_BASE}/chat/",
            json={"mensaje": mensaje},
            timeout=120.0,  # LLM puede tardar
        )
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        return {
            "estado": "error",
            "mensaje": "❌ No se pudo conectar con el API Gateway.\n\n"
            "Asegúrate de que `agent-api` esté corriendo en el puerto 8000.",
            "agente": "Sistema",
        }
    except Exception as e:
        return {
            "estado": "error",
            "mensaje": f"❌ Error de comunicación: {e}",
            "agente": "Sistema",
        }


def check_api_health() -> dict:
    """Verifica el estado del API."""
    try:
        response = httpx.get(f"{API_BASE}/health", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"estado": "inactivo", "agentes": {}}


# ──────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────

health = check_api_health()
status_icon = "🟢" if health.get("estado") == "activo" else "🔴"
status_text = "Activo" if health.get("estado") == "activo" else "API desconectada"

st.markdown(
    f"""
    <div class="gwen-header">
        <h1>🧠 Agent IA</h1>
        <span class="status">{status_icon} {status_text}</span>
    </div>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────
# Layout: Chat (izquierda) + Panel (derecha)
# ──────────────────────────────────────────────────────────────

col_chat, col_panel = st.columns([3, 1])


# ── Panel derecho ──
with col_panel:
    # Agentes
    st.markdown("#### 🤖 Agentes")
    agentes = health.get("agentes", {})
    if agentes:
        for clave, info in agentes.items():
            # Colores por agente
            color = {"curador": "🟠", "estudio": "🔵", "sync": "🟢", "plan": "🟣"}.get(clave, "⚪")
            st.markdown(f"{color} **{info}**")
    else:
        st.caption("API no conectada")

    st.divider()

    # Sistema
    st.markdown("#### ⚙️ Sistema")
    try:
        sys_info = httpx.get(f"{API_BASE}/", timeout=5.0).json()
        st.caption(f"Version: {sys_info.get('version', '?')}")
    except Exception:
        st.caption("Sin datos")

    st.divider()

    # Próximo repaso (stub)
    st.markdown("#### 📚 Próximo repaso")
    st.caption("AgenteEstudio (Fase 2)")


# ── Chat principal ──
with col_chat:
    st.markdown("### 💬 Chat con Hermes")

    # Container de mensajes
    chat_container = st.container(height=500)

    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="chat-user">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                agent_tag = f'<div class="chat-agent-tag">🤖 {msg.get("agente", "Hermes")}</div>'
                st.markdown(
                    f'<div class="chat-assistant">{agent_tag}{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )

    # Input de chat
    if prompt := st.chat_input("Escribe o dicta un mensaje..."):
        # Agregar mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Enviar al API
        with st.spinner("Hermes está pensando..."):
            response = send_message(prompt)

        # Agregar respuesta
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response.get("mensaje", "Sin respuesta"),
                "agente": response.get("agente", "Hermes"),
            }
        )

        st.rerun()


def main() -> None:
    """Entry point para el script `agent-hud`."""
    import subprocess
    import sys

    from agent_ia.infrastructure.config import get_settings

    settings = get_settings()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            __file__,
            "--server.port",
            str(settings.hud_port),
            "--server.headless",
            "true",
        ],
        check=True,
    )
