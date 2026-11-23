"""Normalización de títulos: seniority, escolaridad y limpieza de cargos."""
import pytest

from Adzuna.adzuna_service import normalize_title
from Tendencias.escolaridad import detectar_escolaridad
from Tendencias.seniority import detectar_seniority


@pytest.mark.parametrize("titulo,esperado", [
    ("Senior Software Engineer", "senior"),
    ("Junior Data Analyst", "junior"),
    ("Director de Ventas", "senior"),
    ("Analista contable", "no_especificado"),
    (None, "no_especificado"),
    ("", "no_especificado"),
])
def test_seniority(titulo, esperado):
    assert detectar_seniority(titulo) == esperado


@pytest.mark.parametrize("titulo,esperado", [
    ("Técnico en sistemas", "tecnico"),
    ("Analista contable", "profesional"),
    (None, "no_especificado"),
])
def test_escolaridad(titulo, esperado):
    assert detectar_escolaridad(titulo) == esperado


def test_normalize_title_quita_el_nivel_para_agrupar_cargos():
    # "Senior Software Engineer" y "Software Engineer" deben ser el mismo cargo.
    assert normalize_title("Senior Software Engineer") == normalize_title("Software Engineer")


def test_normalize_title_sin_titulo():
    assert normalize_title("") == "Sin título"
