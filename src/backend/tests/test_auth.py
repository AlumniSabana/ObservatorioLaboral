"""Tokens de Administrador y guardia de las rutas protegidas."""
import time

import pytest
from fastapi.testclient import TestClient

import auth


def test_token_valido_se_acepta():
    token, expira = auth.emitir_token("admin@prueba.test")
    payload = auth.validar_token(token)
    assert payload["rol"] == "admin"
    assert payload["email"] == "admin@prueba.test"
    assert expira > time.time()


def test_token_manipulado_se_rechaza():
    token, _ = auth.emitir_token("admin@prueba.test")
    payload, firma = token.split(".")
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token(payload + "." + firma[:-2] + "xx")
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token("sin-punto")
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token("")


def test_token_caducado_se_rechaza(monkeypatch):
    token, expira = auth.emitir_token("admin@prueba.test")
    monkeypatch.setattr(auth.time, "time", lambda: expira + 1)
    with pytest.raises(auth.TokenExpirado):
        auth.validar_token(token)


@pytest.fixture(scope="module")
def cliente():
    import main  # importa la app completa (con Supabase simulado por conftest)
    return TestClient(main.app)


RUTAS_ADMIN = [
    ("post", "/scrape"),
    ("post", "/scrape/linkedin"),
    ("post", "/informes"),
    ("post", "/informes/insights"),
    ("post", "/tendencias/recolectar"),
    ("post", "/tendencias/sincronizar-google"),
    ("post", "/tendencias/sincronizar-linkedin"),
    ("get", "/asistente/preguntas/resumen"),
    ("get", "/tendencias/fuentes/estado"),
    ("get", "/tendencias/serpapi/estado"),
]


@pytest.mark.parametrize("metodo,ruta", RUTAS_ADMIN)
def test_rutas_de_admin_exigen_token(cliente, metodo, ruta):
    assert getattr(cliente, metodo)(ruta).status_code == 401


def test_ruta_de_admin_rechaza_token_falso(cliente):
    r = cliente.post("/tendencias/recolectar", headers={"Authorization": "Bearer falso.falso"})
    assert r.status_code == 401


def test_login_con_credenciales_malas_falla(cliente):
    r = cliente.post("/auth/login", json={"email": "admin@prueba.test", "password": "incorrecta"})
    assert r.status_code == 401


def test_login_correcto_da_token_que_abre_yo(cliente):
    r = cliente.post("/auth/login", json={"email": "admin@prueba.test", "password": "clave-de-prueba"})
    assert r.status_code == 200
    token = r.json()["token"]
    yo = cliente.get("/auth/yo", headers={"Authorization": f"Bearer {token}"})
    assert yo.status_code == 200
