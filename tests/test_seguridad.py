"""Pruebas de las guardas de seguridad (RS-01 a RS-06) y del limpiador."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from despeja import catalogo, escaner, limpiador, seguridad  # noqa: E402


def _arbol(tmp_path):
    """cache/ con archivos viejos y nuevos, subcarpetas y un enlace a 'documentos' (víctima)."""
    cache = tmp_path / "perfil" / "AppData" / "Local" / "App" / "Cache"
    (cache / "sub" / "hondo").mkdir(parents=True)
    docs = tmp_path / "perfil" / "Documents"
    docs.mkdir(parents=True)
    (docs / "tesis.docx").write_bytes(b"x" * 1000)
    viejo = time.time() - 3 * 24 * 3600
    for nombre, tam, antiguo in (("a.bin", 100, True), ("b.bin", 200, False), ("sub/c.log", 300, True),
                                 ("sub/hondo/d.tmp", 400, True)):
        p = cache / nombre
        p.write_bytes(b"x" * tam)
        if antiguo:
            os.utime(p, (viejo, viejo))
    return cache, docs


def test_dentro_de():
    assert seguridad.dentro_de("/a/b", "/a/b/c/d")
    assert seguridad.dentro_de("/a/b", "/a/b")
    assert not seguridad.dentro_de("/a/b", "/a/bc/d")          # prefijo de texto no basta
    assert not seguridad.dentro_de("/a/b", "/a/b/../x")


def test_ruta_permitida_rechaza_generales_y_protegidas(tmp_path):
    base = str(tmp_path)
    assert seguridad.ruta_permitida("/", [base])[0] is False
    assert seguridad.ruta_permitida("relativa/x", [base])[0] is False
    prot = {seguridad.normalizar(str(tmp_path / "perfil" / "Documents"))}
    (tmp_path / "perfil" / "Documents").mkdir(parents=True)
    ok, motivo = seguridad.ruta_permitida(str(tmp_path / "perfil" / "Documents"), [base], prot)
    assert not ok and "protegida" in motivo
    ok, motivo = seguridad.ruta_permitida("/etc/ssl", [base], set())
    assert not ok and "fuera" in motivo


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sin enlaces simbólicos")
def test_raiz_con_enlace_rechazada(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    enlace = tmp_path / "enlace"
    os.symlink(real, enlace, target_is_directory=True)
    ok, motivo = seguridad.ruta_permitida(str(enlace / "x"), [str(tmp_path)], set())
    assert not ok and "enlace" in motivo


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sin enlaces simbólicos")
def test_limpieza_no_sigue_enlaces(tmp_path):
    """T1: una unión/enlace dentro de una caché que apunta a Documentos no debe vaciarlos."""
    cache, docs = _arbol(tmp_path)
    os.symlink(docs, cache / "trampa", target_is_directory=True)
    (cache / "sub" / "atajo.lnk").symlink_to(docs / "tesis.docx")
    obj = catalogo.Objetivo("t", "t", "sistema", "x", "", (str(cache),))
    r = limpiador.limpiar_objetivo(obj, [str(cache)], simular=False, validar=lambda r: (True, ""))
    assert (docs / "tesis.docx").exists()
    assert os.path.islink(cache / "trampa")                 # el enlace se deja tal cual
    assert r.enlaces >= 2
    assert r.archivos == 4


def test_simular_no_borra(tmp_path):
    cache, _ = _arbol(tmp_path)
    obj = catalogo.Objetivo("t", "t", "sistema", "x", "", (str(cache),))
    r = limpiador.limpiar_objetivo(obj, [str(cache)], simular=True, validar=lambda r: (True, ""))
    assert r.archivos == 4 and r.bytes == 1000
    assert len(list(escaner.recorrer(str(cache)))) == 4


def test_edad_y_patrones(tmp_path):
    cache, _ = _arbol(tmp_path)
    obj = catalogo.Objetivo("t", "t", "sistema", "x", "", (str(cache),), edad_horas=24)
    r = limpiador.limpiar_objetivo(obj, [str(cache)], simular=False, validar=lambda r: (True, ""))
    assert r.archivos == 3                                      # b.bin es reciente
    assert (cache / "b.bin").exists() and not (cache / "a.bin").exists()
    assert not (cache / "sub").exists()                         # carpetas vacías eliminadas
    assert cache.exists()                                       # la raíz nunca se borra
    cache2, _ = _arbol(tmp_path / "otro")
    obj2 = catalogo.Objetivo("t", "t", "sistema", "x", "", (str(cache2),), patrones=("*.log",))
    r2 = limpiador.limpiar_objetivo(obj2, [str(cache2)], simular=True, validar=lambda r: (True, ""))
    assert r2.archivos == 1 and r2.bytes == 300


def test_validacion_rechaza_raiz(tmp_path):
    cache, _ = _arbol(tmp_path)
    obj = catalogo.Objetivo("t", "t", "sistema", "x", "", (str(cache),))
    r = limpiador.limpiar_objetivo(obj, [str(cache)], simular=False, validar=lambda r: (False, "no"))
    assert r.archivos == 0 and r.rechazadas
    assert len(list(escaner.recorrer(str(cache)))) == 4


def test_por_defecto_valida_con_bases_reales(tmp_path):
    """Sin `validar`, una carpeta temporal cualquiera está fuera de las bases permitidas: no se borra."""
    cache, _ = _arbol(tmp_path)
    obj = catalogo.Objetivo("t", "t", "sistema", "x", "", (str(cache),))
    r = limpiador.limpiar_objetivo(obj, [str(cache)], simular=False)
    if r.rechazadas:
        assert r.archivos == 0
        assert len(list(escaner.recorrer(str(cache)))) == 4


def test_modo_papelera_no_borra_directamente(tmp_path):
    cache, _ = _arbol(tmp_path)
    enviados = []
    obj = catalogo.Objetivo("t", "t", "usuario", "x", "", (str(cache),), modo="papelera")
    r = limpiador.limpiar_objetivo(obj, [str(cache)], simular=False, enviar_a_papelera=enviados.append,
                                   validar=lambda r: (True, ""))
    assert r.archivos == 4 and len(enviados) == 4
    assert len(list(escaner.recorrer(str(cache)))) == 4        # el falso «envío» no borró nada


def test_nube_nunca_se_borra(tmp_path, monkeypatch):
    """T10: marcadores de OneDrive (RECALL_ON_DATA_ACCESS) se saltan."""
    cache, _ = _arbol(tmp_path)
    original = seguridad.es_en_nube
    monkeypatch.setattr(seguridad, "es_en_nube", lambda st: st.st_size == 200 or original(st))
    obj = catalogo.Objetivo("t", "t", "sistema", "x", "", (str(cache),))
    r = limpiador.limpiar_objetivo(obj, [str(cache)], simular=False, validar=lambda r: (True, ""))
    assert (cache / "b.bin").exists() and r.nube == 1 and r.archivos == 3


def test_expandir_sin_variable_no_devuelve_nada(monkeypatch):
    monkeypatch.delenv("VARIABLE_QUE_NO_EXISTE", raising=False)
    assert catalogo.expandir(r"%VARIABLE_QUE_NO_EXISTE%\Temp") == []
    assert catalogo.expandir("relativa/Temp") == []


def test_catalogo_bien_formado():
    ids = [o.id for o in catalogo.CATALOGO]
    assert len(ids) == len(set(ids))
    categorias = {c for c, _, _ in catalogo.CATEGORIAS}
    for o in catalogo.CATALOGO:
        assert o.categoria in categorias
        assert o.modo in ("borrar", "papelera", "papelera_windows")
        assert o.riesgo in ("bajo", "medio")
        assert o.rutas or o.modo == "papelera_windows"
        for r in o.rutas:                                       # siempre desde una variable de entorno
            assert r.startswith("%"), r
        assert "ollama" not in " ".join(o.rutas).lower()        # los modelos de Ollama no se tocan


def test_ruta_borrable_usuario(tmp_path):
    f = tmp_path / "grande.iso"
    f.write_bytes(b"x" * 10)
    assert seguridad.ruta_borrable_usuario(str(f), set())[0]
    assert not seguridad.ruta_borrable_usuario(str(tmp_path), set())[0]          # carpeta
    assert not seguridad.ruta_borrable_usuario(str(tmp_path / "no"), set())[0]   # no existe
    assert not seguridad.ruta_borrable_usuario("relativa.txt", set())[0]
