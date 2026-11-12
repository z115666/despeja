"""Acceso a Windows: comandos del sistema (RS-10), unidades, papelera y procesos.

Los comandos se ejecutan siempre con ruta absoluta a System32, argumentos en lista, sin shell y
con tiempo máximo. Ningún dato de la interfaz se interpola en un comando sin validarse antes.
"""
from __future__ import annotations

import os
import re
import shutil
# Justificación B404: uso controlado: rutas absolutas, sin shell, argumentos validados
import subprocess  # nosec B404
import threading
from typing import Callable, Optional

from .seguridad import ES_WINDOWS

LETRA = re.compile(r"^[A-Z]$")
_SIN_VENTANA = 0x08000000 if ES_WINDOWS else 0   # CREATE_NO_WINDOW


def system32(programa: str) -> str:
    """Ruta absoluta a un ejecutable de System32 (evita secuestro por PATH o carpeta actual)."""
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.exe", programa):
        raise ValueError("programa no válido")
    raiz = os.environ.get("SystemRoot", r"C:\Windows")
    if programa.lower() == "powershell.exe":
        return os.path.join(raiz, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return os.path.join(raiz, "System32", programa)


def ejecutar(programa: str, args: list[str], timeout: float = 120,
             por_linea: Optional[Callable[[str], None]] = None,
             cancelado: Optional[threading.Event] = None) -> tuple[int, str]:
    """Ejecuta un programa de System32. Devuelve (código, salida). Con `por_linea` va pasando la
    salida en directo; con `cancelado` se puede detener."""
    exe = system32(programa)
    if not os.path.exists(exe):
        return -1, f"No se encuentra {programa}"
    # Justificación B603: ejecutable absoluto de System32, shell=False, args en lista
    proc = subprocess.Popen(  # nosec B603
        [exe, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        creationflags=_SIN_VENTANA, shell=False)
    salida: list[str] = []

    def leer():
        if proc.stdout is None:
            return
        pendiente = b""
        while True:
            trozo = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
            if not trozo:
                break
            pendiente += trozo
            # cipher y DISM actualizan la misma línea con \r
            partes = re.split(rb"[\r\n]+", pendiente)
            pendiente = partes.pop()
            for p in partes:
                t = _decodificar(p).strip()
                if t:
                    salida.append(t)
                    if por_linea:
                        por_linea(t)
        if pendiente.strip():
            t = _decodificar(pendiente).strip()
            salida.append(t)
            if por_linea:
                por_linea(t)

    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()
    limite = timeout
    while hilo.is_alive():
        hilo.join(0.25)
        limite -= 0.25
        if (cancelado is not None and cancelado.is_set()) or limite <= 0:
            proc.kill()
            hilo.join(2)
            return -2 if limite > 0 else -3, "\n".join(salida)
    return proc.wait(), "\n".join(salida)


def _decodificar(b: bytes) -> str:
    for cod in ("utf-8", "cp850", "cp1252"):
        try:
            return b.decode(cod)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1", errors="replace")


# --------------------------------------------------------------------------- unidades
def unidades() -> list[dict]:
    res = []
    if ES_WINDOWS:
        import ctypes
        k32 = ctypes.windll.kernel32
        mascara = k32.GetLogicalDrives()
        letras = [chr(65 + i) for i in range(26) if mascara & (1 << i)]
    else:
        letras = []
    for letra in letras:
        raiz = f"{letra}:\\"
        tipo = _tipo_unidad(raiz)
        if tipo not in ("fija", "extraible"):
            continue
        try:
            uso = shutil.disk_usage(raiz)
        except OSError:
            continue
        etiqueta, fs = _volumen(raiz)
        res.append({"letra": letra, "raiz": raiz, "etiqueta": etiqueta, "fs": fs, "tipo": tipo,
                    "total": uso.total, "usado": uso.used, "libre": uso.free, "ssd": es_ssd(letra),
                    "sistema": raiz.lower() == (os.environ.get("SystemDrive", "C:") + "\\").lower()})
    if not ES_WINDOWS:                       # para desarrollo y pruebas en Linux/macOS
        uso = shutil.disk_usage("/")
        res.append({"letra": "/", "raiz": "/", "etiqueta": "Sistema", "fs": "", "tipo": "fija", "total": uso.total,
                    "usado": uso.used, "libre": uso.free, "ssd": None, "sistema": True})
    return res


def _tipo_unidad(raiz: str) -> str:
    import ctypes
    t = ctypes.windll.kernel32.GetDriveTypeW(raiz)
    return {2: "extraible", 3: "fija", 4: "red", 5: "cd", 6: "ram"}.get(t, "otra")


def _volumen(raiz: str) -> tuple[str, str]:
    import ctypes
    nombre = ctypes.create_unicode_buffer(261)
    fs = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(raiz, nombre, 261, None, None, None, fs, 261)
    return (nombre.value, fs.value) if ok else ("", "")


def es_ssd(letra: str) -> Optional[bool]:
    """¿La unidad es SSD? Consulta de penalización de búsqueda (no necesita administrador)."""
    if not ES_WINDOWS or not LETRA.match(letra):
        return None
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = wintypes.HANDLE
    h = k32.CreateFileW(f"\\\\.\\{letra}:", 0, 3, None, 3, 0, None)
    if h in (None, wintypes.HANDLE(-1).value):
        return None
    try:
        class Consulta(ctypes.Structure):
            _fields_ = [("PropertyId", ctypes.c_int), ("QueryType", ctypes.c_int), ("Extra", ctypes.c_ubyte * 1)]

        class Penalizacion(ctypes.Structure):
            _fields_ = [("Version", wintypes.DWORD), ("Size", wintypes.DWORD), ("IncursSeekPenalty", wintypes.BOOLEAN)]

        q = Consulta(7, 0)                     # StorageDeviceSeekPenaltyProperty, PropertyStandardQuery
        r = Penalizacion()
        dev = wintypes.DWORD()
        ok = k32.DeviceIoControl(wintypes.HANDLE(h), 0x2D1400, ctypes.byref(q), ctypes.sizeof(q),
                                 ctypes.byref(r), ctypes.sizeof(r), ctypes.byref(dev), None)
        return (not r.IncursSeekPenalty) if ok else None
    finally:
        k32.CloseHandle(wintypes.HANDLE(h))


# --------------------------------------------------------------------------- papelera
def papelera(raiz: Optional[str] = None) -> dict:
    """Tamaño y número de elementos de la papelera (de una unidad o de todas)."""
    if not ES_WINDOWS:
        return {"bytes": 0, "elementos": 0}
    import ctypes

    class Info(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64), ("i64NumItems", ctypes.c_int64)]
    info = Info()
    info.cbSize = ctypes.sizeof(Info)
    r = ctypes.windll.shell32.SHQueryRecycleBinW(raiz, ctypes.byref(info))
    if r != 0:
        return {"bytes": 0, "elementos": 0}
    return {"bytes": int(info.i64Size), "elementos": int(info.i64NumItems)}


def vaciar_papelera() -> bool:
    if not ES_WINDOWS:
        return False
    import ctypes
    sin_confirmar, sin_progreso, sin_sonido = 0x1, 0x2, 0x4
    r = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, sin_confirmar | sin_progreso | sin_sonido)
    return r in (0, -2147418113)               # S_OK o E_UNEXPECTED (ya vacía)


# --------------------------------------------------------------------------- procesos
def procesos_abiertos(nombres: list[str]) -> list[str]:
    """Cuáles de estos programas están abiertos (tasklist, sin shell)."""
    if not ES_WINDOWS or not nombres:
        return []
    codigo, salida = ejecutar("tasklist.exe", ["/fo", "csv", "/nh"], timeout=15)
    if codigo != 0:
        return []
    abiertos = {linea.split('","')[0].strip('"').lower() for linea in salida.splitlines() if linea.startswith('"')}
    return [n for n in nombres if n.lower() in abiertos]


def abrir_ubicacion(ruta: str) -> None:
    """Abre el Explorador con el archivo seleccionado."""
    if ES_WINDOWS and os.path.exists(ruta):
        explorer = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe")
        # Justificación B603: explorer.exe con ruta absoluta, sin shell; `ruta` sale del último análisis
        subprocess.Popen([explorer, "/select,", os.path.normpath(ruta)], shell=False)  # nosec B603


CONFIGURACION = {
    "almacenamiento": "ms-settings:storagesense",
    "limpieza": "ms-settings:storagepolicies",
}


def abrir_configuracion(clave: str) -> bool:
    if not ES_WINDOWS:
        return False
    if clave == "proteccion":
        exe = system32("SystemPropertiesProtection.exe")
        subprocess.Popen([exe], shell=False)  # nosec B603
        return True
    uri = CONFIGURACION.get(clave)
    if uri:
        # Justificación B606: URI fija de la lista blanca
        os.startfile(uri)  # nosec B606
        return True
    return False
