"""Recorrido seguro del sistema de archivos (RS-02, RS-04).

- No sigue uniones, enlaces ni puntos de montaje.
- No abre archivos (solo lee los datos del directorio): los marcadores de OneDrive no se descargan.
- Iterativo (sin recursión): aguanta árboles muy profundos.
"""
from __future__ import annotations

import fnmatch
import os
import stat
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from . import seguridad


@dataclass
class Archivo:
    ruta: str
    bytes: int
    mtime: float
    oculto: bool
    nube: bool


@dataclass
class Incidencias:
    sin_permiso: int = 0
    enlaces_saltados: int = 0
    nube_saltados: int = 0
    carpetas_sin_permiso: list[str] = field(default_factory=list)


def recorrer(raiz: str, incid: Optional[Incidencias] = None,
             cancelado: Optional[threading.Event] = None) -> Iterator[Archivo]:
    """Todos los archivos bajo `raiz` (o la propia raíz si es un archivo)."""
    incid = incid if incid is not None else Incidencias()
    try:
        st = os.lstat(raiz)
    except OSError:
        return
    if seguridad.es_reparse(st):
        incid.enlaces_saltados += 1
        return
    if stat.S_ISREG(st.st_mode):
        yield Archivo(raiz, st.st_size, st.st_mtime, seguridad.es_oculto(st, os.path.basename(raiz)),
                      seguridad.es_en_nube(st))
        return
    pendientes = [raiz]
    while pendientes:
        if cancelado is not None and cancelado.is_set():
            return
        carpeta = pendientes.pop()
        try:
            it = os.scandir(carpeta)
        except PermissionError:
            incid.sin_permiso += 1
            if len(incid.carpetas_sin_permiso) < 200:
                incid.carpetas_sin_permiso.append(carpeta)
            continue
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                if seguridad.es_reparse(st):
                    incid.enlaces_saltados += 1
                    continue
                if stat.S_ISDIR(st.st_mode):
                    pendientes.append(e.path)
                elif stat.S_ISREG(st.st_mode):
                    yield Archivo(e.path, st.st_size, st.st_mtime, seguridad.es_oculto(st, e.name),
                                  seguridad.es_en_nube(st))


def coincide(nombre: str, patrones: tuple[str, ...]) -> bool:
    return not patrones or any(fnmatch.fnmatch(nombre.lower(), p.lower()) for p in patrones)


def candidatos(raiz: str, patrones=(), edad_horas: float = 0, incid: Optional[Incidencias] = None,
               cancelado=None, ahora: Optional[float] = None) -> Iterator[Archivo]:
    """Archivos de `raiz` que cumplen los filtros de un objetivo (sin los de la nube)."""
    incid = incid if incid is not None else Incidencias()
    limite = (ahora or time.time()) - edad_horas * 3600
    for a in recorrer(raiz, incid, cancelado):
        if a.nube:
            incid.nube_saltados += 1
            continue
        if not seguridad.dentro_de(raiz, a.ruta):          # defensa en profundidad
            continue
        if edad_horas and a.mtime > limite:
            continue
        if not coincide(os.path.basename(a.ruta), patrones):
            continue
        yield a


def medir(raices: list[str], patrones=(), edad_horas: float = 0, cancelado=None,
          progreso: Optional[Callable[[int, int], None]] = None) -> dict:
    """Bytes y número de archivos que se limpiarían."""
    total = n = 0
    incid = Incidencias()
    for r in raices:
        for a in candidatos(r, patrones, edad_horas, incid, cancelado):
            total += a.bytes
            n += 1
            if progreso and n % 2000 == 0:
                progreso(n, total)
    return {"bytes": total, "archivos": n, "sin_permiso": incid.sin_permiso,
            "enlaces": incid.enlaces_saltados, "nube": incid.nube_saltados}
