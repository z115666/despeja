"""Pruebas del registro encadenado (RS-11) y de la validación de la API (RS-09)."""
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from despeja import auditoria  # noqa: E402
from despeja.api import Api  # noqa: E402
from despeja.registro import Registro  # noqa: E402


def test_cadena_integra_y_detecta_cambios(tmp_path):
    reg = Registro(str(tmp_path))
    for i in range(5):
        reg.anotar("limpieza", bytes=i * 100, archivos=i)
    assert reg.verificar() == {"ok": True, "entradas": 5}
    lineas = open(reg.ruta, encoding="utf-8").read().splitlines()
    e = json.loads(lineas[2])
    e["bytes"] = 1                                              # alguien rebaja la cifra
    lineas[2] = json.dumps(e, ensure_ascii=False)
    open(reg.ruta, "w", encoding="utf-8").write("\n".join(lineas) + "\n")
    v = reg.verificar()
    assert not v["ok"] and v["linea"] == 3 and "modificada" in v["error"]


def test_cadena_detecta_borrado_de_linea(tmp_path):
    reg = Registro(str(tmp_path))
    for i in range(4):
        reg.anotar("analisis", archivos=i)
    lineas = open(reg.ruta, encoding="utf-8").read().splitlines()
    del lineas[1]
    open(reg.ruta, "w", encoding="utf-8").write("\n".join(lineas) + "\n")
    v = reg.verificar()
    assert not v["ok"] and v["linea"] == 2


def test_exportar(tmp_path):
    reg = Registro(str(tmp_path))
    reg.anotar("limpieza", bytes=2048, archivos=3, detalle={"x": "<script>alert(1)</script>"})
    html = reg.exportar(str(tmp_path / "i.html"), "html")
    texto = open(html, encoding="utf-8").read()
    assert "<script>alert" not in texto and "&lt;script&gt;" in texto   # escapado
    assert "Íntegro" in texto
    csv = reg.exportar(str(tmp_path / "i.csv"), "csv")
    assert "limpieza" in open(csv, encoding="utf-8-sig").read()


def _esperar(api, r):
    for _ in range(200):
        t = api.tarea(r["tarea"])
        if t["estado"] != "corriendo":
            return t
        time.sleep(0.05)
    raise AssertionError("la tarea no termina")


def test_api_valida_entradas(tmp_path):
    api = Api(Registro(str(tmp_path)))
    with pytest.raises(ValueError):
        api.limpiar(["no_existe"])
    with pytest.raises(ValueError):
        api.limpiar("temp_usuario")                             # no es lista
    with pytest.raises(ValueError):
        api.limpiar([{"$where": 1}])
    with pytest.raises(ValueError):
        api.oculto("C:; del *")
    with pytest.raises(ValueError):
        api.oculto("CD")
    with pytest.raises(ValueError):
        api.analizar(str(tmp_path / "no_existe"))
    with pytest.raises(ValueError):
        api.herramienta("format_c")
    assert api.abrir_config("cmd.exe") is False
    assert api.exportar("exe") is None


def test_api_papelera_solo_del_ultimo_analisis(tmp_path):
    api = Api(Registro(str(tmp_path / "datos")))
    victima = tmp_path / "importante.docx"
    victima.write_bytes(b"x")
    r = api.a_papelera([str(victima)])
    assert r["enviados"] == [] and "último análisis" in r["fallos"][0]["motivo"]
    assert victima.exists()
    assert api.abrir_ubicacion(str(victima)) is False


def test_api_analizar_carpeta(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "video.mp4").write_bytes(b"x" * 5000)
    (tmp_path / ".oculto").write_bytes(b"x" * 300)
    api = Api(Registro(str(tmp_path / "datos")))
    t = _esperar(api, api.analizar(str(tmp_path / "a")))
    assert t["estado"] == "hecha"
    res = t["resultado"]
    assert res["visibles"] == 5000 and res["grandes"][0]["tipo"] == "Vídeo"
    assert api._registro.verificar()["ok"]


def test_api_simulacion_registra(tmp_path):
    api = Api(Registro(str(tmp_path)))
    t = _esperar(api, api.limpiar(["temp_usuario", "chrome"], True))
    assert t["estado"] == "hecha" and t["resultado"]["simulado"] is True
    ent = api.registro()
    assert ent["integridad"]["ok"] and ent["entradas"][0]["accion"] == "simulacion"
    assert len(ent["entradas"][0]["lista_sha256"]) == 64


def test_tipos():
    assert auditoria.tipo_de("x.MKV") == "Vídeo"
    assert auditoria.tipo_de("modelo.gguf") == "Modelos de IA"
    assert auditoria.tipo_de("sin_extension") == "Otros"
