"""Tests unitarios para ObsidianAdapter sobre sistema de archivos."""

from __future__ import annotations

import pytest
from pathlib import Path

from agent_ia.domain.entities import Nota
from agent_ia.infrastructure.config import Settings
from agent_ia.infrastructure.obsidian_adapter import ObsidianAdapter, _sanitize_filename


def test_sanitize_filename():
    assert _sanitize_filename('Redes: "TCP/IP" <Lab>?') == "Redes_ _TCP_IP_ _Lab__"
    assert _sanitize_filename("Normal File") == "Normal File"


@pytest.mark.asyncio
async def test_escribirNota_conArea_creaSubdirectorioYArchivoMarkdown(tmp_path: Path):
    settings = Settings(obsidian_vault_path=str(tmp_path))
    adapter = ObsidianAdapter(settings)

    nota = Nota(
        id="nota-1",
        titulo="Protocolo BGP",
        contenido="Explicación de Border Gateway Protocol...",
        area_id="Redes",
        tags=["redes", "routing"],
    )

    filepath = await adapter.escribir_nota(nota)

    assert filepath.exists()
    assert filepath.parent.name == "Redes"
    assert filepath.name == "Protocolo BGP.md"
    assert nota.obsidian_path == str(Path("Redes") / "Protocolo BGP.md")

    content = filepath.read_text(encoding="utf-8")
    assert "titulo: Protocolo BGP" in content
    assert "tags: [redes, routing]" in content
    assert "Explicación de Border Gateway Protocol..." in content


@pytest.mark.asyncio
async def test_escribirNota_sinArea_guardaEnInbox(tmp_path: Path):
    settings = Settings(obsidian_vault_path=str(tmp_path))
    adapter = ObsidianAdapter(settings)

    nota = Nota(
        id="nota-2",
        titulo="Idea suelta",
        contenido="Comprar libro de algoritmos",
    )

    filepath = await adapter.escribir_nota(nota)

    assert filepath.exists()
    assert filepath.parent.name == "inbox"
    assert filepath.name == "Idea suelta.md"


@pytest.mark.asyncio
async def test_leerNota_archivoExistente_retornaContenido(tmp_path: Path):
    settings = Settings(obsidian_vault_path=str(tmp_path))
    adapter = ObsidianAdapter(settings)

    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True)
    archivo = inbox / "prueba.md"
    archivo.write_text("Contenido de prueba", encoding="utf-8")

    contenido = await adapter.leer_nota("inbox/prueba.md")
    assert contenido == "Contenido de prueba"


@pytest.mark.asyncio
async def test_leerNota_archivoInexistente_lanzaFileNotFoundError(tmp_path: Path):
    settings = Settings(obsidian_vault_path=str(tmp_path))
    adapter = ObsidianAdapter(settings)

    with pytest.raises(FileNotFoundError):
        await adapter.leer_nota("no_existe.md")


@pytest.mark.asyncio
async def test_listarYBuscarNotas_retornaResultados(tmp_path: Path):
    settings = Settings(obsidian_vault_path=str(tmp_path))
    adapter = ObsidianAdapter(settings)

    dir1 = tmp_path / "Matematicas"
    dir1.mkdir(parents=True)
    (dir1 / "Calculo_Integral.md").write_text("Teorema Fundamental del Calculo", encoding="utf-8")

    dir2 = tmp_path / "Redes"
    dir2.mkdir(parents=True)
    (dir2 / "OSI_Model.md").write_text("7 capas del modelo OSI", encoding="utf-8")

    notas = await adapter.listar_notas()
    assert len(notas) == 2

    # Buscar por nombre
    res_nombre = await adapter.buscar_notas("Calculo")
    assert len(res_nombre) == 1
    assert "Calculo_Integral.md" in res_nombre[0]

    # Buscar por contenido
    res_contenido = await adapter.buscar_notas("7 capas")
    assert len(res_contenido) == 1
    assert "OSI_Model.md" in res_contenido[0]
