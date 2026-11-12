"""Guardas de seguridad del sistema de archivos (RS-01 a RS-04).

Todo borrado pasa por aquí:
- la raíz de cada objetivo debe estar bajo una base permitida y no ser una ruta protegida;
- ningún tramo de la raíz puede ser un enlace/unión (punto de reanálisis);
- cada archivo a borrar debe estar dentro de su raíz;
- los marcadores de OneDrive/nube no se tocan.
"""
from __future__ import annotations

import ntpath
import os
import stat
import sys

ES_WINDOWS = sys.platform == "win32"

# Atributos de archivo de Windows (stat.FILE_ATTRIBUTE_* no incluye los de la nube)
ATR_OCULTO = 0x2
ATR_SISTEMA = 0x4
ATR_REPARSE = 0x400
ATR_OFFLINE = 0x1000
ATR_RECALL_ON_OPEN = 0x40000
ATR_RECALL_ON_DATA_ACCESS = 0x400000
ATR_NUBE = ATR_OFFLINE | ATR_RECALL_ON_OPEN | ATR_RECALL_ON_DATA_ACCESS


def _nombre_largo(ruta: str) -> str:
    """En Windows, %TEMP% puede venir con nombres cortos 8.3 (C:\\Users\\ALBERT~1\\...). Se pasan a
    nombre largo para que las comparaciones con las rutas protegidas no se puedan esquivar."""
    if not ES_WINDOWS or "~" not in ruta:
        return ruta
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        n = ctypes.windll.kernel32.GetLongPathNameW(ruta, buf, len(buf))
        return buf.value if 0 < n < len(buf) else ruta
    except Exception:  # noqa: BLE001
        return ruta


def normalizar(ruta: str) -> str:
    """Ruta absoluta, normalizada, con nombres largos y en minúsculas (Windows no distingue mayúsculas)."""
    return os.path.normcase(os.path.normpath(_nombre_largo(os.path.abspath(ruta))))


def dentro_de(raiz: str, ruta: str) -> bool:
    """¿`ruta` está dentro de `raiz` (o es la misma)? Sin resolver enlaces: se compara el texto
    normalizado, y los enlaces se rechazan aparte con `es_reparse`."""
    r, p = normalizar(raiz), normalizar(ruta)
    try:
        return os.path.commonpath([r, p]) == r
    except ValueError:            # unidades distintas
        return False


def atributos(st: os.stat_result) -> int:
    return getattr(st, "st_file_attributes", 0)


def es_reparse(st: os.stat_result) -> bool:
    """Unión, enlace simbólico, punto de montaje... (no se siguen nunca)."""
    return bool(atributos(st) & ATR_REPARSE) or stat.S_ISLNK(st.st_mode)


def es_en_nube(st: os.stat_result) -> bool:
    """Marcador de OneDrive/nube sin descargar: no se abre ni se borra."""
    return bool(atributos(st) & ATR_NUBE)


def es_oculto(st: os.stat_result, nombre: str = "") -> bool:
    a = atributos(st)
    return bool(a & (ATR_OCULTO | ATR_SISTEMA)) or (not ES_WINDOWS and nombre.startswith("."))


def _var(nombre: str) -> str:
    v = os.environ.get(nombre, "")
    return normalizar(v) if v else ""


def rutas_protegidas() -> set[str]:
    """Rutas que nunca se borran (ni su contenido directo como objetivo)."""
    sistema = os.environ.get("SystemRoot", r"C:\Windows")
    perfil = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    candidatas = [
        sistema, ntpath.join(sistema, "System32"), ntpath.join(sistema, "SysWOW64"),
        ntpath.join(sistema, "WinSxS"), ntpath.join(sistema, "Installer"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramData", r"C:\ProgramData"),
        os.environ.get("APPDATA", ""), os.environ.get("LOCALAPPDATA", ""),
        perfil, *(ntpath.join(perfil, c) for c in ("Documents", "Desktop", "Pictures", "Videos", "Music",
                                                   "Downloads", "OneDrive", "Favorites")),
        os.environ.get("OneDrive", ""), os.environ.get("OneDriveCommercial", ""),
        os.environ.get("OneDriveConsumer", ""),
    ]
    return {normalizar(c) for c in candidatas if c}


def bases_permitidas() -> list[str]:
    """Bases bajo las que puede estar la raíz de un objetivo del catálogo."""
    sistema = os.environ.get("SystemRoot", r"C:\Windows")
    datos = os.environ.get("ProgramData", r"C:\ProgramData")
    unidad = ntpath.splitdrive(sistema)[0] or "C:"
    bases = [
        os.environ.get("TEMP", ""), os.environ.get("TMP", ""),
        os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", ""),
        os.environ.get("USERPROFILE", ""),
        ntpath.join(sistema, "Temp"), ntpath.join(sistema, "SoftwareDistribution", "Download"),
        ntpath.join(sistema, "ServiceProfiles", "NetworkService", "AppData", "Local", "Microsoft", "Windows",
                    "DeliveryOptimization"),
        ntpath.join(sistema, "Logs"), ntpath.join(sistema, "Minidump"), ntpath.join(sistema, "LiveKernelReports"),
        ntpath.join(sistema, "MEMORY.DMP"),
        ntpath.join(datos, "Microsoft", "Windows", "WER"), ntpath.join(datos, "NVIDIA Corporation", "Downloader"),
        ntpath.join(datos, "Package Cache"),
        unidad + "\\NVIDIA", unidad + "\\AMD",
    ]
    return [normalizar(b) for b in bases if b]


def ruta_permitida(raiz: str, bases: list[str] | None = None, protegidas: set[str] | None = None) -> tuple[bool, str]:
    """¿Se puede limpiar el contenido de `raiz`? Devuelve (sí/no, motivo)."""
    if not raiz or not os.path.isabs(raiz):
        return False, "ruta no absoluta"
    r = normalizar(raiz)
    unidad, resto = os.path.splitdrive(r)
    partes = [p for p in resto.replace("\\", "/").split("/") if p]
    if len(partes) < 2:
        return False, "ruta demasiado general"
    protegidas = rutas_protegidas() if protegidas is None else protegidas
    if r in protegidas:
        return False, "ruta protegida"
    bases = bases_permitidas() if bases is None else bases
    if not any(dentro_de(b, r) for b in bases):
        return False, "fuera de las carpetas permitidas"
    # Ningún tramo de la raíz puede ser un enlace (una unión llevaría el borrado a otra parte)
    actual = unidad + os.sep if unidad else os.sep
    for p in partes:
        actual = os.path.join(actual, p)
        try:
            if es_reparse(os.lstat(actual)):
                return False, f"enlace o unión en la ruta ({p})"
        except FileNotFoundError:
            break
        except OSError:
            return False, "no se puede comprobar la ruta"
    return True, ""


def ruta_borrable_usuario(ruta: str, protegidas: set[str] | None = None) -> tuple[bool, str]:
    """Para enviar a la papelera un archivo elegido en el análisis: archivo normal, no protegido,
    ni dentro de Windows/Program Files."""
    if not os.path.isabs(ruta):
        return False, "ruta no absoluta"
    try:
        st = os.lstat(ruta)
    except OSError:
        return False, "el archivo ya no existe"
    if not stat.S_ISREG(st.st_mode) or es_reparse(st):
        return False, "no es un archivo normal"
    if es_en_nube(st):
        return False, "archivo de OneDrive/nube: bórralo desde OneDrive"
    if atributos(st) & ATR_SISTEMA:
        return False, "archivo de sistema"
    p = normalizar(ruta)
    sistema = os.environ.get("SystemRoot", r"C:\Windows")
    prohibidas = [sistema, os.environ.get("ProgramFiles", r"C:\Program Files"),
                  os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    if any(c and dentro_de(c, p) for c in prohibidas):
        return False, "dentro de Windows o Program Files"
    protegidas = rutas_protegidas() if protegidas is None else protegidas
    if p in protegidas:
        return False, "ruta protegida"
    return True, ""
