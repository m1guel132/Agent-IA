# Agent IA 🧠

Agent IA es un copiloto personal de gestión de conocimiento y estudio, construido con una arquitectura hexagonal. El sistema orquesta agentes especializados mediante LLMs locales para automatizar el mantenimiento del Segundo Cerebro (Notion + Obsidian).

## 🚀 Inicio Rápido

### Prerrequisitos
- **Python 3.14+** (instalado vía Microsoft Store o py launcher)
- **uv** (Gestor de dependencias ultrarrápido)
- **Ollama** con el modelo `llama3.1:8b` y `nomic-embed-text`
- **Docker** (Opcional, para infraestructura externa)
- **n8n** (Instalado de forma nativa)

### 1. Instalación y Configuración

Clona el proyecto o ubícate en la carpeta del repositorio y ejecuta:

```bash
# Sincroniza e instala las dependencias usando uv
uv sync
```

Luego, configura las variables de entorno. Renombra `.env.example` a `.env` e ingresa tus credenciales:

```properties
# .env
AGENT_NOTION_TOKEN=tu_token_aqui
AGENT_NOTION_DATABASE_ID=id_de_tu_db
AGENT_OLLAMA_BASE_URL=http://localhost:11434
AGENT_OLLAMA_MODEL=llama3.1:8b
AGENT_OLLAMA_EMBED_MODEL=nomic-embed-text
AGENT_OBSIDIAN_VAULT_PATH=C:\Users\migue\Agent_IA_Vault
AGENT_N8N_BASE_URL=http://localhost:5678
```

### 2. Levantar el Sistema

El sistema consta de dos procesos principales: **La API Gateway** (el cerebro) y **El HUD** (la interfaz visual).

Abre dos terminales diferentes en la carpeta del proyecto.

**Terminal 1 (Levantar la API):**
```bash
uv run agent-api
```
*(Esto levantará la API de FastAPI en el puerto 8000)*

**Terminal 2 (Levantar el HUD):**
```bash
uv run agent-hud
```
*(Esto abrirá automáticamente tu navegador en `http://localhost:8501`)*

---

## 🛠️ Cómo usar Agent IA (Manual de Usuario)

Agent IA interactúa principalmente a través de lenguaje natural en el **Chat con Hermes** desde el HUD.

### Ejemplos de uso (Fase 1 - Agente Curador)

Puedes pedirle a Agent IA que anote ideas, cree recordatorios de conocimiento o categorice apuntes. Hermes (el orquestador) entenderá la intención y llamará al **Agente Curador**.

> **Miguel:** *"Anota esto: terminé de configurar el firewall del laboratorio de Redes."*

El **Agente Curador** interceptará este mensaje, usará el LLM para detectar el área (ej. `Redes`) y te mostrará una propuesta antes de guardar:

> **Hermes:** *"📋 Propuesta de nota (ID: a3b9f1)\nÁrea sugerida: Redes\nTags: laboratorio, firewall\n¿Confirmas esta categorización?"*

Si hay notas similares, Agent IA usará **ChromaDB** para buscar coincidencias e informarte si estás creando un posible duplicado.

**Para confirmar**, simplemente responde:
> **Miguel:** *"Sí, confirmo"* o *"ok"*

Al confirmar, la nota se guardará automáticamente de forma bidireccional en:
1. **Notion:** En tu base de datos central.
2. **Obsidian:** Como un archivo `.md` en tu vault de Obsidian.

### Organizar el Inbox
Si tienes notas acumuladas en la carpeta `inbox/` de tu Obsidian, puedes pedirle a Agent IA:
> **Miguel:** *"Por favor organiza mi inbox"*

Agent IA escaneará la carpeta y te propondrá qué hacer con los archivos que aún no tienen área asignada.

---

## 🏗️ Arquitectura y Flujos n8n

Agent IA no solo es reactivo, también es proactivo gracias a **n8n**. 

En la carpeta `n8n/` del proyecto encontrarás dos flujos en formato JSON:
- `sync_periodica.json`
- `clasificador_inbox.json`

**Para importarlos:**
1. Abre tu interfaz local de n8n (`http://localhost:5678`).
2. Ve a *Workflows* -> *Import from File*.
3. Selecciona los archivos de la carpeta `n8n/`.
4. Actívalos.

Estos flujos harán peticiones HTTP directamente a `http://localhost:8000/chat` para despertar a Agent IA automáticamente de fondo (por ejemplo, cada 4 horas para revisar el inbox).

---

## 🧪 Desarrollo y Tests

Si quieres contribuir o verificar que todo esté funcionando a nivel interno, puedes correr los tests unitarios ejecutando:

```bash
uv run pytest
```

*(Esto verificará toda la lógica de dominio, el modelo matemático SM-2 y el enrutamiento de los agentes).*
