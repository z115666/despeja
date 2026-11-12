# Despeja: ciclo de vida de desarrollo seguro (SDLC)

Documento de conformidad del proyecto. Sigue las fases de un SDLC seguro (alineado con NIST SSDF SP 800-218 y OWASP SAMM) y enlaza las evidencias de cada una.

| Fase | Entregable | Dónde |
|---|---|---|
| 1. Requisitos | Requisitos funcionales y de seguridad | Este documento, §1 |
| 2. Diseño | Arquitectura y modelo de amenazas STRIDE | §2 y `MODELO_AMENAZAS.md` |
| 3. Implementación | Código con controles trazados a requisitos | `despeja/`, §3 |
| 4. Verificación | Pruebas unitarias, SAST, auditoría de dependencias | `informes/`, §4 |
| 5. Publicación | Compilación reproducible, hashes SHA-256, CI | `build_exe.bat`, `.github/workflows/ci.yml`, §5 |
| 6. Mantenimiento | Política de vulnerabilidades y versiones | `SECURITY.md`, §6 |

---

## 1. Requisitos

### 1.1 Funcionales
| ID | Requisito |
|---|---|
| RF-01 | Mostrar todas las unidades con su espacio total, usado y libre, el sistema de archivos y el tipo (SSD/HDD). |
| RF-02 | Calcular cuánto ocupa cada elemento limpiable: temporales, cachés de navegadores, aplicaciones, GPU, Windows Update, volcados, registros, papelera, cachés de desarrollo y descargas antiguas. |
| RF-03 | Simular la limpieza (qué se borraría y cuánto) sin tocar nada. |
| RF-04 | Limpiar los elementos elegidos y mostrar el espacio recuperado, los archivos en uso que se saltaron y los errores. |
| RF-05 | Auditar el espacio oculto: hiberfil.sys, pagefile.sys, swapfile.sys, puntos de restauración (instantáneas), WinSxS, Windows.old, Installer, papelera y espacio no contabilizado. |
| RF-06 | Analizar una unidad o carpeta: visible frente a oculto, carpetas y archivos más grandes, tipos de archivo, carpetas sin permiso y archivos solo en la nube. |
| RF-07 | Enviar a la papelera archivos grandes elegidos desde el análisis. |
| RF-08 | Herramientas: limpieza de componentes de Windows (DISM), hibernación, puntos de restauración y borrado seguro del espacio libre. |
| RF-09 | Registro de todas las operaciones, verificable, y exportación de informes HTML y CSV. |
| RF-10 | Interfaz moderna y responsive (de 360 px a pantalla completa), con tema claro/oscuro según Windows y manejable con teclado. |

### 1.2 De seguridad
| ID | Requisito | Control |
|---|---|---|
| RS-01 | Solo se borra dentro de una **lista cerrada** de carpetas conocidas; nunca rutas que lleguen de la interfaz. | `catalogo.py`, `seguridad.ruta_permitida` |
| RS-02 | **No se siguen** uniones, enlaces simbólicos ni puntos de montaje (evita borrar fuera por un enlace). | `seguridad.es_reparse`, recorrido sin seguir enlaces |
| RS-03 | Rutas **protegidas** que nunca se tocan aunque un error de catálogo las incluyera: raíz de unidad, Windows, Program Files, perfil, Documentos, Escritorio, OneDrive, `Installer`, `System32`... | `seguridad.RUTAS_PROTEGIDAS` |
| RS-04 | **Archivos de OneDrive/nube** (marcadores sin descargar) nunca se borran ni se abren: borrarlos los quitaría también de la nube. | atributos `RECALL_*`/`OFFLINE` |
| RS-05 | Los temporales solo se borran si llevan más de 24 h sin cambios (no rompe programas abiertos); los archivos en uso se saltan. | filtro `edad_horas` |
| RS-06 | Lo que pertenece al usuario (descargas antiguas, archivos grandes) va a la **papelera**, nunca se borra directamente. | `send2trash` |
| RS-07 | **Simular antes de limpiar** y confirmación explícita con el resumen de lo que se va a borrar. | interfaz + `api.py` |
| RS-08 | **Mínimo privilegio**: arranca sin administrador. Solo se eleva si el usuario lo pide, para los elementos de sistema. | `elevacion.py`, manifiesto `asInvoker` |
| RS-09 | **Validación** de todo lo que entra desde la interfaz: identificadores contra el catálogo, letras de unidad con expresión regular y rutas existentes. | `api.py` |
| RS-10 | Comandos del sistema con **ruta absoluta** a System32, argumentos en lista, sin `shell=True` y con tiempo máximo. | `sistema.ejecutar` |
| RS-11 | **Registro de auditoría a prueba de manipulación**: cada entrada lleva el SHA-256 de la anterior (cadena de hashes) y la app puede verificarla. | `registro.py` |
| RS-12 | **Sin red**: ninguna conexión saliente, sin telemetría y sin servidor local. La interfaz se carga como HTML en memoria con una CSP estricta (`default-src 'none'`). | `app.py`, `ui/index.html` |
| RS-13 | En la interfaz no se inserta HTML con datos: todo va por `textContent` (evita XSS con nombres de archivo maliciosos). | `ui/app.js` |
| RS-14 | Dependencias **mínimas y fijadas**, auditadas con pip-audit; código analizado con bandit; ejecutable publicado con su SHA-256. | `requirements.txt`, CI |

## 2. Diseño

```
┌──────────── Ventana nativa (WebView2, sin red) ────────────┐
│  ui/index.html + app.css + app.js   (HTML en memoria, CSP) │
└───────────────▲────────────────────────────────────────────┘
                │ puente JS ↔ Python (pywebview js_api)
┌───────────────┴───────────── api.py ───────────────────────┐
│ valida entradas · lanza tareas en hilos · progreso/cancelar │
└──┬──────────┬────────────┬─────────────┬──────────┬─────────┘
catalogo   escaner     limpiador     auditoria  herramientas
   └── seguridad (rutas permitidas/protegidas, enlaces, nube)
   └── registro (JSONL encadenado con SHA-256) · sistema (comandos)
```

- La interfaz **no decide rutas**: envía identificadores del catálogo (`chrome_cache`) y el motor resuelve y valida las rutas.
- Las operaciones largas son **tareas**: la interfaz consulta su progreso y puede cancelarlas.
- El modelo de amenazas completo está en `MODELO_AMENAZAS.md`.

## 3. Implementación: trazabilidad

| Requisito | Módulo / función |
|---|---|
| RS-01, RS-03 | `seguridad.ruta_permitida`, `seguridad.dentro_de`, `seguridad.RUTAS_PROTEGIDAS` |
| RS-02 | `seguridad.es_reparse`, `escaner.recorrer` |
| RS-04 | `seguridad.es_en_nube` |
| RS-05, RS-06 | `limpiador.limpiar_objetivo` (`edad_horas`, `modo="papelera"`) |
| RS-08 | `elevacion.es_admin`, `elevacion.reiniciar_como_admin` |
| RS-09 | `api.Api._objetivos`, `api.Api._unidad`, `api.Api._carpeta` |
| RS-10 | `sistema.ejecutar` |
| RS-11 | `registro.Registro.anotar`, `registro.Registro.verificar` |
| RS-12, RS-13 | `app.html_en_memoria`, `ui/app.js` (función `h`) |

## 4. Verificación
Resultados de la última ejecución en `docs/informes/`:
- `pytest.txt`: pruebas unitarias (guardas de rutas, enlaces, nube, edad, simulación, cadena de hashes, validación de la API).
- `bandit.txt`: análisis estático de seguridad (SAST).
- `pip-audit.txt`: vulnerabilidades conocidas en las dependencias.
- `capturas/`: la interfaz a 1440, 1024, 768 y 390 px, en tema claro y oscuro.

`build_exe.bat` repite pruebas, SAST y auditoría en cada compilación y **se detiene si algo falla**.

## 5. Publicación
- Python 3.12 de 64 bits, dependencias con versión fija.
- El `.exe` se prueba solo (`--autotest`) antes de empaquetarlo.
- Se genera `SHA256SUMS.txt` con el hash del ejecutable y del ZIP.
- GitHub Actions (`ci.yml`) ejecuta pruebas, bandit y pip-audit en Windows en cada *push*. Cuando la versión de `despeja/__init__.py` aún no está publicada, compila el `.exe`, lo prueba, crea la etiqueta `vX.Y.Z` y publica la *release* con el ZIP, los SHA-256 y las notas de `CHANGELOG.md`.

## 6. Mantenimiento
- Las vulnerabilidades se notifican según `SECURITY.md`.
- Versionado semántico; cada versión anota sus cambios en `CHANGELOG.md`.
- Revisión de dependencias en cada versión (pip-audit) y del catálogo cuando cambian las rutas de las aplicaciones.

Autor: Alberto
