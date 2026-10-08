"""Proceso completo: DXF -> validación -> hojas de taller, plano, planilla e informe.

Lo usan la línea de comandos (generar_hojas.py) y la web (puente_web.py).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from .contorno import texto_caida
from .caratula import Caratula, hoja_caratula
from .carga import hoja_carga
from .despiece import calcular
from .hoja_taller import hoja_muro, hoja_techo, plano_nomenclatura
from .lector_dxf import leer_plano
from .salida import informe_txt, planilla_xlsx


@dataclass
class Resultado:
    carpeta: Path
    alertas: list[str] = field(default_factory=list)
    n_muros: int = 0
    n_techos: int = 0
    n_vanos: int = 0
    archivos: list[str] = field(default_factory=list)


def carpeta_por_defecto(dxf: str | Path) -> Path:
    """Carpeta junto al DXF, con el nombre del archivo más '_hojas'."""
    dxf = Path(dxf)
    return dxf.with_name(dxf.stem + "_hojas")


def generar(dxf: str | Path, proyecto: str, unidades: str = "auto",
            salida: str | Path | None = None, solo_validar: bool = False,
            log: Callable[[str], None] = print, caratula=None) -> Resultado:
    out = Path(salida) if salida else carpeta_por_defecto(dxf)
    out.mkdir(parents=True, exist_ok=True)

    plano = leer_plano(dxf, proyecto, unidades)
    car = Caratula.desde(caratula)
    d = calcular(plano, car.piel_exterior)
    informe_txt(d, out / "informe_validacion.txt", car)

    res = Resultado(carpeta=out, alertas=list(d.alertas), n_muros=len(d.muros),
                    n_techos=len(d.techos), n_vanos=len(plano.vanos),
                    archivos=["informe_validacion.txt"])
    log(f"Proyecto: {proyecto}")
    log(f"Módulo {plano.modulo.ancho_x:.2f} × {plano.modulo.alto_y:.2f} m · caída hacia {texto_caida(plano)}")
    log(f"{res.n_muros} paneles de muro, {res.n_techos} de techo, {res.n_vanos} vanos")
    if d.avisos:
        log("\nAvisos (no bloquean):")
        for a in d.avisos:
            log(f"  - {a}")
    if d.alertas:
        log(f"\n{len(d.alertas)} ALERTAS:")
        for a in d.alertas:
            log(f"  - {a}")
    else:
        log("\nSin alertas.")
    if solo_validar:
        return res

    log("\nGenerando hojas…")
    fecha = datetime.date.today().strftime("%d/%m/%Y")
    planilla_xlsx(d, out / "planilla_paneles.xlsx", car, fecha)
    (out / "hojas").mkdir(exist_ok=True)
    total = 3 + len(d.muros) + len(d.techos)

    with PdfPages(out / "hojas_taller.pdf") as pdf:
        fig = hoja_caratula(d, car, fecha, f"Hoja 1 de {total}")
        fig.savefig(out / "caratula.pdf")
        pdf.savefig(fig)
        plt.close(fig)
        fig = plano_nomenclatura(d, fecha, f"Hoja 2 de {total}")
        fig.savefig(out / "plano_nomenclatura.pdf")
        fig.savefig(out / "plano_nomenclatura.png", dpi=110)
        pdf.savefig(fig)
        plt.close(fig)
        fig = hoja_carga(d, fecha, car.esquina, car.parrillas == "si", f"Hoja 3 de {total}")
        fig.savefig(out / "secuencia_carga_camion.pdf")
        pdf.savefig(fig)
        plt.close(fig)
        n = 3
        for p in d.muros:
            n += 1
            fig = hoja_muro(d, p, fecha, f"Hoja {n} de {total}")
            fig.savefig(out / "hojas" / f"{p.codigo}.pdf")
            pdf.savefig(fig)
            plt.close(fig)
        for t in d.techos:
            n += 1
            fig = hoja_techo(d, t, fecha, f"Hoja {n} de {total}")
            fig.savefig(out / "hojas" / f"{t.codigo}.pdf")
            pdf.savefig(fig)
            plt.close(fig)
    res.archivos += ["hojas_taller.pdf", "caratula.pdf", "hojas/*.pdf", "plano_nomenclatura.pdf",
                     "plano_nomenclatura.png", "secuencia_carga_camion.pdf", "planilla_paneles.xlsx"]
    log(f"Listo. {total} hojas en: {out}")
    return res
