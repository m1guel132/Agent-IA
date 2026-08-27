"""Tests unitarios para las entidades del Dominio de Agent IA."""

import pytest
from datetime import date, timedelta

from agent_ia.domain.entities import (
    Area,
    Nota,
    Tarea,
    Habito,
    ItemEstudio,
    TipoArea,
    EstadoTarea,
    PrioridadTarea,
    OrigenNota,
)


def test_area_creation_and_validation():
    area = Area(id="1", nombre="Redes", tipo=TipoArea.ACADEMICA)
    assert area.nombre == "Redes"
    assert area.tipo == TipoArea.ACADEMICA

    with pytest.raises(ValueError, match="no puede estar vacío"):
        Area(id="2", nombre="   ")


def test_nota_creation_and_sync_status():
    nota = Nota(id="1", titulo="Apuntes TCP/IP", tags=["redes"], origen=OrigenNota.CHAT)
    assert nota.titulo == "Apuntes TCP/IP"
    assert nota.origen == OrigenNota.CHAT
    assert not nota.esta_sincronizada

    nota.notion_page_id = "page_1"
    nota.obsidian_path = "Redes/Apuntes TCP_IP.md"
    assert nota.esta_sincronizada

    with pytest.raises(ValueError, match="no puede estar vacío"):
        Nota(id="2", titulo="")


def test_tarea_validations_and_properties():
    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    manana = hoy + timedelta(days=1)

    tarea1 = Tarea(id="1", titulo="Hacer lab", fecha_limite=ayer, prioridad=PrioridadTarea.OBLIGATORIA)
    assert tarea1.esta_vencida
    assert tarea1.prioridad == PrioridadTarea.OBLIGATORIA

    tarea2 = Tarea(id="2", titulo="Hacer lab", fecha_limite=ayer, estado=EstadoTarea.COMPLETADA)
    assert not tarea2.esta_vencida

    tarea3 = Tarea(id="3", titulo="Estudiar", fecha_limite=manana)
    assert not tarea3.esta_vencida

    with pytest.raises(ValueError, match="no puede estar vacío"):
        Tarea(id="4", titulo="")


def test_habito_racha_and_validations():
    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    anteayer = hoy - timedelta(days=3)

    # Validaciones
    with pytest.raises(ValueError, match="no puede estar vacío"):
        Habito(id="1", nombre="")
    with pytest.raises(ValueError, match="no puede ser negativa"):
        Habito(id="2", nombre="Leer", racha=-1)

    habito = Habito(id="3", nombre="Meditar")
    assert not habito.verificar_racha()

    # Primer cumplimiento
    habito.registrar_cumplimiento()
    assert habito.racha == 1
    assert habito.verificar_racha()

    # Cumplimiento repetido el mismo día (idempotente)
    habito.registrar_cumplimiento()
    assert habito.racha == 1

    # Forzar fecha a ayer y registrar hoy -> incrementa
    habito.ultimo_cumplimiento = ayer
    habito.registrar_cumplimiento()
    assert habito.racha == 2

    # Racha rota (hace 3 días) -> se reinicia a 1
    habito.ultimo_cumplimiento = anteayer
    habito.registrar_cumplimiento()
    assert habito.racha == 1


def test_item_estudio_sm2_full_lifecycle():
    item = ItemEstudio(id="1", nota_id="n1", facilidad=1.0)
    assert item.facilidad == 1.3  # Min facilidad asegurada por __post_init__

    with pytest.raises(ValueError, match="debe estar entre 0 y 5"):
        item.registrar_repaso(calidad=6)

    # 1ª repetición exitosa (calidad 4)
    item.registrar_repaso(calidad=4)
    assert item.repeticiones == 1
    assert item.intervalo == 1
    assert not item.repaso_pendiente

    # 2ª repetición exitosa (calidad 5)
    item.registrar_repaso(calidad=5)
    assert item.repeticiones == 2
    assert item.intervalo == 6

    # 3ª repetición exitosa (calidad 5) -> intervalo se multiplica por facilidad
    facilidad_actual = item.facilidad
    item.registrar_repaso(calidad=5)
    assert item.repeticiones == 3
    assert item.intervalo == round(6 * item.facilidad)

    # Fallo (calidad 1) -> resetea repeticiones e intervalo
    item.registrar_repaso(calidad=1)
    assert item.repeticiones == 0
    assert item.intervalo == 1
