# Agent IA 🧠 — Copiloto de Conocimiento y Segundo Cerebro

Agent IA es un sistema multi-agente personal para la gestión automatizada de conocimiento, estudio y planificación estratégica. Construido bajo una **Arquitectura Hexagonal (Ports & Adapters)** y potenciado por LLMs locales y vector search (ChromaDB), mantiene sincronizados y enriquecidos tu **Segundo Cerebro en Notion** y tu **Vault en Obsidian**.

---

## ✨ Características Principales

* 🌐 **Interfaz Web AI-Native Moderna** (`http://localhost:8000`):
  * Diseño Dark Glassmorphism Obsidian Slate (`#090D15`).
  * Indicadores en vivo del estado de la flota de agentes.
  * Tarjetas de acción interactivas con botones **`[ Confirmar ]`** / **`[ Cancelar ]`** para propuestas que requieren aprobación.
  * Píldoras de sugerencia (*Prompt Pills*) para interacción rápida.
  * Atajos de teclado: `Ctrl + K` (foco al prompt), `Ctrl + B` (colapsar barra lateral), `Enter` (enviar), `Shift + Enter` (salto de línea).
* 🤖 **Flota de Agentes Especializados**:
  * **Hermes (Orquestador Central)**: Clasifica intenciones mediante LLM rápido, gestiona la máquina de estados de confirmación y enruta tareas hacia los agentes especializados.
  * **AgenteCurador**: Extrae taxonomía (áreas, temas, tags), detecta notas similares o duplicados mediante búsqueda semántica vectorial, y persiste notas simultáneamente en Notion y Obsidian Markdown.
  * **AgentePlan**: Desglosa metas en planes estratégicos estructurados (Objetivos, Proyectos y Tareas relacionales).
  * **AgenteEstudio**: Motor de repaso espaciado con algoritmo SuperMemo SM-2 y generación de flashcards.
  * **AgenteSync**: Motor de consistencia y sincronización bidireccional entre plataformas.
* ⚡ **Mapeo Dinámico de Notion de Ultra-Baja Latencia**:
  * Descubrimiento recursivo de las 29 bases de datos relacionales del usuario.
  * Caché persistente en disco (`data/notion_db_map.json`) con resolución en **<1 ms**.
  * Soporte nativo para `data_sources.query` y endpoints actualizados de Notion.
* 🔍 **Memoria Semántica Vectorial**:
  * Integración con **ChromaDB** y modelos de embeddings locales (`nomic-embed-text`).

---

## 🏛️ Arquitectura del Sistema

```
                         ┌─────────────────────────────────────────┐
                         │       Frontend AI-Native / HUD          │
                         │  (Web :8000 | Streamlit :8501)          │
                         └──────────────────┬──────────────────────┘
                                            │ HTTP / JSON
                                            ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           API Gateway (FastAPI :8000)                             │
├───────────────────────────────────────────────────────────────────────────────────┤
│                                Hermes (Orquestador)                               │
│                   ├── Clasificador Semántico (Dual-Model)                         │
│                   └── Máquina de Confirmaciones Pendientes                        │
├─────────────────┬───────────────────┬───────────────────┬─────────────────────────┤
│  AgenteCurador  │    AgentePlan     │   AgenteEstudio   │       AgenteSync        │
│ (Notas & Tags)  │ (Metas & Tareas)  │    (SM-2 SRS)     │  (Notion <-> Obsidian)  │
├─────────────────┴───────────────────┴───────────────────┴─────────────────────────┤
│                               Puertos (Interfaces)                                │
│   ├── LLMPort           ├── NotionPort             ├── VectorStorePort            │
│   └── ObsidianPort      └── StudyPort              └── NotificationPort           │
├───────────────────────────────────────────────────────────────────────────────────┤
│                             Adaptadores (Infraestructura)                         │
│   ├── OllamaAdapter (Llama 3.1 / Qwen / Llama 3.2)                                │
│   ├── NotionAdapter (29 Relational DBs + Disk Cache)                              │
│   ├── ObsidianAdapter (Local File System Vault)                                   │
│   └── ChromaVectorAdapter (Local Persistent Embeddings)                           │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Inicio Rápido (Windows / Linux)

### Prerrequisitos
1. **Python 3.14+**
2. **uv** (Gestor de paquetes ultrarrápido):
   ```bash
   # Windows (PowerShell):
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   # Linux:
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. **Ollama**:
   ```bash
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   # Opcional (recomendado para máxima velocidad en CPU):
   ollama pull llama3.2:3b
   ```

### 1. Instalación y Dependencias
```bash
git clone https://github.com/m1guel132/Agent-IA.git
cd "Agent IA"
uv sync
```

### 2. Variables de Entorno (`.env`)
Copia `.env.example` a `.env` y configura tus claves:
```properties
AGENT_NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxx
AGENT_NOTION_ROOT_PAGE_ID=tu_root_page_id
AGENT_OLLAMA_BASE_URL=http://localhost:11434
AGENT_OLLAMA_MODEL=llama3.1:8b
AGENT_OLLAMA_MODEL_RAPIDO=qwen3.5:4b
AGENT_OLLAMA_EMBED_MODEL=nomic-embed-text
AGENT_OBSIDIAN_VAULT_PATH=C:\Users\tu_usuario\Obsidian_Vault
AGENT_CHROMA_PERSIST_DIR=./data/chroma
AGENT_API_HOST=0.0.0.0
AGENT_API_PORT=8000
AGENT_HUD_PORT=8501
```

### 3. Ejecución

```bash
# Terminal 1 — Iniciar el API Gateway y Frontend Web AI-Native
uv run agent-api

# Terminal 2 (Opcional) — Iniciar el HUD secundario de Streamlit
uv run agent-hud
```

* **Frontend Web AI-Native**: [http://localhost:8000/](http://localhost:8000/)
* **Documentación OpenAPI / Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **HUD Streamlit**: [http://localhost:8501/](http://localhost:8501/)

---

## 🐧 Guía de Migración y Despliegue en Arch Linux

Migrar Agent IA a **Arch Linux** permite reducir drásticamente el consumo de RAM base (~500 MB frente a 5+ GB en Windows), eliminar la latencia de virtualización y aprovechar el soporte nativo de `epoll`/`uvloop` y aceleración de CPU/GPU en Linux.

### Paso 1: Instalar dependencias base en Arch Linux
```bash
sudo pacman -Syu git base-devel python python-pip curl
```

### Paso 2: Instalar `uv` y `ollama`
```bash
# Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Habilitar e iniciar el servicio de Ollama en systemd
sudo systemctl enable --now ollama
```

### Paso 3: Descargar los modelos en Ollama
```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

### Paso 4: Clonar y configurar Agent IA
```bash
git clone https://github.com/m1guel132/Agent-IA.git ~/Agent-IA
cd ~/Agent-IA

# Instalar dependencias y crear entorno virtual aislado
uv sync

# Crear .env con tus rutas de Linux
cp .env.example .env
nano .env
```
> **Nota de rutas en Linux**: Ajusta `AGENT_OBSIDIAN_VAULT_PATH=/home/tu_usuario/ObsidianVault`.

### Paso 5: Sincronizar el mapa de Notion y verificar tests
```bash
# Sincronizar bases de datos de Notion
uv run python scripts/sync_notion_map.py

# Correr toda la suite de pruebas
uv run pytest
```

### Paso 6: Ejecutar en segundo plano con `systemd` (User Services) o `tmux`
Puedes crear un servicio de usuario en `~/.config/systemd/user/agent-ia.service`:
```ini
[Unit]
Description=Agent IA API Gateway & Web Service
After=network.target ollama.service

[Service]
Type=simple
WorkingDirectory=%h/Agent-IA
ExecStart=%h/.cargo/bin/uv run agent-api
Restart=on-failure

[Install]
WantedBy=default.target
```
Habilítalo con:
```bash
systemctl --user enable --now agent-ia
```

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una suite de pruebas unitarias y de integración que validan el dominio, enrutamiento, API y Notion:

```bash
uv run pytest
```

Todos los tests se ejecutan en memoria y con mocks aislados para garantizar reproducibilidad sin dependencias externas.

---

## 🛠️ Herramientas y Scripts Útiles

* `scripts/sync_notion_map.py`: Escanea la estructura de Notion y genera la caché persistente en `data/notion_db_map.json`.
* `scripts/benchmark_models.py`: Mide latencia, tokens por segundo y validez de formato JSON de tus modelos locales de Ollama.
