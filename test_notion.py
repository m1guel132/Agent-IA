import asyncio
import logging
from agent_ia.infrastructure.config import get_settings
from agent_ia.infrastructure.notion_adapter import NotionAdapter

# Configurar logging para ver los prints del adaptador
logging.basicConfig(level=logging.INFO, format="%(message)s")

async def main():
    settings = get_settings()
    
    # Tomamos el ID que pusiste en el .env (que resultó ser el ID de THE GAME)
    root_page_id = settings.notion_database_id
    
    adapter = NotionAdapter(settings)
    
    print(f"\n[INFO] Escaneando la página raíz (THE GAME): {root_page_id} y sus subpáginas...\n")
    
    # Llama a la función recursiva
    bases_encontradas = await adapter.descubrir_bases_de_datos(root_page_id)
    
    print("\n" + "="*50)
    print("[OK] ESCANEO TERMINADO. Resultados:")
    print("="*50)
    
    if not bases_encontradas:
        print("No se encontró ninguna base de datos.")
    else:
        for nombre, db_id in bases_encontradas.items():
            print(f"-> {nombre}: {db_id}")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
