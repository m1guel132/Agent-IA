"""Exportador de conversaciones de Antigravity IDE al Segundo Cerebro (Obsidian).

Lee los transcripts de conversación de Antigravity (.gemini/antigravity-ide/brain/)
y los estructura como notas Markdown limpias dentro de:
<Obsidian_Vault>/Conversaciones/Antigravity_YYYY-MM-DD.md
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, date
from pathlib import Path

# Cargar configuración del vault desde .env si existe
VAULT_PATH = None
env_file = Path(".env")
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("AGENT_OBSIDIAN_VAULT_PATH="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    VAULT_PATH = Path(val)


def encontrar_transcripts() -> list[Path]:
    """Busca archivos transcript.jsonl en el directorio de Antigravity IDE."""
    user_home = Path.home()
    app_data_brain = user_home / ".gemini" / "antigravity-ide" / "brain"

    if not app_data_brain.exists():
        return []

    transcripts = list(app_data_brain.glob("*/.system_generated/logs/transcript.jsonl"))
    return sorted(transcripts, key=lambda p: p.stat().st_mtime, reverse=True)


def parsear_transcript(transcript_path: Path) -> list[dict]:
    """Extrae los turnos limpios de usuario y Antigravity del archivo JSONL."""
    turnos = []
    
    if not transcript_path.exists():
        return []

    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                tipo = data.get("type")
                contenido = data.get("content", "")
                created_at = data.get("created_at", datetime.now().isoformat())

                # Mensaje de Usuario
                if tipo == "USER_INPUT" and contenido:
                    # Limpiar etiquetas <USER_REQUEST> si existen
                    texto_limpio = contenido
                    if "<USER_REQUEST>" in texto_limpio:
                        m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", texto_limpio, re.DOTALL)
                        if m:
                            texto_limpio = m.group(1).strip()
                    if texto_limpio and not texto_limpio.startswith("{{ CHECKPOINT"):
                        turnos.append({
                            "rol": "Miguel",
                            "mensaje": texto_limpio,
                            "timestamp": created_at,
                        })

                # Mensaje del Asistente
                elif tipo == "PLANNER_RESPONSE" and contenido:
                    if len(contenido.strip()) > 10:
                        turnos.append({
                            "rol": "Antigravity (Asesor)",
                            "mensaje": contenido.strip(),
                            "timestamp": created_at,
                        })
            except Exception:
                continue

    return turnos


def exportar_a_obsidian() -> None:
    transcripts = encontrar_transcripts()
    if not transcripts:
        print("⚠️ No se encontraron logs de transcripción de Antigravity.")
        return

    hoy_str = date.today().isoformat()
    todos_los_turnos = []

    for t_path in transcripts:
        turnos = parsear_transcript(t_path)
        todos_los_turnos.extend(turnos)

    if not todos_los_turnos:
        print("ℹ️ No hay diálogos pendientes por exportar.")
        return

    # Construir contenido en formato Markdown para Obsidian
    lineas_md = [
        "---",
        f"id: antigravity_dialogos_{hoy_str}",
        f"titulo: Bitácora Antigravity — {hoy_str}",
        "area: Conversaciones",
        "tags: [antigravity, asesor, pair_programming, segundo_cerebro]",
        "origen: antigravity_ide",
        f"created: {datetime.now().isoformat()}",
        "---",
        "",
        f"# 🛸 Bitácora de Sesión: Miguel & Antigravity ({hoy_str})",
        "",
        "Registro de pair programming, asesoría técnica y decisiones de arquitectura.",
        "",
        "---",
        "",
    ]

    for turno in todos_los_turnos[-40:]:  # Exportar los últimos 40 turnos más relevantes
        rol = turno["rol"]
        msg = turno["mensaje"]
        ts = turno.get("timestamp", "")
        hora = ts[11:19] if len(ts) >= 19 else "Reciente"

        if rol == "Miguel":
            lineas_md.append(f"### 🕒 {hora} — 👤 Miguel")
            lineas_md.append(f"> {msg}\n")
        else:
            lineas_md.append(f"### 🛸 {hora} — 🤖 Antigravity")
            lineas_md.append(f"{msg}\n")
        lineas_md.append("---\n")

    contenido_final = "\n".join(lineas_md)

    # 1. Guardar en el Vault de Obsidian si existe
    destinos = []
    if VAULT_PATH and VAULT_PATH.exists():
        obs_dir = VAULT_PATH / "Conversaciones"
        obs_dir.mkdir(parents=True, exist_ok=True)
        obs_file = obs_dir / f"Antigravity_{hoy_str}.md"
        with open(obs_file, "w", encoding="utf-8") as f:
            f.write(contenido_final)
        destinos.append(str(obs_file))

    # 2. Guardar copia local en docs/conversaciones/
    local_dir = Path("docs/conversaciones")
    local_dir.mkdir(parents=True, exist_ok=True)
    local_file = local_dir / f"Antigravity_{hoy_str}.md"
    with open(local_file, "w", encoding="utf-8") as f:
        f.write(contenido_final)
    destinos.append(str(local_file))

    print("[OK] Conversaciones de Antigravity exportadas con exito a:")
    for d in destinos:
        print(f"  -> {d}")


if __name__ == "__main__":
    exportar_a_obsidian()
