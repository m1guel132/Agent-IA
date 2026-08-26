"""HUD de Agent IA — Interfaz web local con Streamlit.

Implementa el wireframe del SRS: chat con Hermes a la izquierda,
panel de agentes + sistema + próximo repaso a la derecha.
Se comunica con el sistema a través del API Gateway (:8000).
"""

from __future__ import annotations

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"


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


def render_hud() -> None:
    """Renderiza la interfaz gráfica de Streamlit cuando se ejecuta dentro del contexto de Streamlit."""
    st.set_page_config(
        page_title="Agent IA",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── Estilos CSS personalizados (AI-Native Dark Theme) ──
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        :root {
            --hermes-purple: #6366f1;
            --hermes-dark-bg: #0b0f17;
            --hermes-card-bg: #121824;
            --hermes-card-border: rgba(255, 255, 255, 0.08);
            --hermes-text: #f8fafc;
            --hermes-muted: #94a3b8;
        }

        .gwen-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.9rem 1.4rem;
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 12px;
            margin-bottom: 1.25rem;
            color: white;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }
        .gwen-header h1 {
            margin: 0;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.3rem;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.02em;
        }
        .gwen-header .status {
            font-size: 0.8rem;
            font-family: monospace;
            padding: 4px 10px;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border-radius: 20px;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .chat-user {
            background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
            color: #ffffff;
            padding: 0.85rem 1.15rem;
            border-radius: 16px 16px 4px 16px;
            margin: 0.6rem 0;
            margin-left: 20%;
            text-align: left;
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.25);
        }
        .chat-assistant {
            background-color: #121824;
            color: #f1f5f9;
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 0.85rem 1.15rem;
            border-radius: 16px 16px 16px 4px;
            margin: 0.6rem 0;
            margin-right: 10%;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
        .chat-agent-tag {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.72rem;
            color: #818cf8;
            margin-bottom: 0.4rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .panel-card {
            background: #121824;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            padding: 0.9rem;
            margin-bottom: 0.8rem;
        }
        .panel-card h4 {
            margin: 0 0 0.5rem 0;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.88rem;
            color: #f8fafc;
        }

        footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Estado de sesión ──
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "api_status" not in st.session_state:
        st.session_state.api_status = "desconocido"

    # ── Header ──
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

    # ── Layout: Chat + Panel ──
    col_chat, col_panel = st.columns([3, 1])

    with col_panel:
        st.markdown("#### 🤖 Agentes")
        agentes = health.get("agentes", {})
        if agentes:
            for clave, info in agentes.items():
                color = {"curador": "🟠", "estudio": "🔵", "sync": "🟢", "plan": "🟣"}.get(clave, "⚪")
                st.markdown(f"{color} **{info}**")
        else:
            st.caption("API no conectada")

        st.divider()

        st.markdown("#### ⚙️ Sistema")
        try:
            sys_info = httpx.get(f"{API_BASE}/", timeout=5.0).json()
            st.caption(f"Version: {sys_info.get('version', '?')}")
        except Exception:
            st.caption("Sin datos")

        st.divider()

        st.markdown("#### 📚 Próximo repaso")
        st.caption("AgenteEstudio (Fase 2)")

    with col_chat:
        st.markdown("### 💬 Chat con Hermes")

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
                    if "raw_json" in msg:
                        with st.expander("Ver JSON de la respuesta"):
                            st.json(msg["raw_json"])

        if prompt := st.chat_input("Escribe o dicta un mensaje..."):
            st.session_state.messages.append({"role": "user", "content": prompt})

            with st.spinner("Hermes está pensando..."):
                response = send_message(prompt)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response.get("mensaje", "Sin respuesta"),
                    "agente": response.get("agente", "Hermes"),
                    "raw_json": response,
                }
            )
            st.rerun()


# Ejecutar render_hud() cuando Streamlit lo cargue directamente
if __name__ == "__main__" or (hasattr(st, "runtime") and st.runtime.exists()):
    render_hud()


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
