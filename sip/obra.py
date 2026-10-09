"""Láminas de obra in situ (posteriores al montaje): A3 apaisado, blanco y negro, a escala.

Para que el equipo de obra sepa dónde va cada revestimiento interior, cada tabique, cada boca eléctrica
y cada artefacto sanitario. Salen del mismo DXF que la lámina gráfica:

* Planta 1 · Revestimientos interiores y tabiques: códigos de revestimiento por tramo y, por cada muro,
  una cadena sobre la cara interior del SIP (esquinas, cambios de revestimiento, caras de tabiques).
  Cada tabique con su largo y, si no toca ningún muro, su distancia a la cara más cercana.
* Planta 2 · Instalaciones: bocas (bloques ELEC_* con su ALTURA), tablero, cañerías (capas ELEC_CANERIA y
  ELEC_CANERIA_VISTA, solo dibujadas) y ejes de artefactos (capa SAN_EJE). Cajas y ejes acotados a eje
  desde la cara más cercana del SIP o del tabique.
* Vistas interiores: una por cara de muro y de tabique, con revestimientos, tabiques que llegan, vanos,
  bocas y ejes; cotas acumuladas desde el extremo izquierdo y alturas desde el piso.

Las cotas van al revestimiento terminado (al SIP o al tabique donde no hay revestimiento). Medidas en metros.
Las vistas muestran la pendiente del techo: altura libre C.ALTO_INTERIOR_ALTO junto al muro alto y
C.ALTO_PANEL_BAJO junto al de la caída.
"""
from __future__ import annotations

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, PathPatch, Polygon as MPoly, Rectangle
from matplotlib.path import Path
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from . import config as C
from .dibujo import GRIS, GUIA, NEGRO, logo_gris
from .lamina import CONFIG_BASE, DIRS, ESP_SIP, Modelo, _superponer
from .modelo import Plano

W, H = 420.0, 297.0                       # A3 apaisado (mm)
M = 6.0                                   # margen del marco
BANDA = 24.0                              # rótulo superior
Z_X0, Z_X1 = 14.0, W - 14.0               # zona de dibujo
Z_Y0, Z_Y1 = 13.0, H - M - BANDA - 4.0
COL = 100.0                               # columna de referencias a la derecha de las plantas

GRIS_SIP = "#b8b8b8"
GRIS_SIP_CLARO = "#e2e2e2"
GRIS_LINEA = "#8a8a8a"
TR_EMBUTIDA = (0, (3.0, 1.6))
ROJO = "#d0101a"                          # todo lo de electricidad (bocas, cañerías y sus cotas)
GUIA_ROJA = dict(GUIA, color="#e8868b")
TR_EJE = (0, (6, 1.5, 1, 1.5))
NOMBRE_DIR = {v: k for k, v in DIRS.items()}
ESCALAS_PLANTA = (20, 25, 50, 75, 100, 150, 200)
ESCALAS_VISTA = (25, 50, 75, 100)


def _f(v):
    return f"{v:.2f}".replace(".", ",")


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _mas(a, v, t=1.0):
    return (a[0] + v[0] * t, a[1] + v[1] * t)


# --------------------------------------------------------------------------------------------
# Hoja
def _hoja(subtitulo, proyecto, fecha, pagina, escala, pie=""):
    fig = plt.figure(figsize=(W / 25.4, H / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.add_patch(Rectangle((M, M), W - 2 * M, H - 2 * M, fill=False, ec=NEGRO, lw=1.0))
    ax.add_patch(Rectangle((M, H - M - BANDA), W - 2 * M, BANDA, fill=False, ec=NEGRO, lw=0.8))
    ax.text(M + 5, H - M - 8.5, "OBRA IN SITU", fontsize=20, fontweight="bold", va="center", ha="left", color=NEGRO)
    ax.text(M + 5, H - M - 18.5, f"{subtitulo}   ·   Proyecto: {proyecto}", fontsize=10.5, va="center", ha="left",
            color=NEGRO)
    try:
        im = logo_gris()
        alto = 17.0
        ancho = alto * im.shape[1] / im.shape[0]
        ax.imshow(im, extent=(W - M - 4 - ancho, W - M - 4, H - M - 3.5 - alto, H - M - 3.5), aspect="auto", zorder=3)
    except Exception:                                        # noqa: BLE001
        ancho = 30.0
        ax.text(W - M - 4, H - M - 12, "HABITEC", fontsize=14, fontweight="bold", ha="right", va="center")
    ax.text(W - M - 9 - ancho, H - M - 12, f"Emisión {fecha}", fontsize=9, va="center", ha="right", color=NEGRO)
    partes = [p for p in (f"Escala 1:{escala:g}" if escala else "", "Cotas en metros", pagina) if p]
    ax.text(W - M - 4, M + 4, "   ·   ".join(partes), fontsize=8, ha="right", va="center", color=GRIS)
    if pie:
        ax.text(M + 5, M + 4, pie, fontsize=7, ha="left", va="center", color=GRIS)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


class Lamina:
    """Modelo (m) -> papel (mm) a una escala dada."""

    def __init__(self, ax, esc, ox, oy, x0=0.0, y0=0.0):
        self.ax, self.esc, self.ox, self.oy, self.x0, self.y0 = ax, esc, ox, oy, x0, y0
        self.k = 1000.0 / esc

    def T(self, p):
        return (self.ox + (p[0] - self.x0) * self.k, self.oy + (p[1] - self.y0) * self.k)

    def poly(self, pts, z=2, **kw):
        kw.setdefault("ec", NEGRO)
        kw.setdefault("lw", 0.3)
        self.ax.add_patch(MPoly([self.T(p) for p in pts], closed=True, zorder=z, joinstyle="miter", **kw))

    def shp(self, g, z=2, **kw):
        kw.setdefault("ec", NEGRO)
        kw.setdefault("lw", 0.3)
        for geom in getattr(g, "geoms", [g]):
            if geom.is_empty or geom.geom_type != "Polygon":
                continue
            verts, codes = [], []
            for ring in [geom.exterior, *geom.interiors]:
                cs = [self.T(c) for c in ring.coords]
                verts += cs
                codes += [Path.MOVETO] + [Path.LINETO] * (len(cs) - 2) + [Path.CLOSEPOLY]
            self.ax.add_patch(PathPatch(Path(verts, codes), joinstyle="miter", zorder=z, **kw))

    def linea(self, pts, z=3, **kw):
        kw.setdefault("color", NEGRO)
        kw.setdefault("lw", 0.4)
        P = [self.T(p) for p in pts]
        self.ax.plot([q[0] for q in P], [q[1] for q in P], zorder=z, solid_capstyle="butt", **kw)


def _texto_rot(ax, x, y, s, ang, fs=6.5, **kw):
    """Texto girado con el ángulo de la línea, siempre legible (de abajo hacia arriba o de izquierda a derecha)."""
    a = math.degrees(ang)
    while a > 90.01:
        a -= 180
    while a <= -89.99:
        a += 180
    kw.setdefault("color", NEGRO)
    ax.text(x, y, s, fontsize=fs, rotation=a, rotation_mode="anchor", ha=kw.pop("ha", "center"),
            va=kw.pop("va", "bottom"), zorder=kw.pop("zorder", 12), **kw)
    return a


def _tick(ax, P, z=11, color=NEGRO):
    ax.plot([P[0] - 0.8, P[0] + 0.8], [P[1] - 0.8, P[1] + 0.8], color=color, lw=0.7, zorder=z)


def _cadena(ax, pts, out, d, textos, fs=6.5, color=NEGRO, desde=None):
    """Cadena de cotas: `pts` son puntos de papel alineados sobre la arista medida; la línea de cota va
    a `d` mm en la dirección `out` (versor de papel). `textos[k]` va entre pts[k] y pts[k+1]. Las líneas guía
    (de puntos) salen de `desde[k]` si se da (el elemento acotado), si no de pts[k]."""
    Q = [_mas(p, out, d) for p in pts]
    guia = GUIA_ROJA if color != NEGRO else GUIA
    for p, q in zip(desde or pts, Q):
        e = _mas(q, out, 1.2)
        ax.plot([p[0], e[0]], [p[1], e[1]], zorder=10, **guia)
    ax.plot([Q[0][0], Q[-1][0]], [Q[0][1], Q[-1][1]], color=color, lw=0.55, zorder=11)
    for q in Q:
        _tick(ax, q, color=color)
    alterna = 0
    for k in range(len(Q) - 1):
        a, b = Q[k], Q[k + 1]
        L = math.dist(a, b)
        if L < 1e-6:
            continue
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        a_ = math.radians(_angulo_legible(ang))
        arriba = (-math.sin(a_), math.cos(a_))                 # normal "arriba" del texto legible
        lejos = 1.0 if L >= len(textos[k]) * fs * 0.21 else 1.0 + 3.0 * (alterna % 2 + 1)
        if lejos > 1.0:
            alterna += 1
        m = ((a[0] + b[0]) / 2 + arriba[0] * lejos, (a[1] + b[1]) / 2 + arriba[1] * lejos)
        _texto_rot(ax, m[0], m[1], textos[k], ang, fs=fs, color=color)


def _angulo_legible(ang):
    a = math.degrees(ang)
    while a > 90.01:
        a -= 180
    while a <= -89.99:
        a += 180
    return a


def _cota_simple(ax, a, b, texto, fs=6.5, desp=None):
    """Cota entre dos puntos de papel, sobre la misma línea (sin desplazar); `desp` corre el texto."""
    ax.plot([a[0], b[0]], [a[1], b[1]], color=NEGRO, lw=0.5, zorder=11)
    _tick(ax, a)
    _tick(ax, b)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    a_ = math.radians(_angulo_legible(ang))
    arriba = (-math.sin(a_), math.cos(a_))
    m = ((a[0] + b[0]) / 2 + arriba[0] * 0.8, (a[1] + b[1]) / 2 + arriba[1] * 0.8)
    if desp:
        m = _mas(m, desp)
    _texto_rot(ax, m[0], m[1], texto, ang, fs=fs)


# --------------------------------------------------------------------------------------------
# Símbolos (papel, mm)
def simbolo(ax, tipo, x, y, r=1.6, z=14, color=ROJO):
    NEGRO = color                                            # noqa: N806 (los símbolos eléctricos van en rojo)
    kw = dict(color=NEGRO, lw=0.6, zorder=z + 1, solid_capstyle="butt")
    if tipo == "TABLERO":
        w, h = r * 1.5, r * 0.95
        ax.add_patch(Rectangle((x - w, y - h), 2 * w, 2 * h, fc="white", ec=NEGRO, lw=0.6, zorder=z))
        ax.add_patch(MPoly([(x - w, y - h), (x + w, y - h), (x - w, y + h)], closed=True, fc=NEGRO, lw=0, zorder=z + 1))
        return
    if tipo == "PASE":
        ax.add_patch(Rectangle((x - r, y - r), 2 * r, 2 * r, fc="white", ec=NEGRO, lw=0.6, zorder=z))
        ax.plot([x - r, x + r], [y - r, y + r], **kw)
        ax.plot([x - r, x + r], [y + r, y - r], **kw)
        return
    ax.add_patch(Circle((x, y), r, fc="white", ec=NEGRO, lw=0.6, zorder=z))
    if tipo == "CENTRO":
        q = r * 0.707
        ax.plot([x - q, x + q], [y - q, y + q], **kw)
        ax.plot([x - q, x + q], [y + q, y - q], **kw)
    elif tipo == "TOMA":
        for dx in (-0.45 * r, 0.45 * r):
            ax.plot([x + dx, x + dx], [y - 0.55 * r, y + 0.55 * r], **kw)
    elif tipo == "LLAVE":
        ax.add_patch(Circle((x, y), r * 0.3, fc=NEGRO, lw=0, zorder=z + 1))
    elif tipo == "APLIQUE":
        ax.plot([x - r, x + r], [y, y], **kw)
        ax.add_patch(MPoly([(x - r, y), (x + r, y), (x, y - r)], closed=True, fc=NEGRO, lw=0, zorder=z + 1))
    else:
        ax.add_patch(Circle((x, y), r * 0.3, fc="white", ec=NEGRO, lw=0.5, zorder=z + 1))


def simbolo_eje(ax, x, y, r=1.5, z=14):
    ax.add_patch(Circle((x, y), r, fc="white", ec=NEGRO, lw=0.6, zorder=z))
    ax.plot([x - 2 * r, x + 2 * r], [y, y], color=NEGRO, lw=0.5, zorder=z + 1)
    ax.plot([x, x], [y - 2 * r, y + 2 * r], color=NEGRO, lw=0.5, zorder=z + 1)


# --------------------------------------------------------------------------------------------
# Datos
def _tiras(rects):
    """Une los rectángulos que se tocan y siguen siendo un rectángulo (paneles alineados de un tabique);
    un tabique en L queda como dos tiras."""
    rs = list(rects)
    cambio = True
    while cambio:
        cambio = False
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                if rs[i].distance(rs[j]) > 1e-3:
                    continue
                u = unary_union([rs[i], rs[j]])
                if u.geom_type == "Polygon" and abs(u.area - u.envelope.area) < 1e-6:
                    rs[i] = u.envelope
                    del rs[j]
                    cambio = True
                    break
            if cambio:
                break
    return rs


class Obra:
    """Geometría para las láminas de obra: tabiques, caras, revestimientos, bocas y ejes."""

    def __init__(self, plano: Plano, cfg: dict):
        self.plano = plano
        self.mo = mo = Modelo(plano, cfg)
        self.avisos = list(mo.avisos)
        # tabiques (SIP y durlock), en tiras rectas y en orden de lectura
        borde = mo.contorno.exterior
        sip = [box(r.x0, r.y0, r.x1, r.y1) for r in plano.paneles if borde.distance(Point(*r.centro)) > ESP_SIP * 0.75]
        dur = [box(r.x0, r.y0, r.x1, r.y1) for r in plano.tabiques_durlock]
        tabs = []
        for tipo, rects in (("SIP", sip), ("DURLOCK", dur)):
            for g in _tiras(rects):
                g = g.intersection(mo.cara_sip)
                if g.is_empty or g.area < 1e-4:
                    continue
                if g.geom_type != "Polygon":
                    g = max(g.geoms, key=lambda q: q.area)
                tabs.append({"tipo": tipo, "geom": g.simplify(1e-6)})
        tabs.sort(key=lambda t: (round(-t["geom"].centroid.y, 2), t["geom"].centroid.x))
        for n, t in enumerate(tabs, start=1):
            t["codigo"] = f"TB{n}"
            x0, y0, x1, y1 = t["geom"].bounds
            t["esp"] = min(x1 - x0, y1 - y0)
            t["largo"] = max(x1 - x0, y1 - y0)
        self.tabs = tabs
        self.libre = mo.cara_sip.difference(mo.tabiques)      # el aire del módulo (obra gruesa)
        self.libre_fin = mo.libre                             # el aire con los revestimientos puestos
        self.borde = self.libre_fin.boundary                  # las cotas van al revestimiento terminado
        # códigos de revestimiento: R1, R2… en el orden de la tabla de materiales; el OSB visto no lleva
        usados = []
        for m in mo.muros:
            usados += [mat for mat, _, _ in m.int_]
        self.rev_tab = self._revestimientos_tabiques()
        usados += [mat for mat, _, _ in self.rev_tab]
        orden = list(mo.mats)
        self.codigos = {}
        for mat in sorted(set(usados), key=orden.index):
            if mat != "sip" and mo.mats[mat].get("espesor", 0) >= 0:
                self.codigos[mat] = f"R{len(self.codigos) + 1}"
        self.caras = self._caras()
        self.bocas = self._bocas()
        self.ejes = self._ejes()
        for c in self.caras:
            self._a_terminado(c)

    def z_interior(self, p):
        """Altura libre bajo el techo: ALTO_INTERIOR_ALTO junto al muro alto y ALTO_PANEL_BAJO junto al de la caída."""
        alto, bajo = C.ALTO_INTERIOR_ALTO, C.ALTO_PANEL_BAJO
        c = self.mo.caida
        if c is None:
            return alto
        pr = [_dot(q, c) for q in self.mo.cara_sip.exterior.coords]
        lo, hi = min(pr), max(pr)
        t = (_dot(p, c) - lo) / (hi - lo) if hi > lo else 0.0
        return alto - (alto - bajo) * min(1.0, max(0.0, t))

    def esp_en(self, c, u):
        """Espesor del revestimiento de la cara c en la posición u."""
        return max([self.mo.mats.get(m, {}).get("espesor", 0.0) for m, a, b in c["revs"] if a - 1e-6 <= u <= b + 1e-6]
                   or [0.0])

    def _a_terminado(self, c):
        """Pasa la cara al revestimiento terminado: se mide una línea apenas por delante de la cara terminada;
        sus extremos son las esquinas terminadas (nuevo origen de cotas) y sus cortes, los tabiques con su revestimiento."""
        d = max([self.mo.mats.get(m, {}).get("espesor", 0.0) for m, _, _ in c["revs"]] or [0.0]) + 0.004
        sonda = LineString([_mas(c["A"], c["nf"], d), _mas(c["B"], c["nf"], d)]).intersection(self.libre_fin)
        tramos = sorted((min(self.u(c, q) for q in g.coords), max(self.u(c, q) for q in g.coords))
                        for g in getattr(sonda, "geoms", [sonda])
                        if not g.is_empty and g.geom_type == "LineString" and g.length > 0.005)
        if not tramos:
            return
        f0, f1 = tramos[0][0], tramos[-1][1]
        for t in c["tabs"]:                                  # cada tabique, con el ancho del hueco que deja
            for (a0, a1), (b0, _) in zip(tramos, tramos[1:]):
                if a1 - 0.03 <= t["a"] <= b0 + 0.03 or a1 - 0.03 <= t["b"] <= b0 + 0.03:
                    t["a"], t["b"] = a1, b0
                    break
        L = f1 - f0
        c["A"] = _mas(c["A"], c["r"], f0)
        c["B"] = _mas(c["A"], c["r"], L)
        c["L"] = L
        c["tramos"] = [(a - f0, b - f0) for a, b in tramos]
        c["revs"] = [(m, max(0.0, a - f0), min(L, b - f0)) for m, a, b in c["revs"] if min(L, b - f0) - max(0.0, a - f0) > 0.005]
        if c["revs"]:
            m0, _, b0 = c["revs"][0]
            c["revs"][0] = (m0, 0.0, b0)
            m1, a1, _ = c["revs"][-1]
            c["revs"][-1] = (m1, a1, L)
        c["tabs"] = [dict(t, a=t["a"] - f0, b=t["b"] - f0) for t in c["tabs"]]
        # un cambio de revestimiento que cae contra un tabique se cuenta en la cara terminada del tabique
        def ajustar(v):
            for t in c["tabs"]:
                if t["a"] - 0.02 <= v <= t["b"] + 0.02:
                    return t["a"] if v < (t["a"] + t["b"]) / 2 else t["b"]
            return v
        c["revs"] = [(m, ajustar(a), ajustar(b)) for m, a, b in c["revs"]]
        c["vanos"] = [dict(v, a=v["a"] - f0, b=v["b"] - f0) for v in c["vanos"]]
        for it in c["bocas"] + c["ejes"]:
            it["u"] = min(L, max(0.0, it["u"] - f0))
        c["z0"], c["z1"] = self.z_interior(c["A"]), self.z_interior(c["B"])

    def tramo(self, p, d, largo=60.0):
        """Desde p en la dirección d: (primer punto, último punto) del aire terminado que se cruza primero.
        Desde adentro de un tabique, son sus dos caras terminadas: la propia y la de enfrente."""
        g = LineString([p, _mas(p, d, largo)]).intersection(self.libre_fin)
        segs = [gg for gg in getattr(g, "geoms", [g]) if not gg.is_empty and gg.geom_type == "LineString"]
        if not segs:
            return None
        sg = min(segs, key=lambda q: min(math.dist(p, q.coords[0]), math.dist(p, q.coords[-1])))
        a, b = sorted([sg.coords[0], sg.coords[-1]], key=lambda q: math.dist(p, q))
        return a, b

    def cod_rev(self, mat):
        return "DL" if mat == "durlock" else self.codigos.get(mat, "OSB")

    def _revestimientos_tabiques(self):
        """[(mat, p0, p1)] de las líneas REV_INT_* que quedan sobre un tabique."""
        out = []
        for clave, p0, p1 in self.mo._sueltos:
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            if not self.mo.tabiques.is_empty and self.mo.tabiques.distance(Point(*mid)) <= 0.03:
                out.append((clave, p0, p1))
        return out

    def _caras(self):
        mo = self.mo
        caras = []
        for i, m in enumerate(mo.muros):
            A, B = mo.esq_ini(i, -ESP_SIP, -ESP_SIP), mo.esq_fin(i, -ESP_SIP, -ESP_SIP)
            nf = (-m.n[0], -m.n[1])                          # hacia el interior (hacia quien mira)
            r = (-nf[1], nf[0])                              # derecha de quien mira la cara
            if _dot(A, r) > _dot(B, r):
                A, B = B, A
            h = mo.altura_cara(i)
            caras.append({"nombre": f"MURO {m.letra}", "corto": m.letra, "A": A, "B": B, "r": r, "nf": nf,
                          "L": math.dist(A, B), "z0": h, "z1": h, "muro": i, "tab": None})
        for t in self.tabs:
            cs = list(t["geom"].exterior.coords)
            for p, q in zip(cs, cs[1:]):
                L = math.dist(p, q)
                if L < 0.25:
                    continue
                d = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
                if abs(d[0]) > 1e-3 and abs(d[1]) > 1e-3:
                    continue
                mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                nf = (round(-d[1]), round(d[0]))
                if t["geom"].contains(Point(*_mas(mid, nf, 0.01))):
                    nf = (-nf[0], -nf[1])
                # parte de la arista que da al aire (no contra un muro ni contra otro tabique)
                vis = LineString([_mas(p, nf, 0.01), _mas(q, nf, 0.01)]).intersection(self.libre)
                for sg in getattr(vis, "geoms", [vis]):
                    if sg.is_empty or sg.geom_type != "LineString" or sg.length < 0.25:
                        continue
                    a_, b_ = _mas(sg.coords[0], nf, -0.01), _mas(sg.coords[-1], nf, -0.01)
                    r = (-nf[1], nf[0])
                    A, B = (a_, b_) if _dot(a_, r) <= _dot(b_, r) else (b_, a_)
                    letra = NOMBRE_DIR.get(nf, "")
                    caras.append({"nombre": f"TABIQUE {t['codigo']} · CARA HACIA {letra}",
                                  "corto": f"{t['codigo']}-{letra}", "A": A, "B": B, "r": r, "nf": nf,
                                  "L": math.dist(A, B),
                                  "z0": C.ALTO_PANEL, "z1": C.ALTO_PANEL,
                                  "muro": None, "tab": t})
        # dos caras de un mismo tabique hacia el mismo lado (cortadas por otro tabique): se numeran
        vistos = {}
        for c in caras:
            if c["tab"] is None:
                continue
            vistos.setdefault(c["corto"], []).append(c)
        for lista in vistos.values():
            if len(lista) > 1:
                for n, c in enumerate(sorted(lista, key=lambda c: _dot(c["A"], c["r"])), start=1):
                    c["corto"] += str(n)
                    c["nombre"] += f" ({n})"
        for c in caras:
            c["revs"] = self._revs_cara(c)
            c["tabs"] = self._tabs_cara(c)
            c["vanos"] = self._vanos_cara(c)
            c["bocas"], c["ejes"] = [], []
        return caras

    @staticmethod
    def u(c, p):
        return _dot(_sub(p, c["A"]), c["r"])

    @staticmethod
    def dn(c, p):
        return _dot(_sub(p, c["A"]), c["nf"])

    def _revs_cara(self, c):
        L = c["L"]
        if c["muro"] is not None:
            m = self.mo.muros[c["muro"]]
            out = []
            for mat, a, b in m.int_:
                ua, ub = sorted([self.u(c, m.punto(a, -ESP_SIP)), self.u(c, m.punto(b, -ESP_SIP))])
                ua, ub = max(0.0, ua), min(L, ub)
                if ub - ua > 0.005:
                    out.append((mat, ua, ub))
            out.sort(key=lambda t: t[1])
            # los tramos se miden sobre el largo exterior del muro: cerca de una esquina, llegan hasta ella
            tol = ESP_SIP + 0.06
            out = [(mat, 0.0 if a <= tol else a, L if b >= L - tol else b) for mat, a, b in out]
            return [t for t in out if t[2] - t[1] > 0.005]
        tramos = [("sip" if c["tab"]["tipo"] == "SIP" else "durlock", 0.0, L)]
        for mat, p0, p1 in self.rev_tab:
            if abs(self.dn(c, p0)) > 0.03 or abs(self.dn(c, p1)) > 0.03:
                continue
            ua, ub = sorted([self.u(c, p0), self.u(c, p1)])
            ua, ub = max(0.0, ua), min(L, ub)
            if ub - ua > 0.01:
                tramos = _superponer(tramos, mat, ua, ub)
        return tramos

    def _tabs_cara(self, c):
        franja = LineString([c["A"], c["B"]]).buffer(0.02, cap_style=2)
        out = []
        for t in self.tabs:
            if t is c["tab"]:
                continue
            g = t["geom"].intersection(franja)
            if g.is_empty or g.area < 1e-5:
                continue
            us = [self.u(c, p) for p in (g.exterior.coords if g.geom_type == "Polygon" else
                                         [q for gg in g.geoms for q in gg.exterior.coords])]
            a, b = max(0.0, min(us)), min(c["L"], max(us))
            if b - a > 0.01:
                out.append({"t": t, "a": a, "b": b})
        return sorted(out, key=lambda x: x["a"])

    def _vanos_cara(self, c):
        out = []
        for it in self.mo.vanos:
            v = it["v"]
            if c["muro"] is not None:
                if it["muro"] != c["muro"]:
                    continue
                m = self.mo.muros[c["muro"]]
                a, b = sorted([self.u(c, m.punto(it["a"], -ESP_SIP)), self.u(c, m.punto(it["b"], -ESP_SIP))])
            else:
                if it["muro"] is not None or not it["rect"].intersects(c["tab"]["geom"].buffer(0.01)):
                    continue
                us = [self.u(c, p) for p in it["rect"].exterior.coords]
                a, b = min(us), max(us)
            a, b = max(0.0, a), min(c["L"], b)
            if b - a < 0.02:
                continue
            if v.tipo in C.TIPOS_HASTA_PISO:
                z0, z1 = 0.0, (v.alto or 2.0)
            else:
                z0 = v.antepecho
                z1 = z0 + (v.alto or 1.0)
            out.append({"v": v, "a": a, "b": b, "z0": z0, "z1": z1})
        return out

    def cara_de(self, p, lo, hi):
        """Cara más cercana a un punto (distancia normal entre lo y hi, positiva hacia el interior)."""
        mejor = None
        for c in self.caras:
            uu, dd = self.u(c, p), self.dn(c, p)
            if uu < -0.05 or uu > c["L"] + 0.05 or not (lo <= dd <= hi):
                continue
            if mejor is None or abs(dd) < mejor[0]:
                mejor = (abs(dd), c, uu)
        return mejor

    def _bocas(self):
        bocas = sorted(self.plano.bocas, key=lambda b: (round(-b.y, 2), b.x))
        cuenta, out = {}, []
        for b in bocas:
            pref = C.BOCAS.get(b.tipo, ("B", b.tipo.title(), None))[0]
            cuenta[pref] = cuenta.get(pref, 0) + 1
            unico = sum(1 for x in bocas if x.tipo == b.tipo) == 1
            cod = pref if (b.tipo == "TABLERO" and unico) else f"{pref}{cuenta[pref]}"
            item = {"b": b, "codigo": cod, "cara": None, "u": None}
            if b.tipo != "CENTRO":
                hit = self.cara_de((b.x, b.y), -0.20, 0.15)
                if hit:
                    item["cara"], item["u"] = hit[1], max(0.0, min(hit[1]["L"], hit[2]))
                    hit[1]["bocas"].append(item)
            out.append(item)
        sin = [i["codigo"] for i in out if i["cara"] is None and i["b"].tipo != "CENTRO"]
        if sin:
            self.avisos.append("Bocas que no quedan sobre ningún muro ni tabique (no salen en las vistas): " + ", ".join(sin) + ".")
        return out

    def _ejes(self):
        ejes = sorted(self.plano.ejes_sanitarios, key=lambda e: (round(-e.y, 2), e.x))
        out = []
        for n, e in enumerate(ejes, start=1):
            item = {"e": e, "codigo": f"S{n}", "cara": None, "u": None}
            hit = self.cara_de((e.x, e.y), -0.10, 0.90)
            if hit:
                item["cara"], item["u"] = hit[1], max(0.0, min(hit[1]["L"], hit[2]))
                hit[1]["ejes"].append(item)
            out.append(item)
        return out

    # rayos: distancia desde un punto hasta la cara más cercana (SIP o tabique) en una dirección
    def rayo(self, p, d, largo=60.0):
        g = LineString([p, _mas(p, d, largo)]).intersection(self.borde)
        pts = []
        for gg in getattr(g, "geoms", [g]):
            if gg.is_empty:
                continue
            pts += list(gg.coords)
        dists = [(math.dist(p, q), q) for q in pts if math.dist(p, q) > 1e-4]
        return min(dists) if dists else None


# --------------------------------------------------------------------------------------------
# Plantas
PRIMERA_FILA = 7.0                         # mm desde el módulo hasta la primera fila de cotas
PASO_FILA = 8.0                            # mm entre filas


class Filas:
    """Cotas por fuera del módulo: filas de cadenas en cada lado (A arriba, B derecha, C abajo, D izquierda).
    Cada fila junta puntos del modelo; se acotan proyectados sobre el lado, con líneas guía de puntos desde
    cada elemento."""

    def __init__(self, obra, inicio):
        self.obra, self.inicio = obra, inicio
        self.filas = {dl: [] for dl in DIRS}

    def agregar(self, dl, puntos, color=NEGRO):
        """Una fila con una sola cadena por todos los puntos."""
        r = (-DIRS[dl][1], DIRS[dl][0])
        if len({round(_dot(p, r), 3) for p in puntos}) >= 2:
            self.filas[dl].append(([puntos], color))

    def agregar_pares(self, dl, pares, color=NEGRO):
        """Cotas desde una cara de referencia hasta un eje: las que salen de la misma cara (hacia el mismo lado)
        forman una cadena; las cadenas que se pisan van a otra fila."""
        r = (-DIRS[dl][1], DIRS[dl][0])
        grupos = {}
        for item, ref in pares:
            ui, ur = _dot(item, r), _dot(ref, r)
            if abs(ui - ur) < 0.005:
                continue
            grupos.setdefault((round(ur, 3), ui > ur), [ref]).append(item)
        self.agregar_cadenas(dl, list(grupos.values()), color)

    def agregar_cadenas(self, dl, cadenas, color=NEGRO):
        """Varias cadenas independientes en un lado; las que se pisan van a otra fila."""
        r = (-DIRS[dl][1], DIRS[dl][0])
        cadenas = sorted((g for g in cadenas if len({round(_dot(q, r), 3) for q in g}) >= 2),
                         key=lambda g: min(_dot(q, r) for q in g))
        carriles = []
        for g in cadenas:
            a, b = min(_dot(q, r) for q in g), max(_dot(q, r) for q in g)
            for carril in carriles:
                if a >= carril["fin"] + 0.04:
                    carril["cadenas"].append(g)
                    carril["fin"] = b
                    break
            else:
                carriles.append({"fin": b, "cadenas": [g]})
        for carril in carriles:
            self.filas[dl].append((carril["cadenas"], color))

    def margenes(self):
        return {dl: (self.inicio + PASO_FILA * (len(f) - 1) + 6.0) if f else self.inicio - PRIMERA_FILA + 4.0
                for dl, f in self.filas.items()}

    def dibujar(self, lm):
        ext = list(self.obra.mo.cara_ext.exterior.coords)
        for dl, filas in self.filas.items():
            n = DIRS[dl]
            r = (-n[1], n[0])
            dmax = max(_dot(q, n) for q in ext)
            for i, (cadenas, color) in enumerate(filas):
                d = self.inicio + PASO_FILA * i
                for puntos in cadenas:
                    por_u = {}
                    for p in sorted(puntos, key=lambda p: -_dot(p, n)):      # la guía sale del más cercano al borde
                        u = round(_dot(p, r), 3)
                        if not any(abs(u - v) < 0.004 for v in por_u):
                            por_u[u] = p
                    us = sorted(por_u)
                    if len(us) < 2:
                        continue
                    base = [lm.T(_mas(_mas((0.0, 0.0), r, u), n, dmax)) for u in us]
                    _cadena(lm.ax, base, n, d, [_f(b - a) for a, b in zip(us, us[1:])], fs=6.0, color=color,
                            desde=[lm.T(por_u[u]) for u in us])


def _lienzo_planta(ax, obra, filas: Filas):
    ancho, alto = (Z_X1 - COL - 6) - Z_X0, Z_Y1 - Z_Y0
    m = filas.margenes()
    x0, y0, x1, y1 = obra.mo.cara_ext.bounds
    e = ESCALAS_PLANTA[-1]
    for esc in ESCALAS_PLANTA:                                 # la mayor escala que entra con sus cotas
        k = 1000.0 / esc
        if (x1 - x0) * k + m["B"] + m["D"] <= ancho and (y1 - y0) * k + m["A"] + m["C"] <= alto:
            e = esc
            break
    k = 1000.0 / e
    ox = Z_X0 + m["D"] + (ancho - (x1 - x0) * k - m["B"] - m["D"]) / 2
    oy = Z_Y0 + m["C"] + (alto - (y1 - y0) * k - m["A"] - m["C"]) / 2
    return Lamina(ax, e, ox, oy, x0, y0)


def _base_planta(lm: Lamina, obra: Obra, modo: int):
    mo = obra.mo
    fc_sip = GRIS_SIP if modo == 1 else GRIS_SIP_CLARO
    for i in range(len(mo.muros)):
        lm.poly(mo.banda(i, -ESP_SIP, 0.0), fc=fc_sip, lw=0.25, z=2)
    for q in mo.bandas_ext:
        lm.poly(q, fc="white", lw=0.25, z=2, ec=GRIS_LINEA)
    for q in mo.bandas_int:
        lm.poly(q, fc="white", lw=0.4 if modo == 1 else 0.25, z=2)
    for g in mo.bandas_tab:
        lm.shp(g, fc="white", lw=0.4 if modo == 1 else 0.25, z=4)
    lm.shp(mo.contorno, fc="none", lw=0.8, z=3)
    lm.shp(mo.cara_sip, fc="none", lw=0.5, z=3)
    for t in obra.tabs:
        if t["tipo"] == "SIP":
            lm.shp(t["geom"], fc=fc_sip, lw=0.5, z=4)
        else:
            lm.shp(t["geom"], fc="white", lw=0.5, z=4, hatch="////" if modo == 1 else None)
    # vanos: la abertura corta el muro
    for it in mo.vanos:
        if it["muro"] is not None:
            m = mo.muros[it["muro"]]
            a, b = it["a"], it["b"]
            oi = -(ESP_SIP + m.esp_max("INT"))
            oe = m.esp_max("EXT")
            lm.poly([m.punto(a, oi), m.punto(b, oi), m.punto(b, oe), m.punto(a, oe)], fc="white", ec="none", lw=0, z=5)
            lm.linea([m.punto(a, oi), m.punto(a, oe)], z=6, lw=0.5)
            lm.linea([m.punto(b, oi), m.punto(b, oe)], z=6, lw=0.5)
            if it["v"].tipo not in ("P",):
                lm.linea([m.punto(a, -ESP_SIP / 2), m.punto(b, -ESP_SIP / 2)], z=6, lw=0.3)
        else:
            lm.shp(it["rect"], fc="white", lw=0.4, z=5)
    for pts, cerrado in obra.plano.sanitarios:
        P = list(pts) + ([pts[0]] if cerrado else [])
        lm.linea(P, z=5, color=GRIS_LINEA, lw=0.35)


def _leyenda(ax, x, y, titulo, filas, ancho=COL - 4, fs=7.0, paso=4.2):
    ax.text(x, y, titulo, fontsize=8.5, fontweight="bold", ha="left", va="top", color=NEGRO)
    ax.plot([x, x + ancho], [y - 4.6, y - 4.6], color=NEGRO, lw=0.5)
    y -= 7.5
    for fila in filas:
        if callable(fila):
            fila(ax, x, y)
            y -= paso
            continue
        txt, color = fila if isinstance(fila, tuple) else (fila, NEGRO)
        n = int(ancho / (fs * 0.19))
        for k, ln in enumerate(_partir(txt, n)):
            ax.text(x, y, ln, fontsize=fs, ha="left", va="top", color=color)
            y -= paso
    return y - 3


def _partir(txt, n):
    out, actual = [], ""
    for w in txt.split(" "):
        if actual and len(actual) + 1 + len(w) > n:
            out.append(actual)
            actual = "   " + w
        else:
            actual = (actual + " " + w) if actual else w
    out.append(actual)
    return out


def planta_revestimientos(obra: Obra, fecha, pagina):
    mo = obra.mo
    fig, ax = _hoja("Planta 1 · Revestimientos interiores y tabiques", obra.plano.proyecto, fecha, pagina, None)
    # por fuera: 1ª fila, la cadena de cada muro; después, una cadena por tabique (sus caras terminadas y su
    # largo, desde la cara terminada más cercana): de través y a lo largo, en x abajo y en y a la izquierda
    filas = Filas(obra, PRIMERA_FILA + PASO_FILA)
    por_lado = {"C": [], "D": []}
    for t in obra.tabs:
        caras_t = [c for c in obra.caras if c["tab"] is t]
        if not caras_t:
            continue
        x0, y0, x1, y1 = t["geom"].bounds
        mid = ((x0 + x1) / 2, (y0 + y1) / 2)
        vertical = (x1 - x0) < (y1 - y0)
        a = (1, 0) if vertical else (0, 1)                   # de través
        e = (0, 1) if vertical else (1, 0)                   # a lo largo
        # de través: las dos caras terminadas y la cara más cercana enfrente
        traves = [_mas(_mas(c["A"], c["r"], c["L"] / 2), c["nf"], obra.esp_en(c, c["L"] / 2))
                  for c in caras_t if c["nf"] in (a, (-a[0], -a[1]))]
        trs = [tr for tr in (obra.tramo(mid, a), obra.tramo(mid, (-a[0], -a[1]))) if tr]
        if trs:
            traves.append(min(trs, key=lambda tr: math.dist(*tr))[1])
        # a lo largo: los extremos terminados y, si un extremo queda libre, la cara más cercana
        pr = sorted((q for c in caras_t for q in (c["A"], c["B"])), key=lambda q: _dot(q, e))
        largo = [pr[0], pr[-1]]
        libres = []
        for d_, ext in ((e, pr[-1]), ((-e[0], -e[1]), pr[0])):
            tr = obra.tramo(mid, d_)
            if tr and abs(_dot(tr[0], d_) - _dot(ext, d_)) < 0.03:
                libres.append(tr)
        if libres:
            largo.append(min(libres, key=lambda tr: math.dist(*tr))[1])
        por_lado["C" if vertical else "D"].append(traves)
        por_lado["D" if vertical else "C"].append(largo)
    for dl, cadenas in por_lado.items():
        filas.agregar_cadenas(dl, cadenas)
    lm = _lienzo_planta(ax, obra, filas)
    _base_planta(lm, obra, 1)
    k = lm.k
    # códigos de revestimiento sobre cada tramo de muro
    for c in obra.caras:
        if c["muro"] is None:
            continue
        m = mo.muros[c["muro"]]
        for mat, a, b in c["revs"]:
            piezas = [(a, b)]
            for t in c["tabs"]:                              # un rótulo por local: se corta en cada tabique
                piezas = [q for x0, x1 in piezas for q in ((x0, min(x1, t["a"])), (max(x0, t["b"]), x1))
                          if q[1] - q[0] > 1e-3]
            esp = mo.mats[mat].get("espesor", 0.0)
            for a2, b2 in piezas:
                if b2 - a2 < 0.25:
                    continue
                p = _mas(_mas(c["A"], c["r"], (a2 + b2) / 2), c["nf"], esp + 0.03)
                P = _mas(lm.T(p), c["nf"], 1.6)
                _texto_rot(ax, P[0], P[1], obra.cod_rev(mat), math.atan2(c["r"][1], c["r"][0]), fs=6.5,
                           va="bottom" if c["nf"][1] > 0 or c["nf"][0] < 0 else "top", fontweight="bold")
        # cadena sobre la cara interior del SIP, por fuera del muro
        us = {0.0, c["L"]}
        for _, a, b in c["revs"]:
            us |= {a, b}
        for t in c["tabs"]:
            us |= {t["a"], t["b"]}
        us = sorted(us)
        limpio = [us[0]]
        for v in us[1:]:
            if v - limpio[-1] > 0.004:
                limpio.append(v)
        pts = [lm.T(_mas(c["A"], c["r"], v)) for v in limpio]
        d = (ESP_SIP + m.esp_max("EXT")) * k + 7.0
        _cadena(ax, pts, (-c["nf"][0], -c["nf"][1]), d, [_f(b - a) for a, b in zip(limpio, limpio[1:])])
    # códigos de revestimiento sobre los tabiques
    for mat, p0, p1 in obra.rev_tab:
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        L = math.dist(p0, p1)
        if L < 0.15:
            continue
        d = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
        n = (-d[1], d[0])
        if not obra.libre.contains(Point(*_mas(mid, n, 0.05))):
            n = (-n[0], -n[1])
        P = _mas(lm.T(_mas(mid, n, mo.mats[mat].get("espesor", 0) + 0.02)), n, 1.4)
        _texto_rot(ax, P[0], P[1], obra.cod_rev(mat), math.atan2(d[1], d[0]), fs=6.5,
                   va="bottom" if n[1] > 0 or n[0] < 0 else "top", fontweight="bold")
    # tabiques: código (las cotas van por fuera)
    for t in obra.tabs:
        g = t["geom"]
        x0, y0, x1, y1 = g.bounds
        horiz = (x1 - x0) >= (y1 - y0)
        mid = ((x0 + x1) / 2, (y0 + y1) / 2)
        lados = [(0, 1), (0, -1)] if horiz else [(1, 0), (-1, 0)]
        eje = (1, 0) if horiz else (0, 1)

        def aire(s):                                         # el código va del lado con más lugar
            tr = obra.tramo(mid, s)
            return math.dist(*tr) if tr else 0.0
        s2 = min(lados, key=aire)
        caras_t = [c for c in obra.caras if c["tab"] is t]   # largo terminado: el de sus caras
        if caras_t:
            pr = [_dot(q, eje) for c in caras_t for q in (c["A"], c["B"])]
            t["largo_fin"] = max(pr) - min(pr)
        cuarto = (x0 + (x1 - x0) * 0.22, mid[1]) if horiz else (mid[0], y0 + (y1 - y0) * 0.22)
        P = _mas(lm.T(_mas(cuarto, s2, t["esp"] / 2)), s2, 3.0)
        ax.text(P[0], P[1], t["codigo"], fontsize=7.5, fontweight="bold", ha="center", va="center", zorder=13,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=NEGRO, lw=0.5))
    filas.dibujar(lm)
    # referencias
    x, y = Z_X1 - COL, Z_Y1
    filas = []
    for mat, cod in obra.codigos.items():
        mt = mo.mats[mat]
        esp = mt.get("espesor", 0.0)
        filas.append(f"{cod}  {mt.get('nombre', mat)} ({_f(esp * 100).replace(',00', '')} cm)")
    filas.append("OSB: OSB del SIP visto (sin revestimiento).")
    if any(t["tipo"] == "DURLOCK" for t in obra.tabs):
        filas.append("DL: placa del tabique de durlock, sin revestimiento agregado.")
    y = _leyenda(ax, x, y, "REVESTIMIENTOS INTERIORES", filas)
    filas = []
    for t in obra.tabs:
        tipo = "SIP" if t["tipo"] == "SIP" else "Durlock"
        esp_fin = t["esp"] + sum(max([obra.esp_en(c, u) for c in obra.caras if c["tab"] is t and c["nf"] == s_
                                      for u in (0.0, c["L"])] or [0.0]) for s_ in ((0, 1), (0, -1), (1, 0), (-1, 0)))
        filas.append(f"{t['codigo']}  {tipo} · espesor {_f(esp_fin)} terminado ({_f(t['esp'])} de obra) · "
                      f"largo {_f(t.get('largo_fin', t['largo']))}")
    if not filas:
        filas = ["Sin tabiques."]

    def muestra(fc, hatch):
        def f(ax, x, y):
            ax.add_patch(Rectangle((x, y - 2.6), 8, 2.6, fc=fc, ec=NEGRO, lw=0.4, hatch=hatch))
        return f
    y = _leyenda(ax, x, y, "TABIQUES", filas)
    sw = muestra(GRIS_SIP, None)
    sw(ax, x, y)
    ax.text(x + 11, y - 1.3, "SIP (muros y tabiques)", fontsize=7, va="center")
    y -= 5
    sw = muestra("white", "////")
    sw(ax, x, y)
    ax.text(x + 11, y - 1.3, "Tabique de durlock", fontsize=7, va="center")
    y -= 9
    _leyenda(ax, x, y, "NOTAS", [
        "Cotas al revestimiento terminado; donde no hay revestimiento, al SIP o a la placa del tabique.",
        "Por fuera de cada muro: cadena medida sobre su cara interior terminada (esquinas, cambios de "
        "revestimiento y caras terminadas de los tabiques que llegan).",
        "Más afuera, abajo y a la izquierda: una cadena por tabique, de través (sus caras terminadas) y a lo largo "
        "(sus extremos), desde la cara terminada más cercana. Todas las cotas van por fuera del dibujo, con líneas "
        "guía de puntos.",
        "El código de cada tramo va del lado del local. Ver alturas y bocas en las vistas interiores.",
    ])
    _escala_pie(ax, lm.esc)
    return fig


def _escala_pie(ax, esc):
    for t in ax.texts:
        if "Cotas en metros" in t.get_text():
            t.set_text(f"Escala 1:{esc:g}   ·   " + t.get_text())


def planta_instalaciones(obra: Obra, fecha, pagina):
    fig, ax = _hoja("Planta 2 · Instalaciones: electricidad y ejes sanitarios", obra.plano.proyecto, fecha, pagina,
                    None)
    # cotas por fuera: en cada lado, una fila de electricidad (roja) y otra de ejes sanitarios. Cada boca o eje
    # va al lado hacia el que mira su cara, con las esquinas terminadas de esa cara (y los tabiques que llegan);
    # las de techo y los ejes sueltos, en x abajo y en y a la izquierda, entre las caras más cercanas.
    filas = Filas(obra, PRIMERA_FILA)

    def lado_de(c):
        if c["nf"][1] != 0:
            return "A" if c["nf"][1] < 0 else "C"
        return "D" if c["nf"][0] > 0 else "B"

    def juntar(items, dest):
        for it in items:
            c = it["cara"]
            p = (it["b"].x, it["b"].y) if "b" in it else (it["e"].x, it["e"].y)
            if c is not None:
                # el eje y la cara terminada más cercana sobre su cara (esquina o tabique que llega)
                refs = [0.0, c["L"]] + [v for t in c["tabs"] for v in (t["a"], t["b"])]
                ref = min(refs, key=lambda v: abs(v - it["u"]))
                dest.setdefault(lado_de(c), []).append((_mas(c["A"], c["r"], it["u"]), _mas(c["A"], c["r"], ref)))
            else:
                for dl, d in (("C", (1, 0)), ("D", (0, 1))):     # techo: en x y en y, a la cara más cercana
                    ends = [tr[1] for tr in (obra.tramo(p, d), obra.tramo(p, (-d[0], -d[1]))) if tr]
                    if ends:
                        dest.setdefault(dl, []).append((p, min(ends, key=lambda q: math.dist(p, q))))
    elec, san = {}, {}
    juntar(obra.bocas, elec)
    juntar(obra.ejes, san)
    for dl in "ABCD":
        if dl in elec:
            filas.agregar_pares(dl, elec[dl], ROJO)
        if dl in san:
            filas.agregar_pares(dl, san[dl])
    lm = _lienzo_planta(ax, obra, filas)
    _base_planta(lm, obra, 2)
    # cañerías (solo dibujo, en rojo)
    for pts, vista in obra.plano.canerias:
        if vista:
            lm.linea(pts, z=8, lw=1.1, color=ROJO)
        else:
            lm.linea(pts, z=8, lw=0.6, ls=TR_EMBUTIDA, color=ROJO)

    def rotulo(P, nf, lineas, fs=6.0, color=NEGRO):
        ha = "left" if nf[0] > 0 else "right" if nf[0] < 0 else "center"
        va = "bottom" if nf[1] > 0 else "top" if nf[1] < 0 else "center"
        ax.text(P[0], P[1], "\n".join(lineas), fontsize=fs, fontweight="bold", ha=ha, va=va, zorder=13, color=color,
                linespacing=1.05, bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"))

    # bocas y ejes sobre una cara: símbolo junto a la cara terminada y rótulo hacia el local
    for c in obra.caras:
        nf = c["nf"]
        for it in c["bocas"]:
            b = it["b"]
            P = _mas(lm.T(_mas(c["A"], c["r"], it["u"])), nf, 2.4)
            simbolo(ax, b.tipo, P[0], P[1], r=1.4)
            alt = _f(b.altura) + ("*" if b.por_defecto else "")
            rotulo(_mas(P, nf, 3.0), nf, [it["codigo"], f"h {alt}"], color=ROJO)
        for it in c["ejes"]:
            e = it["e"]
            pie = _mas(c["A"], c["r"], it["u"])
            dd = max(Obra.dn(c, (e.x, e.y)), 0.0)
            lm.linea([pie, _mas(pie, nf, max(0.45, dd + 0.25))], z=9, lw=0.5, ls=TR_EJE)
            P = lm.T(_mas(pie, nf, dd))
            simbolo_eje(ax, P[0], P[1], r=1.3)
            Q = _mas(lm.T(_mas(pie, nf, max(0.45, dd + 0.25))), nf, 1.0)
            rotulo(Q, nf, [it["codigo"], e.artefacto])
    # bocas de techo y ejes sueltos
    for it in obra.bocas:
        b = it["b"]
        if it["cara"] is not None:
            continue
        P = lm.T((b.x, b.y))
        simbolo(ax, b.tipo, P[0], P[1])
        alt = "techo" if b.altura is None else _f(b.altura) + ("*" if b.por_defecto else "")
        ax.text(P[0] + 2.4, P[1] + 2.0, f"{it['codigo']} {alt}", fontsize=6.2, fontweight="bold", ha="left",
                va="bottom", zorder=13, color=ROJO, bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"))
    for it in obra.ejes:
        if it["cara"] is not None:
            continue
        e = it["e"]
        P = lm.T((e.x, e.y))
        simbolo_eje(ax, P[0], P[1])
        ax.text(P[0] + 3.0, P[1] - 3.0, f"{it['codigo']} {e.artefacto}", fontsize=6.2, fontweight="bold", ha="left",
                va="top", zorder=13, bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"))
    filas.dibujar(lm)
    # referencias
    x, y = Z_X1 - COL, Z_Y1

    def fila_sim(tipo, txt):
        def f(ax, x, y):
            simbolo(ax, tipo, x + 3, y - 1.5, r=1.5)
            ax.text(x + 8, y - 1.5, txt, fontsize=7, va="center", color=ROJO)
        return f
    filas = []
    tipos = []
    for it in obra.bocas:
        if it["b"].tipo not in tipos:
            tipos.append(it["b"].tipo)
    for tipo in sorted(tipos, key=lambda t: list(C.BOCAS).index(t) if t in C.BOCAS else 99):
        pref, nombre, defecto = C.BOCAS.get(tipo, ("B", tipo.title(), None))
        extra = "" if defecto is None else f" (h típica {_f(defecto)})"
        filas.append(fila_sim(tipo, f"{pref}  {nombre}{extra}"))

    def fila_lin(lw, ls, txt):
        def f(ax, x, y):
            ax.plot([x, x + 6], [y - 1.5, y - 1.5], color=ROJO, lw=lw, ls=ls)
            ax.text(x + 8, y - 1.5, txt, fontsize=7, va="center", color=ROJO)
        return f
    filas.append(fila_lin(0.6, TR_EMBUTIDA, "Cañería embutida (solo esquema)"))
    filas.append(fila_lin(1.1, "-", "Cañería vista sobre el módulo"))

    def fila_eje(ax, x, y):
        simbolo_eje(ax, x + 3, y - 1.5, r=1.2)
        ax.text(x + 8, y - 1.5, "S  Eje de artefacto sanitario", fontsize=7, va="center")
    filas.append(fila_eje)
    y = _leyenda(ax, x, y, "REFERENCIAS", filas, paso=5.0)
    filas = []
    for it in obra.bocas:
        b = it["b"]
        alt = "techo" if b.altura is None else _f(b.altura) + ("*" if b.por_defecto else "")
        donde = it["cara"]["corto"] if it["cara"] is not None else ("techo" if b.tipo == "CENTRO" else "—")
        filas.append((f"{it['codigo']:<5} h {alt:<7} {donde}", ROJO))
    for it in obra.ejes:
        donde = it["cara"]["corto"] if it["cara"] is not None else "—"
        filas.append(f"{it['codigo']:<5} {it['e'].artefacto} · {donde}")
    if filas:
        y = _leyenda(ax, x, y, "BOCAS Y EJES (código · altura · cara)", filas, fs=6.6, paso=3.6)
    notas = ["Cotas por fuera del dibujo, a eje de cada caja o artefacto, desde las caras terminadas (revestimiento, o "
             "SIP si no hay), desde la cara terminada más cercana sobre la que va (esquina o tabique). Cada boca se "
             "acota del lado hacia el que mira su cara; las de techo, en x abajo y en y a la izquierda. En rojo, "
             "electricidad.",
             "h: altura del eje de la caja desde el piso (base del panel).",
             "Las cañerías van solo dibujadas: se ajustan en obra."]
    if any(it["b"].por_defecto for it in obra.bocas):
        notas.append("* Altura típica: el bloque no trae el atributo ALTURA.")
    _leyenda(ax, x, y, "NOTAS", notas)
    _escala_pie(ax, lm.esc)
    return fig


# --------------------------------------------------------------------------------------------
# Vistas interiores
FILA_COTA = 8.5                       # separación entre filas de cotas acumuladas (mm)
TIT = 8.0


def _medidas_vista(c, k):
    filas = 3
    top = max(c["z0"], c["z1"])
    ancho = c["L"] * k + 26.0
    alto = top * k + 7.0 + filas * FILA_COTA + 6.0 + TIT
    return ancho, alto


def _acumuladas(ax, x0, y, xs_vals, k, guia_desde, color=NEGRO):
    """Fila de cotas acumuladas: línea base, un tick por valor, el valor (vertical) debajo y una línea guía
    de puntos desde el elemento (guia_desde: valor -> y de papel donde arranca; si falta, el piso)."""
    vals = sorted(set(round(v, 3) for v in xs_vals))
    if not vals:
        return
    guia = GUIA_ROJA if color != NEGRO else GUIA
    xa, xb = x0 + vals[0] * k, x0 + vals[-1] * k
    ax.plot([min(x0, xa), xb], [y, y], color=color, lw=0.5, zorder=11)
    ax.plot([x0, x0], [y - 1.4, y + 1.4], color=color, lw=0.8, zorder=11)       # origen
    ult = -1e9
    for v in vals:
        x = x0 + v * k
        if v > 1e-6:
            _tick(ax, (x, y), color=color)
        xt = max(x, ult + 2.7)
        ult = xt
        if abs(xt - x) > 0.3:
            ax.plot([x, xt], [y - 0.6, y - 1.8], color=color, lw=0.3, zorder=11)
        ax.text(xt, y - 2.0, _f(v), fontsize=6.0, rotation=90, ha="center", va="top", zorder=12, color=color)
        yg = guia_desde.get(v, guia_desde.get("piso"))
        if yg is not None and yg > y + 1.2:
            ax.plot([x, x], [yg, y + 1.2], zorder=9, **guia)


def dibujar_vista(ax, obra: Obra, c, x0, y0, k):
    """Vista interior de la cara c con el piso en (x0, y0)."""
    L, z0, z1 = c["L"], c["z0"], c["z1"]
    X = lambda u: x0 + u * k
    Y = lambda z: y0 + z * k
    zt = lambda u: z0 + (z1 - z0) * (u / L if L else 0)
    # revestimientos
    for mat, a, b in c["revs"]:                              # sin trama: solo el código y el cambio de tramo
        piezas = [(a, b)]
        for t in c["tabs"]:                                  # un rótulo por local: se corta en cada tabique
            piezas = [q for x0, x1 in piezas for q in ((x0, min(x1, t["a"])), (max(x0, t["b"]), x1))
                      if q[1] - q[0] > 1e-3]
        for a2, b2 in piezas:
            if b2 - a2 > 0.15:
                ax.text(X((a2 + b2) / 2), Y(min(zt(a2), zt(b2))) - 2.0, obra.cod_rev(mat), fontsize=6.8,
                        fontweight="bold", ha="center", va="top", zorder=13,
                        bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
        if a > 1e-3:
            ax.plot([X(a), X(a)], [Y(0), Y(zt(a))], color=NEGRO, lw=0.45, ls=(0, (2.5, 1.5)), zorder=6)
    # tabiques que llegan
    for t in c["tabs"]:
        a, b = t["a"], t["b"]
        sip = t["t"]["tipo"] == "SIP"
        ax.add_patch(MPoly([(X(a), Y(0)), (X(b), Y(0)), (X(b), Y(zt(b))), (X(a), Y(zt(a)))], closed=True,
                           fc=GRIS_SIP if sip else "white", ec=NEGRO, lw=0.5, hatch=None if sip else "////", zorder=5))
        ax.text(X((a + b) / 2), Y(max(zt(a), zt(b))) + 1.5, t["t"]["codigo"], fontsize=6.5, fontweight="bold",
                ha="center", va="bottom", zorder=13)
    # vanos
    for v in c["vanos"]:
        a, b, va, vb = v["a"], v["b"], v["z0"], v["z1"]
        ax.add_patch(Rectangle((X(a), Y(va)), (b - a) * k, (vb - va) * k, fc="white", ec=NEGRO, lw=0.7, zorder=7))
        ax.plot([X(a), X(b)], [Y(va), Y(vb)], color=GRIS_LINEA, lw=0.3, zorder=7)
        ax.plot([X(a), X(b)], [Y(vb), Y(va)], color=GRIS_LINEA, lw=0.3, zorder=7)
        ax.text(X((a + b) / 2), Y((va + vb) / 2), C.TIPOS_VANO.get(v["v"].tipo, "Vano").lower(),
                fontsize=6, ha="center", va="center", color=GRIS, zorder=8,
                bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"))
    # contorno de la cara y piso
    ax.add_patch(MPoly([(X(0), Y(0)), (X(L), Y(0)), (X(L), Y(z1)), (X(0), Y(z0))], closed=True, fc="none", ec=NEGRO,
                       lw=0.9, zorder=9, joinstyle="miter"))
    ax.plot([X(0) - 4, X(L) + 4], [Y(0), Y(0)], color=NEGRO, lw=1.3, zorder=9, solid_capstyle="butt")
    # ejes sanitarios
    guias = {}
    for e in c["ejes"]:
        u = e["u"]
        ax.plot([X(u), X(u)], [Y(0), Y(zt(u)) + 2.5], color=NEGRO, lw=0.5, ls=TR_EJE, zorder=10)
        ax.text(X(u), Y(zt(u)) + 3.0, f"{e['codigo']} {e['e'].artefacto}", fontsize=6.2, ha="center", va="bottom",
                zorder=13)
    # bocas
    alturas = {}
    for bo in c["bocas"]:
        b = bo["b"]
        u, h = bo["u"], b.altura or 0.0
        simbolo(ax, b.tipo, X(u), Y(h), r=1.5)
        ax.text(X(u) + 2.2, Y(h) + 1.6, bo["codigo"] + ("*" if b.por_defecto else ""), fontsize=6.2,
                fontweight="bold", ha="left", va="bottom", zorder=15, color=ROJO,
                bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none"))
        alturas.setdefault(round(h, 3), []).append(X(u))
        guias[round(u, 3)] = Y(h) - 1.6
    # cotas acumuladas (desde el extremo izquierdo), con línea guía de puntos desde cada elemento:
    # caras (tabiques, revestimientos y vanos), electricidad (en rojo) y ejes sanitarios
    y1 = y0 - 6.0
    fila1 = {0.0, L}
    for _, a, b in c["revs"]:
        fila1 |= {a, b}
    for t in c["tabs"]:
        fila1 |= {t["a"], t["b"]}
    desde1 = {"piso": Y(0)}
    for v in c["vanos"]:
        fila1 |= {v["a"], v["b"]}
        for u in (v["a"], v["b"]):
            desde1[round(u, 3)] = min(desde1.get(round(u, 3), 1e9), Y(v["z0"]))
    _acumuladas(ax, x0, y1, fila1, k, desde1)
    ax.text(X(0) - 2.0, y1, "caras", fontsize=5.8, ha="right", va="center", color=GRIS)
    yf = y1
    if c["bocas"]:
        yf -= FILA_COTA + 6.0
        _acumuladas(ax, x0, yf, [bo["u"] for bo in c["bocas"]], k, guias, color=ROJO)
        ax.text(X(0) - 2.0, yf, "electr.", fontsize=5.8, ha="right", va="center", color=ROJO)
    if c["ejes"]:
        yf -= FILA_COTA + 6.0
        _acumuladas(ax, x0, yf, [e["u"] for e in c["ejes"]], k, {"piso": Y(0)})
        ax.text(X(0) - 2.0, yf, "sanit.", fontsize=5.8, ha="right", va="center", color=GRIS)
    yb = y1 - 2 * (FILA_COTA + 6.0)                          # títulos alineados en la fila
    # alturas desde el piso (a la derecha)
    xc = X(L) + 6.0
    hs = set(alturas) | {round(z0, 3), round(z1, 3)}
    for v in c["vanos"]:
        hs |= {round(v["z0"], 3), round(v["z1"], 3)}
    hs = sorted(h for h in hs if h > 1e-6)
    ax.plot([xc, xc], [Y(0), Y(max(hs))], color=NEGRO, lw=0.5, zorder=11)
    ax.plot([xc - 1.4, xc + 1.4], [Y(0), Y(0)], color=NEGRO, lw=0.8, zorder=11)
    obra_h = {round(z0, 3), round(z1, 3)} | {round(v[k_], 3) for v in c["vanos"] for k_ in ("z0", "z1")}
    ult = -1e9
    for h in hs:
        y = Y(h)
        col = ROJO if h not in obra_h else NEGRO               # alturas de bocas, en rojo
        _tick(ax, (xc, y), color=col)
        yt = max(y, ult + 2.6)
        ult = yt
        ax.text(xc + 1.8, yt, _f(h), fontsize=6.0, ha="left", va="center", zorder=12, color=col)
        for xb in alturas.get(h, []):
            ax.plot([xb + 1.6, xc], [y, y], zorder=9, **GUIA_ROJA)
    # título
    ax.text(X(0), yb - 13.5, c["nombre"], fontsize=8.5, fontweight="bold", ha="left", va="top", color=NEGRO)
    ax.text(X(0), yb - 18.0, "Vista desde el interior", fontsize=6.5, ha="left", va="top", color=GRIS)


def _paginar_vistas(obra):
    """Elige la escala (la mayor que entre en la hoja) y reparte las vistas en filas y hojas."""
    ancho, alto = Z_X1 - Z_X0, Z_Y1 - Z_Y0
    caras = obra.caras
    if not caras:
        return 50, []
    for esc in ESCALAS_VISTA:
        k = 1000.0 / esc
        med = [_medidas_vista(c, k) for c in caras]
        if max(w for w, _ in med) <= ancho and max(h for _, h in med) <= alto:
            break
    hojas, filas, fila, x = [], [], [], 0.0
    GAP_X, GAP_Y = 14.0, 6.0
    for c, (w, h) in zip(caras, med):
        if fila and x + w > ancho:
            filas.append(fila)
            fila, x = [], 0.0
        fila.append((c, w, h))
        x += w + GAP_X
    if fila:
        filas.append(fila)
    hoja, usado = [], 0.0
    for f in filas:
        hf = max(h for _, _, h in f)
        if hoja and usado + hf > alto:
            hojas.append(hoja)
            hoja, usado = [], 0.0
        hoja.append(f)
        usado += hf + GAP_Y
    if hoja:
        hojas.append(hoja)
    return esc, hojas


def hojas_vistas(obra: Obra, fecha, n0, total, esc, paginas):
    k = 1000.0 / esc
    figs = []
    pie = "  ·  ".join(f"{cod} {obra.mo.mats[m].get('nombre', m)}" for m, cod in obra.codigos.items())
    pie = (pie + "  ·  " if pie else "") + ("OSB: SIP visto  ·  DL: placa del tabique de durlock  ·  Cotas acumuladas desde el extremo izquierdo (fila caras: "
                                          "tabiques, revestimientos y vanos; electr., en rojo: bocas; sanit.: artefactos) y "
                                          "alturas desde el piso  ·  * altura típica")
    for j, filas in enumerate(paginas):
        fig, ax = _hoja("Vistas interiores", obra.plano.proyecto, fecha, f"Hoja {n0 + j} de {total}", esc, pie)
        usado = sum(max(h for _, _, h in f) for f in filas) + 6.0 * (len(filas) - 1)
        y = Z_Y1 - max(0.0, (Z_Y1 - Z_Y0 - 8.0 - usado) / 2)
        for f in filas:
            hf = max(h for _, _, h in f)
            top = max(max(c["z0"], c["z1"]) for c, _, _ in f)          # pisos alineados en la fila
            x = Z_X0 + 8.0
            for c, w, h in f:
                dibujar_vista(ax, obra, c, x, y - 7.0 - top * k, k)
                x += w + 14.0
            y -= hf + 6.0
        figs.append(fig)
    return figs


# --------------------------------------------------------------------------------------------
def hojas_obra(plano: Plano, cfg_usuario: dict | None, fecha: str):
    """Devuelve ([figuras A3], avisos): planta de revestimientos y tabiques, planta de instalaciones y
    las vistas interiores de cada muro y tabique."""
    cfg = {**CONFIG_BASE, **{k: v for k, v in (cfg_usuario or {}).items() if v is not None}}
    obra = Obra(plano, cfg)
    esc, paginas = _paginar_vistas(obra)
    total = 2 + len(paginas)
    figs = [planta_revestimientos(obra, fecha, f"Hoja 1 de {total}"),
            planta_instalaciones(obra, fecha, f"Hoja 2 de {total}")]
    figs += hojas_vistas(obra, fecha, 3, total, esc, paginas)
    return figs, obra.avisos
