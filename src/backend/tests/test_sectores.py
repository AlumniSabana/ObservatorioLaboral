"""Taxonomía de sectores: los 18 grupos y el refinamiento por título."""
import pytest

from traducciones import (
    AGROPECUARIO, ENERGIA, GRUPOS_SECTOR_18, INDUSTRIA, MINERIA, OTROS_SECTOR,
    SALUD, SIN_ESPECIFICAR, agrupar_sector, sector_de_vacante, traducir_sector,
)


def test_son_18_grupos_distintos():
    assert len(GRUPOS_SECTOR_18) == 18
    assert len(set(GRUPOS_SECTOR_18)) == 18


def test_toda_categoria_de_adzuna_cae_en_un_grupo_valido():
    from traducciones import SECTORES
    validos = set(GRUPOS_SECTOR_18) | {OTROS_SECTOR, SIN_ESPECIFICAR}
    for etiqueta in SECTORES:
        assert agrupar_sector(traducir_sector(etiqueta)) in validos, etiqueta


def test_sin_categoria_se_queda_sin_sector():
    # Google Jobs y LinkedIn no traen sector: no se inventa uno.
    assert sector_de_vacante(None, "Solar Engineer") is None
    assert agrupar_sector(None) is None


def test_modalidad_y_nivel_no_son_sector():
    assert agrupar_sector(traducir_sector("Part time Jobs")) == OTROS_SECTOR


@pytest.mark.parametrize("categoria,titulo,esperado", [
    ("Engineering Jobs", "Senior Water/Wastewater Engineer", ENERGIA),
    ("Engineering Jobs", "Lead Transmission Line Engineer", ENERGIA),
    ("Engineering Jobs", "Irrigation Service Technician", AGROPECUARIO),
    ("Trade & Construction Jobs", "Solar Installer", ENERGIA),
    # Petróleo y gas sigue siendo minería aunque diga "energy".
    ("Energy, Oil & Gas Jobs", "Drilling Engineer", MINERIA),
    ("Energy, Oil & Gas Jobs", "Oil & Gas Energy Analyst", MINERIA),
    # Falsos amigos: la base no es refinable o el término está excluido.
    ("Healthcare & Nursing Jobs", "Nuclear Medicine Technologist", SALUD),
    ("Healthcare & Nursing Jobs", "Occupational Therapy Assistant - Bryant Farm", SALUD),
    # Sin pista en el título, manda la categoría.
    ("Engineering Jobs", "Mechanical Design Engineer", INDUSTRIA),
])
def test_refinamiento_por_titulo(categoria, titulo, esperado):
    assert sector_de_vacante(categoria, titulo) == esperado
