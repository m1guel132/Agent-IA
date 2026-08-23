import pytest
from datetime import date, timedelta

from agent_ia.domain.entities import Area, Nota, Tarea, Habito, ItemEstudio, TipoArea, EstadoTarea


def test_area_creation():
    area = Area(id="1", nombre="Redes", tipo=TipoArea.ACADEMICA)
    assert area.nombre == "Redes"
    assert area.tipo == TipoArea.ACADEMICA

    with pytest.raises(ValueError):
        Area(id="2", nombre="")


def test_nota_creation():
    nota = Nota(id="1", titulo="Apuntes TCP/IP", tags=["redes"])
    assert nota.titulo == "Apuntes TCP/IP"
    assert not nota.esta_sincronizada

    nota.notion_page_id = "page_1"
    nota.obsidian_path = "Redes/Apuntes TCP_IP.md"
    assert nota.esta_sincronizada


def test_tarea_vencida():
    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    
    tarea1 = Tarea(id="1", titulo="Hacer lab", fecha_limite=ayer)
    assert tarea1.esta_vencida

    tarea2 = Tarea(id="2", titulo="Hacer lab", fecha_limite=ayer, estado=EstadoTarea.COMPLETADA)
    assert not tarea2.esta_vencida


def test_habito_racha():
    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    
    habito = Habito(id="1", nombre="Leer")
    habito.registrar_cumplimiento()
    assert habito.racha == 1

    # Forzar fecha a ayer y registrar de nuevo
    habito.ultimo_cumplimiento = ayer
    habito.registrar_cumplimiento()
    assert habito.racha == 2


def test_item_estudio_sm2():
    item = ItemEstudio(id="1", nota_id="n1")
    
    # Repaso exitoso
    item.registrar_repaso(calidad=4)
    assert item.repeticiones == 1
    assert item.intervalo == 1
    
    # Repaso exitoso de nuevo
    item.registrar_repaso(calidad=5)
    assert item.repeticiones == 2
    assert item.intervalo == 6
    assert item.facilidad > 2.5
    
    # Fallo
    item.registrar_repaso(calidad=1)
    assert item.repeticiones == 0
    assert item.intervalo == 1
    assert item.facilidad < 2.6
