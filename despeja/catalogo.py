"""Catálogo cerrado de lo que se puede limpiar (RS-01).

Cada objetivo define carpetas con variables de entorno y comodines (`*` para perfiles de navegador).
La interfaz solo envía identificadores; las rutas se resuelven y validan aquí y en `seguridad`.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

from . import seguridad


@dataclass(frozen=True)
class Objetivo:
    id: str
    nombre: str
    categoria: str
    icono: str
    descripcion: str
    rutas: tuple[str, ...]
    patrones: tuple[str, ...] = ()        # si hay, solo archivos que encajen (p. ej. *.log)
    edad_horas: float = 0                 # solo archivos sin cambios desde hace X horas
    admin: bool = False                   # requiere ejecutar como administrador
    riesgo: str = "bajo"                  # bajo | medio
    por_defecto: bool = True
    modo: str = "borrar"                  # borrar | papelera | papelera_windows
    procesos: tuple[str, ...] = ()        # si están abiertos, se avisa (y se saltan archivos en uso)
    nota: str = ""
    archivos_sueltos: bool = False        # la ruta es un archivo concreto (MEMORY.DMP)


CATEGORIAS = [
    ("sistema", "Sistema", "monitor"),
    ("navegadores", "Navegadores", "globe"),
    ("aplicaciones", "Aplicaciones", "app-window"),
    ("gpu", "Gráficos y juegos", "gamepad-2"),
    ("desarrollo", "Desarrollo", "code"),
    ("usuario", "Tus archivos", "folder"),
]

_CHROMIUM = ("Cache", "Code Cache", "GPUCache", "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache",
             r"Service Worker\CacheStorage", r"Service Worker\ScriptCache")


def _chromium(base: str) -> tuple[str, ...]:
    perfiles = tuple(rf"{base}\User Data\*\{c}" for c in _CHROMIUM)
    return perfiles + (rf"{base}\User Data\ShaderCache", rf"{base}\User Data\GrShaderCache",
                       rf"{base}\User Data\GraphiteDawnCache", rf"{base}\User Data\component_crx_cache")


_ELECTRON = ("Cache", "Code Cache", "GPUCache", "DawnCache", r"Service Worker\CacheStorage")


def _electron(base: str) -> tuple[str, ...]:
    return tuple(rf"{base}\{c}" for c in _ELECTRON)


CATALOGO: tuple[Objetivo, ...] = (
    # ---------------------------------------------------------------- Sistema
    Objetivo("temp_usuario", "Archivos temporales", "sistema", "clock",
             "Temporales de tu usuario con más de 24 horas sin usarse.",
             (r"%TEMP%",), edad_horas=24),
    Objetivo("temp_windows", "Temporales de Windows", "sistema", "clock",
             "Carpeta Temp del sistema (más de 24 horas).", (r"%SystemRoot%\Temp",), edad_horas=24, admin=True),
    Objetivo("papelera", "Papelera de reciclaje", "sistema", "trash-2",
             "Vacía la papelera de todas las unidades. Lo que hay en ella no se puede recuperar después.",
             (), modo="papelera_windows", riesgo="medio", por_defecto=False),
    Objetivo("windows_update", "Descargas de Windows Update", "sistema", "download",
             "Actualizaciones ya instaladas. Windows las vuelve a descargar si las necesita.",
             (r"%SystemRoot%\SoftwareDistribution\Download",), admin=True, edad_horas=24),
    Objetivo("optimizacion_entrega", "Optimización de distribución", "sistema", "share-2",
             "Caché de actualizaciones compartidas con otros equipos.",
             (r"%SystemRoot%\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache",),
             admin=True),
    Objetivo("informes_errores", "Informes de errores", "sistema", "file-warning",
             "Informes de fallos de programas ya enviados o en cola.",
             (r"%LOCALAPPDATA%\Microsoft\Windows\WER\ReportArchive", r"%LOCALAPPDATA%\Microsoft\Windows\WER\ReportQueue",
              r"%ProgramData%\Microsoft\Windows\WER\ReportArchive", r"%ProgramData%\Microsoft\Windows\WER\ReportQueue",
              r"%ProgramData%\Microsoft\Windows\WER\Temp")),
    Objetivo("volcados", "Volcados de memoria", "sistema", "cpu",
             "Copias de la memoria tras pantallazos azules o cierres de programas. Solo sirven para diagnosticar.",
             (r"%LOCALAPPDATA%\CrashDumps", r"%SystemRoot%\Minidump", r"%SystemRoot%\LiveKernelReports"),
             admin=True),
    Objetivo("volcado_completo", "Volcado completo (MEMORY.DMP)", "sistema", "cpu",
             "Último volcado completo de memoria. Puede ocupar tanto como tu RAM.",
             (r"%SystemRoot%\MEMORY.DMP",), admin=True, archivos_sueltos=True),
    Objetivo("registros_windows", "Registros de Windows", "sistema", "scroll-text",
             "Registros de instalación y mantenimiento con más de 7 días.",
             (r"%SystemRoot%\Logs\CBS", r"%SystemRoot%\Logs\DISM", r"%SystemRoot%\Logs\MoSetup",
              r"%SystemRoot%\Logs\WindowsUpdate"),
             patrones=("*.log", "*.cab", "*.etl", "*.txt"), edad_horas=24 * 7, admin=True),
    Objetivo("miniaturas", "Miniaturas e iconos", "sistema", "image",
             "Caché de miniaturas del Explorador. Se regenera sola; parte estará en uso y se saltará.",
             (r"%LOCALAPPDATA%\Microsoft\Windows\Explorer",), patrones=("thumbcache_*.db", "iconcache_*.db")),
    Objetivo("directx", "Caché de sombreadores de DirectX", "sistema", "layers",
             "Se regenera al abrir juegos y programas 3D.", (r"%LOCALAPPDATA%\D3DSCache",)),
    Objetivo("cache_web_windows", "Caché web de Windows", "sistema", "globe",
             "Caché de INetCache usada por componentes de Windows y Office.",
             (r"%LOCALAPPDATA%\Microsoft\Windows\INetCache\IE", r"%LOCALAPPDATA%\Microsoft\Windows\INetCache\Low")),
    # ---------------------------------------------------------------- Navegadores
    Objetivo("chrome", "Google Chrome", "navegadores", "chrome",
             "Caché de páginas, código y GPU de todos los perfiles. No toca contraseñas, historial ni sesiones.",
             _chromium(r"%LOCALAPPDATA%\Google\Chrome"), procesos=("chrome.exe",)),
    Objetivo("edge", "Microsoft Edge", "navegadores", "globe",
             "Caché de todos los perfiles. No toca contraseñas, historial ni sesiones.",
             _chromium(r"%LOCALAPPDATA%\Microsoft\Edge"), procesos=("msedge.exe",)),
    Objetivo("brave", "Brave", "navegadores", "shield",
             "Caché de todos los perfiles.", _chromium(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser"),
             procesos=("brave.exe",)),
    Objetivo("opera", "Opera", "navegadores", "globe",
             "Caché del navegador.", (r"%LOCALAPPDATA%\Opera Software\Opera Stable\Cache",
                                     r"%LOCALAPPDATA%\Opera Software\Opera GX Stable\Cache"),
             procesos=("opera.exe",)),
    Objetivo("firefox", "Mozilla Firefox", "navegadores", "flame",
             "Caché de todos los perfiles. No toca contraseñas, historial ni sesiones.",
             (r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles\*\cache2", r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles\*\startupCache",
              r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles\*\thumbnails"), procesos=("firefox.exe",)),
    # ---------------------------------------------------------------- Aplicaciones
    Objetivo("teams", "Microsoft Teams", "aplicaciones", "users",
             "Caché de Teams (nuevo y clásico). No borra chats ni archivos.",
             _electron(r"%APPDATA%\Microsoft\Teams")
             + (r"%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\Default\Cache",
                r"%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\Default\Code Cache",
                r"%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\Default\GPUCache"),
             procesos=("ms-teams.exe", "Teams.exe")),
    Objetivo("discord", "Discord", "aplicaciones", "message-circle", "Caché de imágenes y código.",
             _electron(r"%APPDATA%\discord"), procesos=("Discord.exe",)),
    Objetivo("slack", "Slack", "aplicaciones", "hash", "Caché de imágenes y código.",
             _electron(r"%APPDATA%\Slack"), procesos=("slack.exe",)),
    Objetivo("spotify", "Spotify", "aplicaciones", "music",
             "Canciones en caché para escucharlas más rápido (no las descargas sin conexión).",
             (r"%LOCALAPPDATA%\Spotify\Data", r"%LOCALAPPDATA%\Packages\SpotifyAB.SpotifyMusic_zpdnekdrzrea0\LocalCache\Spotify\Data"),
             procesos=("Spotify.exe",)),
    Objetivo("vscode", "Visual Studio Code", "aplicaciones", "code",
             "Caché, registros y extensiones ya instaladas descargadas.",
             _electron(r"%APPDATA%\Code") + (r"%APPDATA%\Code\CachedData", r"%APPDATA%\Code\CachedExtensionVSIXs",
                                             r"%APPDATA%\Code\logs"), procesos=("Code.exe",)),
    Objetivo("steam_web", "Steam (caché web)", "aplicaciones", "gamepad-2", "Caché del navegador interno de Steam.",
             (r"%LOCALAPPDATA%\Steam\htmlcache",), procesos=("steam.exe", "steamwebhelper.exe")),
    # ---------------------------------------------------------------- GPU
    Objetivo("nvidia_cache", "Cachés de NVIDIA", "gpu", "zap",
             "Sombreadores compilados de DirectX, OpenGL y Vulkan. Se regeneran al jugar (los primeros minutos pueden ir a tirones).",
             (r"%LOCALAPPDATA%\NVIDIA\DXCache", r"%LOCALAPPDATA%\NVIDIA\GLCache", r"%LOCALAPPDATA%\NVIDIA Corporation\NV_Cache")),
    Objetivo("nvidia_instaladores", "Instaladores de NVIDIA", "gpu", "package",
             "Controladores descargados y descomprimidos que ya se instalaron.",
             (r"%ProgramData%\NVIDIA Corporation\Downloader", r"%SystemDrive%\NVIDIA"), admin=True),
    Objetivo("amd_cache", "Cachés de AMD", "gpu", "zap", "Sombreadores compilados. Se regeneran al jugar.",
             (r"%LOCALAPPDATA%\AMD\DxCache", r"%LOCALAPPDATA%\AMD\DxcCache", r"%LOCALAPPDATA%\AMD\GLCache",
              r"%LOCALAPPDATA%\AMD\VkCache")),
    Objetivo("amd_instaladores", "Instaladores de AMD", "gpu", "package",
             "Controladores descomprimidos que ya se instalaron.", (r"%SystemDrive%\AMD",), admin=True),
    # ---------------------------------------------------------------- Desarrollo
    Objetivo("pip", "Caché de pip", "desarrollo", "package", "Paquetes de Python descargados. Se vuelven a bajar si hacen falta.",
             (r"%LOCALAPPDATA%\pip\Cache",), por_defecto=False),
    Objetivo("npm", "Caché de npm", "desarrollo", "package", "Paquetes de Node.js descargados.",
             (r"%LOCALAPPDATA%\npm-cache", r"%APPDATA%\npm-cache"), por_defecto=False),
    Objetivo("yarn_pnpm", "Cachés de Yarn y pnpm", "desarrollo", "package", "Paquetes de Node.js descargados.",
             (r"%LOCALAPPDATA%\Yarn\Cache", r"%LOCALAPPDATA%\pnpm-cache", r"%LOCALAPPDATA%\pnpm\store"), por_defecto=False),
    Objetivo("nuget", "Caché de NuGet", "desarrollo", "package", "Paquetes de .NET descargados.",
             (r"%LOCALAPPDATA%\NuGet\v3-cache", r"%LOCALAPPDATA%\NuGet\plugins-cache", r"%USERPROFILE%\.nuget\packages"),
             por_defecto=False, riesgo="medio", nota="Los proyectos .NET volverán a descargar sus paquetes al compilar."),
    Objetivo("gradle", "Caché de Gradle", "desarrollo", "package", "Dependencias de proyectos Java/Android.",
             (r"%USERPROFILE%\.gradle\caches",), por_defecto=False, riesgo="medio"),
    Objetivo("huggingface", "Modelos de Hugging Face", "desarrollo", "brain",
             "Modelos de IA descargados por Python. Pueden ocupar decenas de GB, pero volver a descargarlos tarda.",
             (r"%USERPROFILE%\.cache\huggingface",), por_defecto=False, riesgo="medio"),
    # ---------------------------------------------------------------- Usuario
    Objetivo("descargas_antiguas", "Descargas antiguas", "usuario", "archive",
             "Archivos de Descargas sin cambios en más de 90 días. Van a la papelera: puedes recuperarlos.",
             (r"%USERPROFILE%\Downloads",), edad_horas=24 * 90, por_defecto=False, riesgo="medio", modo="papelera"),
)

POR_ID = {o.id: o for o in CATALOGO}


def expandir(patron: str) -> list[str]:
    """Expande variables de entorno y comodines. Si falta una variable, no devuelve nada
    (nunca se deja `%VAR%` literal ni se cae a una ruta relativa)."""
    ruta = os.path.expandvars(patron)
    if "%" in ruta or "$" in ruta:
        return []
    if not os.path.isabs(ruta):
        return []
    if "*" in ruta:
        return sorted(glob.glob(ruta))
    return [ruta]


def resolver(obj: Objetivo, bases=None, protegidas=None) -> tuple[list[str], list[str]]:
    """Rutas existentes y permitidas de un objetivo, y avisos de las rechazadas."""
    validas, avisos = [], []
    vistas = set()
    for patron in obj.rutas:
        for r in expandir(patron):
            if not os.path.exists(r):
                continue
            n = seguridad.normalizar(r)
            prot = protegidas
            if obj.modo == "papelera":         # Descargas está protegida para borrar, no para enviar a la papelera
                prot = (seguridad.rutas_protegidas() if protegidas is None else set(protegidas)) - {n}
            ok, motivo = seguridad.ruta_permitida(r, bases, prot)
            if n in vistas:
                continue
            vistas.add(n)
            if ok:
                validas.append(r)
            else:
                avisos.append(f"{r}: {motivo}")
    return validas, avisos


def a_dict(obj: Objetivo) -> dict:
    return {"id": obj.id, "nombre": obj.nombre, "categoria": obj.categoria, "icono": obj.icono,
            "descripcion": obj.descripcion, "admin": obj.admin, "riesgo": obj.riesgo,
            "por_defecto": obj.por_defecto, "modo": obj.modo, "nota": obj.nota,
            "procesos": list(obj.procesos)}
