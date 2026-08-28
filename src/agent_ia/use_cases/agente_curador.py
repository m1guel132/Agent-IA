"""AgenteCurador — curaduría del Segundo Cerebro en modo revisión.

Este agente opera en modo "propone, no aplica solo" (RF5.4):
categoriza notas y propone cambios, pero NO los ejecuta hasta
que el usuario confirme a través de Hermes.

Dominio: Nota, Área (clasificación y organización).
"""

from __future__ import annotations

import json
import logging
import uuid

from agent_ia.domain.entities import Nota
from agent_ia.domain.entities.nota import OrigenNota
from agent_ia.domain.ports.llm_port import LLMPort
from agent_ia.domain.ports.notion_port import NotionPort
from agent_ia.domain.ports.obsidian_port import ObsidianPort
from agent_ia.domain.ports.vector_store_port import VectorStorePort
from agent_ia.use_cases.agente import Agente, EstadoResultado, Resultado

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_CLASIFICAR = """Eres el AgenteCurador de Agent IA, un sistema de gestión de conocimiento personal.
Tu trabajo es categorizar notas del Segundo Cerebro del usuario.

Dado el contenido de una nota, debes:
1. Sugerir un área temática (e.g., "Redes", "Cálculo", "Salud", "Proyectos").
2. Sugerir tags relevantes (máximo 5).
3. Detectar si es posible que sea un duplicado de algo existente.

Responde SIEMPRE en JSON con esta estructura exacta:
{
    "area_sugerida": "nombre del área",
    "tags": ["tag1", "tag2"],
    "es_posible_duplicado": false,
    "razon": "breve explicación de por qué sugieres esa categorización"
}
"""

SYSTEM_PROMPT_ORGANIZAR = """Eres el AgenteCurador de Agent IA.
Tu trabajo es detectar notas desorganizadas (huérfanas, sin área, duplicadas)
y proponer acciones de organización.

Responde en JSON con esta estructura:
{
    "acciones": [
        {
            "tipo": "reclasificar|fusionar|archivar",
            "nota_id": "id de la nota",
            "descripcion": "qué hacer y por qué"
        }
    ]
}
"""


SYSTEM_PROMPT_CONSULTA = """Eres el consultor analítico del Segundo Cerebro de Miguel.
Tu misión es responder de forma clara, natural, fluida y precisa a las consultas y preguntas de Miguel sobre sus notas y conocimiento acumulado.

Directrices:
1. Utiliza el contexto recuperado de sus notas (Obsidian, ChromaDB, Notion) para responder con exactitud.
2. Si el usuario pide consultar un tema, sintetiza las ideas principales, conceptos clave y conexiones lógicas.
3. Habla con tono natural, empático y estructurado (usando títulos, viñetas y Markdown limpio).
4. Si no hay suficiente información en sus notas sobre lo que pregunta, explícalo con naturalidad y sugiérele qué conceptos podría documentar para cerrar esa brecha.
"""


class AgenteCurador(Agente):
    """Agente especializado en curaduría y consulta del Segundo Cerebro.

    Opera en modo revisión para crear notas (propone y espera confirmación),
    y en modo RAG conversacional para consultas de conocimiento.
    """

    def __init__(
        self,
        llm: LLMPort,
        obsidian: ObsidianPort,
        vector_store: VectorStorePort,
        notion: NotionPort,
    ) -> None:
        super().__init__(nombre="AgenteCurador", dominio="Nota, Área")
        self._llm = llm
        self._obsidian = obsidian
        self._vector_store = vector_store
        self._notion = notion

        # Almacén temporal de propuestas pendientes de confirmación
        self._propuestas_pendientes: dict[str, dict] = {}

    async def ejecutar(self, instruccion: str, contexto: dict | None = None) -> Resultado:
        """Ejecuta una instrucción de curaduría o consulta de conocimiento."""
        ctx = contexto or {}
        instruccion_lower = instruccion.strip().lower()

        # 1. Si es una confirmación de propuesta pendiente
        if ctx.get("confirmar_propuesta"):
            return await self._aplicar_propuesta(ctx["confirmar_propuesta"])

        import re

        # 2. Organizar inbox
        if re.search(r'\b(organiza|organizar|limpiar|inbox|ordenar)\b', instruccion_lower) and not re.search(r'\b(anota|guarda|crea)\b', instruccion_lower):
            return await self._organizar_inbox()

        # 3. ¿Es una intención explícita de CAPTURAR / CREAR una nota nueva?
        # Solo proponemos crear nota si el usuario claramente quiere capturar o guardar algo nuevo
        patron_captura = r'^(anota(r)?|guarda(r)?|registra(r)?|apunta(r)?|crea(r)? una nota|nueva nota|toma nota|documenta(r)?)\b'
        es_captura = bool(re.search(patron_captura, instruccion_lower)) or bool(
            re.search(r'\b(anota esto|guardar nota|crear nota|apunta esto)\b', instruccion_lower)
        )

        if es_captura:
            return await self._proponer_nota(instruccion, ctx)

        # 4. Para cualquier otra pregunta, búsqueda o consulta del Segundo Cerebro: RAG Conversacional
        return await self._consultar_segundo_cerebro(instruccion, ctx)

    async def _proponer_nota(self, instruccion: str, contexto: dict) -> Resultado:
        """Crea una propuesta de nota categorizada (modo revisión)."""
        # Usar LLM para categorizar
        response = await self._llm.generate(
            prompt=f"Categoriza la siguiente nota del usuario:\n\n{instruccion}",
            system=SYSTEM_PROMPT_CLASIFICAR,
            temperature=0.3,
        )

        # Parsear la respuesta JSON del LLM
        try:
            clasificacion = json.loads(response.content)
        except json.JSONDecodeError:
            # Si el LLM no devuelve JSON válido, extraer lo que se pueda
            clasificacion = {
                "area_sugerida": "inbox",
                "tags": [],
                "es_posible_duplicado": False,
                "razon": response.content,
            }

        # Buscar contexto relevante en el vector store
        resultados_similares = await self._vector_store.buscar(instruccion, n_results=3)
        posibles_duplicados = [
            r for r in resultados_similares if r.score > 0.85
        ]

        # Crear la propuesta (NO aplica todavía — RF5.4)
        propuesta_id = str(uuid.uuid4())[:8]
        nota_propuesta = Nota(
            id=str(uuid.uuid4()),
            titulo=self._extraer_titulo(instruccion),
            contenido=instruccion,
            tags=clasificacion.get("tags", []),
            area_id=clasificacion.get("area_sugerida", "inbox"),
            origen=OrigenNota.CHAT,
        )

        self._propuestas_pendientes[propuesta_id] = {
            "nota": nota_propuesta,
            "clasificacion": clasificacion,
        }

        # Construir mensaje de propuesta para el usuario
        mensaje = (
            f"📋 **Propuesta de nota** (ID: `{propuesta_id}`)\n\n"
            f"**Título:** {nota_propuesta.titulo}\n"
            f"**Área sugerida:** `{clasificacion.get('area_sugerida', 'inbox')}`\n"
            f"**Tags:** {', '.join(clasificacion.get('tags', []))}\n"
            f"**Razón:** {clasificacion.get('razon', 'Sin explicación')}\n"
        )

        if posibles_duplicados:
            mensaje += "\n⚠️ **Posibles duplicados encontrados:**\n"
            for dup in posibles_duplicados:
                mensaje += f"  - {dup.content[:80]}... (similitud: {dup.score:.0%})\n"

        mensaje += "\n¿Confirmas esta categorización? [Confirmar] [Ajustar]"

        return Resultado(
            estado=EstadoResultado.REQUIERE_CONFIRMACION,
            mensaje=mensaje,
            datos={
                "propuesta_id": propuesta_id,
                "nota": {
                    "titulo": nota_propuesta.titulo,
                    "area": clasificacion.get("area_sugerida"),
                    "tags": clasificacion.get("tags", []),
                },
                "duplicados": [
                    {"content": d.content[:100], "score": d.score}
                    for d in posibles_duplicados
                ],
            },
            accion_pendiente=f"Crear nota '{nota_propuesta.titulo}' en área '{clasificacion.get('area_sugerida')}'",
            agente=self.nombre,
        )

    async def _aplicar_propuesta(self, propuesta_id: str) -> Resultado:
        """Aplica una propuesta previamente confirmada por el usuario."""
        if propuesta_id not in self._propuestas_pendientes:
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje=f"❌ Propuesta `{propuesta_id}` no encontrada o ya aplicada.",
                agente=self.nombre,
            )

        propuesta = self._propuestas_pendientes.pop(propuesta_id)
        nota: Nota = propuesta["nota"]

        try:
            # 1. Escribir en Obsidian (Memoria Física)
            filepath = await self._obsidian.escribir_nota(nota)

            # 2. Escribir en Notion (Segundo Cerebro / Cloud)
            page_id = await self._notion.crear_pagina(nota)
            nota.notion_page_id = page_id

            # 3. Indexar en ChromaDB (Índice Cognitivo)
            await self._vector_store.indexar(
                doc_id=nota.id,
                content=f"{nota.titulo}\n{nota.contenido}",
                metadata={
                    "area": nota.area_id or "inbox",
                    "tags": ",".join(nota.tags),
                    "origen": nota.origen,
                    "obsidian_path": nota.obsidian_path or "",
                    "notion_page_id": nota.notion_page_id or "",
                },
            )

            return Resultado(
                estado=EstadoResultado.EXITO,
                mensaje=(
                    f"✅ **Conocimiento guardado en la memoria del sistema**\n\n"
                    f"• Obsidian: `{nota.obsidian_path}`\n"
                    f"• Notion: `{nota.notion_page_id}`\n"
                    f"• ChromaDB: indexada para búsqueda semántica"
                ),
                datos={
                    "nota_id": nota.id,
                    "obsidian_path": str(filepath),
                    "notion_page_id": nota.notion_page_id,
                },
                agente=self.nombre,
            )
        except Exception as e:
            logger.exception("Error al aplicar propuesta %s", propuesta_id)
            # Devolver la propuesta al pendiente si falla
            self._propuestas_pendientes[propuesta_id] = propuesta
            return Resultado(
                estado=EstadoResultado.ERROR,
                mensaje=f"❌ Error al guardar la nota: {e}",
                agente=self.nombre,
            )

    async def _organizar_inbox(self) -> Resultado:
        """Revisa el inbox del vault y propone organización."""
        notas_inbox = await self._obsidian.listar_notas("inbox")

        if not notas_inbox:
            return Resultado(
                estado=EstadoResultado.SIN_ACCION,
                mensaje="📥 El inbox está vacío. No hay notas por organizar.",
                agente=self.nombre,
            )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=f"📥 Encontré **{len(notas_inbox)}** nota(s) en el inbox:\n"
            + "\n".join(f"  - `{n}`" for n in notas_inbox[:10]),
            datos={"notas_inbox": notas_inbox},
            agente=self.nombre,
        )

    async def _consultar_segundo_cerebro(self, query: str, contexto: dict | None = None) -> Resultado:
        """Realiza una consulta semántica y sintetiza una respuesta conversacional con el LLM."""
        import re

        # 1. Buscar en ChromaDB
        try:
            resultados_vector = await self._vector_store.buscar(query, n_results=5)
        except Exception as e:
            logger.warning("Error consultando vector store: %s", e)
            resultados_vector = []

        # 2. Buscar en Obsidian si hay archivos con nombres o áreas relevantes
        notas_obsidian = []
        try:
            todas_notas = await self._obsidian.listar_notas()
            palabras_clave = [p for p in re.findall(r'\w+', query.lower()) if len(p) > 3]
            for n in todas_notas:
                if any(k in n.lower() for k in palabras_clave):
                    notas_obsidian.append(n)
        except Exception:
            pass

        # 3. Construir contexto enriquecido para el LLM
        fragmentos_contexto = []
        if resultados_vector:
            for r in resultados_vector:
                fragmentos_contexto.append(f"[Fragmento de nota (score: {r.score:.2f})]:\n{r.content}")

        if notas_obsidian:
            fragmentos_contexto.append(f"[Archivos relacionados en Obsidian Vault]: {', '.join(notas_obsidian[:5])}")

        texto_contexto = (
            "\n\n---\n\n".join(fragmentos_contexto)
            if fragmentos_contexto
            else "No se encontraron notas directamente relacionadas en la base vectorial."
        )

        # 4. Sintetizar respuesta conversacional fluida
        prompt = (
            f"Contexto recuperado del Segundo Cerebro de Miguel:\n{texto_contexto}\n\n"
            f"Pregunta o consulta de Miguel:\n{query}\n\n"
            f"Responde a Miguel de manera conversacional, analítica, clara y directa:"
        )

        try:
            response = await self._llm.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT_CONSULTA,
                temperature=0.3,
            )
            mensaje = response.content
        except Exception as e:
            logger.exception("Error al sintetizar respuesta de consulta")
            mensaje = (
                f"🔍 **Resultados encontrados:**\n\n"
                + "\n".join(f"• {r.content[:150]}..." for r in resultados_vector[:3])
            )

        return Resultado(
            estado=EstadoResultado.EXITO,
            mensaje=mensaje,
            datos={
                "resultados_count": len(resultados_vector),
                "archivos_obsidian": notas_obsidian[:5],
            },
            agente=self.nombre,
        )

    @staticmethod
    def _extraer_titulo(instruccion: str) -> str:
        """Extrae un título corto de la instrucción del usuario."""
        # Remover prefijos comunes
        prefijos = ["anota esto:", "anota:", "nota:", "apunta:", "registra:"]
        texto = instruccion.strip()
        for prefijo in prefijos:
            if texto.lower().startswith(prefijo):
                texto = texto[len(prefijo):].strip()
                break

        # Tomar la primera oración o los primeros 60 caracteres
        for sep in [".", "\n", ";"]:
            if sep in texto:
                texto = texto.split(sep)[0].strip()
                break

        if len(texto) > 60:
            texto = texto[:57] + "..."

        return texto or "Nota sin título"
