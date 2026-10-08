"""Axonometrías esquemáticas del módulo (para la carátula)."""
from __future__ import annotations

import math

from matplotlib.patches import Circle, FancyArrowPatch, Polygon

from . import config as C
from .dibujo import AJUSTE, AMBAR, AZUL, GRIS, NEGRO, ROJO, VERDE
from .contorno import punto_interior
from .modelo import Despiece

C30, S30 = math.cos(math.radians(30)), math.sin(math.radians(30))
INTERIOR = "#fafafa"
OSB_EXT = "#ffffff"
TAPA_SUP = "#cfcfcf"


def _proy(x, y, z):
    """Isométrica con la cámara al sudeste: C queda a la izquierda y B a la derecha."""
    return ((x + y) * C30, (y - x) * S30 + z)


def _ajustar(puntos, caja):
    """Devuelve una función (x, y, z) -> papel (mm) que encuadra `puntos` en `caja`."""
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    x, y, w, h = caja
    k = min(w / (bx1 - bx0), h / (by1 - by0))
    ox = x + (w - (bx1 - bx0) * k) / 2 - bx0 * k
    oy = y + (h - (by1 - by0) * k) / 2 - by0 * k

    def f(px, py, pz):
        sx, sy = _proy(px, py, pz)
        return (ox + sx * k, oy + sy * k)
    f.k = k
    return f


def _poly(ax, f, pts3, fc, ec=NEGRO, lw=0.35, z=2, **kw):
    ax.add_patch(Polygon([f(*p) for p in pts3], closed=True, fc=fc, ec=ec, lw=lw, zorder=z, **kw))


def _lado_de_vano(d: Despiece, vano_id: str):
    for p in d.muros:
        if any(v.vano_id == vano_id for v in p.vanos):
            return p.lado
    return None


def _marca_lado(ax, f, d, x, y, lado, r=3.4, z=0.0, zorder=9):
    X, Y = f(x, y, z)
    ax.add_patch(Circle((X, Y), r, fc="white", ec=NEGRO, lw=0.7, zorder=zorder))
    ax.text(X, Y, lado, ha="center", va="center", fontsize=8, fontweight="bold", zorder=zorder + 1)


def _contorno(d: Despiece):
    m = d.plano.modulo
    return [(x - m.x0, y - m.y0) for x, y in (d.plano.contorno or
            [(m.x0, m.y0), (m.x1, m.y0), (m.x1, m.y1), (m.x0, m.y1)])]


def _puntos_muros(d: Despiece):
    m = d.plano.modulo
    W, H = m.ancho_x, m.alto_y
    pts = [_proy(0, 0, 0), _proy(W + 0.7, 0, 0), _proy(0, H + 0.7, C.ALTO_PANEL + 0.9)]
    for p in d.muros:
        r = p.rect
        for (x, y) in ((r.x0 - m.x0, r.y0 - m.y0), (r.x1 - m.x0, r.y1 - m.y0),
                       (r.x0 - m.x0, r.y1 - m.y0), (r.x1 - m.x0, r.y0 - m.y0)):
            pts += [_proy(x, y, 0), _proy(x, y, p.alto)]
    return pts


def _techo_z(d: Despiece, exagerar: float = 4.0):
    """Función de cota del techo (con la pendiente exagerada) y elevación que lo deja por encima de los muros."""
    m = d.plano.modulo
    W, H = m.ancho_x, m.alto_y
    caida = d.plano.caida_hacia or "A"
    alto, bajo = C.ALTO_PANEL, C.ALTO_PANEL_BAJO

    def zt(x, y):
        t = {"A": y / H, "C": 1 - y / H, "B": x / W, "D": 1 - x / W}[caida]
        return alto - t * (alto - bajo) * exagerar

    cont = _contorno(d)
    sy_muros = max(_proy(x, y, C.ALTO_PANEL)[1] for x, y in cont)
    sy_techo = min(_proy(x, y, zt(x, y))[1] for x, y in cont)
    lift = sy_muros - sy_techo + 0.35          # el techo flota justo por encima de lo más alto de los muros
    return zt, lift


def _puntos_techo(d: Despiece):
    zt, lift = _techo_z(d)
    pts = []
    for (x, y) in _contorno(d):
        pts += [_proy(x, y, zt(x, y) + lift + 0.15), _proy(x, y, 0)]
    return pts


def axo_muros(ax, d: Despiece, caja, f=None):
    """Muros sin techo: se ven por dentro los lados A y D y por fuera los lados B y C."""
    m = d.plano.modulo
    W, H = m.ancho_x, m.alto_y
    cont = _contorno(d)
    if f is None:
        f = _ajustar(_puntos_muros(d), caja)
    ax.add_patch(Polygon([f(x, y, 0) for x, y in cont], closed=True,
                         fc="#f7f7f7", ec=GRIS, lw=0.4, zorder=1))

    orden = sorted(d.muros, key=lambda p: (p.rect.centro[0] - m.x0) - (p.rect.centro[1] - m.y0))
    posicion = {p.codigo: i for i, p in enumerate(orden)}
    vanos = {v.id: v for v in d.plano.vanos}
    # Cada vano se dibuja justo después del último (más cercano) de los paneles que toca, así
    # los muros más cercanos a la cámara lo tapan como corresponde.
    vano_en = {}
    for p in d.muros:
        for vp in p.vanos:
            if vp.vano_id not in vano_en or posicion[p.codigo] > posicion[vano_en[vp.vano_id].codigo]:
                vano_en[vp.vano_id] = p

    for i, p in enumerate(orden):
        zb = 3 + i * 0.1
        r = p.rect
        x0, y0, x1, y1 = r.x0 - m.x0, r.y0 - m.y0, r.x1 - m.x0, r.y1 - m.y0
        h = p.alto
        ext = p.dir in ("B", "C") and p.lado != "I"
        cara = (AJUSTE if p.es_ajuste else (AMBAR if p.smart else OSB_EXT)) if ext else INTERIOR
        sur = [(x0, y0, 0), (x1, y0, 0), (x1, y0, h), (x0, y0, h)]
        est = [(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, y0, h)]
        top = [(x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h)]
        # cara vista de este lado (A y D: interior; B y C: exterior)
        _poly(ax, f, sur, cara if p.dir in ("A", "C") else "#bdbdbd", z=zb)
        _poly(ax, f, est, cara if p.dir in ("B", "D") else "#bdbdbd", z=zb)
        _poly(ax, f, top, TAPA_SUP, z=zb)
        c = ((x0 + x1) / 2, y0, h * 0.5) if p.dir in ("A", "C") else (x1, (y0 + y1) / 2, h * 0.5)
        X, Y = f(*c)
        ax.text(X, Y, p.codigo, fontsize=5.4, ha="center", va="center", color=GRIS, zorder=zb + 0.02)

        for vid, q in vano_en.items():
            if q is not p:
                continue
            v = vanos[vid]
            if v.alto is None:
                continue
            rr = v.rect
            z0 = 0.0 if v.tipo in C.TIPOS_HASTA_PISO else v.antepecho
            z1 = v.antepecho + v.alto
            vx0, vy0, vx1, vy1 = rr.x0 - m.x0, rr.y0 - m.y0, rr.x1 - m.x0, rr.y1 - m.y0
            lado = p.dir
            if lado in ("A", "C"):
                yy = y0                       # cara que se ve de ese muro (A: interior; C: exterior)
                poly = [(vx0, yy, z0), (vx1, yy, z0), (vx1, yy, z1), (vx0, yy, z1)]
                cc = ((vx0 + vx1) / 2, yy, (z0 + z1) / 2)
            else:
                xx = x1                       # B: exterior; D: interior
                poly = [(xx, vy0, z0), (xx, vy1, z0), (xx, vy1, z1), (xx, vy0, z1)]
                cc = (xx, (vy0 + vy1) / 2, (z0 + z1) / 2)
            _poly(ax, f, poly, "white", ec=AZUL, lw=0.8, z=zb + 0.05)
            X, Y = f(*cc)
            ax.text(X, Y, v.id, fontsize=5.8, ha="center", va="center", color=AZUL,
                    fontweight="bold", zorder=zb + 0.06)


def axo_techo(ax, d: Despiece, caja, f=None, con_base=True):
    """Techo inclinado (pendiente exagerada) flotando sobre los muros, con las punteadas que bajan a sus aristas."""
    m = d.plano.modulo
    zt, lift = _techo_z(d)
    cont = _contorno(d)
    if f is None:
        f = _ajustar(_puntos_techo(d), caja)
    caida = d.plano.caida_hacia or "A"

    # Altura de los muros en cada vértice del contorno (los lados de la caída son más bajos)
    def tope(x, y):
        hs = []
        for l in d.plano.lados:
            for v in (l.ini, l.fin):
                if abs(v[0] - m.x0 - x) < 1e-6 and abs(v[1] - m.y0 - y) < 1e-6:
                    hs.append(C.ALTO_PANEL_BAJO if l.dir == caida else C.ALTO_PANEL)
        return max(hs) if hs else C.ALTO_PANEL

    esp = C.ESPESOR_PANEL
    for (x, y) in cont:
        a, b = f(x, y, tope(x, y)), f(x, y, zt(x, y) + lift - esp)
        ax.plot([a[0], b[0]], [a[1], b[1]], color=GRIS, lw=0.6, ls=(0, (3, 2)), zorder=12)

    for t in sorted(d.techos, key=lambda t: (t.rect.centro[0] - m.x0) - (t.rect.centro[1] - m.y0)):
        r = t.rect
        x0, y0, x1, y1 = r.x0 - m.x0, r.y0 - m.y0, r.x1 - m.x0, r.y1 - m.y0
        cs = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        sup = [(x, y, zt(x, y) + lift) for x, y in cs]
        inf = [(x, y, zt(x, y) + lift - esp) for x, y in cs]
        # cantos vistos (lado sur y lado este) con el espesor del panel
        _poly(ax, f, [inf[0], inf[1], sup[1], sup[0]], "#b0b0b0", z=20)
        _poly(ax, f, [inf[1], inf[2], sup[2], sup[1]], "#8f8f8f", z=20)
        _poly(ax, f, sup, AJUSTE if t.es_ajuste else "#f4f4f4", z=21)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        X, Y = f(cx, cy, zt(cx, cy) + lift)
        ax.text(X, Y, t.codigo, fontsize=6.4, ha="center", va="center", color=NEGRO, fontweight="bold", zorder=25)


def axo_modulo(ax, d: Despiece, caja):
    """Una sola axonometría: los muros abajo y el techo inclinado flotando encima."""
    f = _ajustar(_puntos_muros(d) + _puntos_techo(d), caja)
    axo_muros(ax, d, caja, f=f)
    axo_techo(ax, d, caja, f=f)
