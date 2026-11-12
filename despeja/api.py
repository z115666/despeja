"""Puente entre la interfaz y el motor (RS-09).

Todo lo que llega de la interfaz se valida aquí: identificadores contra el catálogo, letras de
unidad con expresión regular y rutas contra el último análisis. La interfaz nunca envía rutas
para borrar.
"""
from __future__ import annotations

import hashlib
import os
import platform
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Optional

from . import NOMBRE, VERSION, auditoria, catalogo, escaner, herramientas, limpiador, seguridad, sistema
from .elevacion import es_admin, reiniciar_como_admin
from .registro import Registro


class Tarea:
    def __init__(self, tipo: str):
        self.id = uuid.uuid4().hex[:12]
        self.tipo = tipo
        self.estado = "corriendo"
        self.progreso: Optional[float] = None
        self.mensaje = ""
        self.lineas: list[str] = []
        self.resultado: Any = None
        self.error = ""
        self.cancelado = threading.Event()
        self.inicio = time.time()

    def linea(self, texto: str):
        self.lineas.append(texto)
        del self.lineas[:-200]

    def a_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo, "estado": self.estado, "progreso": self.progreso,
                "mensaje": self.mensaje, "lineas": self.lineas[-40:], "resultado": self.resultado,
                "error": self.error, "segundos": round(time.time() - self.inicio, 1)}


class Api:
    """Métodos públicos = llamables desde JavaScript (window.pywebview.api.<método>)."""

    def __init__(self, registro: Optional[Registro] = None):
        self._registro = registro or Registro()
        self._tareas: dict[str, Tarea] = {}
        self._ventana = None
        self._ultimo_analisis: set[str] = set()      # rutas que se pueden enviar a la papelera / mostrar
        self._cerrojo = threading.Lock()

    # ------------------------------------------------------------------ utilidades internas
    def _lanzar(self, tipo: str, trabajo: Callable[[Tarea], Any]) -> dict:
        with self._cerrojo:
            for t in self._tareas.values():
                if t.tipo == tipo and t.estado == "corriendo":
                    return {"ok": False, "error": "Ya hay una tarea de este tipo en marcha.", "tarea": t.id}
            t = Tarea(tipo)
            self._tareas[t.id] = t

        def ejecutar():
            try:
                t.resultado = trabajo(t)
                t.estado = "cancelada" if t.cancelado.is_set() else "hecha"
            except Exception as e:  # noqa: BLE001
                t.estado = "error"
                t.error = str(e) or e.__class__.__name__
                t.linea(traceback.format_exc(limit=3))
        threading.Thread(target=ejecutar, daemon=True, name=f"tarea-{tipo}").start()
        return {"ok": True, "tarea": t.id}

    @staticmethod
    def _objetivos(ids) -> list[catalogo.Objetivo]:
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError("lista de elementos no válida")
        desconocidos = [i for i in ids if i not in catalogo.POR_ID]
        if desconocidos:
            raise ValueError(f"elementos desconocidos: {', '.join(desconocidos[:5])}")
        return [catalogo.POR_ID[i] for i in dict.fromkeys(ids)]

    @staticmethod
    def _unidad(letra) -> str:
        letra = str(letra or "").strip().rstrip(":\\").upper()
        if not sistema.LETRA.match(letra):
            raise ValueError("unidad no válida")
        return letra

    @staticmethod
    def _carpeta(ruta) -> str:
        if not isinstance(ruta, str) or not ruta or len(ruta) > 1024 or "\x00" in ruta:
            raise ValueError("ruta no válida")
        ruta = os.path.abspath(ruta)
        if not os.path.isdir(ruta):
            raise ValueError("la carpeta no existe")
        return ruta

    # ------------------------------------------------------------------ información
    def info(self) -> dict:
        return {"nombre": NOMBRE, "version": VERSION, "admin": es_admin(), "equipo": platform.node(),
                "windows": seguridad.ES_WINDOWS, "datos": self._registro.carpeta}

    def unidades(self) -> list[dict]:
        return sistema.unidades()

    def catalogo(self) -> dict:
        return {"categorias": [{"id": i, "nombre": n, "icono": ic} for i, n, ic in catalogo.CATEGORIAS],
                "elementos": [catalogo.a_dict(o) for o in catalogo.CATALOGO]}

    # ------------------------------------------------------------------ limpieza
    def medir(self) -> dict:
        """Calcula cuánto se puede recuperar en cada elemento del catálogo."""
        def trabajo(t: Tarea):
            admin = es_admin()
            todos = [o for o in catalogo.CATALOGO]
            hechos = 0
            resultados: dict[str, dict] = {}

            def uno(o: catalogo.Objetivo):
                try:
                    return medir_uno(o)
                except Exception as e:  # noqa: BLE001 - un elemento con error no detiene el resto
                    return o.id, {"bytes": 0, "archivos": 0, "rutas": 0, "avisos": [f"Error al medir: {e}"]}

            def medir_uno(o: catalogo.Objetivo):
                if o.modo == "papelera_windows":
                    p = sistema.papelera()
                    return o.id, {"bytes": p["bytes"], "archivos": p["elementos"], "rutas": 1, "avisos": []}
                rutas, avisos = catalogo.resolver(o)
                m = escaner.medir(rutas, o.patrones, o.edad_horas, t.cancelado)
                m.update({"rutas": len(rutas), "avisos": avisos})
                return o.id, m

            with ThreadPoolExecutor(max_workers=6) as pool:
                for id_, m in pool.map(uno, todos):
                    hechos += 1
                    t.progreso = hechos / len(todos)
                    t.mensaje = catalogo.POR_ID[id_].nombre
                    m["bloqueado"] = catalogo.POR_ID[id_].admin and not admin
                    resultados[id_] = m
            procesos = sorted({p for o in todos for p in o.procesos})
            abiertos = set(sistema.procesos_abiertos(procesos))
            for o in todos:
                resultados[o.id]["abiertos"] = [p for p in o.procesos if p in abiertos]
            return resultados
        return self._lanzar("medir", trabajo)

    def limpiar(self, ids, simular=True) -> dict:
        objetivos = self._objetivos(ids)
        simular = bool(simular)

        def trabajo(t: Tarea):
            admin = es_admin()
            total_b = total_n = 0
            resumen, filas = {}, []
            for i, o in enumerate(objetivos):
                if t.cancelado.is_set():
                    break
                t.mensaje = o.nombre
                t.progreso = i / max(1, len(objetivos))
                if o.admin and not admin:
                    resumen[o.id] = {"saltado": "requiere administrador"}
                    continue
                if o.modo == "papelera_windows":
                    p = sistema.papelera()
                    ok = True if simular else sistema.vaciar_papelera()
                    r = {"bytes": p["bytes"] if ok else 0, "archivos": p["elementos"] if ok else 0, "en_uso": 0,
                         "errores": 0 if ok else 1}
                else:
                    rutas, avisos = catalogo.resolver(o)
                    res = limpiador.limpiar_objetivo(o, rutas, simular, t.cancelado)
                    r = res.a_dict()
                    r["avisos"] = avisos + res.rechazadas
                    filas += [(e, ruta, b) for e, ruta, b in res.filas]
                resumen[o.id] = r
                total_b += r.get("bytes", 0)
                total_n += r.get("archivos", 0)
                t.linea(f"{o.nombre}: {r.get('archivos', 0)} archivos")
            t.progreso = 1
            nombre = f"{'simulacion' if simular else 'limpieza'}_{datetime.now():%Y%m%d_%H%M%S}"
            csv = self._registro.guardar_detalle(nombre, filas)
            with open(csv, "rb") as f:
                huella = hashlib.sha256(f.read()).hexdigest()
            self._registro.anotar("simulacion" if simular else "limpieza", bytes=total_b, archivos=total_n,
                                  detalle={k: {c: v for c, v in r.items() if c in ("bytes", "archivos", "en_uso",
                                                                                     "errores", "saltado")}
                                           for k, r in resumen.items()},
                                  lista=os.path.basename(csv), lista_sha256=huella)
            return {"simulado": simular, "bytes": total_b, "archivos": total_n, "elementos": resumen,
                    "lista": csv, "cancelado": t.cancelado.is_set()}
        return self._lanzar("limpiar", trabajo)

    # ------------------------------------------------------------------ auditoría
    def oculto(self, letra) -> dict:
        letra = self._unidad(letra)

        def trabajo(t: Tarea):
            def prog(texto):
                t.mensaje = texto
            items = auditoria.espacio_oculto(letra, t.cancelado, prog)
            self._registro.anotar("auditoria_oculto", unidad=letra,
                                  bytes=sum(i["bytes"] or 0 for i in items),
                                  detalle={i["id"]: i["bytes"] for i in items})
            return {"letra": letra, "elementos": items}
        return self._lanzar("oculto", trabajo)

    def analizar(self, destino) -> dict:
        """Analiza una unidad («C») o una carpeta (ruta completa)."""
        if isinstance(destino, str) and len(destino.strip().rstrip(":\\")) == 1:
            raiz = f"{self._unidad(destino)}:\\"
        else:
            raiz = self._carpeta(destino)

        def trabajo(t: Tarea):
            def prog(p):
                t.mensaje = p["carpeta"]
                t.resultado = {"parcial": True, "archivos": p["archivos"], "bytes": p["bytes"]}
            res = auditoria.analizar(raiz, t.cancelado, prog)
            self._ultimo_analisis = {seguridad.normalizar(g["ruta"]) for g in res["grandes"]}
            self._ultimo_analisis |= {seguridad.normalizar(c["ruta"]) for c in res["carpetas"]}
            self._registro.anotar("analisis", raiz=raiz, bytes=res["visibles"] + res["ocultos"],
                                  archivos=res["archivos"], detalle={"ocultos": res["ocultos"], "nube": res["nube"],
                                                                     "sin_permiso": res["sin_permiso"]})
            return res
        return self._lanzar("analizar", trabajo)

    def elegir_carpeta(self) -> Optional[str]:
        if self._ventana is None:
            return None
        import webview
        r = self._ventana.create_file_dialog(webview.FileDialog.FOLDER)
        return r[0] if r else None

    def a_papelera(self, rutas) -> dict:
        """Envía a la papelera archivos del último análisis (RS-06, RS-03)."""
        if not isinstance(rutas, list) or not rutas or len(rutas) > 500:
            raise ValueError("lista de archivos no válida")
        from send2trash import send2trash
        hechos, fallos, total = [], [], 0
        for r in rutas:
            if not isinstance(r, str) or seguridad.normalizar(r) not in self._ultimo_analisis:
                fallos.append({"ruta": str(r)[:300], "motivo": "no está en el último análisis"})
                continue
            ok, motivo = seguridad.ruta_borrable_usuario(r)
            if not ok:
                fallos.append({"ruta": r, "motivo": motivo})
                continue
            try:
                tam = os.lstat(r).st_size
                send2trash(r)
                hechos.append(r)
                total += tam
                self._ultimo_analisis.discard(seguridad.normalizar(r))
            except Exception as e:  # noqa: BLE001
                fallos.append({"ruta": r, "motivo": str(e)[:200]})
        self._registro.anotar("papelera_archivos", bytes=total, archivos=len(hechos),
                              detalle={"enviados": hechos[:200], "fallos": len(fallos)})
        return {"ok": True, "bytes": total, "enviados": hechos, "fallos": fallos}

    def abrir_ubicacion(self, ruta) -> bool:
        if not isinstance(ruta, str) or seguridad.normalizar(ruta) not in self._ultimo_analisis:
            return False
        sistema.abrir_ubicacion(ruta)
        return True

    # ------------------------------------------------------------------ herramientas
    def herramienta(self, id_, letra=None) -> dict:
        if id_ not in herramientas.HERRAMIENTAS:
            raise ValueError("herramienta desconocida")
        if herramientas.HERRAMIENTAS[id_]["admin"] and not es_admin():
            return {"ok": False, "error": "Esta herramienta necesita ejecutar Despeja como administrador."}
        letra = self._unidad(letra) if id_ == "borrado_libre" else None

        def trabajo(t: Tarea):
            t.mensaje = herramientas.HERRAMIENTAS[id_]["nombre"]

            def linea(texto: str):
                t.linea(texto)
                if id_.startswith("dism") and "%" in texto:
                    try:
                        t.progreso = float(texto.split("%")[0].split()[-1].strip("[=")) / 100
                    except (ValueError, IndexError):
                        pass
                if id_ == "borrado_libre":
                    fase = herramientas.fase_cipher(texto)
                    if fase:
                        t.progreso = (fase - 1) / 3
                        t.mensaje = f"Pasada {fase} de 3"
            if id_ in ("dism_analizar", "dism_limpiar"):
                codigo, salida = herramientas.dism(id_ == "dism_limpiar", linea, t.cancelado)
            elif id_.startswith("hibernacion"):
                codigo, salida = herramientas.hibernacion(id_ == "hibernacion_on")
                t.linea(salida or "Hecho.")
            else:
                codigo, salida = herramientas.borrado_libre(letra, linea, t.cancelado)
            t.progreso = 1
            self._registro.anotar("herramienta", herramienta=id_, unidad=letra, codigo=codigo)
            if codigo not in (0, -2):
                raise RuntimeError(f"El comando terminó con código {codigo}. {salida[-300:]}")
            return {"codigo": codigo}
        return self._lanzar(id_, trabajo)

    def abrir_config(self, clave) -> bool:
        if clave not in ("almacenamiento", "limpieza", "proteccion"):
            return False
        return sistema.abrir_configuracion(clave)

    # ------------------------------------------------------------------ tareas
    def tarea(self, id_) -> dict:
        t = self._tareas.get(str(id_))
        return t.a_dict() if t else {"estado": "desconocida"}

    def cancelar(self, id_) -> bool:
        t = self._tareas.get(str(id_))
        if t:
            t.cancelado.set()
        return bool(t)

    # ------------------------------------------------------------------ registro
    def registro(self) -> dict:
        return {"entradas": self._registro.leer(300), "integridad": self._registro.verificar(),
                "carpeta": self._registro.carpeta}

    def exportar(self, formato) -> Optional[str]:
        if formato not in ("html", "csv") or self._ventana is None:
            return None
        import webview
        nombre = f"Despeja_informe_{datetime.now():%Y%m%d_%H%M}.{formato}"
        r = self._ventana.create_file_dialog(webview.FileDialog.SAVE, save_filename=nombre)
        if not r:
            return None
        destino = r if isinstance(r, str) else r[0]
        return self._registro.exportar(destino, formato)

    def abrir_datos(self) -> bool:
        if seguridad.ES_WINDOWS:
            # Justificación B606: carpeta propia de la app
            os.startfile(self._registro.carpeta)  # nosec B606
            return True
        return False

    def reiniciar_admin(self) -> bool:
        if reiniciar_como_admin():
            if self._ventana is not None:
                threading.Timer(0.5, self._ventana.destroy).start()
            return True
        return False
