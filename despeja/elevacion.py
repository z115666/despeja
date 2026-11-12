"""Mínimo privilegio (RS-08): se arranca como usuario y solo se eleva si el usuario lo pide."""
from __future__ import annotations

import os
import sys

from .seguridad import ES_WINDOWS


def es_admin() -> bool:
    if ES_WINDOWS:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:  # noqa: BLE001
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def reiniciar_como_admin() -> bool:
    """Vuelve a abrir la app con UAC. True si Windows aceptó lanzarla (el usuario dijo «Sí»)."""
    if not ES_WINDOWS:
        return False
    import ctypes
    # Justificación B404: solo para list2cmdline (citado seguro de argumentos)
    import subprocess  # nosec B404
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, sys.argv[1:]
    else:
        exe, args = sys.executable, [os.path.abspath(sys.argv[0]), *sys.argv[1:]]
    parametros = subprocess.list2cmdline(args)
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, parametros, None, 1)
    return r > 32
