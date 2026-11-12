"""Auditoría del espacio visible y oculto (RF-05, RF-06). Solo lectura."""
from __future__ import annotations

import heapq
import json
import os
import threading
import time
from collections import defaultdict
from typing import Callable, Optional

from . import escaner, sistema
from .elevacion import es_admin
from .seguridad import ES_WINDOWS

TIPOS = {
    "Vídeo": ("mp4", "mkv", "avi", "mov", "wmv", "webm", "m4v", "ts", "mts", "flv"),
    "Imágenes": ("jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "heic", "webp", "raw", "cr2", "nef", "arw", "psd", "svg"),
    "Audio": ("mp3", "wav", "flac", "aac", "m4a", "ogg", "wma", "opus"),
    "Documentos": ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "txt", "md", "rtf", "csv", "epub"),
    "Comprimidos": ("zip", "rar", "7z", "tar", "gz", "bz2", "xz", "cab", "zst"),
    "Instaladores e imágenes de disco": ("exe", "msi", "msix", "appx", "iso", "img", "dmg"),
    "Máquinas virtuales": ("vhd", "vhdx", "vmdk", "vdi", "qcow2", "avhdx"),
    "Modelos de IA": ("gguf", "safetensors", "ckpt", "pt", "pth", "onnx", "bin"),
    "Programas y bibliotecas": ("dll", "sys", "so", "pyd", "lib", "jar", "node"),
    "Código": ("py", "js", "ts", "cs", "java", "c", "cpp", "h", "go", "rs", "ps1", "json", "xml", "html", "css"),
    "Bases de datos y cachés": ("db", "sqlite", "ldb", "log", "etl", "dat", "tmp", "pak", "pst", "ost"),
}
_EXT = {e: t for t, exts in TIPOS.items() for e in exts}


def tipo_de(nombre: str) -> str:
    _, ext = os.path.splitext(nombre)
    return _EXT.get(ext[1:].lower(), "Otros")


def analizar(raiz: str, cancelado: Optional[threading.Event] = None,
             progreso: Optional[Callable[[dict], None]] = None, top: int = 60) -> dict:
    """Recorre `raiz` (unidad o carpeta) y devuelve el desglose del espacio."""
    t0 = time.time()
    incid = escaner.Incidencias()
    visibles = ocultos = nube = n = 0
    por_carpeta: dict[str, int] = defaultdict(int)
    por_tipo: dict[str, int] = defaultdict(int)
    grandes: list[tuple[int, str, bool]] = []
    raiz_n = os.path.normpath(raiz)
    ultimo = 0.0
    for a in escaner.recorrer(raiz, incid, cancelado):
        n += 1
        if a.nube:
            nube += a.bytes
            continue
        if a.oculto:
            ocultos += a.bytes
        else:
            visibles += a.bytes
        rel = os.path.relpath(a.ruta, raiz_n)
        primera = rel.split(os.sep, 1)[0] if os.sep in rel else "(archivos sueltos)"
        por_carpeta[primera] += a.bytes
        por_tipo[tipo_de(a.ruta)] += a.bytes
        if len(grandes) < top:
            heapq.heappush(grandes, (a.bytes, a.ruta, a.oculto))
        elif a.bytes > grandes[0][0]:
            heapq.heapreplace(grandes, (a.bytes, a.ruta, a.oculto))
        if progreso and time.time() - ultimo > 0.4:
            ultimo = time.time()
            progreso({"archivos": n, "bytes": visibles + ocultos, "carpeta": os.path.dirname(a.ruta)})
    carpetas = sorted(por_carpeta.items(), key=lambda x: -x[1])[:25]
    res = {
        "raiz": raiz, "segundos": round(time.time() - t0, 1), "archivos": n,
        "visibles": visibles, "ocultos": ocultos, "nube": nube,
        "carpetas": [{"nombre": k, "ruta": os.path.join(raiz_n, k) if k != "(archivos sueltos)" else raiz_n, "bytes": v}
                     for k, v in carpetas],
        "tipos": [{"tipo": k, "bytes": v} for k, v in sorted(por_tipo.items(), key=lambda x: -x[1])],
        "grandes": [{"ruta": r, "nombre": os.path.basename(r), "carpeta": os.path.dirname(r), "bytes": b,
                     "oculto": o, "tipo": tipo_de(r)} for b, r, o in sorted(grandes, reverse=True)],
        "sin_permiso": incid.sin_permiso, "carpetas_sin_permiso": incid.carpetas_sin_permiso[:50],
        "enlaces": incid.enlaces_saltados, "cancelado": bool(cancelado and cancelado.is_set()),
    }
    # En una unidad completa, lo que el sistema dice ocupado y no se ha podido contar
    if os.path.splitdrive(raiz_n)[1] in ("\\", "/", ""):
        try:
            import shutil
            usado = shutil.disk_usage(raiz).used
            res["usado_unidad"] = usado
            res["no_contabilizado"] = max(0, usado - visibles - ocultos)
        except OSError:
            pass
    return res


def _tam_raiz(letra: str, nombre: str) -> Optional[int]:
    """Tamaño de un archivo de la raíz de la unidad sin abrirlo (pagefile.sys no se puede abrir)."""
    try:
        with os.scandir(f"{letra}:\\") as it:
            for e in it:
                if e.name.lower() == nombre.lower():
                    return e.stat(follow_symlinks=False).st_size
    except OSError:
        return None
    return None


def instantaneas() -> dict:
    """Espacio de puntos de restauración / instantáneas por unidad (WMI; requiere administrador)."""
    if not ES_WINDOWS:
        return {}
    script = ("$v=@{}; Get-CimInstance Win32_Volume | ForEach-Object { $v[$_.DeviceID]=$_.DriveLetter };"
              "Get-CimInstance Win32_ShadowStorage | ForEach-Object { [pscustomobject]@{"
              "letra=$v[$_.Volume.DeviceID]; usado=$_.UsedSpace; maximo=$_.MaxSpace; asignado=$_.AllocatedSpace } }"
              " | ConvertTo-Json -Compress")
    codigo, salida = sistema.ejecutar("powershell.exe", ["-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                                                         "Bypass", "-Command", script], timeout=60)
    if codigo != 0 or not salida.strip():
        return {}
    try:
        datos = json.loads(salida[salida.find("["):] if salida.lstrip().startswith("[") else salida[salida.find("{"):])
    except (json.JSONDecodeError, ValueError):
        return {}
    if isinstance(datos, dict):
        datos = [datos]
    res = {}
    for d in datos:
        letra = (d.get("letra") or "").rstrip(":").upper()
        if letra:
            res[letra] = {"usado": int(d.get("usado") or 0), "maximo": int(d.get("maximo") or 0)}
    return res


def espacio_oculto(letra: str, cancelado: Optional[threading.Event] = None,
                   progreso: Optional[Callable[[str], None]] = None) -> list[dict]:
    """Lo que ocupa espacio sin verse en el Explorador, con qué se puede hacer."""
    if not sistema.LETRA.match(letra):
        raise ValueError("unidad no válida")
    sistema_drive = os.environ.get("SystemDrive", "C:").rstrip(":").upper()
    raiz_sistema = os.environ.get("SystemRoot", r"C:\Windows")
    items = []

    def item(id_, nombre, bytes_, descripcion, accion=None, icono="eye-off", nota=""):
        items.append({"id": id_, "nombre": nombre, "bytes": bytes_, "descripcion": descripcion,
                      "accion": accion, "icono": icono, "nota": nota})

    hib = _tam_raiz(letra, "hiberfil.sys")
    if hib:
        item("hiberfil", "Hibernación (hiberfil.sys)", hib,
             "Guarda la memoria al hibernar y para el inicio rápido. Desactivar la hibernación lo elimina.",
             "hibernacion", "moon")
    pag = _tam_raiz(letra, "pagefile.sys")
    if pag:
        item("pagefile", "Archivo de paginación (pagefile.sys)", pag,
             "Memoria virtual. Windows lo gestiona; no conviene quitarlo.", None, "memory-stick")
    swp = _tam_raiz(letra, "swapfile.sys")
    if swp:
        item("swapfile", "Intercambio de apps (swapfile.sys)", swp, "Memoria de las apps de la Tienda. Lo gestiona Windows.",
             None, "memory-stick")
    pap = sistema.papelera(f"{letra}:\\")
    item("papelera", "Papelera de reciclaje", pap["bytes"],
         f"{pap['elementos']} elementos borrados que siguen ocupando espacio.", "papelera", "trash-2")

    if progreso:
        progreso("Puntos de restauración")
    if es_admin():
        sh = instantaneas().get(letra)
        if sh:
            item("instantaneas", "Puntos de restauración", sh["usado"],
                 f"Instantáneas de volumen (máximo asignado: {sh['maximo'] / 1024**3:.1f} GB).", "proteccion", "history")
    else:
        item("instantaneas", "Puntos de restauración", None,
             "Para medirlos hace falta ejecutar como administrador.", "proteccion", "history",
             nota="admin")

    if letra == sistema_drive:
        for id_, nombre, ruta, desc, accion, icono in (
            ("winsxs", "Almacén de componentes (WinSxS)", os.path.join(raiz_sistema, "WinSxS"),
             "Componentes de Windows y versiones anteriores de actualizaciones. Parte de su tamaño son archivos "
             "compartidos con Windows, así que lo que ocupa de verdad es menos. Se reduce con DISM, nunca a mano.",
             "dism", "boxes"),
            ("installer", "Instaladores de programas (Installer)", os.path.join(raiz_sistema, "Installer"),
             "Necesarios para reparar y desinstalar programas. No se deben borrar.", None, "package"),
            ("windows_old", "Instalación anterior (Windows.old)", f"{letra}:\\Windows.old",
             "Copia de la versión anterior de Windows. Se borra desde Configuración ▸ Almacenamiento.",
             "almacenamiento", "archive"),
            ("actualizaciones", "Windows Update (SoftwareDistribution)", os.path.join(raiz_sistema, "SoftwareDistribution"),
             "Base de datos y descargas de actualizaciones. Las descargas se limpian en la pestaña Limpieza.",
             None, "download"),
        ):
            if cancelado is not None and cancelado.is_set():
                break
            if not os.path.exists(ruta):
                continue
            if progreso:
                progreso(nombre)
            incid = escaner.Incidencias()
            total = sum(a.bytes for a in escaner.recorrer(ruta, incid, cancelado) if not a.nube)
            nota = "parcial" if incid.sin_permiso else ""
            item(id_, nombre, total, desc, accion, icono, nota)
    return items
