# Despeja: modelo de amenazas (STRIDE)

**Alcance**: aplicación de escritorio local para Windows 10/11 que lee el sistema de archivos y borra contenido de una lista cerrada de carpetas. Puede ejecutarse como usuario normal o, a petición, como administrador.

**Activos**: los datos del usuario (lo más valioso; un borrado erróneo es irreversible), la integridad del sistema operativo, la integridad del registro de auditoría y la confidencialidad de las rutas y nombres de archivo.

**Límites de confianza**:
1. Interfaz (JavaScript en WebView2) → motor (Python). Toda entrada se trata como no confiable.
2. Sistema de archivos → motor. Nombres, enlaces y atributos pueden ser hostiles (otro programa o malware puede crear uniones o nombres con HTML).
3. Motor → comandos del sistema (cipher, DISM, powercfg, PowerShell).

| # | STRIDE | Amenaza | Mitigación | Riesgo residual |
|---|---|---|---|---|
| T1 | Tampering | Una **unión o enlace simbólico** dentro de una caché apunta a `C:\Users\…\Documents` y la limpieza borra los documentos. | No se sigue ningún punto de reanálisis (`FILE_ATTRIBUTE_REPARSE_POINT`); cada ruta se comprueba con `dentro_de(raíz)`; la raíz se rechaza si algún tramo es un enlace. Probado en `test_seguridad.py`. | Bajo |
| T2 | Tampering | Un error de catálogo o una variable de entorno manipulada (`TEMP=C:\`) dirige el borrado a una ruta crítica. | Lista de **rutas protegidas** y prohibición de raíces de unidad o poco profundas; la raíz debe estar bajo una base permitida (perfil, AppData, Temp, subcarpetas concretas de Windows/ProgramData). | Bajo |
| T3 | Elevation | La interfaz (o un script inyectado en ella) pide borrar una ruta arbitraria. | La API **no acepta rutas para borrar**, solo identificadores del catálogo. La única ruta aceptada es para *enviar a la papelera* archivos del último análisis, y debe estar en ese análisis y fuera de las rutas protegidas. | Bajo |
| T4 | Spoofing / XSS | Un archivo con nombre `<img onerror=…>` ejecuta código en la interfaz al listarse. | Todo se inserta con `textContent`; CSP `default-src 'none'` sin orígenes remotos. | Muy bajo |
| T5 | Info. disclosure | La interfaz o la app envían rutas y nombres a Internet. | Sin red: el HTML se carga en memoria, sin servidor local ni recursos remotos; la CSP bloquea `connect-src`. Sin telemetría. | Muy bajo |
| T6 | Tampering | Alguien edita el registro para ocultar un borrado. | Cadena de hashes SHA-256 (cada entrada incluye el hash de la anterior) con verificación en la app. *Detecta* la manipulación; no la impide (un administrador local puede reescribir todo el archivo). | Medio, aceptado |
| T7 | Elevation | Inyección de comandos al ejecutar cipher, DISM, powercfg o PowerShell. | Ruta absoluta a `%SystemRoot%\System32`, argumentos en lista, `shell=False`, letra de unidad validada con `^[A-Z]$` y textos de PowerShell fijos, sin interpolar datos. | Muy bajo |
| T8 | Elevation | Secuestro de DLL o ejecutable si se llama a `cmd`/`powershell` por nombre desde una carpeta controlada. | Siempre ruta absoluta; PyInstaller sin carpeta de trabajo en el PATH de búsqueda. | Bajo |
| T9 | DoS | Borrar temporales o cachés en uso rompe programas abiertos. | Temporales con más de 24 h; los archivos bloqueados se saltan; aviso si el navegador está abierto. | Bajo |
| T10 | Tampering | Borrar marcadores de OneDrive elimina los archivos también de la nube. | Los archivos con atributos `RECALL_ON_DATA_ACCESS`, `RECALL_ON_OPEN` u `OFFLINE` nunca se borran ni se abren; OneDrive está en las rutas protegidas. | Muy bajo |
| T11 | Repudiation | No poder demostrar qué se borró y quién lo hizo. | Cada operación anota fecha, usuario, equipo, si se ejecutaba como administrador, elementos, bytes y número de archivos, y guarda la lista detallada en CSV. | Bajo |
| T12 | DoS | El borrado seguro del espacio libre llena el disco o desgasta un SSD. | `cipher /w` (nativo, libera el espacio al acabar), se puede cancelar, y aviso específico en SSD (TRIM ya lo resuelve y escribir de más lo desgasta). | Bajo |
| T13 | Supply chain | Una dependencia comprometida o vulnerable. | Solo 2 dependencias de ejecución (pywebview, send2trash), con versión fija; pip-audit en cada compilación; hash del ejecutable publicado. | Bajo |

## Decisiones de seguridad explícitas
- **Windows.old y los puntos de restauración no se borran desde la app**: solo se miden y se abre la herramienta oficial de Windows (Configuración ▸ Almacenamiento y Protección del sistema), que gestiona permisos y dependencias correctamente.
- **`%SystemRoot%\Installer` y `WinSxS` nunca se borran a mano**: hacerlo rompe la desinstalación y las actualizaciones. Para WinSxS se usa DISM.
- **Prefetch no se limpia**: no libera casi nada y ralentiza el arranque.
- **Cachés de modelos de IA (Ollama, Hugging Face) no se borran por defecto**: pesan mucho, pero volver a descargarlos cuesta horas.
