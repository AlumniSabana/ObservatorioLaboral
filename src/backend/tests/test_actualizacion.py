"""Orquestador de "Actualizar histórico": con TODAS las dependencias simuladas
(sin red ni Supabase) para comprobar el orden, el aislamiento de fallos y el
cerrojo de una sola corrida a la vez."""
import pytest

from Tendencias import actualizacion as act


@pytest.fixture
def deps(monkeypatch):
    """Sustituye cada dependencia externa; `llamadas` registra qué se invocó."""
    llamadas: list[str] = []

    def falsa(nombre, resultado=None):
        def _f(*a, **k):
            llamadas.append(nombre)
            return resultado
        return _f

    falsas = {
        "adzuna_recolectar": falsa("adzuna", {"filas": 3, "llamadas": 1}),
        "serpapi_cuota": falsa("cuota", {"semaforo": "rojo", "restantes": 0}),
        "serpapi_registrar_uso": falsa("uso"),
        "google_recolectar": falsa("google"),
        "google_sincronizar": falsa("google_sync", {"filas": 0}),
        "linkedin_recolectar": falsa("linkedin", {}),
        "linkedin_sincronizar": falsa("linkedin_sync", {"filas": 0}),
        "cargar_ubicaciones": falsa("ubicaciones", {"ciudades": 1}),
        "leer_historico": falsa("leer", [{"title": "x"}]),
        "leer_volumenes": falsa("vols", []),
        "recalcular_todo": falsa("recalculo", {"observaciones": 1}),
        "invalidar_caches": falsa("caches"),
    }
    for k, v in falsas.items():
        monkeypatch.setitem(act.DEPENDENCIAS, k, v)
    return llamadas


def test_fuente_desconocida_se_rechaza_y_libera_el_cerrojo(deps):
    with pytest.raises(ValueError):
        act.actualizar_todo(fuentes=["facebook"])
    # El cerrojo quedó libre: una corrida válida posterior funciona.
    assert act.actualizar_todo(fuentes=["adzuna"], pais_adzuna="us")["status"] in ("completed", "parcial")


def test_recalcula_siempre_al_final_y_limpia_caches(deps):
    resumen = act.actualizar_todo(fuentes=["adzuna"], pais_adzuna="us")
    assert deps.index("ubicaciones") < deps.index("recalculo")  # ubicaciones antes de recalcular
    assert deps[-1] == "caches"
    assert resumen["recalculo"] == {"observaciones": 1}
    assert resumen["vacantes_historicas_totales"] == 1


def test_un_fallo_no_detiene_las_demas_fuentes(deps, monkeypatch):
    def rota(*a, **k):
        raise RuntimeError("Adzuna caído")
    monkeypatch.setitem(act.DEPENDENCIAS, "adzuna_recolectar", rota)
    resumen = act.actualizar_todo(fuentes=["adzuna"], pais_adzuna="us")
    assert resumen["fuentes"][0]["estado"] == act.ERROR
    assert "Adzuna caído" in resumen["fuentes"][0]["error"]
    assert "recalculo" in deps          # el recálculo corrió igual
    assert resumen["status"] == "parcial"


def test_falla_del_recalculo_marca_error(deps, monkeypatch):
    def rota(*a, **k):
        raise RuntimeError("BD sin conexión")
    monkeypatch.setitem(act.DEPENDENCIAS, "recalcular_todo", rota)
    resumen = act.actualizar_todo(fuentes=["adzuna"], pais_adzuna="us")
    assert resumen["status"] == "error"
    assert "Recálculo falló" in resumen["error"]


def test_solo_una_corrida_a_la_vez(deps):
    assert act._lock.acquire(blocking=False)
    try:
        with pytest.raises(act.ActualizacionEnCurso):
            act.actualizar_todo(fuentes=["adzuna"], pais_adzuna="us")
    finally:
        act._lock.release()
