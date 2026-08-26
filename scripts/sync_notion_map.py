import asyncio
import json
import sys
from pathlib import Path
from agent_ia.infrastructure.config import get_settings
from agent_ia.infrastructure.notion_adapter import NotionAdapter

sys.stdout.reconfigure(encoding="utf-8")

async def sync_map():
    settings = get_settings()
    adapter = NotionAdapter(settings)
    
    print(f"Sincronizando mapa de bases de datos desde root_page_id: {adapter._root_page_id}...", flush=True)
    await adapter._asegurar_mapeo(force=True)
    
    cache_file = Path(settings.chroma_persist_dir).resolve().parent / "notion_db_map.json"
    print(f"✅ Mapeo completado y guardado en {cache_file}", flush=True)
    print(f"Total bases registradas: {len(adapter._db_map)}", flush=True)
    for name, data in adapter._db_map.items():
        rel_keys = list(data.get("relations", {}).keys())
        print(f"  • {name} (ID: {data['id']}) - Relaciones: {rel_keys}", flush=True)

if __name__ == "__main__":
    asyncio.run(sync_map())
