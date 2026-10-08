/* Ejecuta el programa de Python (Pyodide) en segundo plano para no trabar la página. */
function crearMotor(postMessage) {
let py = null;
let puente = null;
let cfg = {};

function estado(texto) { postMessage({ tipo: "estado", texto }); }

async function iniciar() {
  estado("Cargando Python (la primera vez tarda un poco; después queda guardado)…");
  const { loadPyodide } = await import(new URL(cfg.pyodide + "pyodide.mjs", self.location.href).href);
  py = await loadPyodide({ indexURL: new URL(cfg.pyodide, self.location.href).href });
  estado("Cargando librerías de cálculo y dibujo…");
  await py.loadPackage(["numpy", "matplotlib", "micropip", "pyparsing", "typing-extensions", "fonttools", "shapely"]);
  estado("Instalando lectura de DXF y planillas…");
  const micropip = py.pyimport("micropip");
  if (cfg.wheels) {
    // Modo de prueba: ruedas servidas desde el mismo sitio.
    await micropip.install(cfg.wheels.map((w) => new URL(w, self.location.href).href), { deps: false });
  } else {
    await micropip.install(["ezdxf", "openpyxl"]);
  }
  estado("Cargando el programa…");
  let zip = cfg.zip ? new Uint8Array(cfg.zip) : null;       // versión de un solo archivo: viene incluido
  if (!zip) {
    const resp = await fetch("sip_python.zip", { cache: "no-cache" });
    if (!resp.ok) throw new Error("No se pudo leer sip_python.zip (¿falta ejecutar crear_web.py?)");
    zip = new Uint8Array(await resp.arrayBuffer());
  }
  py.unpackArchive(zip, "zip", { extractDir: "/proj" });
  py.runPython("import sys; sys.path.insert(0, '/proj')");
  puente = py.pyimport("puente_web");
}

function leerArchivo(ruta) {
  const datos = py.FS.readFile(ruta);           // Uint8Array
  return datos.buffer.slice(datos.byteOffset, datos.byteOffset + datos.byteLength);
}

return async (m) => {
  try {
    if (m.tipo === "iniciar") {
      cfg = m;
      await iniciar();
      postMessage({ tipo: "listo" });
    } else if (m.tipo === "generar") {
      estado(m.soloValidar ? "Validando el dibujo…" : "Generando las hojas (puede tardar uno o dos minutos)…");
      await new Promise((r) => setTimeout(r, 60));          // deja que la página muestre el mensaje
      const salida = JSON.parse(puente.correr(new Uint8Array(m.dxf), m.proyecto, m.unidades,
                                              JSON.stringify(m.caratula), m.soloValidar));
      if (!salida.ok) {
        postMessage({ tipo: "resultado", salida });
        return;
      }
      const base = "/tmp/trabajo/resultado/";
      const archivos = {};
      const transferibles = [];
      for (const rel of salida.archivos) {
        if (rel.startsWith("hojas/")) continue;            // van dentro del ZIP
        const buf = leerArchivo(base + rel);
        archivos[rel] = buf;
        transferibles.push(buf);
      }
      const zip = leerArchivo("/tmp/trabajo/hojas.zip");
      transferibles.push(zip);
      postMessage({ tipo: "resultado", salida, archivos, zip }, transferibles);
    } else if (m.tipo === "esquinas") {
      const lista = JSON.parse(puente.esquinas(new Uint8Array(m.dxf), m.unidades));
      postMessage({ tipo: "esquinas", lista });
    } else if (m.tipo === "lados") {
      const lista = JSON.parse(puente.lados(new Uint8Array(m.dxf), m.unidades));
      postMessage({ tipo: "lados", lista });
    } else if (m.tipo === "lamina") {
      estado("Dibujando la lámina gráfica…");
      await new Promise((r) => setTimeout(r, 60));
      const salida = JSON.parse(puente.lamina(new Uint8Array(m.dxf), m.proyecto, m.unidades, JSON.stringify(m.cfg)));
      if (!salida.ok) { postMessage({ tipo: "lamina", salida }); return; }
      const buf = leerArchivo(salida.ruta);
      postMessage({ tipo: "lamina", salida, buf }, [buf]);
    } else if (m.tipo === "plantilla") {
      const ruta = puente.plantilla();
      const buf = leerArchivo(ruta);
      postMessage({ tipo: "archivo", nombre: ruta.split("/").pop(), buf }, [buf]);
    }
  } catch (e) {
    postMessage({ tipo: "error", mensaje: String((e && e.message) || e) });
  }
};
}

// Como worker: se conecta solo. En la versión de un solo archivo, la página lo usa directamente (sin worker).
if (typeof WorkerGlobalScope !== "undefined" && self instanceof WorkerGlobalScope) {
  const recibir = crearMotor((m, t) => postMessage(m, t));
  onmessage = (ev) => recibir(ev.data);
}
