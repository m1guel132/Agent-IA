"""Test script para verificar el descubrimiento dinamico de bases
de datos y la resolucion de relaciones en Notion."""

import asyncio
import logging

from agent_ia.infrastructure.config import get_settings
from agent_ia.infrastructure.notion_adapter import NotionAdapter

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def main():
    settings = get_settings()
    adapter = NotionAdapter(settings)

    # ── Paso 1: Mapeo completo ──────────────────────────────────
    print("\n" + "=" * 60)
    print("[PASO 1] Descubriendo bases de datos y schemas...")
    print("=" * 60)

    await adapter._asegurar_mapeo()

    for nombre, info in adapter._db_map.items():
        relations_str = ", ".join(
            f"{k} -> {v[:12]}..." for k, v in info["relations"].items()
        ) or "(sin relaciones)"
        print(f"  -> {nombre}: {info['id'][:12]}... | Relaciones: {relations_str}")

    # ── Paso 2: Crear tarea sin relaciones ──────────────────────
    print("\n" + "=" * 60)
    print("[PASO 2] Creando tarea simple (sin relaciones)...")
    print("=" * 60)

    try:
        page_id = await adapter.crear_tarea(titulo="[TEST] Tarea de prueba sin relaciones")
        print(f"  -> Tarea creada: {page_id}")
    except Exception as e:
        print(f"  -> ERROR: {e}")

    # ── Paso 3: Crear tarea con relaciones ──────────────────────
    print("\n" + "=" * 60)
    print("[PASO 3] Creando tarea con relaciones...")
    print("=" * 60)

    # Ajusta estos valores a los nombres reales de tus proyectos/areas en Notion
    relaciones_test = {
        "Proyecto": "Gwen OS",
        # Puedes probar nombres adicionales si quieres
    }

    try:
        page_id = await adapter.crear_tarea(
            titulo="[TEST] Compilar modulo de relaciones dinamicas",
            relaciones=relaciones_test,
        )
        print(f"  -> Tarea creada: {page_id}")
    except Exception as e:
        print(f"  -> ERROR: {e}")

    print("\n" + "=" * 60)
    print("[OK] Test completado. Verifica en Notion.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
