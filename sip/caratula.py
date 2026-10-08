"""Datos de la carátula (los completa quien emite) y su hoja."""
from __future__ import annotations

from dataclasses import dataclass, asdict

from matplotlib.patches import Rectangle

from . import config as C
from .contorno import texto_caida
from .axo import axo_modulo
from .dibujo import (AJUSTE, AMBAR, AZUL, GRIS, NEGRO, ROJO, VERDE, PAG_H, PAG_W, pie_hoja,
                     logo_gris, poner_logo, nueva_hoja, mm)
from .logo_datos import logo_array
from .modelo import Despiece

MARCA = "HABITEC"

SUGERIDOS_INTERIOR = [
    "Placa de yeso (Durlock) sobre perfil de 35 mm",
    "Placa de yeso (Durlock) sobre perfil de 70 mm",
    "Placa de yeso (Durlock) sobre omega",
    "Placa de yeso pegada directo",
    "SIP visto hacia el interior",
    "Combinado según instalaciones (detallar)",
]
SUGERIDOS_CIELORRASO = SUGERIDOS_INTERIOR + ["Sin cielorraso (SIP visto)"]
SUGERIDOS_EXTERIOR = ["Smart panel", "WPC", "Chapa acanalada", "Otro (detallar)"]


@dataclass
class Caratula:
    interior: str = ""          # revestimiento interior de muros
    cielorraso: str = ""        # revestimiento interior de techo
    exterior: str = ""          # revestimiento exterior
    observaciones: str = ""
    revision: str = "00"
    piel_exterior: str = "smart"   # "smart" o "osb": la cara exterior de los paneles (cambia las hojas)
    esquina: str = "NO"            # esquina de arranque del montaje: letras de sus lados ("A-F") o NO/NE/SO/SE
    parrillas: str = "no"          # "si" si el camión lleva las parrillas de piso

    @classmethod
    def desde(cls, datos) -> "Caratula":
        if isinstance(datos, cls):
            return datos
        datos = datos or {}
        car = cls(**{k: str(datos.get(k, getattr(cls(), k)) or "") for k in asdict(cls())})
        car.piel_exterior = "osb" if car.piel_exterior.strip().lower().startswith("osb") else "smart"
        car.esquina = car.esquina.strip().upper() or "NO"
        car.parrillas = "si" if car.parrillas.strip().lower() in ("si", "sí", "true", "1") else "no"
        return car


def _envolver(txt: str, n: int) -> list[str]:
    out = []
    for parrafo in (txt or "").split("\n"):
        actual = ""
        for w in parrafo.split():
            if actual and len(actual) + 1 + len(w) > n:
                out.append(actual)
                actual = w
            else:
                actual = (actual + " " + w).strip()
        out.append(actual)
    return out


def hoja_caratula(d: Despiece, car: Caratula, fecha: str, pagina: str = ""):
    fig, ax = nueva_hoja()
    pl = d.plano
    pie_hoja(ax, fecha, pagina)        # la portada no lleva marco ni rótulo de lámina

    # Marca: logo (grises) y título
    im = logo_gris()
    alto_logo = 22.0
    ancho_logo = alto_logo * im.shape[1] / im.shape[0]
    poner_logo(ax, 12 + ancho_logo, PAG_H - 10, alto_logo)
    ax.text(12 + ancho_logo + 7, PAG_H - 19, pl.proyecto, fontsize=19, fontweight="bold", ha="left", va="center")
    ax.text(12 + ancho_logo + 7, PAG_H - 28, "Hojas de taller · Paneles SIP", fontsize=10.5, color=GRIS, ha="left", va="center")
    ax.plot([12, 180], [PAG_H - 36, PAG_H - 36], color=NEGRO, lw=0.8)

    osb = car.piel_exterior == "osb"

    axo_modulo(ax, d, (12, 14, 172, 154))

    # Columna de datos
    x0, y = 192.0, PAG_H - 14
    W = 97.0

    def titulo(txt, y):
        ax.text(x0, y, txt, fontsize=9.5, fontweight="bold", ha="left", va="top")
        ax.plot([x0, x0 + W], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
        return y - 8.6

    def fila(y, etiqueta, valor, color=NEGRO, ancho=40):
        ax.text(x0, y, etiqueta, fontsize=7.8, color=GRIS, ha="left", va="top")
        lineas = _envolver(valor, ancho)
        for ln in lineas:
            ax.text(x0 + 27, y, ln, fontsize=8.2, color=color, ha="left", va="top")
            y -= 4.5
        return y - (1.4 if len(lineas) == 1 else 0.6)

    y = titulo("PROYECTO", y)
    m = pl.modulo
    y = fila(y, "Proyecto", pl.proyecto)
    y = fila(y, "Módulo", f"{mm(m.ancho_x)} × {mm(m.alto_y)} mm (en planta" + (", contorno con escalones)" if len(pl.contorno) > 4 else ")"))
    y = fila(y, "Caída", f"hacia el lado {texto_caida(pl)}")
    y = fila(y, "Emisión", fecha)
    y = fila(y, "Revisión", car.revision or "00")
    y -= 3

    y = titulo("RESUMEN", y)
    est_m = [p for p in d.muros if not p.es_ajuste]
    aj_m = [p for p in d.muros if p.es_ajuste]
    est_t = [t for t in d.techos if not t.es_ajuste]
    aj_t = [t for t in d.techos if t.es_ajuste]
    n_tab = sum(1 for p in d.muros if p.lado == "I")
    y = fila(y, "Muros", f"{len(d.muros)} paneles ({len(est_m)} estándar, {len(aj_m)} de ajuste)"
                         + (f"; {n_tab} son tabiques interiores" if n_tab else ""))
    y = fila(y, "Cara ext.", "OSB (sin smart panel)" if osb else "Smart panel")
    y = fila(y, "Techo", f"{len(d.techos)} paneles ({len(est_t)} estándar, {len(aj_t)} de ajuste)")
    tipos = {}
    for v in pl.vanos:
        tipos[C.TIPOS_VANO.get(v.tipo, v.tipo)] = tipos.get(C.TIPOS_VANO.get(v.tipo, v.tipo), 0) + 1
    y = fila(y, "Vanos", ", ".join(f"{n} {t.lower()}" for t, n in tipos.items()) or "ninguno")
    y = fila(y, "Muro alto", f"{mm(C.ALTO_PANEL_BAJO)} mm en el lado de la caída; {mm(C.ALTO_PANEL)} mm en el resto")
    y = fila(y, "Espesor", f"{mm(C.ESPESOR_PANEL)} mm (" + ("OSB 9" if osb else "smart panel 9") + " + EPS 70 + OSB 9)")
    y -= 3

    y = titulo("REVESTIMIENTOS Y TERMINACIONES", y)
    for etq, val in (("Interior", car.interior), ("Cielorraso", car.cielorraso), ("Exterior", car.exterior)):
        if val.strip():
            y = fila(y, etq, val)
        else:
            y = fila(y, etq, "a definir", color=NEGRO)
    if car.observaciones.strip():
        y = fila(y, "Observ.", " ".join(car.observaciones.split())[:240])
    if d.alertas:
        y -= 3
        ax.text(x0, y, f"ALERTAS ({len(d.alertas)})", fontsize=9.5, fontweight="bold", ha="left", va="top", color="#d00000")
        ax.plot([x0, x0 + W], [y - 5.2, y - 5.2], color="#d00000", lw=0.6)
        y -= 8.6
        for a in d.alertas:
            for ln in _envolver("• " + a, 58):
                ax.text(x0, y, ln, fontsize=8, color="#d00000", ha="left", va="top")
                y -= 4.2
    return fig
