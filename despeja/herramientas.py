"""Herramientas de sistema (RF-08). Todas usan programas nativos de Windows."""
from __future__ import annotations

import threading
from typing import Callable, Optional

from . import sistema

HERRAMIENTAS = {
    "dism_analizar": {"nombre": "Analizar el almacén de componentes", "admin": True},
    "dism_limpiar": {"nombre": "Limpiar componentes de Windows", "admin": True},
    "hibernacion_off": {"nombre": "Desactivar la hibernación", "admin": True},
    "hibernacion_on": {"nombre": "Activar la hibernación", "admin": True},
    "borrado_libre": {"nombre": "Borrado seguro del espacio libre", "admin": True},
}


def dism(limpiar: bool, por_linea: Callable[[str], None], cancelado: Optional[threading.Event]) -> tuple[int, str]:
    accion = "/StartComponentCleanup" if limpiar else "/AnalyzeComponentStore"
    return sistema.ejecutar("Dism.exe", ["/Online", "/Cleanup-Image", accion, "/English"], timeout=3 * 3600,
                            por_linea=por_linea, cancelado=cancelado)


def hibernacion(activar: bool) -> tuple[int, str]:
    return sistema.ejecutar("powercfg.exe", ["/hibernate", "on" if activar else "off"], timeout=60)


def borrado_libre(letra: str, por_linea: Callable[[str], None], cancelado: Optional[threading.Event]) -> tuple[int, str]:
    """`cipher /w`: sobrescribe el espacio libre (0x00, 0xFF y aleatorio) para que lo borrado
    no se pueda recuperar. No toca archivos existentes."""
    if not sistema.LETRA.match(letra):
        raise ValueError("unidad no válida")
    return sistema.ejecutar("cipher.exe", [f"/w:{letra}:\\"], timeout=48 * 3600, por_linea=por_linea,
                            cancelado=cancelado)


def fase_cipher(linea: str) -> Optional[int]:
    """Fase de cipher (1-3) a partir de su salida, en inglés o español."""
    l = linea.lower()
    if "0x00" in l:
        return 1
    if "0xff" in l:
        return 2
    if "random" in l or "aleatorio" in l:
        return 3
    return None
