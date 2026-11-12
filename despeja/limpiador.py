"""Limpieza de un objetivo del catálogo (RS-01 a RS-07).

Solo borra archivos que devuelve `escaner.candidatos` (dentro de la raíz, sin enlaces ni nube).
Los archivos en uso se saltan. En modo «papelera» se envían a la papelera de Windows.
Las carpetas vacías se eliminan de abajo arriba, nunca la raíz del objetivo.
"""
from __future__ import annotations

import os
import stat
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import escaner, seguridad
from .catalogo import Objetivo


@dataclass
class Resultado:
    id: str
    simulado: bool
    bytes: int = 0
    archivos: int = 0
    en_uso: int = 0
    errores: int = 0
    sin_permiso: int = 0
    enlaces: int = 0
    nube: int = 0
    rechazadas: list[str] = field(default_factory=list)
    filas: list[tuple] = field(default_factory=list)     # (resultado, ruta, bytes) para el detalle

    def a_dict(self) -> dict:
        d = self.__dict__.copy()
        d.pop("filas")
        return d


MAX_FILAS = 50000


def _borrar(ruta: str) -> str:
    """'ok', 'en_uso' o 'error'."""
    try:
        os.remove(ruta)
        return "ok"
    except PermissionError:
        try:                                   # solo lectura: se quita el atributo y se reintenta
            os.chmod(ruta, stat.S_IWRITE)
            os.remove(ruta)
            return "ok"
        except PermissionError:
            return "en_uso"
        except OSError:
            return "error"
    except FileNotFoundError:
        return "ok"
    except OSError as e:
        return "en_uso" if getattr(e, "winerror", 0) == 32 else "error"


def _subcarpetas_seguras(raiz: str) -> list[str]:
    """Subcarpetas de `raiz` (de más profunda a menos), sin entrar en enlaces ni uniones."""
    todas, pendientes = [], [raiz]
    while pendientes:
        c = pendientes.pop()
        try:
            with os.scandir(c) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat.S_ISDIR(st.st_mode) and not seguridad.es_reparse(st):
                        todas.append(e.path)
                        pendientes.append(e.path)
        except OSError:
            continue
    return sorted(todas, key=lambda p: p.count(os.sep), reverse=True)


def _quitar_carpetas_vacias(raiz: str, cancelado=None):
    """Elimina subcarpetas vacías (nunca la raíz ni nada alcanzado a través de un enlace)."""
    for carpeta in _subcarpetas_seguras(raiz):
        if cancelado is not None and cancelado.is_set():
            return
        if not seguridad.dentro_de(raiz, carpeta):
            continue
        try:
            os.rmdir(carpeta)                  # falla si no está vacía: correcto
        except OSError:
            pass


def limpiar_objetivo(obj: Objetivo, raices: list[str], simular: bool = True,
                     cancelado: Optional[threading.Event] = None,
                     progreso: Optional[Callable[[int, int], None]] = None,
                     enviar_a_papelera: Optional[Callable[[str], None]] = None,
                     validar: Optional[Callable[[str], tuple[bool, str]]] = None) -> Resultado:
    res = Resultado(obj.id, simular)
    incid = escaner.Incidencias()
    if enviar_a_papelera is None and obj.modo == "papelera" and not simular:
        from send2trash import send2trash
        enviar_a_papelera = send2trash
    for raiz in raices:
        # La raíz se vuelve a validar justo antes de borrar (por si cambió desde el análisis)
        if validar is not None:
            ok, motivo = validar(raiz)
        elif obj.modo == "papelera":           # Descargas: protegida para borrar, no para la papelera
            ok, motivo = seguridad.ruta_permitida(
                raiz, protegidas=seguridad.rutas_protegidas() - {seguridad.normalizar(raiz)})
        else:
            ok, motivo = seguridad.ruta_permitida(raiz)
        if not ok:
            res.rechazadas.append(f"{raiz}: {motivo}")
            continue
        for a in escaner.candidatos(raiz, obj.patrones, obj.edad_horas, incid, cancelado):
            if cancelado is not None and cancelado.is_set():
                break
            if simular:
                estado = "simulado"
            elif obj.modo == "papelera":
                try:
                    enviar_a_papelera(a.ruta)
                    estado = "papelera"
                except Exception:  # noqa: BLE001 - archivo en uso o sin permiso
                    estado = "en_uso"
            else:
                estado = _borrar(a.ruta)
            if estado in ("ok", "simulado", "papelera"):
                res.bytes += a.bytes
                res.archivos += 1
            elif estado == "en_uso":
                res.en_uso += 1
            else:
                res.errores += 1
            if len(res.filas) < MAX_FILAS:
                res.filas.append((estado, a.ruta, a.bytes))
            if progreso and (res.archivos + res.en_uso) % 500 == 0:
                progreso(res.archivos, res.bytes)
        if not simular and obj.modo == "borrar" and not obj.archivos_sueltos:
            _quitar_carpetas_vacias(raiz, cancelado)
    res.sin_permiso, res.enlaces, res.nube = incid.sin_permiso, incid.enlaces_saltados, incid.nube_saltados
    return res
