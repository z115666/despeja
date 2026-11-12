"""Registro de auditoría a prueba de manipulación (RS-11).

Archivo JSON Lines: cada entrada incluye el SHA-256 de la anterior (`prev`) y su propio hash
(`hash`, calculado sobre la entrada sin ese campo). Si alguien edita, borra o reordena una línea,
`verificar()` indica la primera que no cuadra.
"""
from __future__ import annotations

import csv
import getpass
import hashlib
import html
import json
import os
import platform
import threading
from datetime import datetime, timezone

GENESIS = "0" * 64


def carpeta_datos() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    ruta = os.path.join(base, "Despeja")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def _hash(entrada: dict) -> str:
    datos = json.dumps({k: v for k, v in entrada.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(datos.encode("utf-8")).hexdigest()


class Registro:
    def __init__(self, carpeta: str | None = None):
        self.carpeta = carpeta or carpeta_datos()
        os.makedirs(self.carpeta, exist_ok=True)
        self.ruta = os.path.join(self.carpeta, "registro.jsonl")
        self.detalles = os.path.join(self.carpeta, "detalles")
        os.makedirs(self.detalles, exist_ok=True)
        self._cerrojo = threading.Lock()

    def _ultimo_hash(self) -> str:
        if not os.path.exists(self.ruta):
            return GENESIS
        ultimo = GENESIS
        with open(self.ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    try:
                        ultimo = json.loads(linea).get("hash", ultimo)
                    except json.JSONDecodeError:
                        continue
        return ultimo

    def anotar(self, accion: str, **datos) -> dict:
        from .elevacion import es_admin
        with self._cerrojo:
            entrada = {
                "fecha": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "accion": accion,
                "usuario": _usuario(),
                "equipo": platform.node(),
                "admin": es_admin(),
                **datos,
                "prev": self._ultimo_hash(),
            }
            entrada["hash"] = _hash(entrada)
            with open(self.ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
            return entrada

    def guardar_detalle(self, nombre: str, filas: list[tuple]) -> str:
        """Lista de archivos de una operación (CSV). Devuelve la ruta y su SHA-256 va al registro."""
        seguro = "".join(c for c in nombre if c.isalnum() or c in "-_")[:60]
        ruta = os.path.join(self.detalles, f"{seguro}.csv")
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["resultado", "ruta", "bytes"])
            w.writerows(filas)
        return ruta

    def leer(self, limite: int = 500) -> list[dict]:
        if not os.path.exists(self.ruta):
            return []
        entradas = []
        with open(self.ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    try:
                        entradas.append(json.loads(linea))
                    except json.JSONDecodeError:
                        entradas.append({"accion": "linea_ilegible", "hash": ""})
        return entradas[-limite:][::-1]

    def verificar(self) -> dict:
        """Comprueba la cadena completa. {'ok': bool, 'entradas': n, 'error': ..., 'linea': n}."""
        if not os.path.exists(self.ruta):
            return {"ok": True, "entradas": 0}
        prev = GENESIS
        n = 0
        with open(self.ruta, encoding="utf-8") as f:
            for n, linea in enumerate((l for l in f if l.strip()), start=1):
                try:
                    e = json.loads(linea)
                except json.JSONDecodeError:
                    return {"ok": False, "entradas": n, "linea": n, "error": "línea ilegible"}
                if e.get("prev") != prev:
                    return {"ok": False, "entradas": n, "linea": n, "error": "falta o se ha movido una entrada anterior"}
                if _hash(e) != e.get("hash"):
                    return {"ok": False, "entradas": n, "linea": n, "error": "entrada modificada"}
                prev = e["hash"]
        return {"ok": True, "entradas": n}

    def exportar(self, destino: str, formato: str) -> str:
        entradas = self.leer(limite=100000)[::-1]
        if formato == "csv":
            with open(destino, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["fecha", "accion", "usuario", "equipo", "admin", "bytes", "archivos", "detalle", "hash"])
                for e in entradas:
                    w.writerow([e.get("fecha", ""), e.get("accion", ""), e.get("usuario", ""), e.get("equipo", ""),
                                e.get("admin", ""), e.get("bytes", ""), e.get("archivos", ""),
                                json.dumps(e.get("detalle", ""), ensure_ascii=False), e.get("hash", "")])
        else:
            v = self.verificar()
            filas = "".join(
                "<tr>" + "".join(f"<td>{html.escape(str(x))}</td>" for x in (
                    e.get("fecha", ""), e.get("accion", ""), e.get("usuario", ""), _bytes(e.get("bytes", 0)),
                    e.get("archivos", ""), json.dumps(e.get("detalle", ""), ensure_ascii=False)[:300],
                    e.get("hash", "")[:16])) + "</tr>" for e in entradas)
            estado = "Íntegro" if v["ok"] else f"MANIPULADO (línea {v.get('linea')}: {v.get('error')})"
            doc = f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>Informe Despeja</title>
<style>body{{font:14px/1.5 'Segoe UI',sans-serif;margin:32px;color:#1d2733}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #dde3ea;padding:6px 8px;text-align:left;vertical-align:top}}th{{background:#f1f4f7}}
td:nth-child(6){{font-size:12px;color:#5b6675}}</style>
<h1>Informe de auditoría de Despeja</h1>
<p>Equipo: {html.escape(platform.node())} · Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}
· Entradas: {v['entradas']} · Cadena de hashes: <b>{html.escape(estado)}</b></p>
<table><tr><th>Fecha</th><th>Acción</th><th>Usuario</th><th>Espacio</th><th>Archivos</th><th>Detalle</th><th>Hash</th></tr>
{filas}</table></html>"""
            with open(destino, "w", encoding="utf-8") as f:
                f.write(doc)
        return destino


def _usuario() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "desconocido"


def _bytes(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024
    return ""
