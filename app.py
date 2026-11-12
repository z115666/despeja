"""Despeja: limpieza y auditoría del espacio visible y oculto de los discos.

Arranque:
    Despeja.exe                 abre la aplicación
    Despeja.exe --autotest F    comprobación sin ventana (la usa build_exe.bat); escribe OK en F
"""
from __future__ import annotations

import base64
import os
import re
import sys
import traceback


def recurso(*partes: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *partes)


def html_en_memoria(extra_cabecera: str = "") -> str:
    """Une index.html, app.css (con las fuentes en base64), iconos.js y app.js en un solo documento.
    Sin servidor local ni archivos externos (RS-12): la CSP `default-src 'none'` lo impide todo lo demás."""
    ui = recurso("ui")

    def leer(nombre: str) -> str:
        with open(os.path.join(ui, nombre), encoding="utf-8") as f:
            return f.read()

    css = leer("app.css")

    def fuente(m: re.Match) -> str:
        with open(os.path.join(ui, m.group(1)), "rb") as f:
            return 'url("data:font/woff2;base64,' + base64.b64encode(f.read()).decode("ascii") + '")'
    css = re.sub(r'url\("(fonts/[a-z0-9\-]+\.woff2)"\)', fuente, css)
    html = leer("index.html")
    html = html.replace('<link rel="stylesheet" href="app.css">', f"<style>\n{css}\n</style>")
    scripts = extra_cabecera + f"<script>\n{leer('iconos.js')}\n</script>\n<script>\n{leer('app.js')}\n</script>"
    html = html.replace('<script src="iconos.js"></script>\n<script src="app.js"></script>', scripts)
    if re.search(r"<script[^>]*\ssrc=|<link[^>]*\shref=", html):
        raise RuntimeError("La interfaz hace referencia a archivos externos")
    return html


def _mensaje_error(titulo: str, texto: str) -> None:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10)
    else:
        print(f"{titulo}: {texto}", file=sys.stderr)


def _comprobar(condicion, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def autotest(destino: str) -> int:
    """Comprueba que el ejecutable empaquetado tiene todo lo necesario, sin abrir ventana."""
    try:
        import webview  # noqa: F401
        from despeja import VERSION, catalogo
        from despeja.api import Api
        from despeja.registro import Registro
        import tempfile
        html = html_en_memoria()
        _comprobar("Content-Security-Policy" in html and "ICONOS" in html and "arrancar" in html, "interfaz incompleta")
        with tempfile.TemporaryDirectory() as tmp:
            api = Api(Registro(tmp))
            _comprobar(api.info()["version"] == VERSION, "versión")
            _comprobar(len(api.catalogo()["elementos"]) == len(catalogo.CATALOGO), "catálogo")
            api.unidades()
            r = api.limpiar(["temp_usuario"], True)          # simulación real sobre %TEMP%
            import time
            for _ in range(600):
                t = api.tarea(r["tarea"])
                if t["estado"] != "corriendo":
                    break
                time.sleep(0.1)
            _comprobar(t["estado"] == "hecha", f"simulación: {t}")
            _comprobar(api.registro()["integridad"]["ok"], "registro")
        with open(destino, "w", encoding="utf-8") as f:
            f.write("OK\n")
        return 0
    except Exception:  # noqa: BLE001
        with open(destino, "w", encoding="utf-8") as f:
            f.write("ERROR\n" + traceback.format_exc())
        return 1


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--autotest":
        return autotest(sys.argv[2])
    try:
        import webview
    except Exception as e:  # noqa: BLE001
        _mensaje_error("Despeja", f"No se puede cargar la interfaz:\n{e}")
        return 1
    from despeja import NOMBRE, VERSION
    from despeja.api import Api
    from despeja.elevacion import es_admin
    api = Api()
    titulo = f"{NOMBRE} {VERSION}" + (" (administrador)" if es_admin() else "")
    ventana = webview.create_window(titulo, html=html_en_memoria(), js_api=api, width=1280, height=860,
                                    min_size=(380, 560), background_color="#EDF0F3", text_select=True)
    api._ventana = ventana
    try:
        # private_mode: sin caché ni almacenamiento persistente del navegador integrado
        webview.start(gui="edgechromium" if sys.platform == "win32" else None, private_mode=True, debug=False)
    except Exception as e:  # noqa: BLE001
        _mensaje_error("Despeja", "No se puede abrir la ventana. Instala o repara «Microsoft Edge WebView2 Runtime» "
                       f"(https://developer.microsoft.com/microsoft-edge/webview2/).\n\nDetalle: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
