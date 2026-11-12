/* Datos de demostración para revisar la interfaz en un navegador (capturas y pruebas visuales).
   NO se incluye en la aplicación: app.py solo inserta iconos.js y app.js. */
(function () {
  const GB = 1024 ** 3, MB = 1024 ** 2;
  const unidades = [
    { letra: "C", raiz: "C:\\", etiqueta: "Windows", fs: "NTFS", tipo: "fija", total: 952 * GB, usado: 901 * GB, libre: 51 * GB, ssd: true, sistema: true },
    { letra: "D", raiz: "D:\\", etiqueta: "Datos", fs: "NTFS", tipo: "fija", total: 1863 * GB, usado: 1210 * GB, libre: 653 * GB, ssd: false, sistema: false },
  ];
  const medidas = {
    temp_usuario: 6.4 * GB, temp_windows: 1.1 * GB, papelera: 3.2 * GB, windows_update: 4.8 * GB, optimizacion_entrega: 1.9 * GB,
    informes_errores: 420 * MB, volcados: 2.3 * GB, volcado_completo: 0, registros_windows: 610 * MB, miniaturas: 380 * MB,
    directx: 1.4 * GB, cache_web_windows: 210 * MB, chrome: 3.9 * GB, edge: 1.6 * GB, brave: 0, opera: 0, firefox: 0,
    teams: 2.1 * GB, discord: 640 * MB, slack: 0, spotify: 5.2 * GB, vscode: 1.2 * GB, steam_web: 890 * MB,
    nvidia_cache: 4.6 * GB, nvidia_instaladores: 2.8 * GB, amd_cache: 0, amd_instaladores: 0, pip: 3.4 * GB, npm: 2.2 * GB,
    yarn_pnpm: 0, nuget: 1.7 * GB, gradle: 0, huggingface: 38 * GB, descargas_antiguas: 14.6 * GB,
  };
  const admin = location.hash.includes("admin");
  let tareas = {}, n = 0;
  function tarea(tipo, resultado, ms) {
    const id = "t" + (++n), inicio = Date.now();
    tareas[id] = { tipo, resultado, ms, inicio };
    return { ok: true, tarea: id };
  }
  const oculto = [
    { id: "hiberfil", nombre: "Hibernación (hiberfil.sys)", bytes: 25.4 * GB, descripcion: "Guarda la memoria al hibernar y para el inicio rápido. Desactivar la hibernación lo elimina.", accion: "hibernacion", icono: "moon", nota: "" },
    { id: "pagefile", nombre: "Archivo de paginación (pagefile.sys)", bytes: 19 * GB, descripcion: "Memoria virtual. Windows lo gestiona; no conviene quitarlo.", accion: null, icono: "memory-stick", nota: "" },
    { id: "swapfile", nombre: "Intercambio de apps (swapfile.sys)", bytes: 256 * MB, descripcion: "Memoria de las apps de la Tienda. Lo gestiona Windows.", accion: null, icono: "memory-stick", nota: "" },
    { id: "papelera", nombre: "Papelera de reciclaje", bytes: 3.2 * GB, descripcion: "214 elementos borrados que siguen ocupando espacio.", accion: "papelera", icono: "trash-2", nota: "" },
    { id: "instantaneas", nombre: "Puntos de restauración", bytes: admin ? 31.5 * GB : null, descripcion: admin ? "Instantáneas de volumen (máximo asignado: 47,6 GB)." : "Para medirlos hace falta ejecutar como administrador.", accion: "proteccion", icono: "history", nota: admin ? "" : "admin" },
    { id: "winsxs", nombre: "Almacén de componentes (WinSxS)", bytes: 11.8 * GB, descripcion: "Componentes de Windows y versiones anteriores de actualizaciones. Parte de su tamaño son archivos compartidos con Windows, así que lo que ocupa de verdad es menos. Se reduce con DISM, nunca a mano.", accion: "dism", icono: "boxes", nota: "parcial" },
    { id: "installer", nombre: "Instaladores de programas (Installer)", bytes: 7.3 * GB, descripcion: "Necesarios para reparar y desinstalar programas. No se deben borrar.", accion: null, icono: "package", nota: "" },
    { id: "windows_old", nombre: "Instalación anterior (Windows.old)", bytes: 22.1 * GB, descripcion: "Copia de la versión anterior de Windows. Se borra desde Configuración ▸ Almacenamiento.", accion: "almacenamiento", icono: "archive", nota: "" },
  ];
  const nombres = ["Grabación OBS 2026-10-03.mkv", "Win11_24H2_Spanish_x64.iso", "gemma3-12b-q4.gguf", "Ubuntu-24.04.vhdx", "Copia iPhone.zip",
    "<img src=x onerror=alert(1)>.mp4", "RTX5080_driver_581.15.exe", "Fotos vacaciones 2025.zip", "backup_sgsi_2026.7z", "clase_unir_tema4.mp4"];
  const grandes = nombres.map((nom, i) => ({ ruta: "C:\\Users\\Alberto\\Downloads\\" + nom, nombre: nom, carpeta: i % 3 ? "C:\\Users\\Alberto\\Downloads" : "C:\\Users\\Alberto\\Videos\\Capturas\\2026\\Octubre",
    bytes: (48 - i * 4.1) * GB, oculto: i === 3, tipo: ["Vídeo", "Instaladores e imágenes de disco", "Modelos de IA", "Máquinas virtuales", "Comprimidos", "Vídeo", "Instaladores e imágenes de disco", "Comprimidos", "Comprimidos", "Vídeo"][i] }));
  const analisis = {
    raiz: "C:\\", segundos: 94.2, archivos: 1284331, visibles: 742 * GB, ocultos: 96 * GB, nube: 214 * GB, no_contabilizado: 63 * GB, usado_unidad: 901 * GB,
    carpetas: [["Users", 512], ["Windows", 38], ["Program Files", 96], ["ProgramData", 21], ["Program Files (x86)", 44], ["Games", 128], ["hiberfil.sys", 25]]
      .map(([n, g]) => ({ nombre: n, ruta: "C:\\" + n, bytes: g * GB })).sort((a, b) => b.bytes - a.bytes),
    tipos: [["Vídeo", 214], ["Programas y bibliotecas", 141], ["Modelos de IA", 96], ["Otros", 88], ["Máquinas virtuales", 64], ["Instaladores e imágenes de disco", 52], ["Imágenes", 41], ["Bases de datos y cachés", 38], ["Comprimidos", 33], ["Documentos", 12]]
      .map(([t, g]) => ({ tipo: t, bytes: g * GB })),
    grandes, sin_permiso: 37, carpetas_sin_permiso: [], enlaces: 112, cancelado: false,
  };
  const registro = { integridad: { ok: true, entradas: 6 }, carpeta: "C:\\Users\\Alberto\\AppData\\Local\\Despeja", entradas: [
    { fecha: "2026-11-12T01:12:00+01:00", accion: "limpieza", usuario: "alberto", admin: true, bytes: 41.3 * GB, archivos: 182340, hash: "9f2c1ab07e5d44c1a0" },
    { fecha: "2026-11-12T01:10:00+01:00", accion: "simulacion", usuario: "alberto", admin: true, bytes: 41.9 * GB, archivos: 184002, hash: "51be09c2d7a3e8f114" },
    { fecha: "2026-11-12T01:05:00+01:00", accion: "auditoria_oculto", usuario: "alberto", admin: true, unidad: "C", bytes: 121 * GB, hash: "c03d8e1f22b7a90e5b" },
    { fecha: "2026-11-12T00:58:00+01:00", accion: "analisis", usuario: "alberto", admin: false, raiz: "C:\\", bytes: 838 * GB, archivos: 1284331, hash: "7aa41f0be2c9d0136d" },
    { fecha: "2026-11-11T22:40:00+01:00", accion: "papelera_archivos", usuario: "alberto", admin: false, bytes: 52 * GB, archivos: 2, hash: "e81f5d4c0a9b7e3d21" },
    { fecha: "2026-11-11T22:31:00+01:00", accion: "herramienta", usuario: "alberto", admin: true, hash: "3c7b9e2f1d0a8c4e65" },
  ] };
  const api = {
    info: async () => ({ nombre: "Despeja", version: "1.0.0", admin, equipo: "PC-ALBERTO", windows: true, datos: registro.carpeta }),
    unidades: async () => unidades,
    catalogo: async () => window.__catalogo,
    medir: async () => {
      const r = {};
      for (const e of window.__catalogo.elementos) r[e.id] = { rutas: (medidas[e.id] || e.id === "papelera" || e.id === "volcado_completo") ? 1 : 0, bytes: medidas[e.id] || 0, archivos: Math.round((medidas[e.id] || 0) / 180000), bloqueado: e.admin && !admin,
        abiertos: e.id === "chrome" ? ["chrome.exe"] : [], avisos: [] };
      return tarea("medir", r, 1200);
    },
    limpiar: async (ids, simular) => {
      const el = {};
      let b = 0, a = 0;
      for (const id of ids) { const x = medidas[id] || 0; el[id] = { bytes: x * 0.96, archivos: Math.round(x / 190000), en_uso: id === "chrome" ? 41 : 0, errores: 0, avisos: [] }; b += x * 0.96; a += el[id].archivos; }
      return tarea("limpiar", { simulado: simular, bytes: b, archivos: a, elementos: el, lista: "x.csv", cancelado: false }, 1500);
    },
    oculto: async () => tarea("oculto", { letra: "C", elementos: oculto }, 1000),
    analizar: async () => tarea("analizar", analisis, 1500),
    elegir_carpeta: async () => null,
    a_papelera: async rutas => ({ ok: true, bytes: 40 * GB, enviados: rutas, fallos: [] }),
    abrir_ubicacion: async () => true, herramienta: async (id) => tarea("herramienta", { codigo: 0 }, 2000),
    abrir_config: async () => true, cancelar: async () => true, registro: async () => registro, exportar: async () => "x",
    abrir_datos: async () => true, reiniciar_admin: async () => false,
    tarea: async id => {
      const t = tareas[id];
      const p = Math.min(1, (Date.now() - t.inicio) / t.ms);
      if (p < 1) return { id, tipo: t.tipo, estado: "corriendo", progreso: t.tipo === "analizar" ? null : p, mensaje: { analizar: "C:\\Users\\Alberto\\AppData\\Local\\Packages", herramienta: "Analizar el almacén de componentes", oculto: "Puntos de restauración" }[t.tipo] || "Google Chrome",
        lineas: t.tipo === "herramienta" ? ["Deployment Image Servicing and Management tool", "[==========                 18.4%                ]"] : [],
        resultado: t.tipo === "analizar" ? { parcial: true, archivos: Math.round(p * 1284331), bytes: p * 838 * GB } : null };
      return { id, tipo: t.tipo, estado: "hecha", progreso: 1, mensaje: "", lineas: [], resultado: t.resultado };
    },
  };
  window.pywebview = { api };
})();
