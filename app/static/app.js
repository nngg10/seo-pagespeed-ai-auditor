"use strict";

// ------------------------------------------------------------ Sesión y API
const Sesion = {
  token: () => localStorage.getItem("token"),
  usuario: () => JSON.parse(localStorage.getItem("usuario") || "null"),
  guardar(datos) {
    localStorage.setItem("token", datos.access_token);
    localStorage.setItem("usuario", JSON.stringify(datos.usuario));
  },
  cerrar() {
    localStorage.removeItem("token");
    localStorage.removeItem("usuario");
  },
};

class SesionExpirada extends Error {}

async function api(metodo, ruta, cuerpo) {
  const headers = {};
  if (cuerpo !== undefined) headers["Content-Type"] = "application/json";
  const token = Sesion.token();
  if (token) headers["Authorization"] = "Bearer " + token;

  const r = await fetch("/api" + ruta, {
    method: metodo, headers, body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
  });

  if (r.status === 401 && token) {           // CA-7.2: token vencido o inválido
    Sesion.cerrar();
    ir("#/expirada");
    throw new SesionExpirada("Sesión expirada");
  }
  if (r.status === 204) return null;
  const tipo = r.headers.get("content-type") || "";
  if (!tipo.includes("application/json")) {
    if (!r.ok) throw new Error("Error del servidor (" + r.status + ")");
    return r;
  }
  const datos = await r.json();
  if (!r.ok) {
    const d = datos && datos.detail;
    throw new Error(Array.isArray(d) ? d.map((x) => x.msg).join(". ") : d || "Error inesperado");
  }
  return datos;
}

// ---------------------------------------------------------------- Utilidades
const $app = document.getElementById("app");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const ir = (hash) => { if (location.hash === hash) router(); else location.hash = hash; };

function alerta(tipo, texto) {
  return `<div class="alerta alerta-${tipo}">${esc(texto)}</div>`;
}

function estadoPuntaje(v) {
  if (v === null || v === undefined) return ["No disponible", "nd"];
  if (v >= 90) return ["Bueno", "bueno"];
  if (v >= 50) return ["Necesita mejora", "mejora"];
  return ["Crítico", "critico"];
}
function estadoLcp(v) {
  if (v === null || v === undefined) return ["No disponible", "nd"];
  if (v <= 2.5) return ["Bueno", "bueno"];
  if (v <= 4) return ["Necesita mejora", "mejora"];
  return ["Crítico", "critico"];
}
const chipEstado = ([texto, clase]) => `<span class="estado estado-${clase}">${texto}</span>`;

function fmtVar(n) {
  if (n === null || n === undefined) return "—";
  if (n > 0) return `<span class="var-pos">+${n}</span>`;
  if (n < 0) return `<span class="var-neg">${n}</span>`;
  return "0";
}

function fmtFecha(f) {
  if (!f) return "";
  const d = new Date(f.replace(" ", "T"));
  if (isNaN(d)) return f;
  return d.toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit", year: "numeric" }) +
    " " + d.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
}

function enviarForm(form, manejador) {
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const boton = form.querySelector("button[type=submit]");
    const zona = form.querySelector(".mensajes");
    zona.innerHTML = "";
    boton.disabled = true;
    try {
      await manejador(Object.fromEntries(new FormData(form)), zona);
    } catch (e) {
      if (!(e instanceof SesionExpirada)) zona.innerHTML = alerta("error", e.message);
    } finally {
      boton.disabled = false;
    }
  });
}

// --------------------------------------------------------------------- Vistas
const Vistas = {
  // HU-01
  login() {
    $app.innerHTML = `
      <div class="centrado panel">
        <div class="panel-cab">Iniciar sesión <small>Seguridad JWT</small></div>
        <form class="panel-cuerpo" id="f">
          <p class="sub">Auditor SEO &amp; PageSpeed AI</p>
          <div class="mensajes"></div>
          <div class="campo"><label>Correo electrónico</label><input name="email" type="email" required autofocus></div>
          <div class="campo"><label>Contraseña</label><input name="password" type="password" required></div>
          <button class="btn btn-bloque" type="submit">Iniciar sesión</button>
          <div class="pie-form">¿No tienes cuenta? <a href="#/registro">Regístrate</a></div>
        </form>
      </div>`;
    enviarForm(document.getElementById("f"), async (d) => {
      Sesion.guardar(await api("POST", "/auth/login", d));
      ir("#/dashboard");
    });
  },

  // HU-00
  registro() {
    $app.innerHTML = `
      <div class="centrado panel">
        <div class="panel-cab">Registro de cuenta PYME <small>Paso 1 de 1</small></div>
        <form class="panel-cuerpo" id="f">
          <div class="mensajes"></div>
          <div class="campo"><label>Nombre completo</label><input name="nombre" required autofocus></div>
          <div class="campo"><label>Correo corporativo</label><input name="email" type="email" required></div>
          <div class="campo"><label>Contraseña segura (mínimo 8 caracteres)</label><input name="password" type="password" minlength="8" required></div>
          <div class="campo"><label>Confirmar contraseña</label><input name="confirmacion" type="password" minlength="8" required></div>
          <button class="btn btn-bloque" type="submit">Crear cuenta e iniciar</button>
          <div class="pie-form">¿Ya tienes cuenta? <a href="#/login">Inicia sesión</a></div>
        </form>
      </div>`;
    enviarForm(document.getElementById("f"), async (d, zona) => {
      await api("POST", "/auth/registro", d);
      zona.innerHTML = alerta("ok", "Cuenta creada correctamente. Iniciando sesión…");
      Sesion.guardar(await api("POST", "/auth/login", { email: d.email, password: d.password }));
      setTimeout(() => ir("#/dashboard"), 900);
    });
  },

  // HU-07
  expirada() {
    $app.innerHTML = `
      <div class="centrado panel">
        <div class="panel-cab">Sesión expirada <small>Seguridad JWT</small></div>
        <div class="panel-cuerpo">
          <p>Tu sesión ha expirado o ya no es válida.</p>
          <p class="sub">Por seguridad, vuelve a iniciar sesión para continuar.</p>
          <a class="btn btn-bloque" href="#/login" style="text-align:center">Volver a iniciar sesión</a>
        </div>
      </div>`;
  },

  // HU-02
  async dashboard() {
    const lista = await api("GET", "/tiendas");
    const u = Sesion.usuario();
    const filas = lista.map((t) => {
      const ua = t.ultima_auditoria;
      const resumen = ua
        ? `Última auditoría: ${fmtFecha(ua.fecha)} · Rendimiento ${ua.rendimiento ?? "N/D"} · SEO ${ua.seo}`
        : "Sin auditorías todavía";
      return `<li>
          <div class="info"><strong>${esc(t.nombre)}</strong><span>${esc(t.url)}</span><br><span>${resumen}</span></div>
          <div class="acciones">
            ${ua ? `<a class="btn btn-sec btn-peq" href="#/auditoria/${ua.id}">Ver último reporte</a>` : ""}
            <a class="btn btn-sec btn-peq" href="#/historial/${t.id}">Historial (${t.total_auditorias})</a>
            <a class="btn btn-peq" href="#/auditar/${t.id}">Auditar</a>
          </div></li>`;
    }).join("");

    $app.innerHTML = `
      <h1>Panel principal</h1>
      <p class="sub">Hola, ${esc(u && u.nombre)}. Aquí están tus tiendas y sus auditorías.</p>
      <div class="panel">
        <div class="panel-cab">Mis tiendas registradas (${lista.length})
          <span class="acciones"><a class="btn btn-sec btn-peq" href="#/tiendas">Gestionar tiendas</a>
          ${lista.length ? `<a class="btn btn-peq" href="#/auditar">+ Nueva auditoría</a>` : ""}</span>
        </div>
        ${lista.length ? `<ul class="lista">${filas}</ul>` : `
          <div class="vacio"><p>Aún no tienes tiendas registradas.</p>
          <a class="btn" href="#/tiendas">Registrar mi primera tienda</a></div>`}
      </div>`;
  },

  // HU-05
  async tiendas() {
    const lista = await api("GET", "/tiendas");
    const filas = lista.map((t) => `
      <li data-id="${t.id}">
        <div class="info"><strong>${esc(t.nombre)}</strong><span>${esc(t.url)}</span></div>
        <div class="acciones">
          <button class="btn btn-sec btn-peq" data-accion="editar">Editar</button>
          <button class="btn btn-peligro btn-peq" data-accion="eliminar">Eliminar</button>
        </div></li>`).join("");

    $app.innerHTML = `
      <h1>Gestión de tiendas</h1>
      <p class="sub">Agrega, edita o elimina las tiendas que quieres auditar.</p>
      <div class="panel">
        <div class="panel-cab" id="titulo-form">Registrar tienda</div>
        <form class="panel-cuerpo" id="f">
          <div class="mensajes"></div>
          <input type="hidden" name="editar_id">
          <div class="fila">
            <div class="campo"><label>Nombre de la tienda</label><input name="nombre" required placeholder="Zapatería Cuero Fino"></div>
            <div class="campo"><label>URL principal</label><input name="url" required placeholder="https://mitienda.com"></div>
          </div>
          <div class="acciones">
            <button class="btn" type="submit">Guardar tienda</button>
            <button class="btn btn-sec oculto" type="button" id="cancelar">Cancelar edición</button>
          </div>
        </form>
      </div>
      <h2>Mis tiendas registradas (${lista.length})</h2>
      <div class="panel">${lista.length ? `<ul class="lista">${filas}</ul>` :
        `<div class="vacio"><p>Aún no tienes tiendas registradas.</p></div>`}</div>`;

    const form = document.getElementById("f");
    const cancelar = document.getElementById("cancelar");
    const modoCrear = () => {
      form.reset(); form.editar_id.value = "";
      document.getElementById("titulo-form").textContent = "Registrar tienda";
      cancelar.classList.add("oculto");
    };
    cancelar.onclick = modoCrear;

    enviarForm(form, async (d) => {
      const cuerpo = { nombre: d.nombre, url: d.url };
      if (d.editar_id) await api("PUT", "/tiendas/" + d.editar_id, cuerpo);
      else await api("POST", "/tiendas", cuerpo);
      await Vistas.tiendas();
      document.querySelector(".mensajes").innerHTML = alerta("ok", d.editar_id ? "Tienda actualizada." : "Tienda registrada.");
    });

    $app.querySelectorAll("[data-accion]").forEach((b) => {
      b.onclick = async () => {
        const li = b.closest("li");
        const t = lista.find((x) => x.id === Number(li.dataset.id));
        if (b.dataset.accion === "editar") {
          form.editar_id.value = t.id; form.nombre.value = t.nombre; form.url.value = t.url;
          document.getElementById("titulo-form").textContent = "Editar tienda";
          cancelar.classList.remove("oculto");
          form.nombre.focus();
        } else if (confirm(`¿Eliminar "${t.nombre}"? También se borrará su historial de auditorías.`)) {
          await api("DELETE", "/tiendas/" + t.id);
          await Vistas.tiendas();
          document.querySelector(".mensajes").innerHTML = alerta("ok", "Tienda eliminada.");
        }
      };
    });
  },

  // HU-03
  async auditar(tiendaId) {
    const lista = await api("GET", "/tiendas");
    if (!lista.length) {
      $app.innerHTML = `<h1>Nueva auditoría</h1><div class="panel"><div class="vacio">
        <p>Primero registra una tienda para poder auditarla.</p><a class="btn" href="#/tiendas">Registrar tienda</a></div></div>`;
      return;
    }
    const sel = lista.find((t) => t.id === Number(tiendaId)) || lista[0];
    $app.innerHTML = `
      <h1>Nueva auditoría</h1>
      <p class="sub">Ingresa la URL de una página de producto o categoría. Se ejecutan en paralelo el scraper On-Page y Google PageSpeed (móvil).</p>
      <div class="panel">
        <div class="panel-cab">Módulo de auditoría · URL objetivo <span class="chip">Estado: Activo</span></div>
        <form class="panel-cuerpo" id="f">
          <div class="mensajes"></div>
          <div class="fila">
            <div class="campo" style="max-width:260px"><label>Tienda</label>
              <select name="tienda_id">${lista.map((t) =>
                `<option value="${t.id}" data-url="${esc(t.url)}" ${t.id === sel.id ? "selected" : ""}>${esc(t.nombre)}</option>`).join("")}
              </select></div>
            <div class="campo"><label>URL a auditar</label><input name="url" required value="${esc(sel.url)}"></div>
          </div>
          <button class="btn" type="submit">Auditar sitio</button>
          <div class="progreso oculto" id="prog"><div class="giro"></div><span id="prog-txt"></span></div>
        </form>
      </div>`;

    const form = document.getElementById("f");
    form.tienda_id.onchange = () => { form.url.value = form.tienda_id.selectedOptions[0].dataset.url; };

    enviarForm(form, async (d) => {
      const prog = document.getElementById("prog");
      const txt = document.getElementById("prog-txt");
      const t0 = Date.now();
      prog.classList.remove("oculto");
      const reloj = setInterval(() => {
        txt.textContent = `Analizando HTML, consultando PageSpeed y generando diagnóstico… ${Math.round((Date.now() - t0) / 1000)}s`;
      }, 250);
      try {
        const a = await api("POST", "/auditorias", { tienda_id: Number(d.tienda_id), url: d.url });
        sessionStorage.setItem("recien", a.id);
        ir("#/auditoria/" + a.id);
      } finally {
        clearInterval(reloj);
        prog.classList.add("oculto");
      }
    });
  },

  // HU-04
  async auditoria(id) {
    const a = await api("GET", "/auditorias/" + id);
    const recien = sessionStorage.getItem("recien") === String(a.id);
    sessionStorage.removeItem("recien");
    const s = a.scraper, p = a.pagespeed || {};
    const v = a.variacion;

    const recs = a.recomendaciones.length ? a.recomendaciones.map((r) => `
      <div class="rec ${esc(r.severidad)}">
        <span class="etq">${esc(r.severidad)} · ${esc(r.categoria)}</span>
        <p class="titulo">${esc(r.titulo)}</p><p>${esc(r.accion)}</p>
      </div>`).join("") : `<div class="vacio"><p>No se detectaron problemas relevantes.</p></div>`;

    const filasTec = [
      ["Title", s.title || "(vacío)"],
      ["Meta description", s.meta_description || "(ausente)"],
      ["H1", (s.encabezados.h1 || []).join(" | ") || "(ausente)"],
      ["H2 / H3", `${s.encabezados.h2.length} / ${s.encabezados.h3.length}`],
      ["Imágenes sin alt", `${s.imagenes_sin_alt} de ${s.imagenes_total}`],
      ["Canonical", s.canonical || "(ausente)"],
      ["Idioma (lang)", s.lang || "(ausente)"],
      ["Meta viewport", s.meta_viewport || "(ausente)"],
      ["Etiquetas meta extraídas", s.etiquetas_meta_total],
      ["Open Graph", Object.keys(s.open_graph).join(", ") || "(ausente)"],
      ["Enlaces internos / externos", `${s.enlaces_internos} / ${s.enlaces_externos}`],
      ["Palabras en la página", s.palabras],
      ["Respuesta del servidor", `${s.tiempo_respuesta_ms} ms`],
    ];
    if (a.pagespeed && p.rendimiento !== undefined) {
      filasTec.push(["CLS", p.cls ?? "N/D"], ["Total Blocking Time", p.tbt_ms != null ? p.tbt_ms + " ms" : "N/D"],
        ["First Contentful Paint", p.fcp_s != null ? p.fcp_s + " s" : "N/D"], ["SEO según Lighthouse", p.seo_lighthouse ?? "N/D"]);
    }

    $app.innerHTML = `
      <h1>Resultados y diagnóstico IA</h1>
      <p class="sub">Reporte #${esc(a.codigo)} · ${esc(a.tienda.nombre)} · <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.url)}</a></p>
      ${recien ? alerta("ok", `✓ Análisis completado con éxito en ${a.duracion_s} segundos. Estado HTTP: ${a.http_status} OK.`) : ""}
      <div class="meta-linea"><span>Fecha: ${fmtFecha(a.fecha)}</span><span>Duración: ${a.duracion_s}s</span><span>HTTP ${a.http_status}</span>
        ${v ? `<span>Frente a #${esc(v.codigo_anterior)}: rendimiento ${fmtVar(v.rendimiento)} · SEO ${fmtVar(v.seo)}</span>` : ""}</div>
      ${a.pagespeed_error ? alerta("aviso", "Métricas de velocidad no disponibles: " + a.pagespeed_error) : ""}
      <div class="tarjetas">
        <div class="tarjeta"><div class="t">Rendimiento Mobile</div>
          <div class="v">${a.rendimiento ?? "N/D"}${a.rendimiento != null ? " <small>/ 100</small>" : ""}</div>${chipEstado(estadoPuntaje(a.rendimiento))}</div>
        <div class="tarjeta"><div class="t">SEO On-Page</div>
          <div class="v">${a.seo} <small>/ 100</small></div>${chipEstado(estadoPuntaje(a.seo))}</div>
        <div class="tarjeta"><div class="t">Core Web Vitals (LCP)</div>
          <div class="v">${a.lcp_s != null ? a.lcp_s + "s" : "N/D"}</div>${chipEstado(estadoLcp(a.lcp_s))}</div>
      </div>
      <div class="acciones" style="margin-bottom:18px">
        <button class="btn" id="pdf">Exportar PDF</button>
        <a class="btn btn-sec" href="#/historial/${a.tienda_id}">Ver historial de la tienda</a>
        <a class="btn btn-sec" href="#/auditar/${a.tienda_id}">Nueva auditoría</a>
      </div>
      <div class="mensajes" id="msg"></div>
      ${a.ia_aviso ? `<div class="alerta alerta-aviso">${esc(a.ia_aviso)}
        ${a.ia_fallo ? ` <button class="btn btn-sec btn-peq" id="reintentar">Reintentar diagnóstico IA</button>` : ""}</div>` : ""}
      <div class="panel">
        <div class="panel-cab">Plan de acción <small>Generado por: ${esc(a.ia_fuente)}</small></div>
        ${recs}
      </div>
      <h2>Datos técnicos extraídos</h2>
      <div class="panel"><table class="tabla">${filasTec.map(([k, val]) => `<tr><th>${esc(k)}</th><td>${esc(val)}</td></tr>`).join("")}</table></div>`;

    document.getElementById("pdf").onclick = async (ev) => {
      ev.target.disabled = true;
      try {
        const r = await api("GET", `/auditorias/${a.id}/pdf`);
        const url = URL.createObjectURL(await r.blob());
        const enlace = Object.assign(document.createElement("a"), { href: url, download: `Reporte-${a.codigo}.pdf` });
        document.body.appendChild(enlace); enlace.click(); enlace.remove();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
      } catch (e) {
        if (!(e instanceof SesionExpirada)) document.getElementById("msg").innerHTML = alerta("error", e.message);
      } finally { ev.target.disabled = false; }
    };

    const reintentar = document.getElementById("reintentar");
    if (reintentar) reintentar.onclick = async () => {
      reintentar.disabled = true;
      reintentar.textContent = "Consultando IA…";
      try { await api("POST", `/auditorias/${a.id}/diagnostico`); await Vistas.auditoria(a.id); }
      catch (e) { if (!(e instanceof SesionExpirada)) document.getElementById("msg").innerHTML = alerta("error", e.message); }
    };
  },

  // HU-06
  async historial(tiendaId) {
    const { tienda, auditorias } = await api("GET", `/tiendas/${tiendaId}/auditorias`);
    const filas = auditorias.map((a) => `
      <li>
        <div class="info"><strong>#${esc(a.codigo)} · ${fmtFecha(a.fecha)}</strong>
          <span>Rendimiento ${a.rendimiento ?? "N/D"} · SEO ${a.seo} · ${esc(a.url)}</span>
          ${a.variacion ? `<br><span>Variación frente a la anterior: Rendimiento ${fmtVar(a.variacion.rendimiento)} · SEO ${fmtVar(a.variacion.seo)}</span>` : ""}
        </div>
        <div class="acciones"><a class="btn btn-sec btn-peq" href="#/auditoria/${a.id}">Ver detalle</a></div>
      </li>`).join("");
    $app.innerHTML = `
      <h1>Historial de auditorías</h1>
      <p class="sub">Tienda: ${esc(tienda.nombre)} · ${esc(tienda.url)}</p>
      <div class="panel">
        <div class="panel-cab">Auditorías (${auditorias.length}) <a class="btn btn-peq" href="#/auditar/${tienda.id}">+ Nueva auditoría</a></div>
        ${auditorias.length ? `<ul class="lista">${filas}</ul>` :
          `<div class="vacio"><p>Aún no hay auditorías para esta tienda.</p><a class="btn" href="#/auditar/${tienda.id}">+ Nueva auditoría</a></div>`}
      </div>`;
  },
};

// --------------------------------------------------------------------- Router
const PUBLICAS = ["login", "registro", "expirada"];

async function router() {
  const [, vista = "", param] = (location.hash || "#/").split("/");
  const autenticado = !!Sesion.token();
  let nombre = vista || (autenticado ? "dashboard" : "login");
  if (!Vistas[nombre]) nombre = autenticado ? "dashboard" : "login";
  if (!autenticado && !PUBLICAS.includes(nombre)) nombre = "login";
  if (autenticado && (nombre === "login" || nombre === "registro")) nombre = "dashboard";

  const barra = document.getElementById("barra");
  barra.classList.toggle("oculto", !autenticado);
  if (autenticado) {
    document.getElementById("nombre-usuario").textContent = (Sesion.usuario() || {}).nombre || "";
    barra.querySelectorAll("nav a").forEach((a) => a.classList.toggle("activo", a.getAttribute("href") === "#/" + nombre));
  }

  try {
    await Vistas[nombre](param);
  } catch (e) {
    if (!(e instanceof SesionExpirada)) $app.innerHTML = alerta("error", e.message);
  }
  window.scrollTo(0, 0);
}

// HU-07: cierre de sesión manual
document.getElementById("btn-salir").onclick = () => { Sesion.cerrar(); ir("#/login"); };
window.addEventListener("hashchange", router);
router();
