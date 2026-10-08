"""Secuencia de carga del camión.

Regla: en obra el camión se descarga formando una pila invertida, así que lo primero que se carga queda
arriba y se monta primero. El orden de carga es entonces el orden de montaje:
parrillas de piso (si van), muros desde la esquina de arranque, tabiques interiores y, al final, el techo
(se carga último, se descarga primero y se monta último).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .dibujo import GRIS, NEGRO, PAG_H, PAG_W, cuadro_titulo, mm, nueva_hoja
from .modelo import Despiece

ESQUINAS = {"NO": "arriba a la izquierda", "NE": "arriba a la derecha",
            "SO": "abajo a la izquierda", "SE": "abajo a la derecha"}   # solo compatibilidad: se prefiere "A-F"


@dataclass
class Item:
    grupo: str            # título del grupo: "PARRILLAS DE PISO", "ESQUINA DE ARRANQUE A-F", "PANELES A", ...
    codigo: str
    medidas: str
    detalle: str


def _centro_esquina(d: Despiece, esquina: str):
    m = d.plano.modulo
    return {"NO": (m.x0, m.y1), "NE": (m.x1, m.y1), "SO": (m.x0, m.y0), "SE": (m.x1, m.y0)}[esquina]


def _vertices_convexos(d: Despiece):
    return [l.ini for l in d.plano.lados if l.convexo_ini]


def lados_de_la_esquina(d: Despiece, v) -> tuple[str, str]:
    """(lado que llega, lado que sale) en sentido horario en el vértice v."""
    llega = next(l.letra for l in d.plano.lados if math.hypot(l.fin[0] - v[0], l.fin[1] - v[1]) < 1e-6)
    sale = next(l.letra for l in d.plano.lados if math.hypot(l.ini[0] - v[0], l.ini[1] - v[1]) < 1e-6)
    return llega, sale


def nombre_esquina(d: Despiece, v) -> str:
    """Nombre de la esquina por las letras de sus dos lados, en orden alfabético (A-F, A-B, B-C...)."""
    return "-".join(sorted(lados_de_la_esquina(d, v)))


def esquinas_disponibles(d: Despiece) -> list[str]:
    """Esquinas convexas del contorno, nombradas por sus lados, ordenadas."""
    return sorted({nombre_esquina(d, v) for v in _vertices_convexos(d)})


def vertice_arranque(d: Despiece, esquina: str):
    """Vértice de arranque: por letras ("A-F") o, por compatibilidad, NO/NE/SO/SE (el convexo más cercano)."""
    esquina = (esquina or "").strip().upper()
    for v in _vertices_convexos(d):
        if nombre_esquina(d, v) == esquina:
            return v
    if esquina not in ESQUINAS:
        esquina = "NO"
    cx, cy = _centro_esquina(d, esquina)
    return min(_vertices_convexos(d), key=lambda v: math.hypot(v[0] - cx, v[1] - cy))


def secuencia(d: Despiece, esquina: str = "NO", parrillas: bool = False) -> tuple[list[Item], tuple]:
    v0 = vertice_arranque(d, esquina)
    llega0, sale0 = lados_de_la_esquina(d, v0)
    nombre = nombre_esquina(d, v0)
    lados = {l.letra: l for l in d.plano.lados}
    # posición de cada lado a lo largo del perímetro, en sentido horario
    acum, s = {}, 0.0
    for l in d.plano.lados:
        acum[l.letra] = s
        s += math.hypot(l.fin[0] - l.ini[0], l.fin[1] - l.ini[1])
    perim = s or 1.0
    s0 = next(acum[l.letra] for l in d.plano.lados if math.hypot(l.ini[0] - v0[0], l.ini[1] - v0[1]) < 1e-6)

    def pos(p):
        l = lados[p.lado]
        cx, cy = p.rect.centro
        a = abs(cx - l.ini[0]) if l.dir in ("A", "C") else abs(cy - l.ini[1])
        return (acum[l.letra] + a - s0) % perim

    muros = sorted((p for p in d.muros if p.lado != "I"), key=pos)
    items: list[Item] = []
    # primero los lados completos que forman la esquina (el que sale y el que llega), después el resto en sentido horario
    letras = [l.letra for l in d.plano.lados]
    i0 = letras.index(sale0)
    horario = letras[i0:] + letras[:i0]
    par = sorted((sale0, llega0))          # el par de la esquina, en el orden de su nombre (A-B: primero A, después B)
    lados_orden = par + [x for x in horario if x not in par]
    orden = []
    for lt in lados_orden:
        ps = [p for p in muros if p.lado == lt]
        if lt == llega0:
            ps.sort(key=pos, reverse=True)        # desde la esquina hacia afuera
        elif lt == sale0:
            ps.sort(key=pos)
        orden += [(f"PANELES {lt}", p) for p in ps]
    if parrillas:
        m = d.plano.modulo
        items.append(Item("PARRILLAS DE PISO", "Parrilla de piso", f"{mm(m.ancho_x)}×{mm(m.alto_y)}", "módulo completo"))

    def det_muro(p):
        o = []
        if p.es_ajuste:
            o.append("ajuste")
        if p.vanos:
            o.append(",".join(v.vano_id for v in p.vanos))
        return " · ".join(o)

    for g, p in orden:
        items.append(Item(g, p.codigo, f"{mm(p.largo)}×{mm(p.alto)}", det_muro(p)))
    for p in sorted((p for p in d.muros if p.lado == "I"), key=lambda p: p.codigo):
        items.append(Item("TABIQUES INTERIORES", p.codigo, f"{mm(p.largo)}×{mm(p.alto)}", det_muro(p)))
    def dist(t):
        cx, cy = t.rect.centro
        return (math.hypot(cx - v0[0], cy - v0[1]), t.codigo)
    for t in sorted(d.techos, key=dist):
        items.append(Item("TECHO", t.codigo, f"{mm(t.ancho)}×{mm(t.largo)}", "ajuste" if t.es_ajuste else ""))
    return items, v0


def hoja_carga(d: Despiece, fecha: str, esquina: str = "NO", parrillas: bool = False, pagina: str = ""):
    fig, ax = nueva_hoja()
    items, v0 = secuencia(d, esquina, parrillas)
    nombre = nombre_esquina(d, v0)
    llega0, sale0 = lados_de_la_esquina(d, v0)
    cuadro_titulo(ax, d.plano.proyecto, "CARGA", "", None, fecha, pagina)
    ax.text(12, PAG_H - 41, "Secuencia de carga del camión", fontsize=12, fontweight="bold", ha="left", va="top")
    nota = (f"Esquina de arranque del montaje: {nombre}: primero todo el lado {min(sale0, llega0)} y todo el lado {max(sale0, llega0)}; después el resto de los lados en sentido horario.\n"
            "El orden de carga es el orden de montaje: en obra se descarga en pila invertida, así que lo primero que se carga\n"
            "queda arriba y se monta primero. El techo se carga último, se descarga primero y se monta último.")
    ax.text(12, PAG_H - 48, nota, fontsize=8, color=GRIS, ha="left", va="top", linespacing=1.4)

    lineas, ult = [], None
    for n, it in enumerate(items, start=1):
        if it.grupo != ult:
            lineas.append(("grupo", it.grupo))
            ult = it.grupo
        lineas.append(("fila", n, it))
    mitad = (len(lineas) + 1) // 2
    # que un título de grupo no quede solo al final de la primera columna
    if lineas and mitad < len(lineas) and lineas[mitad - 1][0] == "grupo":
        mitad -= 1
    cols = [lineas[:mitad], lineas[mitad:]]
    paso, y0 = 5.2, PAG_H - 68
    for c, col in enumerate(cols):
        x = 12 + c * 140
        ax.text(x, y0 + 1, "N°", fontsize=7.5, color=GRIS, ha="left", va="bottom")
        ax.text(x + 11, y0 + 1, "Código", fontsize=7.5, color=GRIS, ha="left", va="bottom")
        ax.text(x + 40, y0 + 1, "Medidas (mm)", fontsize=7.5, color=GRIS, ha="left", va="bottom")
        ax.text(x + 80, y0 + 1, "Observaciones", fontsize=7.5, color=GRIS, ha="left", va="bottom")
        ax.plot([x, x + 130], [y0, y0], color=NEGRO, lw=0.6)
        y = y0 - 5.5
        for l in col:
            if l[0] == "grupo":
                y -= 1.5
                ax.text(x, y, l[1], fontsize=8.5, fontweight="bold", ha="left", va="center")
                y -= paso
            else:
                _, n, it = l
                ax.text(x, y, f"{n}", fontsize=8.5, ha="left", va="center", family="DejaVu Sans Mono")
                ax.text(x + 11, y, it.codigo, fontsize=8.5, ha="left", va="center", fontweight="bold")
                ax.text(x + 40, y, it.medidas, fontsize=8.5, ha="left", va="center")
                ax.text(x + 80, y, it.detalle, fontsize=8.5, ha="left", va="center")
                y -= paso
    return fig
