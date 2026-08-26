"""Adaptador de Notion — implementación del puerto NotionPort.

Usa la librería oficial notion-client para interactuar con la API
de Notion. El token de integración y el root_page_id se leen
de la configuración centralizada.

El adaptador descubre dinámicamente todas las bases de datos dentro
de la página raíz, inspecciona sus schemas para detectar relaciones,
y resuelve vínculos por título con fuzzy matching.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import unicodedata
from datetime import date
from pathlib import Path

from notion_client import AsyncClient as NotionAsyncClient

from agent_ia.domain.entities import Area, Nota, Tarea
from agent_ia.domain.entities.area import TipoArea
from agent_ia.domain.entities.tarea import EstadoTarea
from agent_ia.domain.ports.notion_port import NotionPort
from agent_ia.infrastructure.config import Settings

logger = logging.getLogger(__name__)


# ── Utilidades ──────────────────────────────────────────────────


def _normalizar(texto: str) -> str:
    """Normaliza texto: lowercase + sin tildes."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()


# ── Adaptador ───────────────────────────────────────────────────


class NotionAdapter(NotionPort):
    """Adaptador concreto de la API de Notion con descubrimiento dinámico y cache persistente."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = NotionAsyncClient(auth=settings.notion_token)
        self._root_page_id = settings.notion_root_page_id
        self._lock = asyncio.Lock()

        # Cache en disco para mapeo de bases de datos
        self._cache_file = Path(settings.chroma_persist_dir).resolve().parent / "notion_db_map.json"

        # Mapa de bases de datos: {"Notas": {"id": "...", "data_source_id": "...", "relations": {...}}}
        self._db_map: dict[str, dict] = {}
        self._cargar_cache_disco()

        # Cache de título→page_id por base de datos (se llena bajo demanda).
        # Estructura: {"db_id_abc": {"proyecto gwen os": "page_id_xyz", ...}}
        self._title_cache: dict[str, dict[str, str]] = {}

    def _cargar_cache_disco(self) -> None:
        """Carga el mapa de bases de datos desde el archivo local si existe."""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._db_map = json.load(f)
                logger.info("Mapeo de Notion cargado desde cache en disco (%d bases)", len(self._db_map))
            except Exception as e:
                logger.warning("No se pudo leer cache de Notion en disco: %s", e)

    def _guardar_cache_disco(self) -> None:
        """Persiste el mapa de bases de datos a disco."""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._db_map, f, indent=2, ensure_ascii=False)
            logger.debug("Mapeo de Notion guardado en disco (%s)", self._cache_file)
        except Exception as e:
            logger.warning("No se pudo guardar cache de Notion en disco: %s", e)

    # ── Descubrimiento recursivo ────────────────────────────────

    async def descubrir_bases_de_datos(
        self, block_id: str, *, _depth: int = 0, max_depth: int = 20,
    ) -> dict[str, str]:
        """Recorre recursivamente las subpáginas buscando bases de datos.

        Retorna un diccionario: {"Nombre de la BD": "ID_DE_LA_BD"}.
        Las bases llamadas "Untitled" se ignoran para evitar colisiones.
        """
        if _depth >= max_depth:
            return {}

        bases_encontradas: dict[str, str] = {}
        _TIPOS_ESTRUCTURALES = {"child_page", "column_list", "column"}

        try:
            response = await self._client.blocks.children.list(block_id=block_id)
        except Exception as e:
            logger.warning("No se pudo leer el bloque %s: %s", block_id, e)
            return {}

        for bloque in response.get("results", []):
            tipo = bloque.get("type")
            bloque_id = bloque.get("id")

            if tipo == "child_database":
                titulo = bloque["child_database"]["title"]
                if titulo and titulo.strip() and titulo.strip() != "Untitled":
                    bases_encontradas[titulo.strip()] = bloque_id
                    logger.debug("Base de datos descubierta: %s -> %s", titulo, bloque_id)

            elif tipo in _TIPOS_ESTRUCTURALES and bloque.get("has_children"):
                bases_hijas = await self.descubrir_bases_de_datos(
                    bloque_id, _depth=_depth + 1, max_depth=max_depth,
                )
                bases_encontradas.update(bases_hijas)

        return bases_encontradas

    # ── Lazy loading + introspección de schema ──────────────────

    async def _asegurar_mapeo(self, force: bool = False) -> None:
        """Descubre bases de datos y sus relaciones si no se ha hecho aún o si se fuerza refresh."""
        async with self._lock:
            if self._db_map and not force:
                return

            if not force and self._cache_file.exists():
                self._cargar_cache_disco()
                if self._db_map:
                    return

            logger.info("Iniciando escaneo de bases de datos en Notion desde root: %s", self._root_page_id)
            bases_raw = await self.descubrir_bases_de_datos(self._root_page_id)

            nuevos_mapas: dict[str, dict] = {}
            for nombre_db, db_id in bases_raw.items():
                relations: dict[str, str] = {}
                data_source_id: str | None = None
                try:
                    db_info = await self._client.databases.retrieve(database_id=db_id)
                    properties = db_info.get("properties")

                    if not properties and "data_sources" in db_info:
                        data_sources = db_info["data_sources"]
                        if data_sources:
                            ds_id = data_sources[0]["id"]
                            data_source_id = ds_id
                            ds_info = await self._client.data_sources.retrieve(data_source_id=ds_id)
                            properties = ds_info.get("properties", {})

                    if not properties:
                        properties = {}

                    for prop_name, prop_def in properties.items():
                        if prop_def.get("type") == "relation":
                            related_db_id = prop_def["relation"]["database_id"]
                            relations[prop_name] = related_db_id
                except Exception as e:
                    logger.warning("No se pudo leer schema de '%s': %s", nombre_db, e)

                nuevos_mapas[nombre_db] = {
                    "id": db_id,
                    "data_source_id": data_source_id,
                    "relations": relations,
                }

            self._db_map = nuevos_mapas
            self._guardar_cache_disco()

            logger.info(
                "Mapeo completado: %d bases descubiertas, %d con relaciones",
                len(self._db_map),
                sum(1 for v in self._db_map.values() if v.get("relations")),
            )

    async def _obtener_db_id(self, nombre_base: str) -> str:
        """Obtiene el ID de una base de datos por nombre con resolución flexible."""
        await self._asegurar_mapeo()

        # 1. Match exacto
        entry = self._db_map.get(nombre_base)
        if entry and isinstance(entry, dict):
            return entry["id"]

        # 2. Match normalizado (case-insensitive, sin tildes)
        nombre_norm = _normalizar(nombre_base)
        for nombre, info in self._db_map.items():
            if _normalizar(nombre) == nombre_norm:
                return info["id"]

        # 3. Match parcial / fuzzy
        for nombre, info in self._db_map.items():
            k_norm = _normalizar(nombre)
            if nombre_norm in k_norm or k_norm in nombre_norm:
                return info["id"]

        # 4. Fallback: forzar refresh por si la base es nueva
        logger.info("Base '%s' no encontrada en cache, refrescando mapeo...", nombre_base)
        await self._asegurar_mapeo(force=True)

        for nombre, info in self._db_map.items():
            if _normalizar(nombre) == nombre_norm or nombre_norm in _normalizar(nombre):
                return info["id"]

        bases_disponibles = list(self._db_map.keys())
        raise KeyError(
            f"Base de datos '{nombre_base}' no encontrada en el mapa. Bases disponibles: {bases_disponibles}"
        )

    # ── Resolución de títulos (fuzzy matching) ──────────────────

    async def _poblar_cache_titulos(self, db_id: str) -> None:
        """Consulta todas las páginas de una base y cachea titulo_normalizado → page_id."""
        try:
            resultados = await self.consultar_database(db_id)
        except Exception as e:
            logger.warning("No se pudo consultar base %s para cache de títulos: %s", db_id, e)
            self._title_cache[db_id] = {}
            return

        cache: dict[str, str] = {}
        for page in resultados:
            props = page.get("properties", {})
            for prop_def in props.values():
                if prop_def.get("type") == "title":
                    titulo_raw = "".join(
                        t.get("plain_text", "") for t in prop_def.get("title", [])
                    )
                    if titulo_raw:
                        cache[_normalizar(titulo_raw)] = page["id"]
                    break

        self._title_cache[db_id] = cache
        logger.info("Cache de títulos para %s: %d entradas", db_id, len(cache))

    async def _resolver_page_id(self, nombre_base: str, titulo: str) -> str | None:
        """Resuelve el page_id de una página en `nombre_base` dado su título.

        Estrategia:
        1. Normalizar texto (lowercase, sin tildes).
        2. Match exacto contra cache de títulos de esa base.
        3. Fuzzy matching con difflib.get_close_matches(cutoff=0.8) como fallback.
        4. Si no hay match o hay ambigüedad, loguea warning y retorna None.
        5. Si el título no está en cache, refresca consultando Notion en vivo.
        """
        await self._asegurar_mapeo()

        # Obtener db_id
        entry = self._db_map.get(nombre_base)
        if not entry:
            db_id = nombre_base  # fallback: tratar como db_id directo
        else:
            db_id = entry["id"]

        titulo_norm = _normalizar(titulo)

        # Poblar cache si está vacío para esta base
        if db_id not in self._title_cache:
            await self._poblar_cache_titulos(db_id)

        cache = self._title_cache.get(db_id, {})

        # 1. Match exacto
        if titulo_norm in cache:
            return cache[titulo_norm]

        # 2. Fuzzy matching
        candidatos = difflib.get_close_matches(titulo_norm, cache.keys(), n=2, cutoff=0.8)

        if len(candidatos) == 1:
            logger.info("Fuzzy match: '%s' -> '%s'", titulo, candidatos[0])
            return cache[candidatos[0]]

        if len(candidatos) > 1:
            logger.warning(
                "Ambiguedad al resolver '%s' en base '%s': candidatos=%s. Omitiendo relacion.",
                titulo, nombre_base, candidatos,
            )
            return None

        # 3. Fallback: consulta en vivo (por si la página se creó después del cache)
        logger.info("Titulo '%s' no encontrado en cache, consultando Notion en vivo...", titulo)
        await self._poblar_cache_titulos(db_id)
        cache = self._title_cache.get(db_id, {})

        if titulo_norm in cache:
            return cache[titulo_norm]

        logger.warning("No se pudo resolver '%s' en base '%s'. Omitiendo relacion.", titulo, nombre_base)
        return None

    # ── Notas ───────────────────────────────────────────────────

    async def crear_pagina(self, nota: Nota) -> str:
        """Crea una página en Notion a partir de una Nota (base 'Notas')."""
        db_id = await self._obtener_db_id("Notas")

        properties: dict = {
            "title": {
                "title": [{"text": {"content": nota.titulo}}],
            },
        }

        if nota.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in nota.tags],
            }

        try:
            response = await self._client.pages.create(
                parent={"database_id": db_id},
                properties=properties,
                children=[
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": nota.contenido or ""}}],
                        },
                    }
                ],
            )
        except Exception as e:
            # Fallback si la propiedad "Tags" no existe en la DB
            if "is not a property that exists" in str(e) and "Tags" in properties:
                logger.warning("Propiedad 'Tags' no existe en Notion. Reintentando sin tags...")
                del properties["Tags"]
                response = await self._client.pages.create(
                    parent={"database_id": db_id},
                    properties=properties,
                    children=[
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"text": {"content": nota.contenido or ""}}],
                            },
                        }
                    ],
                )
            else:
                raise

        page_id = response["id"]
        nota.notion_page_id = page_id
        logger.info("Página creada en Notion: %s (id=%s)", nota.titulo, page_id)
        return page_id

    async def obtener_pagina(self, page_id: str) -> dict:
        """Obtiene los datos crudos de una página."""
        return await self._client.pages.retrieve(page_id=page_id)

    async def actualizar_pagina(self, page_id: str, propiedades: dict) -> None:
        """Actualiza propiedades de una página existente."""
        await self._client.pages.update(page_id=page_id, properties=propiedades)
        logger.debug("Página actualizada: %s", page_id)

    # ── Base de datos ───────────────────────────────────────────

    async def consultar_database(
        self,
        database_id: str,
        filtro: dict | None = None,
        orden: list[dict] | None = None,
    ) -> list[dict]:
        """Consulta una base de datos con filtros opcionales soportando databases y data_sources."""
        filter_kwargs: dict = {}
        if filtro:
            filter_kwargs["filter"] = filtro
        if orden:
            filter_kwargs["sorts"] = orden

        # Caso 1: API con databases.query tradicional
        if hasattr(self._client.databases, "query"):
            try:
                kwargs = {"database_id": database_id, **filter_kwargs}
                resultados = []
                response = await self._client.databases.query(**kwargs)
                resultados.extend(response.get("results", []))
                while response.get("has_more"):
                    response = await self._client.databases.query(
                        **kwargs, start_cursor=response["next_cursor"]
                    )
                    resultados.extend(response.get("results", []))
                return resultados
            except Exception as e:
                logger.debug("databases.query falló (%s), intentando vía data_sources...", e)

        # Caso 2: API reciente vía data_sources.query
        ds_id = database_id
        # Buscar si tenemos el data_source_id en el mapa
        for info in self._db_map.values():
            if isinstance(info, dict) and info.get("id") == database_id and info.get("data_source_id"):
                ds_id = info["data_source_id"]
                break

        if ds_id == database_id and hasattr(self._client, "databases"):
            try:
                db_info = await self._client.databases.retrieve(database_id=database_id)
                if "data_sources" in db_info and db_info["data_sources"]:
                    ds_id = db_info["data_sources"][0]["id"]
            except Exception as e:
                logger.warning("No se pudo obtener data_source para base %s: %s", database_id, e)

        if hasattr(self._client, "data_sources"):
            kwargs = {"data_source_id": ds_id, **filter_kwargs}
            resultados = []
            response = await self._client.data_sources.query(**kwargs)
            resultados.extend(response.get("results", []))
            while response.get("has_more"):
                response = await self._client.data_sources.query(
                    **kwargs, start_cursor=response["next_cursor"]
                )
                resultados.extend(response.get("results", []))
            return resultados

        return []

    # ── Áreas ───────────────────────────────────────────────────

    async def listar_areas(self) -> list[Area]:
        """Lista todas las áreas del Segundo Cerebro (base 'Areas')."""
        db_id = await self._obtener_db_id("Areas")
        resultados = await self.consultar_database(db_id)
        areas = []

        for page in resultados:
            try:
                props = page.get("properties", {})
                title_prop = props.get("Name", props.get("title", props.get("Nombre", {})))
                titulo = ""
                if title_prop and "title" in title_prop:
                    titulo = "".join(
                        t.get("plain_text", "") for t in title_prop["title"]
                    )

                areas.append(
                    Area(
                        id=page["id"],
                        nombre=titulo or "Sin nombre",
                        tipo=TipoArea.ACADEMICA,
                        notion_page_id=page["id"],
                    )
                )
            except (KeyError, TypeError) as e:
                logger.warning("Error parseando área de Notion: %s", e)
                continue

        return areas

    # ── Tareas ──────────────────────────────────────────────────

    async def listar_tareas_pendientes(self) -> list[Tarea]:
        """Lista tareas pendientes de Notion (base 'Tareas')."""
        db_id = await self._obtener_db_id("Tareas")

        filtro = {
            "property": "Status",
            "status": {"does_not_equal": "Done"},
        }

        try:
            resultados = await self.consultar_database(db_id, filtro=filtro)
        except Exception:
            logger.warning("Filtro de status no disponible, consultando sin filtro")
            resultados = await self.consultar_database(db_id)

        tareas = []
        for page in resultados:
            try:
                props = page.get("properties", {})
                title_prop = props.get("Name", props.get("title", props.get("Nombre", {})))
                titulo = ""
                if title_prop and "title" in title_prop:
                    titulo = "".join(
                        t.get("plain_text", "") for t in title_prop["title"]
                    )

                fecha_limite = None
                date_prop = props.get("Due", props.get("Fecha", props.get("Date", {})))
                if date_prop and "date" in date_prop and date_prop["date"]:
                    fecha_str = date_prop["date"].get("start", "")
                    if fecha_str:
                        fecha_limite = date.fromisoformat(fecha_str)

                tareas.append(
                    Tarea(
                        id=page["id"],
                        titulo=titulo or "Sin título",
                        estado=EstadoTarea.PENDIENTE,
                        fecha_limite=fecha_limite,
                        notion_page_id=page["id"],
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Error parseando tarea de Notion: %s", e)
                continue

        return tareas

    async def _crear_elemento(
        self,
        base_nombre: str,
        titulo: str,
        relaciones: dict[str, str] | None = None,
    ) -> str:
        """Helper genérico para crear un elemento en una base de datos específica."""
        await self._asegurar_mapeo()
        db_id = await self._obtener_db_id(base_nombre)

        properties: dict = {
            "title": {"title": [{"text": {"content": titulo}}]},
        }

        # Resolver relaciones dinámicamente
        if relaciones:
            base_entry = self._db_map.get(base_nombre, {})
            schema_relations = base_entry.get("relations", {})

            for prop_name, titulo_objetivo in relaciones.items():
                if prop_name not in schema_relations:
                    logger.warning(
                        "Propiedad '%s' no es una relación conocida en %s. Omitiendo.",
                        prop_name,
                        base_nombre,
                    )
                    continue

                related_db_id = schema_relations[prop_name]

                # Buscar el nombre de la base relacionada para el resolver
                nombre_base_relacionada = None
                for name, entry in self._db_map.items():
                    if entry["id"] == related_db_id:
                        nombre_base_relacionada = name
                        break

                target = nombre_base_relacionada or related_db_id
                page_id = await self._resolver_page_id(target, titulo_objetivo)

                if page_id:
                    properties[prop_name] = {"relation": [{"id": page_id}]}
                    logger.info(
                        "Relación resuelta: %s -> '%s' (page_id=%s)",
                        prop_name, titulo_objetivo, page_id,
                    )

        try:
            response = await self._client.pages.create(
                parent={"database_id": db_id},
                properties=properties,
            )
            logger.info("Elemento creado en Notion (%s): %s", base_nombre, titulo)
            return response["id"]
        except Exception as e:
            logger.error("Error al crear elemento '%s' en %s: %s", titulo, base_nombre, e)
            raise RuntimeError(f"Error creando elemento en Notion: {e}") from e

    async def crear_tarea(
        self,
        titulo: str,
        relaciones: dict[str, str] | None = None,
    ) -> str:
        """Crea una tarea en la base de datos 'Tareas' de Notion."""
        return await self._crear_elemento("Tareas", titulo, relaciones)

    async def crear_proyecto(
        self,
        titulo: str,
        relaciones: dict[str, str] | None = None,
    ) -> str:
        """Crea un proyecto en la base de datos 'Proyectos' de Notion."""
        return await self._crear_elemento("Proyectos", titulo, relaciones)

    async def crear_objetivo(
        self,
        titulo: str,
        relaciones: dict[str, str] | None = None,
    ) -> str:
        """Crea un objetivo en la base de datos 'Objetivos' de Notion."""
        return await self._crear_elemento("Objetivos", titulo, relaciones)

    # ── Health ──────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Verifica la conexión con Notion leyendo la página raíz."""
        try:
            await self._client.blocks.children.list(block_id=self._root_page_id)
            return True
        except Exception:
            logger.exception("Notion health check fallo")
            return False
