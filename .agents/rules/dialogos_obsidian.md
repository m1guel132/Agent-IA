# Regla: Registro de Diálogos en el Segundo Cerebro (Obsidian)

1. Cada interacción y sesión técnica entre Miguel y Antigravity forma parte del conocimiento acumulado del proyecto.
2. Las conversaciones se consolidan en el Obsidian Vault en la ruta `Conversaciones/Antigravity_YYYY-MM-DD.md`.
3. Para exportar la transcripción completa de la sesión activa, se ejecuta el script:
   ```bash
   .venv\Scripts\python scripts/export_antigravity_to_obsidian.py
   ```
4. El script actualiza simultáneamente la nota en `<AGENT_OBSIDIAN_VAULT_PATH>/Conversaciones/` y la copia de respaldo en `docs/conversaciones/`.
