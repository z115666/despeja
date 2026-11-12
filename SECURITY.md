# Security policy / Política de seguridad

[English](#english) · [Español](#español)

---

## English

### Supported versions
| Version | Supported |
|---|---|
| 1.0.x | Yes |

### Reporting a vulnerability
Please do not open a public issue. Use **Security ▸ Report a vulnerability** (GitHub private advisory) in this repository and include:
- Despeja and Windows versions;
- steps to reproduce and the impact (for example, deletion outside the allowed folders);
- a minimal proof of concept, if possible.

First response within 7 days. Fixes are released as a patch version, with their SHA-256 and a note in `CHANGELOG.md`.

### Scope of particular interest
- Any way for the cleanup to delete outside the catalogue paths (links, junctions, environment variables, race conditions).
- Code execution from the interface (XSS) or through file names.
- Tampering with the audit log without `verificar()` detecting it.

### Verifying a download
```
certutil -hashfile Despeja-Windows.zip SHA256
```
The result must match `SHA256SUMS.txt` in the release.

---

## Español

### Versiones con soporte
| Versión | Soporte |
|---|---|
| 1.0.x | Sí |

### Notificar una vulnerabilidad
No abras una incidencia pública. Usa **Security ▸ Report a vulnerability** (aviso privado de GitHub) en este repositorio e incluye:
- versión de Despeja y de Windows;
- pasos para reproducirla y el impacto (por ejemplo, borrado fuera de las carpetas permitidas);
- si es posible, una prueba de concepto mínima.

Respuesta inicial en un máximo de 7 días. Las correcciones se publican como versión de parche, con su SHA-256 y una nota en `CHANGELOG.md`.

### Alcance especialmente relevante
- Cualquier forma de que la limpieza borre fuera de las rutas del catálogo (enlaces, uniones, variables de entorno, condiciones de carrera).
- Ejecución de código desde la interfaz (XSS) o a través de nombres de archivo.
- Manipulación del registro de auditoría sin que `verificar()` lo detecte.

### Verificar una descarga
```
certutil -hashfile Despeja-Windows.zip SHA256
```
El resultado debe coincidir con `SHA256SUMS.txt` de la publicación.
