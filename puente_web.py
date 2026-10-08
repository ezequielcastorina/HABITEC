"""Puente entre la página web (Pyodide) y el programa. No se usa desde la ventana ni la consola."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

BASE = Path("/tmp/trabajo")


def _bytes(x) -> bytes:
    if hasattr(x, "to_py"):
        x = x.to_py()
    return bytes(x)


def correr(dxf_bytes, proyecto: str, unidades: str, caratula_json: str, solo_validar: bool) -> str:
    from sip.proceso import generar
    shutil.rmtree(BASE, ignore_errors=True)
    BASE.mkdir(parents=True)
    dxf = BASE / "plano.dxf"
    dxf.write_bytes(_bytes(dxf_bytes))
    out = BASE / "resultado"
    logs: list[str] = []
    try:
        res = generar(dxf, proyecto, unidades, out, bool(solo_validar), logs.append,
                      json.loads(caratula_json or "{}"))
    except Exception as e:                                   # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}", "log": logs})
    logs = [("Listo: hojas generadas." if l.startswith("Listo.") else l) for l in logs]
    archivos = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    zpath = BASE / "hojas.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in archivos:
            z.write(out / rel, rel)
    return json.dumps({"ok": True, "log": logs, "alertas": res.alertas, "archivos": archivos,
                       "n_muros": res.n_muros, "n_techos": res.n_techos, "n_vanos": res.n_vanos,
                       "solo_validar": bool(solo_validar)})


def plantilla() -> str:
    from generar_ejemplo import crear
    ruta = BASE / "plantilla_habitec.dxf"
    BASE.mkdir(parents=True, exist_ok=True)
    crear(str(ruta), "m")
    return str(ruta)


def esquinas(dxf_bytes, unidades: str = "auto") -> str:
    """Esquinas convexas del módulo, nombradas por las letras de sus lados (para el selector de la web)."""
    from sip.carga import esquinas_disponibles
    from sip.lector_dxf import leer_plano
    from sip.despiece import calcular
    BASE.mkdir(parents=True, exist_ok=True)
    dxf = BASE / "plano_esquinas.dxf"
    dxf.write_bytes(_bytes(dxf_bytes))
    try:
        return json.dumps(esquinas_disponibles(calcular(leer_plano(dxf, "x", unidades or "auto"))))
    except Exception:                                        # noqa: BLE001
        return "[]"


def lados(dxf_bytes, unidades: str = "auto") -> str:
    """Lados del módulo (letra, largo, hacia dónde mira, vanos) para el formulario de revestimientos."""
    from sip.lamina import lados_para_web
    from sip.lector_dxf import leer_plano
    BASE.mkdir(parents=True, exist_ok=True)
    dxf = BASE / "plano_lados.dxf"
    dxf.write_bytes(_bytes(dxf_bytes))
    try:
        return json.dumps(lados_para_web(leer_plano(dxf, "x", unidades or "auto")))
    except Exception:                                        # noqa: BLE001
        return "[]"


def lamina(dxf_bytes, proyecto: str, unidades: str, cfg_json: str) -> str:
    """Genera la lámina gráfica (planta y vistas) en /tmp/trabajo/lamina_grafica.pdf."""
    import datetime
    import matplotlib.pyplot as plt
    from sip.lamina import hoja_lamina
    from sip.lector_dxf import leer_plano
    BASE.mkdir(parents=True, exist_ok=True)
    dxf = BASE / "plano_lamina.dxf"
    dxf.write_bytes(_bytes(dxf_bytes))
    try:
        plano = leer_plano(dxf, proyecto, unidades or "auto")
        fig, avisos = hoja_lamina(plano, json.loads(cfg_json or "{}"), datetime.date.today().strftime("%d/%m/%Y"))
        ruta = BASE / "lamina_grafica.pdf"
        fig.savefig(ruta)
        plt.close(fig)
    except Exception as e:                                   # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})
    return json.dumps({"ok": True, "ruta": str(ruta), "avisos": avisos})
