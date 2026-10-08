"""Contorno del módulo: polígono de lados horizontales y verticales (rectángulo, L, U, con escalones…).

Los lados se nombran A, B, C… en sentido horario empezando por el lado horizontal más alto
(en un rectángulo: A arriba, B derecha, C abajo, D izquierda). Cada lado tiene además una
«dirección» (A, B, C o D) según hacia dónde mira su cara exterior: A arriba, B derecha,
C abajo, D izquierda. La numeración de paneles y la vista interior dependen de esa dirección.
"""
from __future__ import annotations

import math

from . import config as C
from .modelo import Lado

LETRAS = "ABCDEFGHJKLMNPQRSTUVWXYZ"          # sin I: se reserva para los tabiques interiores


def _limpiar(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Quita vértices repetidos y los que quedan alineados entre sus vecinos."""
    out: list[tuple[float, float]] = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= 1e-6:
        out.pop()
    cambio = True
    while cambio and len(out) > 3:
        cambio = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            cruz = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(cruz) < 1e-9:
                out.pop(i)
                cambio = True
                break
    return out


def area_firmada(pts) -> float:
    s = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        s += x0 * y1 - x1 * y0
    return s / 2


def construir(pts_crudos: list[tuple[float, float]]) -> tuple[list[tuple[float, float]], list[Lado]]:
    """Devuelve (vértices en sentido horario, lados). Lanza ValueError si hay lados inclinados."""
    pts = _limpiar([(float(x), float(y)) for x, y in pts_crudos])
    if len(pts) < 4:
        raise ValueError("El contorno del módulo necesita al menos 4 vértices.")
    # Todos los lados deben ser horizontales o verticales
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if abs(a[0] - b[0]) > C.TOL and abs(a[1] - b[1]) > C.TOL:
            raise ValueError("El contorno del módulo tiene un lado inclinado: solo se admiten lados "
                             "horizontales y verticales (rectángulo, L, U, con escalones…).")
    # Alinea las coordenadas casi iguales (ruido de dibujo)
    n = len(pts)
    pts = [list(p) for p in pts]
    for i in range(n):
        j = (i + 1) % n
        if abs(pts[i][0] - pts[j][0]) <= C.TOL:
            pts[j][0] = pts[i][0]
        if abs(pts[i][1] - pts[j][1]) <= C.TOL:
            pts[j][1] = pts[i][1]
    pts = [tuple(p) for p in pts]
    if area_firmada(pts) > 0:                  # antihorario -> horario
        pts.reverse()
    n = len(pts)
    # Arranca en el lado horizontal más alto (el de más a la izquierda si hay varios)
    mejor, ini = None, 0
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if abs(a[1] - b[1]) <= C.TOL:
            clave = (-a[1], min(a[0], b[0]))
            if mejor is None or clave < mejor:
                mejor, ini = clave, i
    pts = pts[ini:] + pts[:ini]

    if n > len(LETRAS):
        raise ValueError("El contorno tiene demasiados lados.")
    lados: list[Lado] = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        c = pts[(i + 2) % n]
        if abs(a[1] - b[1]) <= C.TOL:                       # horizontal
            direccion = "A" if b[0] > a[0] else "C"         # horario: hacia +x mira arriba
            coord, lo, hi = a[1], min(a[0], b[0]), max(a[0], b[0])
        else:
            direccion = "B" if b[1] < a[1] else "D"         # horario: hacia -y mira a la derecha
            coord, lo, hi = a[0], min(a[1], b[1]), max(a[1], b[1])
        # vértice final: convexo si se gira a la derecha (cruz negativa) en un polígono horario
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        cruz_fin = v1[0] * v2[1] - v1[1] * v2[0]
        lados.append(Lado(letra=LETRAS[i], dir=direccion, coord=coord, lo=lo, hi=hi,
                          ini=a, fin=b, convexo_fin=cruz_fin < 0))
    for i, l in enumerate(lados):
        l.letra_prev = lados[i - 1].letra
        l.letra_sig = lados[(i + 1) % n].letra
        l.convexo_ini = lados[i - 1].convexo_fin
    return pts, lados


def extremos_esperados(l: Lado, lateral: bool, e: float) -> tuple[float, float]:
    """Intervalo (mín, máx) que deben cubrir los paneles de muro del lado, a lo largo del muro.

    El lateral (perpendicular a la caída) toma las esquinas: llega al vértice si es convexo y
    avanza el espesor del muro más allá si es entrante. El otro lado se retrae un espesor en las
    esquinas convexas y llega justo al vértice en las entrantes."""
    def ajuste(convexo: bool) -> float:
        if lateral:
            return 0.0 if convexo else e
        return -e if convexo else 0.0
    # extremos en coordenadas del plano (menor, mayor); según el sentido de recorrido
    hacia_mas = l.fin[0] > l.ini[0] if l.dir in ("A", "C") else l.fin[1] > l.ini[1]
    if hacia_mas:
        c_lo, c_hi = l.convexo_ini, l.convexo_fin
    else:
        c_lo, c_hi = l.convexo_fin, l.convexo_ini
    return l.lo - ajuste(c_lo), l.hi + ajuste(c_hi)


def punto_en_poligono(x: float, y: float, pts) -> bool:
    dentro = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                dentro = not dentro
    return dentro


def desplazar(lados: list[Lado], desp: dict[int, float]) -> list[tuple[float, float]]:
    """Polígono resultante de mover cada lado `i` hacia adentro la distancia desp[i] (negativa = hacia afuera)."""
    n = len(lados)
    pos = []
    for i, l in enumerate(lados):
        d = desp.get(i, 0.0)
        signo = {"A": -1, "B": -1, "C": 1, "D": 1}[l.dir]      # hacia adentro: A baja, B va a -x, C sube, D va a +x
        pos.append(l.coord + signo * d)
    pts = []
    for i in range(n):
        a, b = lados[i], lados[(i + 1) % n]
        # vértice entre a y b: x del vertical, y del horizontal
        if a.dir in ("A", "C"):
            pts.append((pos[(i + 1) % n], pos[i]))
        else:
            pts.append((pos[i], pos[(i + 1) % n]))
    return pts


def punto_interior(d) -> tuple[float, float]:
    """Un punto dentro del módulo, cerca del centro de la caja envolvente (para flechas y rótulos)."""
    m = d.plano.modulo
    cx, cy = (m.x0 + m.x1) / 2, (m.y0 + m.y1) / 2
    pts = d.plano.contorno
    if not pts or punto_en_poligono(cx, cy, pts):
        return cx, cy
    mejor = None
    for t in d.techos:
        px, py = t.rect.centro
        dist = math.hypot(px - cx, py - cy)
        if mejor is None or dist < mejor[0]:
            mejor = (dist, px, py)
    if mejor:
        return mejor[1], mejor[2]
    for p in d.muros:
        return p.rect.centro
    return cx, cy


def texto_caida(plano) -> str:
    """'A', 'C y E'… : los lados que miran hacia donde baja el techo."""
    if not plano.caida_hacia:
        return "—"
    ls = [l.letra for l in plano.lados if l.dir == plano.caida_hacia]
    if not ls:
        return plano.caida_hacia
    return ls[0] if len(ls) == 1 else ", ".join(ls[:-1]) + " y " + ls[-1]
