/* Despeja: lógica de la interfaz.
   Seguridad (RS-13): nunca se usa innerHTML con datos; todo se crea con h() y textContent. */
"use strict";

// ------------------------------------------------------------------ utilidades
function h(tag, attrs, ...hijos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style") for (const [p, val] of Object.entries(v)) el.style.setProperty(p, val);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const hijo of hijos.flat()) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    el.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return el;
}

const SVG = "http://www.w3.org/2000/svg";
function icono(nombre, clase) {
  const s = document.createElementNS(SVG, "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("class", "icono" + (clase ? " " + clase : ""));
  s.setAttribute("aria-hidden", "true");
  // Los iconos son contenido estático del propio programa (iconos.js), no datos del usuario
  const plantilla = document.createElementNS(SVG, "g");
  plantilla.innerHTML = ICONOS[nombre] || ICONOS["hard-drive"];
  while (plantilla.firstChild) s.append(plantilla.firstChild);
  return s;
}

const num = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1, minimumFractionDigits: 0 });
const entero = new Intl.NumberFormat("es-ES");
function tam(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let n = Number(bytes), i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i === 0 ? entero.format(n) : num.format(n >= 100 ? Math.round(n) : n)) + " " + u[i];
}
function fecha(iso) {
  try { return new Date(iso).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" }); }
  catch { return iso || ""; }
}
function plural(n, uno, varios) { return `${entero.format(n)} ${n === 1 ? uno : varios}`; }

function aviso(texto, tipo) {
  const t = h("div", { class: "toast" }, icono(tipo === "error" ? "triangle-alert" : "circle-check"), texto);
  document.getElementById("avisos").append(t);
  setTimeout(() => t.remove(), 4500);
}

// ------------------------------------------------------------------ puente con Python
function api(metodo, ...args) {
  return window.pywebview.api[metodo](...args);
}
async function seguir(id, alActualizar) {
  for (;;) {
    const t = await api("tarea", id);
    if (alActualizar) alActualizar(t);
    if (t.estado !== "corriendo") return t;
    await new Promise(r => setTimeout(r, 350));
  }
}
async function lanzar(metodo, args, alActualizar) {
  let r;
  try { r = await api(metodo, ...args); }
  catch (e) { aviso(String(e.message || e), "error"); return null; }
  if (!r.ok) { aviso(r.error || "No se pudo iniciar", "error"); return null; }
  estado.tareas[metodo] = r.tarea;
  const t = await seguir(r.tarea, alActualizar);
  delete estado.tareas[metodo];
  if (t.estado === "error") aviso(t.error || "La tarea ha fallado", "error");
  return t;
}

// ------------------------------------------------------------------ estado
const estado = {
  vista: "resumen", info: {}, unidades: [], catalogo: null, medidas: null, seleccion: new Set(),
  oculto: {}, unidadOculto: null, analisis: null, destinoAnalisis: null, marcados: new Set(),
  tareas: {}, progresoMedir: null, progresoLimpiar: null, resultadoLimpieza: null, progresoAnalisis: null,
  herramienta: null, letraBorrado: null, animado: false,
};

const VISTAS = [
  { id: "resumen", nombre: "Resumen", icono: "layout-dashboard",
    sub: "Cómo está repartido cada disco y cuánto puedes recuperar." },
  { id: "limpieza", nombre: "Limpieza", icono: "brush",
    sub: "Elige qué limpiar. Prueba antes con «Simular»: no borra nada." },
  { id: "oculto", nombre: "Espacio oculto", icono: "eye-off",
    sub: "Lo que ocupa sitio sin verse en el Explorador, y qué se puede hacer con ello." },
  { id: "analisis", nombre: "Análisis", icono: "scan-search",
    sub: "Qué carpetas, archivos y tipos ocupan más en una unidad o carpeta." },
  { id: "herramientas", nombre: "Herramientas", icono: "wrench",
    sub: "Mantenimiento de Windows y borrado seguro del espacio libre." },
  { id: "registro", nombre: "Registro", icono: "list-checks",
    sub: "Todo lo que ha hecho Despeja, con verificación de integridad." },
];

function ir(vista) {
  estado.vista = vista;
  for (const b of document.querySelectorAll(".nav-boton"))
    b.setAttribute("aria-current", b.dataset.vista === vista ? "page" : "false");
  const v = VISTAS.find(x => x.id === vista);
  document.getElementById("titulo").textContent = v.nombre;
  document.getElementById("subtitulo").textContent = v.sub;
  pintar();
  document.getElementById("vista").focus({ preventScroll: true });
  window.scrollTo(0, 0);
}

function pintar() {
  const cont = document.getElementById("vista");
  const nuevo = ({ resumen: vResumen, limpieza: vLimpieza, oculto: vOculto, analisis: vAnalisis,
                   herramientas: vHerramientas, registro: vRegistro })[estado.vista]();
  cont.replaceChildren(...[].concat(nuevo));
}

// ------------------------------------------------------------------ comunes
function bloqueProgreso(p, texto) {
  const pct = p && typeof p.progreso === "number" ? Math.round(p.progreso * 100) : null;
  return h("div", { class: "progreso", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100,
                    "aria-valuenow": pct === null ? null : pct },
    h("div", { class: "barra" + (pct === null ? " indeterminada" : "") }, h("span", { style: { width: (pct || 0) + "%" } })),
    h("div", { class: "progreso-texto" }, h("span", {}, (p && p.mensaje) || texto || "Trabajando…"),
      h("span", {}, pct === null ? "" : pct + " %")));
}
function boton(texto, nombreIcono, onclick, clase, extra) {
  return h("button", { class: "boton " + (clase || ""), type: "button", onclick, ...(extra || {}) },
    nombreIcono ? icono(nombreIcono) : null, texto);
}
function nota(texto, tipo, nombreIcono) {
  return h("div", { class: "nota " + (tipo || "") }, icono(nombreIcono || (tipo === "aviso" ? "triangle-alert" : "info")), h("div", {}, texto));
}
function totalRecuperable() {
  if (!estado.medidas) return null;
  // Solo lo seguro (marcado por defecto): sin descargas, modelos de IA ni papelera
  return estado.catalogo.elementos.reduce((s, e) => {
    const m = estado.medidas[e.id] || {};
    return s + (e.por_defecto && !m.bloqueado ? (m.bytes || 0) : 0);
  }, 0);
}

// ------------------------------------------------------------------ Resumen
function mapaSectores(u, celdas) {
  const total = u.total || 1;
  const rec = u.sistema ? (totalRecuperable() || 0) : 0;
  const ocu = estado.oculto[u.letra] ? estado.oculto[u.letra].reduce((s, i) => s + (i.bytes || 0), 0) : 0;
  const n = { r: Math.round(rec / total * celdas), o: Math.round(ocu / total * celdas), l: Math.round(u.libre / total * celdas) };
  if (rec > 0 && n.r === 0) n.r = 1;
  if (ocu > 0 && n.o === 0) n.o = 1;
  n.v = Math.max(0, celdas - n.r - n.o - n.l);
  const clases = [].concat(Array(n.v).fill("v"), Array(n.o).fill("o"), Array(n.r).fill("r"));
  const grid = h("div", { class: "sectores" + (estado.animado ? "" : " animar"), role: "img", style: { "--cols": celdas === 240 ? 24 : 60 },
    "aria-label": `${u.letra}: ${tam(u.usado)} usados de ${tam(u.total)}; ${tam(u.libre)} libres` });
  for (let i = 0; i < celdas; i++) {
    grid.append(h("span", { class: "sector " + (clases[i] || ""), style: { "--i": i } }));
  }
  return { grid, rec, ocu };
}

function vResumen() {
  const partes = [];
  const rec = totalRecuperable();
  const midiendo = !!estado.tareas.medir;
  partes.push(h("div", { class: "panel recuperar" },
    midiendo || rec === null
      ? h("div", { style: { flex: "1" } }, bloqueProgreso(estado.progresoMedir, "Calculando lo que se puede limpiar…"))
      : h("p", { class: "recuperar-texto" }, "Puedes recuperar ", h("span", { class: "cifra" }, tam(rec)),
          " limpiando temporales y cachés, sin tocar tus documentos."),
    h("div", { class: "cabecera-acciones" },
      boton("Volver a calcular", "refresh-cw", () => medir(), "discreto", { disabled: midiendo }),
      boton("Revisar limpieza", "brush", () => ir("limpieza"), "primario", { disabled: midiendo }))));

  const discos = h("div", { class: "discos" });
  for (const u of estado.unidades) {
    const movil = window.matchMedia("(max-width: 640px)").matches;
    const celdas = movil ? 240 : 600;
    const { grid, rec: r, ocu } = mapaSectores(u, celdas);
    const fila = (cls, nombre, valor) => h("div", { class: "leyenda-fila" }, h("span", { class: "punto " + cls }), h("span", {}, nombre),
      h("span", { class: "cifra" }, valor));
    const tipo = [u.ssd === true ? "SSD" : u.ssd === false ? "Disco duro" : null, u.fs, u.tipo === "extraible" ? "Extraíble" : null]
      .filter(Boolean).join(", ");
    discos.append(h("article", { class: "panel" },
      h("div", { class: "disco" },
        h("div", {},
          h("div", { class: "disco-cab" }, h("span", { class: "disco-nombre" }, `${u.letra}: ${u.etiqueta || (u.sistema ? "Windows" : "Disco local")}`),
            h("span", { class: "tenue" }, tipo), u.sistema ? h("span", { class: "pastilla" }, icono("monitor"), "Sistema") : null),
          grid),
        h("div", { class: "leyenda" },
          fila("v", "Ocupado visible", tam(Math.max(0, u.usado - r - ocu))),
          fila("o", "Oculto", estado.oculto[u.letra] ? tam(ocu) : h("button", { class: "boton discreto", type: "button",
            style: { "min-height": "24px", padding: "0 6px" }, onclick: () => { estado.unidadOculto = u.letra; ir("oculto"); auditarOculto(u.letra); } }, "Medir")),
          u.sistema ? fila("r", "Recuperable", rec === null ? "…" : tam(r)) : null,
          fila("", "Libre", tam(u.libre)),
          h("div", { class: "leyenda-total" }, h("span", {}, "Total"), h("span", { class: "cifra" }, tam(u.total)))))));
  }
  if (!estado.unidades.length) discos.append(h("div", { class: "panel vacio" }, "No se encuentran unidades."));
  partes.push(discos);
  estado.animado = true;
  return partes;
}

// ------------------------------------------------------------------ Limpieza
async function medir() {
  estado.progresoMedir = { progreso: 0 };
  pintar();
  const t = await lanzar("medir", [], p => { estado.progresoMedir = p; if (["resumen", "limpieza"].includes(estado.vista)) actualizarProgreso(); });
  if (t && t.estado === "hecha") {
    estado.medidas = t.resultado;
    if (!estado.seleccion.size) {
      for (const e of estado.catalogo.elementos) {
        const m = estado.medidas[e.id];
        if (e.por_defecto && m && !m.bloqueado && m.bytes > 0) estado.seleccion.add(e.id);
      }
    }
  }
  estado.progresoMedir = null;
  pintar();
}
let ultimoPintado = 0;
function actualizarProgreso() {
  const ahora = Date.now();
  if (ahora - ultimoPintado < 300) return;
  ultimoPintado = ahora;
  const foco = document.activeElement && document.activeElement.id;
  pintar();
  if (foco) { const el = document.getElementById(foco); if (el) el.focus(); }
}

function vLimpieza() {
  const partes = [];
  if (!estado.catalogo) return h("div", { class: "panel" }, bloqueProgreso(null, "Cargando…"));
  if (estado.progresoLimpiar) {
    partes.push(h("div", { class: "panel" }, h("div", { class: "panel-cab" }, h("h2", {}, estado.progresoLimpiar.simular ? "Simulando…" : "Limpiando…"),
      boton("Cancelar", "square", () => api("cancelar", estado.tareas.limpiar), "discreto")), bloqueProgreso(estado.progresoLimpiar)));
  } else if (estado.resultadoLimpieza) {
    partes.push(panelResultado(estado.resultadoLimpieza));
  }
  if (!estado.info.admin && estado.medidas && estado.catalogo.elementos.some(e => e.admin && (estado.medidas[e.id] || {}).bytes > 0)) {
    partes.push(nota(h("span", {}, "Algunos elementos de sistema necesitan permisos de administrador. ",
      h("button", { class: "boton discreto", type: "button", style: { "min-height": "24px", padding: "0 6px" }, onclick: reiniciarAdmin },
        "Reiniciar como administrador")), "aviso", "lock"));
  }
  // Lo que no existe en este equipo (programas no instalados) no se muestra
  const presente = e => !estado.medidas || !estado.medidas[e.id] || estado.medidas[e.id].rutas > 0 || estado.medidas[e.id].bytes > 0;
  const ausentes = estado.catalogo.elementos.filter(e => !presente(e)).length;
  for (const cat of estado.catalogo.categorias) {
    const elementos = estado.catalogo.elementos.filter(e => e.categoria === cat.id && presente(e));
    if (!elementos.length) continue;
    const totalCat = elementos.reduce((s, e) => s + ((estado.medidas || {})[e.id] || {}).bytes || 0, 0);
    const lista = h("ul", { class: "lista" });
    for (const e of elementos) lista.append(filaElemento(e));
    partes.push(h("section", { class: "grupo", "aria-labelledby": "g-" + cat.id },
      h("div", { class: "grupo-cab" }, icono(cat.icono), h("h2", { id: "g-" + cat.id }, cat.nombre),
        h("span", { class: "tenue" }, estado.medidas ? tam(totalCat) : "")),
      lista));
  }
  if (ausentes) partes.push(h("p", { class: "tenue", style: { "font-size": "13px" } },
    `${plural(ausentes, "elemento no aparece porque ese programa no está", "elementos no aparecen porque esos programas no están")} en este equipo.`));
  // barra de acción fija
  const sel = [...estado.seleccion];
  const bytes = sel.reduce((s, id) => s + ((estado.medidas || {})[id] || {}).bytes || 0, 0);
  const ocupado = !!estado.tareas.limpiar || !!estado.tareas.medir;
  partes.push(h("div", { class: "pie-accion" },
    h("span", {}, sel.length ? h("span", {}, h("span", { class: "cifra" }, tam(bytes)), ` en ${plural(sel.length, "elemento", "elementos")}`) : "Elige qué limpiar"),
    h("div", { class: "cabecera-acciones" },
      boton("Simular", "play", () => limpiar(true), "", { disabled: !sel.length || ocupado }),
      boton("Limpiar", "brush", () => confirmarLimpieza(), "primario", { disabled: !sel.length || ocupado }))));
  return partes;
}

function filaElemento(e) {
  const m = (estado.medidas || {})[e.id];
  const bloqueado = m && m.bloqueado;
  const id = "c-" + e.id;
  const marcada = estado.seleccion.has(e.id);
  const casilla = h("input", { type: "checkbox", class: "casilla", id, checked: marcada && !bloqueado, disabled: bloqueado,
    onchange: ev => { ev.target.checked ? estado.seleccion.add(e.id) : estado.seleccion.delete(e.id); pintar(); document.getElementById(id).focus(); } });
  const etiquetas = [];
  if (e.admin) etiquetas.push(h("span", { class: "pastilla" + (bloqueado ? " aviso" : "") }, icono("lock"), "Administrador"));
  if (e.riesgo === "medio") etiquetas.push(h("span", { class: "pastilla aviso" }, icono("triangle-alert"), "Revisar"));
  if (e.modo === "papelera") etiquetas.push(h("span", { class: "pastilla" }, icono("trash-2"), "A la papelera"));
  if (m && m.abiertos && m.abiertos.length) etiquetas.push(h("span", { class: "pastilla aviso" }, icono("info"), "Abierto: se saltará lo que esté en uso"));
  return h("li", { class: "fila" + (bloqueado ? " desactivada" : "") },
    casilla,
    h("span", { class: "fila-icono" }, icono(e.icono)),
    h("label", { class: "fila-cuerpo", for: id },
      h("span", { class: "fila-titulo" }, e.nombre, ...etiquetas),
      h("span", { class: "fila-desc" }, e.descripcion + (e.nota ? " " + e.nota : ""))),
    h("div", { class: "fila-dcha" },
      h("span", { class: "cifra" }, m ? tam(m.bytes) : "…"),
      m && m.archivos ? h("span", { class: "tenue", style: { "font-size": "12px" } }, plural(m.archivos, "archivo", "archivos")) : null));
}

function confirmarLimpieza() {
  const sel = [...estado.seleccion];
  const lista = h("ul", { class: "dialogo-lista" });
  let total = 0;
  for (const id of sel) {
    const e = estado.catalogo.elementos.find(x => x.id === id);
    const b = ((estado.medidas || {})[id] || {}).bytes || 0;
    total += b;
    lista.append(h("li", {}, h("span", {}, e.nombre), h("span", { class: "cifra" }, tam(b))));
  }
  const dlg = document.getElementById("dialogo");
  const papelera = sel.includes("papelera");
  dlg.replaceChildren(h("div", { class: "dialogo-cuerpo" },
    h("h2", {}, `¿Limpiar ${tam(total)}?`),
    h("p", { class: "tenue" }, "Se borrarán los archivos de estos elementos. Los que estén en uso se saltan y lo que vaya a la papelera se puede recuperar."),
    lista,
    papelera ? nota("Vaciar la papelera no tiene vuelta atrás.", "aviso") : null,
    h("div", { class: "dialogo-botones" },
      boton("Cancelar", null, () => dlg.close(), "discreto"),
      boton("Limpiar", "brush", () => { dlg.close(); limpiar(false); }, "primario", { autofocus: true }))));
  dlg.showModal();
}

async function limpiar(simular) {
  const ids = [...estado.seleccion];
  estado.resultadoLimpieza = null;
  estado.progresoLimpiar = { progreso: 0, simular };
  pintar();
  const t = await lanzar("limpiar", [ids, simular], p => { estado.progresoLimpiar = { ...p, simular }; actualizarProgreso(); });
  estado.progresoLimpiar = null;
  if (t && (t.estado === "hecha" || t.estado === "cancelada")) {
    estado.resultadoLimpieza = t.resultado;
    if (!simular) {
      aviso(`Limpieza terminada: ${tam(t.resultado.bytes)} recuperados`);
      estado.unidades = await api("unidades");
      medir();
      return;
    }
  }
  pintar();
}

function panelResultado(r) {
  const filas = [];
  let enUso = 0, avisos = [];
  for (const [id, x] of Object.entries(r.elementos)) {
    const e = estado.catalogo.elementos.find(c => c.id === id);
    enUso += x.en_uso || 0;
    avisos = avisos.concat(x.avisos || []);
    filas.push(h("tr", {}, h("td", {}, e ? e.nombre : id),
      h("td", { class: "num" }, x.saltado ? x.saltado : tam(x.bytes)),
      h("td", { class: "num" }, x.saltado ? "" : entero.format(x.archivos || 0)),
      h("td", { class: "num ocultar-movil" }, x.en_uso ? entero.format(x.en_uso) : "")));
  }
  return h("div", { class: "panel" },
    h("div", { class: "panel-cab" },
      h("h2", {}, r.simulado ? `La simulación liberaría ${tam(r.bytes)}` : `Recuperados ${tam(r.bytes)}`),
      h("div", { class: "cabecera-acciones" },
        r.simulado ? h("span", { class: "pastilla" }, icono("info"), "No se ha borrado nada") : h("span", { class: "pastilla ok" }, icono("circle-check"), "Hecho"),
        boton("Cerrar", "x", () => { estado.resultadoLimpieza = null; pintar(); }, "discreto"))),
    h("div", { class: "tabla-envoltura" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Elemento"), h("th", { class: "num" }, "Espacio"), h("th", { class: "num" }, "Archivos"),
        h("th", { class: "num ocultar-movil" }, "En uso"))),
      h("tbody", {}, filas))),
    h("p", { class: "tenue", style: { "margin-top": "12px", "font-size": "13px" } },
      `${plural(r.archivos, "archivo", "archivos")}${enUso ? `, ${plural(enUso, "en uso saltado", "en uso saltados")}` : ""}. La lista completa queda en el registro.`),
    avisos.length ? nota(`${plural(avisos.length, "ruta rechazada", "rutas rechazadas")} por seguridad: ${avisos.slice(0, 3).join("; ")}`, "aviso") : null);
}

// ------------------------------------------------------------------ Espacio oculto
async function auditarOculto(letra) {
  estado.unidadOculto = letra;
  estado.progresoOculto = { mensaje: "Midiendo…" };
  pintar();
  const t = await lanzar("oculto", [letra], p => { estado.progresoOculto = p; if (estado.vista === "oculto") actualizarProgreso(); });
  estado.progresoOculto = null;
  if (t && t.estado === "hecha") estado.oculto[letra] = t.resultado.elementos;
  pintar();
}

const ACCIONES_OCULTO = {
  hibernacion: { texto: "Ver opciones", icono: "moon", hacer: () => ir("herramientas") },
  papelera: { texto: "Vaciar", icono: "trash-2", hacer: () => { estado.seleccion = new Set(["papelera"]); ir("limpieza"); confirmarLimpieza(); } },
  proteccion: { texto: "Abrir Protección del sistema", icono: "external-link", hacer: () => api("abrir_config", "proteccion") },
  dism: { texto: "Reducir con DISM", icono: "wrench", hacer: () => ir("herramientas") },
  almacenamiento: { texto: "Abrir Almacenamiento", icono: "external-link", hacer: () => api("abrir_config", "almacenamiento") },
};

function vOculto() {
  const partes = [];
  const sel = estado.unidadOculto || (estado.unidades.find(u => u.sistema) || estado.unidades[0] || {}).letra;
  estado.unidadOculto = sel;
  partes.push(h("div", { class: "panel-cab" },
    h("div", { class: "chips", role: "group", "aria-label": "Unidad" },
      estado.unidades.map(u => h("button", { class: "chip", type: "button", "aria-pressed": String(u.letra === sel),
        onclick: () => { estado.unidadOculto = u.letra; pintar(); } }, icono("hard-drive"), `${u.letra}:`))),
    boton(estado.oculto[sel] ? "Volver a medir" : "Medir espacio oculto", "scan-search", () => auditarOculto(sel), "primario",
      { disabled: !!estado.tareas.oculto || !sel })));
  if (estado.progresoOculto) partes.push(h("div", { class: "panel" }, bloqueProgreso(estado.progresoOculto, "Midiendo…")));
  const items = estado.oculto[sel];
  if (!items) {
    if (!estado.progresoOculto) partes.push(h("div", { class: "panel vacio" }, icono("eye-off"),
      h("p", {}, "Mide la hibernación, la memoria virtual, los puntos de restauración, WinSxS, Windows.old y la papelera de esta unidad.")));
    return partes;
  }
  const max = Math.max(1, ...items.map(i => i.bytes || 0));
  const total = items.reduce((s, i) => s + (i.bytes || 0), 0);
  const lista = h("ul", { class: "lista" });
  for (const i of items) {
    const acc = ACCIONES_OCULTO[i.accion];
    lista.append(h("li", { class: "fila sin-check" },
      h("span", { class: "fila-icono" }, icono(i.icono)),
      h("div", { class: "fila-cuerpo" },
        h("span", { class: "fila-titulo" }, i.nombre,
          i.nota === "admin" ? h("span", { class: "pastilla aviso" }, icono("lock"), "Administrador") : null,
          i.nota === "parcial" ? h("span", { class: "pastilla" }, icono("info"), "Medida parcial") : null),
        h("span", { class: "fila-desc" }, i.descripcion),
        i.bytes ? h("div", { class: "barra", style: { "max-width": "420px", "margin-top": "6px" } },
          h("span", { style: { width: Math.max(1, i.bytes / max * 100) + "%", background: "var(--oculto)" } })) : null),
      h("div", { class: "fila-dcha" }, h("span", { class: "cifra" }, i.bytes === null ? "—" : tam(i.bytes)),
        acc ? boton(acc.texto, acc.icono, acc.hacer, "discreto") : null)));
  }
  partes.push(h("p", { class: "tenue" }, `Total oculto en ${sel}: `, h("span", { class: "cifra", style: { color: "var(--tinta)" } }, tam(total))));
  partes.push(lista);
  partes.push(nota("WinSxS, Installer y los archivos de sistema no se borran a mano: romperían actualizaciones y desinstalaciones. Despeja te lleva a la herramienta oficial de Windows en cada caso."));
  return partes;
}

// ------------------------------------------------------------------ Análisis
async function analizar(destino) {
  estado.destinoAnalisis = destino;
  estado.analisis = null;
  estado.marcados.clear();
  estado.progresoAnalisis = { mensaje: "Empezando…" };
  pintar();
  const t = await lanzar("analizar", [destino], p => { estado.progresoAnalisis = p; if (estado.vista === "analisis") actualizarProgreso(); });
  estado.progresoAnalisis = null;
  if (t && (t.estado === "hecha" || t.estado === "cancelada")) estado.analisis = t.resultado;
  pintar();
}
async function elegirCarpeta() {
  const r = await api("elegir_carpeta");
  if (r) analizar(r);
}

function vAnalisis() {
  const partes = [];
  const ocupado = !!estado.tareas.analizar;
  partes.push(h("div", { class: "panel-cab" },
    h("div", { class: "chips", role: "group", "aria-label": "Qué analizar" },
      estado.unidades.map(u => h("button", { class: "chip", type: "button", disabled: ocupado,
        "aria-pressed": String(estado.destinoAnalisis === u.letra), onclick: () => analizar(u.letra) }, icono("hard-drive"), `Unidad ${u.letra}:`)),
      h("button", { class: "chip", type: "button", disabled: ocupado, onclick: elegirCarpeta }, icono("folder-open"), "Elegir carpeta…"))));

  if (estado.progresoAnalisis) {
    const p = estado.progresoAnalisis, r = p.resultado || {};
    partes.push(h("div", { class: "panel" }, h("div", { class: "panel-cab" },
      h("h2", {}, r.archivos ? `${entero.format(r.archivos)} archivos, ${tam(r.bytes)}` : "Analizando…"),
      boton("Detener", "square", () => api("cancelar", estado.tareas.analizar), "discreto")), bloqueProgreso({ mensaje: p.mensaje })));
    return partes;
  }
  const a = estado.analisis;
  if (!a) {
    partes.push(h("div", { class: "panel vacio" }, icono("scan-search"),
      h("p", {}, "Elige una unidad o una carpeta. El análisis solo lee: no cambia nada."),
      h("p", { style: { "font-size": "13px" } }, "Una unidad completa puede tardar unos minutos.")));
    return partes;
  }
  const nc = a.no_contabilizado || 0;
  const base = Math.max(1, a.visibles + a.ocultos + nc);
  partes.push(h("div", { class: "panel" },
    h("div", { class: "panel-cab" }, h("h2", {}, a.raiz),
      h("span", { class: "tenue" }, `${entero.format(a.archivos)} archivos en ${num.format(a.segundos)} s${a.cancelado ? " (detenido)" : ""}`)),
    h("div", { class: "apilada", role: "img", "aria-label": "Reparto del espacio" },
      h("span", { style: { width: a.visibles / base * 100 + "%", background: "var(--visible)" } }),
      h("span", { style: { width: a.ocultos / base * 100 + "%", background: "var(--oculto)" } }),
      h("span", { style: { width: nc / base * 100 + "%", background: "var(--tenue)" } })),
    h("div", { class: "metricas" },
      metrica("v", "Visible", a.visibles), metrica("o", "Oculto o de sistema", a.ocultos),
      a.usado_unidad ? metrica("", "Sin acceso o reservado", nc, "var(--tenue)") : null,
      metrica("", "Solo en la nube", a.nube)),
    a.sin_permiso ? nota(`${plural(a.sin_permiso, "carpeta no se ha podido leer", "carpetas no se han podido leer")} por permisos.${estado.info.admin ? "" : " Como administrador se ve más."}`, "", "lock") : null,
    nc > 0 && a.usado_unidad ? h("p", { class: "tenue", style: { "font-size": "13px", "margin-top": "10px" } },
      "«Sin acceso o reservado» incluye los puntos de restauración, la tabla del sistema de archivos (MFT) y las carpetas sin permiso. Mira «Espacio oculto».") : null));

  const maxC = Math.max(1, ...a.carpetas.map(c => c.bytes));
  const maxT = Math.max(1, ...a.tipos.map(t => t.bytes));
  partes.push(h("div", { class: "columnas" },
    h("div", { class: "panel" }, h("div", { class: "panel-cab" }, h("h2", {}, "Carpetas que más ocupan")),
      h("div", { class: "barras" }, a.carpetas.slice(0, 12).map(c => barraFila(c.nombre, c.bytes, maxC, c.ruta)))),
    h("div", { class: "panel" }, h("div", { class: "panel-cab" }, h("h2", {}, "Por tipo de archivo")),
      h("div", { class: "barras" }, a.tipos.slice(0, 12).map(t => barraFila(t.tipo, t.bytes, maxT))))));

  const filas = a.grandes.map(g => {
    const id = "g" + btoa(unescape(encodeURIComponent(g.ruta))).replace(/[^a-zA-Z0-9]/g, "").slice(-24);
    return h("tr", {},
      h("td", {}, h("input", { type: "checkbox", class: "casilla", id, "aria-label": "Marcar " + g.nombre, checked: estado.marcados.has(g.ruta),
        onchange: ev => { ev.target.checked ? estado.marcados.add(g.ruta) : estado.marcados.delete(g.ruta); pintar(); document.getElementById(id).focus(); } })),
      h("td", {}, h("div", { class: "celda-nombre" }, h("span", {}, g.nombre, g.oculto ? h("span", { class: "pastilla", style: { "margin-left": "6px" } }, "Oculto") : null),
        h("span", { class: "ruta", title: g.carpeta }, g.carpeta))),
      h("td", { class: "ocultar-movil" }, g.tipo),
      h("td", { class: "num cifra" }, tam(g.bytes)),
      h("td", {}, h("button", { class: "boton discreto", type: "button", title: "Mostrar en el Explorador", "aria-label": "Mostrar " + g.nombre + " en el Explorador",
        onclick: () => api("abrir_ubicacion", g.ruta) }, icono("external-link"))));
  });
  const marcados = [...estado.marcados];
  const bytesMarcados = a.grandes.filter(g => estado.marcados.has(g.ruta)).reduce((s, g) => s + g.bytes, 0);
  partes.push(h("section", { class: "grupo" },
    h("div", { class: "grupo-cab" }, icono("file-text"), h("h2", {}, "Archivos más grandes"),
      h("span", { class: "tenue" }, "Revisa antes de enviar algo a la papelera")),
    h("div", { class: "tabla-envoltura" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, h("span", { class: "oculto-a11y" }, "Marcar")), h("th", {}, "Archivo"),
        h("th", { class: "ocultar-movil" }, "Tipo"), h("th", { class: "num" }, "Tamaño"), h("th", {}, h("span", { class: "oculto-a11y" }, "Acciones")))),
      h("tbody", {}, filas)))));
  if (marcados.length) {
    partes.push(h("div", { class: "pie-accion" },
      h("span", {}, h("span", { class: "cifra" }, tam(bytesMarcados)), ` en ${plural(marcados.length, "archivo", "archivos")}`),
      h("div", { class: "cabecera-acciones" },
        boton("Desmarcar", "x", () => { estado.marcados.clear(); pintar(); }),
        boton("Enviar a la papelera", "trash-2", aPapelera, "primario"))));
  }
  return partes;
}
function metrica(cls, nombre, bytes, color) {
  return h("div", { class: "metrica" }, h("span", {}, h("span", { class: "punto " + cls, style: color ? { background: color } : null }), nombre),
    h("span", { class: "cifra" }, tam(bytes)));
}
function barraFila(nombre, bytes, max, titulo) {
  return h("div", { class: "barra-fila" }, h("span", { class: "nombre", title: titulo || nombre }, nombre), h("span", { class: "cifra" }, tam(bytes)),
    h("div", { class: "barra" }, h("span", { style: { width: Math.max(0.5, bytes / max * 100) + "%" } })));
}
async function aPapelera() {
  const rutas = [...estado.marcados];
  const r = await api("a_papelera", rutas);
  for (const ruta of r.enviados) estado.marcados.delete(ruta);
  if (estado.analisis) estado.analisis.grandes = estado.analisis.grandes.filter(g => !r.enviados.includes(g.ruta));
  if (r.enviados.length) aviso(`${plural(r.enviados.length, "archivo enviado", "archivos enviados")} a la papelera (${tam(r.bytes)})`);
  if (r.fallos.length) aviso(`${plural(r.fallos.length, "archivo no se ha podido", "archivos no se han podido")} enviar: ${r.fallos[0].motivo}`, "error");
  pintar();
}

// ------------------------------------------------------------------ Herramientas
async function herramienta(id, letra) {
  estado.herramienta = { id, progreso: null, mensaje: "Empezando…", lineas: [] };
  pintar();
  const t = await lanzar("herramienta", [id, letra], p => { estado.herramienta = { id, ...p }; if (estado.vista === "herramientas") actualizarProgreso(); });
  if (t) {
    estado.herramienta = { id, ...t, fin: true };
    if (t.estado === "hecha") aviso("Terminado");
    if (id.startsWith("hibernacion")) estado.oculto = {};
  } else estado.herramienta = null;
  pintar();
}
function confirmar(titulo, texto, accion, textoBoton, peligro) {
  const dlg = document.getElementById("dialogo");
  dlg.replaceChildren(h("div", { class: "dialogo-cuerpo" }, h("h2", {}, titulo), ...[].concat(texto),
    h("div", { class: "dialogo-botones" }, boton("Cancelar", null, () => dlg.close(), "discreto"),
      boton(textoBoton, null, () => { dlg.close(); accion(); }, peligro ? "peligro" : "primario"))));
  dlg.showModal();
}

function vHerramientas() {
  const partes = [];
  const admin = estado.info.admin;
  const ocupado = !!estado.tareas.herramienta;
  if (!admin) partes.push(nota(h("span", {}, "Estas herramientas necesitan permisos de administrador. ",
    h("button", { class: "boton discreto", type: "button", style: { "min-height": "24px", padding: "0 6px" }, onclick: reiniciarAdmin }, "Reiniciar como administrador")), "aviso", "lock"));
  const hT = estado.herramienta;
  if (hT) {
    partes.push(h("div", { class: "panel" },
      h("div", { class: "panel-cab" }, h("h2", {}, hT.mensaje || "Herramienta"),
        hT.fin ? boton("Cerrar", "x", () => { estado.herramienta = null; pintar(); }, "discreto")
               : boton("Cancelar", "square", () => api("cancelar", estado.tareas.herramienta), "discreto")),
      hT.fin ? h("span", { class: "pastilla " + (hT.estado === "hecha" ? "ok" : "aviso") }, hT.estado === "hecha" ? "Terminado" : hT.estado === "cancelada" ? "Cancelado" : "Con errores")
             : bloqueProgreso(hT),
      (hT.lineas || []).length ? h("pre", { class: "consola" }, (hT.lineas || []).slice(-20).join("\n")) : null));
  }
  const sistema = estado.unidades.find(u => u.sistema) || {};
  const hib = (estado.oculto[sistema.letra] || []).find(i => i.id === "hiberfil");
  const letra = estado.letraBorrado || sistema.letra;
  const uBorrado = estado.unidades.find(u => u.letra === letra) || {};
  const lista = h("ul", { class: "lista" },
    filaHerramienta("boxes", "Limpiar componentes de Windows",
      "Elimina versiones antiguas de actualizaciones del almacén WinSxS con DISM, la herramienta oficial. Puede tardar de 5 a 30 minutos.",
      [boton("Analizar", "scan-search", () => herramienta("dism_analizar"), "", { disabled: !admin || ocupado }),
       boton("Limpiar", "brush", () => confirmar("¿Limpiar componentes de Windows?", h("p", { class: "tenue" }, "Después no podrás desinstalar las actualizaciones ya instaladas. Es seguro y no afecta a tus programas."),
         () => herramienta("dism_limpiar"), "Limpiar"), "primario", { disabled: !admin || ocupado })]),
    filaHerramienta("moon", "Hibernación",
      `Desactivarla elimina hiberfil.sys${hib ? ` (${tam(hib.bytes)})` : ""} y el inicio rápido. Útil en equipos de sobremesa; en portátiles perderás la hibernación.`,
      [boton("Desactivar", null, () => confirmar("¿Desactivar la hibernación?", h("p", { class: "tenue" }, "Se borra hiberfil.sys y se desactiva el inicio rápido. Puedes volver a activarla aquí mismo."),
        () => herramienta("hibernacion_off"), "Desactivar"), "", { disabled: !admin || ocupado }),
       boton("Activar", null, () => herramienta("hibernacion_on"), "discreto", { disabled: !admin || ocupado })]),
    filaHerramienta("history", "Puntos de restauración",
      "Elige cuánto espacio pueden usar o borra los antiguos desde la herramienta de Windows.",
      [boton("Abrir Protección del sistema", "external-link", () => api("abrir_config", "proteccion"))]),
    filaHerramienta("hard-drive", "Configuración de almacenamiento",
      "Sensor de almacenamiento y limpieza de Windows.old y de actualizaciones anteriores.",
      [boton("Abrir", "external-link", () => api("abrir_config", "almacenamiento"))]),
    h("li", { class: "fila sin-check" },
      h("span", { class: "fila-icono" }, icono("eraser")),
      h("div", { class: "fila-cuerpo" },
        h("span", { class: "fila-titulo" }, "Borrado seguro del espacio libre", h("span", { class: "pastilla" }, icono("shield-check"), "cipher /w")),
        h("span", { class: "fila-desc" }, "Sobrescribe el espacio libre tres veces para que lo que borraste no se pueda recuperar con programas forenses. No toca tus archivos. Tarda horas en discos grandes."),
        h("div", { class: "chips", style: { "margin-top": "8px" } },
          estado.unidades.map(u => h("button", { class: "chip", type: "button", "aria-pressed": String(u.letra === letra),
            onclick: () => { estado.letraBorrado = u.letra; pintar(); } }, `${u.letra}:`, u.ssd ? " SSD" : ""))),
        uBorrado.ssd ? h("div", { style: { "margin-top": "8px" } }, nota("En un SSD no hace falta: TRIM ya borra los bloques libres, y escribir el disco entero lo desgasta. Úsalo en discos duros o antes de deshacerte del equipo (en ese caso, mejor el borrado seguro del fabricante).", "aviso")) : null),
      h("div", { class: "fila-dcha" }, boton("Borrar espacio libre", "eraser", () => confirmar(`¿Borrar el espacio libre de ${letra}:?`,
        [h("p", { class: "tenue" }, `Se escribirá ${tam(uBorrado.libre)} tres veces. El disco irá lento mientras tanto y puedes cancelarlo en cualquier momento.`)],
        () => herramienta("borrado_libre", letra), "Empezar", true), "", { disabled: !admin || ocupado || !letra }))));
  partes.push(lista);
  return partes;
}
function filaHerramienta(ic, titulo, desc, botones) {
  return h("li", { class: "fila sin-check" }, h("span", { class: "fila-icono" }, icono(ic)),
    h("div", { class: "fila-cuerpo" }, h("span", { class: "fila-titulo" }, titulo), h("span", { class: "fila-desc" }, desc)),
    h("div", { class: "fila-dcha" }, h("div", { class: "cabecera-acciones", style: { "justify-content": "flex-end" } }, botones)));
}

// ------------------------------------------------------------------ Registro
const NOMBRES_ACCION = { limpieza: "Limpieza", simulacion: "Simulación", analisis: "Análisis", auditoria_oculto: "Espacio oculto",
  papelera_archivos: "Enviados a la papelera", herramienta: "Herramienta" };
function vRegistro() {
  const partes = [];
  const r = estado.registro;
  if (!r) {
    api("registro").then(x => { estado.registro = x; if (estado.vista === "registro") pintar(); });
    return h("div", { class: "panel" }, bloqueProgreso(null, "Leyendo el registro…"));
  }
  const ok = r.integridad.ok;
  partes.push(h("div", { class: "panel" }, h("div", { class: "panel-cab", style: { "margin-bottom": "0" } },
    h("div", { style: { display: "flex", gap: "12px", "align-items": "center" } },
      h("span", { class: "fila-icono", style: { color: ok ? "var(--recuperable)" : "var(--peligro)" } }, icono(ok ? "shield-check" : "shield-alert")),
      h("div", {}, h("h2", {}, ok ? "Registro íntegro" : "El registro se ha modificado"),
        h("p", { class: "tenue", style: { "font-size": "13px" } }, ok
          ? `${plural(r.integridad.entradas, "entrada", "entradas")} encadenadas con SHA-256. Ninguna se ha cambiado ni borrado.`
          : `La entrada ${r.integridad.linea} no cuadra: ${r.integridad.error}.`))),
    h("div", { class: "cabecera-acciones" },
      boton("Exportar HTML", "file-down", () => exportar("html")),
      boton("CSV", "file-down", () => exportar("csv"), "discreto"),
      boton("Abrir carpeta", "folder-open", () => api("abrir_datos"), "discreto"),
      boton("Actualizar", "refresh-cw", () => { estado.registro = null; pintar(); }, "discreto")))));
  if (!r.entradas.length) {
    partes.push(h("div", { class: "panel vacio" }, icono("list-checks"), h("p", {}, "Aún no hay operaciones. Cada simulación, limpieza y análisis quedará aquí.")));
    return partes;
  }
  partes.push(h("div", { class: "tabla-envoltura" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Fecha"), h("th", {}, "Operación"), h("th", { class: "num" }, "Espacio"),
      h("th", { class: "num ocultar-movil" }, "Archivos"), h("th", { class: "ocultar-movil" }, "Usuario"), h("th", { class: "ocultar-movil" }, "Hash"))),
    h("tbody", {}, r.entradas.map(e => h("tr", {},
      h("td", {}, fecha(e.fecha)),
      h("td", {}, NOMBRES_ACCION[e.accion] || e.accion, e.admin ? h("span", { class: "pastilla", style: { "margin-left": "6px" } }, icono("lock"), "admin") : null,
        e.raiz || e.unidad ? h("div", { class: "ruta" }, e.raiz || (e.unidad + ":")) : null),
      h("td", { class: "num cifra" }, e.bytes !== undefined ? tam(e.bytes) : ""),
      h("td", { class: "num ocultar-movil" }, e.archivos !== undefined ? entero.format(e.archivos) : ""),
      h("td", { class: "ocultar-movil" }, e.usuario || ""),
      h("td", { class: "ocultar-movil tenue", title: e.hash || "" }, (e.hash || "").slice(0, 12))))))));
  return partes;
}
async function exportar(formato) {
  const r = await api("exportar", formato);
  if (r) aviso("Informe guardado");
}

// ------------------------------------------------------------------ permisos y arranque
async function reiniciarAdmin() {
  const ok = await api("reiniciar_admin");
  if (!ok) aviso("No se ha podido reiniciar como administrador", "error");
}
function pintarPermisos() {
  const c = document.getElementById("permisos");
  c.replaceChildren(estado.info.admin
    ? h("span", { class: "pastilla ok" }, icono("shield-check"), "Administrador")
    : boton("Reiniciar como administrador", "lock", reiniciarAdmin, "discreto"));
  document.getElementById("nav-pie").textContent = `Versión ${estado.info.version || ""} · ${estado.info.equipo || ""}`;
}

function construirNav() {
  const ul = document.getElementById("nav");
  ul.replaceChildren(...VISTAS.map(v => h("li", {},
    h("button", { class: "nav-boton", type: "button", "data-vista": v.id, title: v.nombre, "aria-label": v.nombre,
      onclick: () => ir(v.id) }, icono(v.icono), h("span", { class: "nav-texto" }, v.nombre)))));
  const logo = document.querySelector(".marca-logo");
  logo.replaceChildren(...Array.from({ length: 9 }, () => h("i")));
}

async function arrancar() {
  construirNav();
  ir("resumen");
  const [info, unidades, cat] = await Promise.all([api("info"), api("unidades"), api("catalogo")]);
  estado.info = info; estado.unidades = unidades; estado.catalogo = cat;
  pintarPermisos();
  pintar();
  medir();
}

if (window.pywebview && window.pywebview.api && window.pywebview.api.info) arrancar();
else window.addEventListener("pywebviewready", arrancar);
