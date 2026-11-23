"use strict";

const API = "/api";
const $ = (id) => document.getElementById(id);
const SERIES = {
  cpu_percent:    { label: "CPU %",     color: "#3dbf9f", fill: "rgba(61,191,159,.12)" },
  memory_percent: { label: "Memoria %", color: "#4a8df0", fill: false },
  disk_percent:   { label: "Disco %",   color: "#e0a030", fill: false, dash: [6, 4] },
};

let token = sessionStorage.getItem("token");
let grafico = null;
let timer = null;
let rango = 60;

function mostrar(el, texto, error = false) {
  el.textContent = texto;               // textContent: nunca interpreta HTML
  el.className = error ? "msg error" : "msg";
}

async function api(ruta, opciones = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API + ruta, { ...opciones, headers });
  if (res.status === 401 && token) {
    salir();
    throw new Error("Sesión expirada, ingresa de nuevo");
  }
  const datos = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = datos.detail;
    throw new Error(typeof d === "string" ? d : "Error " + res.status);
  }
  return datos;
}

const credenciales = (email, password) => JSON.stringify({ email, password });

/* ---------- vistas de acceso: login / registro / olvidé ---------- */
function verAuth(id) {
  for (const v of ["vista-login", "vista-registro", "vista-olvide"]) $(v).hidden = v !== id;
}
$("ir-registro").addEventListener("click", (e) => { e.preventDefault(); verAuth("vista-registro"); });
$("link-olvide").addEventListener("click", (e) => { e.preventDefault(); verAuth("vista-olvide"); });
for (const id of ["ir-login-1", "ir-login-2"])
  $(id).addEventListener("click", (e) => { e.preventDefault(); verAuth("vista-login"); });

async function entrar(email, password) {
  const d = await api("/auth/login", { method: "POST", body: credenciales(email, password) });
  token = d.access_token;
  sessionStorage.setItem("token", token);
  await iniciarApp();
}

$("form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await entrar($("login-email").value, $("login-password").value);
  } catch (err) {
    mostrar($("msg-login"), err.message, true);
  }
});

$("form-registro").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = $("reg-email").value, password = $("reg-password").value;
  if (password !== $("reg-password2").value) {
    mostrar($("msg-registro"), "Las contraseñas no coinciden", true);
    return;
  }
  try {
    await api("/auth/register", { method: "POST", body: credenciales(email, password) });
    await entrar(email, password);          // tras registrarse, entra directamente
  } catch (err) {
    mostrar($("msg-registro"), err.message, true);
  }
});

// Requiere el endpoint POST /auth/forgot-password (aún no existe en el backend)
$("form-olvide").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email: $("olv-email").value }) });
    mostrar($("msg-olvide"), "Si el correo está registrado, recibirás un enlace en unos minutos.");
  } catch (err) {
    const noExiste = err.message === "Not Found" || err.message === "Error 404";
    mostrar($("msg-olvide"), noExiste ? "La recuperación de contraseña aún no está disponible." : err.message, true);
  }
});

function salir() {
  for (const f of ["form-login", "form-registro", "form-olvide"]) $(f).reset();
  for (const m of ["msg-login", "msg-registro", "msg-olvide"]) mostrar($(m), "");
  token = null;
  sessionStorage.removeItem("token");
  clearInterval(timer);
  if (grafico) { grafico.destroy(); grafico = null; }
  $("vista-app").hidden = true;
  $("vista-auth").hidden = false;
  $("btn-salir").hidden = true;
  verAuth("vista-login");
}
$("btn-salir").addEventListener("click", salir);

/* ---------- servidores y monitoreo ---------- */
async function cargarHosts() {
  const hosts = await api("/hosts");
  const sel = $("sel-host");
  const actual = sel.value;
  sel.replaceChildren();
  for (const h of hosts) {
    const o = document.createElement("option");
    o.value = h.id;
    o.textContent = `${h.name} (id ${h.id})`;
    sel.appendChild(o);
  }
  if (actual) sel.value = actual;
}

$("form-host").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const h = await api("/hosts", { method: "POST", body: JSON.stringify({ name: $("nuevo-host").value }) });
    $("nuevo-host").value = "";
    mostrar($("msg-app"), `Servidor creado con id ${h.id}. Pon HOST_ID=${h.id} en el .env del worker que lo mide.`);
    await cargarHosts();
  } catch (err) {
    mostrar($("msg-app"), err.message, true);
  }
});

$("btn-iniciar").addEventListener("click", async () => {
  try {
    const r = await api("/runs", { method: "POST" });
    mostrar($("msg-app"), `Monitoreo activo. workflow_id=${r.workflow_id}`);
  } catch (err) {
    mostrar($("msg-app"), err.message, true);
  }
});

/* ---------- panel: indicadores, barras y gráfico ---------- */
const nivel = (v) => (v >= 90 ? "critico" : v >= 70 ? "aviso" : "ok");
const gb = (bytes) => (bytes / 1024 ** 3).toFixed(1) + " GB";

function ultimo(series, nombre) {
  const s = series.find((x) => x.metric.__name__ === nombre);
  if (!s || !s.values.length) return null;
  const [t, v] = s.values[s.values.length - 1];
  return { t: t * 1000, v: Number(v) };
}

function pintarIndicador(clave, valor, texto) {
  const k = $("kpi-" + clave), v = $("val-" + clave), b = $("bar-" + clave);
  if (valor === null) { k.textContent = "--"; v.textContent = "--"; b.style.width = "0%"; return; }
  k.textContent = valor + "%";
  k.className = nivel(valor);
  v.textContent = texto ? `${valor}% · ${texto}` : valor + "%";
  b.style.width = valor + "%";
  b.className = "relleno " + nivel(valor);
}

function pintarIndicadores(series) {
  const cpu = ultimo(series, "cpu_percent"), mem = ultimo(series, "memory_percent"), disco = ultimo(series, "disk_percent");
  const libre = ultimo(series, "memory_available"), usado = ultimo(series, "disk_used");
  pintarIndicador("cpu", cpu && cpu.v);
  pintarIndicador("mem", mem && mem.v, libre && gb(libre.v) + " libres");
  pintarIndicador("disk", disco && disco.v, usado && gb(usado.v) + " usados");
  $("sub-mem").textContent = libre ? gb(libre.v) + " libres" : "uso actual";
  $("sub-disk").textContent = usado ? gb(usado.v) + " usados" : "uso actual";
  const l = cpu || mem || disco;
  const el = $("kpi-lectura");
  if (!l) { el.textContent = "--"; $("sub-lectura").textContent = "sin datos"; return; }
  const seg = Math.max(0, Math.round((Date.now() - l.t) / 1000));
  el.textContent = seg < 60 ? `hace ${seg} s` : `hace ${Math.round(seg / 60)} min`;
  el.className = seg > 60 ? "critico" : "ok";
  $("sub-lectura").textContent = seg > 60 ? "el worker no está midiendo" : "midiendo con normalidad";
}

async function cargarGrafico() {
  const hostId = $("sel-host").value;
  if (!hostId) return;
  const paso = rango <= 60 ? "5s" : "15s";
  const d = await api(`/hosts/${hostId}/historial?minutos=${rango}&paso=${paso}`);
  pintarIndicadores(d.metricas);
  const datasets = d.metricas
    .filter((s) => SERIES[s.metric.__name__])
    .map((s) => {
      const c = SERIES[s.metric.__name__];
      return {
        label: c.label, borderColor: c.color, backgroundColor: c.fill || "transparent", fill: !!c.fill,
        borderDash: c.dash || [], borderWidth: 2, pointRadius: 0, tension: 0.25,
        data: s.values.map(([t, v]) => ({ x: t * 1000, y: Number(v) })),
      };
    });
  if (grafico) {
    grafico.data.datasets = datasets;
    grafico.update();
    return;
  }
  Chart.defaults.color = "#8b97ab";
  Chart.defaults.borderColor = "#2a3547";
  grafico = new Chart($("grafico"), {
    type: "line",
    data: { datasets },
    options: {
      parsing: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { align: "end", labels: { usePointStyle: true, boxWidth: 8 } } },
      scales: {
        x: { type: "linear", grid: { display: false }, ticks: { maxTicksLimit: 8, callback: (v) => new Date(v).toLocaleTimeString() } },
        y: { min: 0, max: 100 },
      },
    },
  });
}

async function cargarPromedios() {
  const hostId = $("sel-host").value;
  if (!hostId) return;
  const filas = await api(`/hosts/${hostId}/promedios?horas=1`);
  const tbody = $("tabla-prom");
  tbody.replaceChildren();
  for (const f of filas.slice(-10)) {
    const tr = document.createElement("tr");
    const celdas = [
      new Date(f.minuto).toLocaleTimeString(),
      f.cpu_avg.toFixed(1), f.cpu_max,
      f.memory_avg.toFixed(1), f.memory_max,
      f.disk_avg.toFixed(1),
    ];
    for (const v of celdas) {
      const td = document.createElement("td");
      td.textContent = v;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

async function refrescar() {
  try {
    await Promise.all([cargarGrafico(), cargarPromedios()]);
  } catch (err) {
    mostrar($("msg-app"), err.message, true);
  }
}
$("sel-host").addEventListener("change", refrescar);
$("rangos").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-min]");
  if (!b) return;
  for (const x of $("rangos").children) x.classList.toggle("activo", x === b);
  rango = Number(b.dataset.min);
  refrescar();
});

/* ---------- arranque ---------- */
async function iniciarApp() {
  $("vista-auth").hidden = true;
  $("vista-app").hidden = false;
  $("btn-salir").hidden = false;
  await cargarHosts();
  await refrescar();
  clearInterval(timer);
  timer = setInterval(refrescar, 5000);
}

if (token) iniciarApp().catch(salir);
