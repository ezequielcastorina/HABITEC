"""Lámina gráfica: planta acotada, vistas y axonometría del módulo (A3 apaisado, sin escala).

Usa el mismo plano que las hojas de taller (MODULO, PANEL, VANO, CAIDA) más las capas propias de la
lámina: REV_EXT_* y REV_INT_* (revestimientos por tramo), TABIQUE_DURLOCK, SANITARIOS, PUERTA_GIRO y
ELECTRICIDAD. Sin línea de revestimiento, el exterior es smart panel (la cara del SIP) y el interior
es el OSB del SIP visto.

Dibujo monocromático: tinta azul verdosa sobre fondo crema. Medidas internas en metros.
"""
from __future__ import annotations

import copy
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, PathPatch, Polygon as MPoly, Rectangle
from matplotlib.path import Path
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from . import config as C
from .modelo import Plano


def _registrar_fuentes():
    """Inter (OFL) viaja con el programa para que la lámina salga igual en el navegador."""
    from pathlib import Path
    from matplotlib import font_manager
    carpeta = Path(__file__).with_name("fuentes")
    ok = False
    for f in carpeta.glob("*.otf"):
        try:
            font_manager.fontManager.addfont(str(f))
            ok = True
        except Exception:                                    # noqa: BLE001
            pass
    return ok


FUENTE = ["Inter", "DejaVu Sans"] if _registrar_fuentes() else ["DejaVu Sans"]

ESP_SIP = C.ESPESOR_PANEL
HOJA_W, HOJA_H = 297.0, 420.0                      # A3 vertical (mm)
TINTA = "#1e4d55"                                  # azul verdoso oscuro: todas las líneas, rellenos y textos
CREMA = "#f7f2e7"                                  # fondo de la lámina; los elementos "blancos" van en este tono

# Revestimientos. La clave es lo que sigue a REV_EXT_ / REV_INT_ en el nombre de la capa.
# espesor en metros; dibujo en la vista: tablas (juntas verticales cada `paso`), chapa (líneas de a pares
# cada `paso`) o liso.
MATERIALES = {
    # exteriores
    "smart": {"nombre": "Smart panel", "espesor": 0.0, "patron": "tablas", "paso": 0.20},
    "chapa": {"nombre": "Chapa acanalada s/ clavaderas", "espesor": 0.030, "patron": "chapa", "paso": 0.20},
    "wpc": {"nombre": "WPC s/ clavaderas", "espesor": 0.035, "patron": "tablas", "paso": 0.07},
    # interiores (placas de yeso de 12,5 mm)
    "sip": {"nombre": "OSB visto (SIP)", "espesor": 0.0, "patron": "liso"},
    "placa": {"nombre": "Placa de yeso pegada s/ SIP", "espesor": 0.0125, "patron": "liso"},
    "omega": {"nombre": "Placa de yeso s/ omega", "espesor": 0.025, "patron": "liso"},
    "p35": {"nombre": "Placa de yeso s/ perfil 35", "espesor": 0.048, "patron": "liso"},
    "p70": {"nombre": "Placa de yeso s/ perfil 70", "espesor": 0.083, "patron": "liso"},
    "ceramico": {"nombre": "Cerámico pegado", "espesor": 0.012, "patron": "liso"},
    "pvc": {"nombre": "Machimbre de PVC", "espesor": 0.010, "patron": "liso"},
}
EXT_DEFECTO, INT_DEFECTO = "smart", "sip"

CONFIG_BASE = {
    "materiales": {},                # pisa o suma revestimientos (espesor, patrón, paso)
    "espesor_piso": 0.10,            # base del módulo -> piso interior (parrilla + fenólico, aprox.)
    "zingueria_inferior": 0.15,
    "zingueria_superior": 0.03,
    "zingueria_esquina": 0.15,
    "vistas": "con_aberturas",       # "con_aberturas" | "todas"
}

DIRS = {"A": (0, 1), "B": (1, 0), "C": (0, -1), "D": (-1, 0)}       # hacia dónde mira la cara exterior
ORDEN_VISTAS = ("C", "B", "A", "D")
LW_FINA, LW_MEDIA, LW_GRUESA = 0.25, 0.45, 0.9
LW_V_GRUESO, LW_V_FINO = 1.1, 0.06          # vistas: zinguerías, bordes de vanos y tierra / tramas y líneas internas
LW_PISO = 0.06                             # la línea más fina: el piso no compite con el resto
COTA_COLOR = "#7fa3a9"
TINTA_CLARA = "#b6cbce"                    # misma paleta, mucho más clara: piso en planta y trama de revestimientos en vista                     # cotas: un tono más claro que la tinta
SEP_TIERRA = 0.06                          # el módulo se separa un poco de la línea de tierra en las vistas


def _f(v):
    return f"{v:.2f}".replace(".", ",")


# --------------------------------------------------------------------------------------------
# Modelo
def _superponer(tramos, mat, a, b):
    """Pone el material `mat` entre a y b sobre una lista de tramos [(mat, a, b)] que cubre el muro."""
    out = []
    for m, x0, x1 in tramos:
        if x1 <= a or x0 >= b:
            out.append((m, x0, x1))
            continue
        if x0 < a:
            out.append((m, x0, a))
        if x1 > b:
            out.append((m, b, x1))
    out.append((mat, a, b))
    return sorted((t for t in out if t[2] - t[1] > 1e-4), key=lambda t: t[1])


class Muro:
    def __init__(self, lado, mats):
        self.lado = lado
        self.letra, self.dir = lado.letra, lado.dir
        self.p0, self.p1 = lado.ini, lado.fin
        self.largo = math.dist(self.p0, self.p1)
        self.d = ((self.p1[0] - self.p0[0]) / self.largo, (self.p1[1] - self.p0[1]) / self.largo)
        self.n = DIRS[lado.dir]
        self.mats = mats
        self.ext = [(EXT_DEFECTO, 0.0, self.largo)]
        self.int_ = [(INT_DEFECTO, 0.0, self.largo)]

    def punto(self, s, off):
        return (self.p0[0] + self.d[0] * s + self.n[0] * off, self.p0[1] + self.d[1] * s + self.n[1] * off)

    def s_de(self, p):
        return (p[0] - self.p0[0]) * self.d[0] + (p[1] - self.p0[1]) * self.d[1]

    def esp(self, cara, s):
        for m, a, b in (self.ext if cara == "EXT" else self.int_):
            if a - 1e-6 <= s <= b + 1e-6:
                return self.mats[m]["espesor"]
        return 0.0

    def esp_max(self, cara):
        return max(self.mats[m]["espesor"] for m, _, _ in (self.ext if cara == "EXT" else self.int_))


class Modelo:
    def __init__(self, plano: Plano, cfg: dict):
        self.cfg, self.plano = cfg, plano
        self.mats = copy.deepcopy(MATERIALES)
        for k, v in (cfg.get("materiales") or {}).items():
            self.mats[k.lower()] = {**self.mats.get(k.lower(), {"nombre": k, "espesor": 0.0, "patron": "liso"}), **v}
        self.avisos: list[str] = []
        self.muros = [Muro(l, self.mats) for l in plano.lados]
        nm = len(self.muros)
        self._asignar_revestimientos()

        self.contorno = Polygon(plano.contorno)
        self.cara_sip = self.offset(lambda i: -ESP_SIP)
        # bandas de revestimiento (cuadriláteros por tramo)
        self.bandas_int, self.bandas_ext = [], []
        for i, m in enumerate(self.muros):
            mp, mn = self.muros[i - 1], self.muros[(i + 1) % nm]
            ti_p, ti_n = mp.esp("INT", mp.largo), mn.esp("INT", 0.0)
            te_p, te_n = mp.esp("EXT", mp.largo), mn.esp("EXT", 0.0)
            for mat, a, b in m.int_:
                t = self.mats[mat]["espesor"]
                if t > 0:
                    self.bandas_int.append(self.banda(i, -(ESP_SIP + t), -ESP_SIP, a, b,
                                                      o1p=-(ESP_SIP + ti_p), o1n=-(ESP_SIP + ti_n),
                                                      o2p=-ESP_SIP, o2n=-ESP_SIP))
            for mat, a, b in m.ext:
                t = self.mats[mat]["espesor"]
                if t > 0:
                    self.bandas_ext.append(self.banda(i, 0.0, t, a, b, o1p=0.0, o1n=0.0, o2p=te_p, o2n=te_n))
        bi = unary_union([Polygon(q) for q in self.bandas_int]) if self.bandas_int else Polygon()
        self.cara_int = self.cara_sip.difference(bi)
        be = unary_union([Polygon(q) for q in self.bandas_ext]) if self.bandas_ext else Polygon()
        self.cara_ext = unary_union([self.contorno, be])

        # tabiques: SIP (PANEL que no apoya sobre el contorno) y durlock
        borde = self.contorno.exterior
        sip = [box(r.x0, r.y0, r.x1, r.y1) for r in plano.paneles if borde.distance(Point(*r.centro)) > ESP_SIP * 0.75]
        dur = [box(r.x0, r.y0, r.x1, r.y1) for r in plano.tabiques_durlock]
        self.tab_sip = unary_union(sip).intersection(self.cara_sip) if sip else Polygon()
        self.tab_dur = unary_union(dur).intersection(self.cara_sip) if dur else Polygon()
        self.tabiques = unary_union([self.tab_sip, self.tab_dur])

        self.vanos = []
        for v in plano.vanos:
            r = box(v.rect.x0, v.rect.y0, v.rect.x1, v.rect.y1)
            c = r.centroid
            i = min(range(nm), key=lambda k: LineString([self.muros[k].p0, self.muros[k].p1]).distance(c))
            m = self.muros[i]
            item = {"v": v, "rect": r, "muro": None, "a": 0.0, "b": 0.0}
            if LineString([m.p0, m.p1]).distance(c) <= ESP_SIP:
                ss = [m.s_de(p) for p in r.exterior.coords]
                item.update(muro=i, a=min(ss), b=max(ss))
            self.vanos.append(item)

        # revestimientos interiores sobre las caras de los tabiques
        self.bandas_tab = []
        sin_tabique = 0
        for clave, p0, p1 in self._sueltos:
            t = self.mats[clave]["espesor"]
            L = math.dist(p0, p1)
            d = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
            nrm = (-d[1], d[0])
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            if self.tabiques.is_empty or self.tabiques.distance(Point(*mid)) > 0.03:
                sin_tabique += 1
                continue
            # la banda crece hacia el lado libre (el que no es tabique)
            lado = -1 if self.tabiques.contains(Point(mid[0] + nrm[0] * 0.02, mid[1] + nrm[1] * 0.02)) else 1
            if t > 0:
                q = [p0, p1, (p1[0] + nrm[0] * t * lado, p1[1] + nrm[1] * t * lado),
                     (p0[0] + nrm[0] * t * lado, p0[1] + nrm[1] * t * lado)]
                self.bandas_tab.append(Polygon(q).intersection(self.cara_int))
        if sin_tabique:
            self.avisos.append(f"{sin_tabique} línea(s) de revestimiento no quedan junto a ningún muro ni tabique (se ignoran).")
        self.libre = self.cara_int.difference(unary_union([self.tabiques] + self.bandas_tab))
        self.locales = [g for g in getattr(self.libre, "geoms", [self.libre]) if g.area > 0.3]
        self.caida = DIRS.get(plano.caida_hacia) if plano.caida_hacia else None

    def _asignar_revestimientos(self):
        self._sueltos = []
        sin_muro = 0
        for cara, clave, p0, p1 in self.plano.revestimientos:
            if clave not in self.mats:
                self.avisos.append(f"Capa REV_{cara}_{clave.upper()}: revestimiento desconocido (se ignora).")
                continue
            if math.dist(p0, p1) < 0.02:
                continue
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            mejor = None
            for i, m in enumerate(self.muros):
                paralela = abs((p1[0] - p0[0]) * m.n[0] + (p1[1] - p0[1]) * m.n[1]) < 0.02
                if not paralela:
                    continue
                off = (mid[0] - m.p0[0]) * m.n[0] + (mid[1] - m.p0[1]) * m.n[1]   # + afuera
                s = m.s_de(mid)
                if not (-0.2 <= s <= m.largo + 0.2):
                    continue
                if cara == "EXT" and not (-0.05 <= off <= 0.30):
                    continue
                if cara == "INT" and not (-0.40 <= off <= 0.0):
                    continue
                if mejor is None or abs(off) < mejor[0]:
                    mejor = (abs(off), i)
            if mejor is None:
                if cara == "INT":
                    self._sueltos.append((clave, p0, p1))      # puede ser el revestimiento de un tabique
                else:
                    sin_muro += 1
                continue
            m = self.muros[mejor[1]]
            a, b = sorted([m.s_de(p0), m.s_de(p1)])
            a, b = max(0.0, a), min(m.largo, b)
            # la cara interior es más corta que el muro (esquinas): cerca de un extremo, se completa hasta él
            tol = ESP_SIP + 0.06
            a = 0.0 if a <= tol else a
            b = m.largo if b >= m.largo - tol else b
            if b - a < 0.01:
                continue
            if cara == "EXT":
                m.ext = _superponer(m.ext, clave, a, b)
            else:
                m.int_ = _superponer(m.int_, clave, a, b)
        if sin_muro:
            self.avisos.append(f"{sin_muro} línea(s) de revestimiento no quedan junto a ningún muro (se ignoran).")

    # esquinas: intersección de los lados desplazados (lados horizontales y verticales)
    def esq_ini(self, i, off, off_prev):
        m, mp = self.muros[i], self.muros[i - 1]
        return (m.p0[0] + m.n[0] * off + mp.n[0] * off_prev, m.p0[1] + m.n[1] * off + mp.n[1] * off_prev)

    def esq_fin(self, i, off, off_next):
        m, mn = self.muros[i], self.muros[(i + 1) % len(self.muros)]
        return (m.p1[0] + m.n[0] * off + mn.n[0] * off_next, m.p1[1] + m.n[1] * off + mn.n[1] * off_next)

    def offset(self, f):
        return Polygon([self.esq_ini(i, f(i), f(i - 1)) for i in range(len(self.muros))])

    def banda(self, i, o1, o2, s0=None, s1=None, o1p=None, o2p=None, o1n=None, o2n=None):
        m = self.muros[i]
        s0 = 0.0 if s0 is None else s0
        s1 = m.largo if s1 is None else s1

        def ini(o, op):
            return self.esq_ini(i, o, o if op is None else op) if s0 <= 1e-6 else m.punto(s0, o)

        def fin(o, on):
            return self.esq_fin(i, o, o if on is None else on) if s1 >= m.largo - 1e-6 else m.punto(s1, o)
        return [ini(o1, o1p), fin(o1, o1n), fin(o2, o2n), ini(o2, o2p)]

    def extremos_cara(self, i):
        """(s inicial, s final) de la cara exterior terminada del muro i, con los retornos de esquina."""
        m, nm = self.muros[i], len(self.muros)
        mp, mn = self.muros[i - 1], self.muros[(i + 1) % nm]
        pa = self.esq_ini(i, m.esp("EXT", 0.0), mp.esp("EXT", mp.largo))
        pb = self.esq_fin(i, m.esp("EXT", m.largo), mn.esp("EXT", 0.0))
        return m.s_de(pa), m.s_de(pb)

    # alturas: laterales rectos al alto del lado alto; la cara de la caída, al del lado bajo
    def alto(self):
        return self.cfg["espesor_piso"] + C.ALTO_PANEL

    def bajo(self):
        return self.cfg["espesor_piso"] + C.ALTO_PANEL_BAJO

    def altura_cara(self, i):
        if self.plano.caida_hacia and self.muros[i].dir == self.plano.caida_hacia:
            return self.bajo()
        return self.alto()

    def z_techo(self, p):
        if self.caida is None:
            return self.alto()
        c = self.caida
        pr = [x * c[0] + y * c[1] for x, y in self.plano.contorno]
        lo, hi = min(pr), max(pr)
        t = ((p[0] * c[0] + p[1] * c[1]) - lo) / (hi - lo if hi > lo else 1)
        return self.alto() - (self.alto() - self.bajo()) * t


# --------------------------------------------------------------------------------------------
# Dibujo
class Hoja:
    def __init__(self):
        self.fig = plt.figure(figsize=(HOJA_W / 25.4, HOJA_H / 25.4), facecolor=CREMA)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, HOJA_W)
        self.ax.set_ylim(0, HOJA_H)
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self.ax.set_facecolor(CREMA)
        self.k, self.ox, self.oy = 1.0, 0.0, 0.0

    def T(self, x, y):
        return (self.ox + x * self.k, self.oy + y * self.k)

    def poly(self, pts, fc="none", lw=LW_FINA, z=2, papel=False, **kw):
        P = pts if papel else [self.T(*q) for q in pts]
        self.ax.add_patch(MPoly(P, closed=True, fc=fc, ec=kw.pop("ec", TINTA), lw=lw, zorder=z, joinstyle="miter", **kw))

    def shp(self, g, **kw):
        kw.setdefault("lw", LW_FINA)
        kw.setdefault("ec", TINTA)
        for geom in getattr(g, "geoms", [g]):
            if geom.is_empty or geom.geom_type != "Polygon":
                continue
            verts, codes = [], []
            for ring in [geom.exterior, *geom.interiors]:
                cs = [self.T(*c) for c in ring.coords]
                verts += cs
                codes += [Path.MOVETO] + [Path.LINETO] * (len(cs) - 2) + [Path.CLOSEPOLY]
            self.ax.add_patch(PathPatch(Path(verts, codes), joinstyle="miter", **kw))

    def linea(self, a, b, lw=LW_FINA, z=3, papel=False, **kw):
        A, B = (a, b) if papel else (self.T(*a), self.T(*b))
        self.ax.plot([A[0], B[0]], [A[1], B[1]], color=TINTA, lw=lw, zorder=z, solid_capstyle="butt", **kw)


def _cota(ax, a, b, size=11.0):
    """Cota entre dos puntos de papel (horizontal o vertical). Texto horizontal arriba de la línea;
    vertical a la izquierda, leyéndose desde la derecha."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 0.5:
        return
    ux, uy = dx / L, dy / L
    ax.plot([a[0] - ux * 1.2, b[0] + ux * 1.2], [a[1] - uy * 1.2, b[1] + uy * 1.2], color=COTA_COLOR, lw=0.4, zorder=6)
    for P in (a, b):                                         # ticks a 45°
        ax.plot([P[0] - 1.0, P[0] + 1.0], [P[1] - 1.0, P[1] + 1.0], color=COTA_COLOR, lw=0.8, zorder=6)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    texto = f"{L / _cota.k:.2f}".replace(".", ",")
    if abs(dy) < abs(dx):
        ax.text(mx, my + 0.9, texto, fontsize=size, color=COTA_COLOR, ha="center", va="bottom", zorder=10)
    else:
        ax.text(mx - 0.9, my, texto, fontsize=size, color=COTA_COLOR, ha="center", va="bottom", rotation=90,
                rotation_mode="anchor", zorder=10)


_cota.k = 1.0


# ---------------- planta
def _dibujar_libre(h, lista, z=5):
    for pts, cerrado in lista:
        if cerrado:
            h.poly(pts, fc=CREMA, lw=LW_FINA, z=z)
        else:
            P = [h.T(*q) for q in pts]
            h.ax.plot([q[0] for q in P], [q[1] for q in P], color=TINTA, lw=LW_FINA, zorder=z)


def dibujar_planta(h: Hoja, mo: Modelo):
    nm = len(mo.muros)
    for pts, _ in mo.plano.piso:                      # trama de piso de la capa PISO
        P = [h.T(*q) for q in pts]
        h.ax.plot([q[0] for q in P], [q[1] for q in P], color=TINTA_CLARA, lw=LW_PISO, zorder=1.5, solid_capstyle="butt")
    for i in range(nm):
        h.poly(mo.banda(i, -ESP_SIP, 0.0), fc=TINTA, lw=0.2, z=2)
    for q in mo.bandas_int + mo.bandas_ext:
        h.poly(q, fc=CREMA, lw=LW_FINA, z=2)
    h.shp(mo.contorno, fc="none", lw=LW_MEDIA, zorder=3)
    # tabiques, cortados donde hay puertas
    cortes = []
    for it in mo.vanos:
        if it["muro"] is None:
            x0, y0, x1, y1 = it["rect"].bounds
            cortes.append(box(x0 - 0.2, y0, x1 + 0.2, y1) if (x1 - x0) < (y1 - y0) else box(x0, y0 - 0.2, x1, y1 + 0.2))
    corte = unary_union(cortes) if cortes else None
    if not mo.tab_sip.is_empty:
        h.shp(mo.tab_sip.difference(corte) if corte is not None else mo.tab_sip, fc=TINTA, lw=0.2, zorder=4)
    if not mo.tab_dur.is_empty:
        h.shp(mo.tab_dur.difference(corte) if corte is not None else mo.tab_dur, fc=CREMA, lw=LW_MEDIA, zorder=4)
    for g in mo.bandas_tab:
        h.shp(g.difference(corte) if corte is not None else g, fc=CREMA, lw=LW_FINA, zorder=4)
    _dibujar_libre(h, mo.plano.sanitarios)
    _dibujar_libre(h, mo.plano.electricidad, z=8)
    for it in mo.vanos:
        if it["muro"] is not None:
            _vano_planta(h, mo, it)
        else:
            _puerta_tabique(h, mo, it)


def _piso_tablas(h, mo, paso=0.06):
    """Trama lineal de piso: líneas paralelas al lado corto del módulo, muy finas y juntas."""
    libre = mo.libre
    if libre.is_empty:
        return
    x0, y0, x1, y1 = libre.bounds
    verticales = (x1 - x0) >= (y1 - y0)          # el módulo es más largo en x: tablas en el sentido corto
    t = (x0 if verticales else y0) + paso
    fin = x1 if verticales else y1
    while t < fin - 1e-3:
        a, b = ((t, y0 - 1), (t, y1 + 1)) if verticales else ((x0 - 1, t), (x1 + 1, t))
        g = LineString([a, b]).intersection(libre)
        for sg in getattr(g, "geoms", [g]):
            if sg.is_empty or sg.geom_type != "LineString":
                continue
            A, B = h.T(*sg.coords[0]), h.T(*sg.coords[-1])
            h.ax.plot([A[0], B[0]], [A[1], B[1]], color=TINTA, lw=LW_PISO, zorder=1.5, solid_capstyle="butt")
        t += paso


def _tiene_dibujo_de_puerta(mo, rect):
    zona = rect.buffer(0.3)
    return any(zona.intersects(LineString(pts) if len(pts) > 1 else Point(pts[0])) for pts, _ in mo.plano.puertas)


def _vano_planta(h, mo, it):
    m = mo.muros[it["muro"]]
    a, b, tipo = it["a"], it["b"], it["v"].tipo
    oi = -(ESP_SIP + max(m.esp("INT", a), m.esp("INT", b), m.esp("INT", (a + b) / 2)))
    oe = max(m.esp("EXT", a), m.esp("EXT", b), m.esp("EXT", (a + b) / 2))
    h.poly([m.punto(a, oi), m.punto(b, oi), m.punto(b, oe), m.punto(a, oe)], fc=CREMA, ec="none", lw=0, z=5)
    for s in (a, b):
        h.linea(m.punto(s, oi), m.punto(s, oe), lw=LW_MEDIA, z=6)
    if tipo in ("PV", "C"):
        mid = (a + b) / 2
        for s0, s1, o0, o1 in ((a, mid + 0.04, -0.075, -0.045), (mid - 0.04, b, -0.045, -0.015)):
            h.poly([m.punto(s0, o0), m.punto(s1, o0), m.punto(s1, o1), m.punto(s0, o1)], fc=CREMA, lw=LW_FINA, z=6)
    elif tipo == "P":
        pass                                                 # el giro de puertas no va en esta lámina
    else:
        h.poly([m.punto(a, -0.065), m.punto(b, -0.065), m.punto(b, -0.025), m.punto(a, -0.025)], fc=CREMA, lw=LW_FINA, z=6)
        h.linea(m.punto(a, -0.045), m.punto(b, -0.045), lw=0.2, z=7)
    h.shp(it["rect"], fc="none", lw=LW_FINA, zorder=7)              # y las líneas de la capa VANO, tal cual


def _hoja_puerta(h, bisagra, eje, abre, ancho):
    fin = (bisagra[0] + abre[0] * ancho, bisagra[1] + abre[1] * ancho)
    h.linea(bisagra, fin, lw=LW_MEDIA, z=7)
    X, Y = h.T(*bisagra)
    a0 = math.degrees(math.atan2(eje[1], eje[0]))
    a1 = math.degrees(math.atan2(abre[1], abre[0]))
    t1, t2 = sorted([a0, a1])
    if t2 - t1 > 180:
        t1, t2 = t2, t1 + 360
    h.ax.add_patch(Arc((X, Y), 2 * ancho * h.k, 2 * ancho * h.k, theta1=t1, theta2=t2, lw=LW_FINA, color=TINTA, zorder=7))


def _puerta_tabique(h, mo, it):
    h.shp(it["rect"], fc="none", lw=LW_FINA, zorder=7)              # rectángulo de la capa VANO
    return                                                          # el giro de puertas no va en esta lámina
    x0, y0, x1, y1 = it["rect"].bounds
    if (x1 - x0) < (y1 - y0):
        cx = (x0 + x1) / 2
        a, b, eje, lados = (cx, y0), (cx, y1), (0, 1), [(1, 0), (-1, 0)]
    else:
        cy = (y0 + y1) / 2
        a, b, eje, lados = (x0, cy), (x1, cy), (1, 0), [(0, 1), (0, -1)]

    def area_local(p):
        return next((loc.area for loc in mo.locales if loc.contains(Point(*p))), 1e9)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    abre = min(lados, key=lambda s: area_local((mx + s[0] * 0.3, my + s[1] * 0.3)))
    _hoja_puerta(h, a, eje, abre, math.dist(a, b))


# ---------------- cotas de planta
SEP_COTA, PASO_COTA, PROF_COTA_INT = 0.40, 0.42, 0.30


def cadenas(mo: Modelo):
    """Todas las cotas van por fuera. Por cada lado, una sola cadena de medidas interiores
    (sin repetir valores ya acotados) y, por fuera de todo, el largo y el ancho totales."""
    muros = mo.muros
    libre = mo.cara_int.difference(mo.tabiques)
    ext = list(mo.cara_ext.exterior.coords)
    lados, candidatos = {}, []
    for dl, n in DIRS.items():
        caras = [i for i, m in enumerate(muros) if m.dir == dl]
        if not caras:
            continue
        r = (-n[1], n[0])
        u = lambda p, r=r: p[0] * r[0] + p[1] * r[1]
        dep = lambda p, n=n: p[0] * n[0] + p[1] * n[1]
        cont = list(mo.contorno.exterior.coords)          # totales: medida del módulo (sin revestimiento)
        lados[dl] = {"n": n, "r": r, "dmax": max(map(dep, ext)), "umin": min(map(u, cont)),
                     "umax": max(map(u, cont)), "int": [], "total": False}
        for i in caras:
            m = muros[i]
            prof = ESP_SIP + m.esp_max("INT") + PROF_COTA_INT
            seg = LineString([m.punto(-50, -prof), m.punto(m.largo + 50, -prof)]).intersection(libre)
            ua, ub = sorted([u(m.p0), u(m.p1)])
            for sg in getattr(seg, "geoms", [seg]):
                if sg.is_empty or sg.length < 0.25 or sg.geom_type != "LineString":
                    continue
                s0, s1 = sorted([u(sg.coords[0]), u(sg.coords[-1])])
                if min(s1, ub) - max(s0, ua) > 0.05:
                    candidatos.append((dl, s0, s1))
    # sin repetir medidas iguales (al cm) en la misma dirección; una sola fila por lado
    vistos = set()
    for dl, s0, s1 in sorted(candidatos, key=lambda c: -(c[2] - c[1])):
        clave = (DIRS[dl][0] != 0, round(s1 - s0, 2))
        if clave in vistos:
            continue
        fila = lados[dl]["int"]
        if all(s1 <= a + 1e-6 or s0 >= b - 1e-6 for a, b in fila):
            fila.append((s0, s1))
            vistos.add(clave)
    # totales: el largo abajo (o arriba) y el ancho a la izquierda (o a la derecha)
    for opciones in (("C", "A"), ("D", "B")):
        for dl in opciones:
            if dl in lados:
                lados[dl]["total"] = True
                break
    return lados


def margen_cotas(cad):
    return {dl: SEP_COTA + PASO_COTA * (bool(c["int"]) + c["total"]) + 0.2 for dl, c in cad.items()}


def dibujar_cotas(h: Hoja, cad):
    _cota.k = h.k
    for c in cad.values():
        n, r = c["n"], c["r"]

        def P(uu, dd):
            return h.T(r[0] * uu + n[0] * dd, r[1] * uu + n[1] * dd)
        k = 0
        if c["int"]:
            d = c["dmax"] + SEP_COTA
            for a, b in c["int"]:
                _cota(h.ax, P(a, d), P(b, d))
            k = 1
        if c["total"]:
            d = c["dmax"] + SEP_COTA + k * PASO_COTA
            _cota(h.ax, P(c["umin"], d), P(c["umax"], d))


# ---------------- caras (vistas y axonometría): todo se dibuja en coordenadas de la cara (s, z)
# y una función F(s, z) -> papel, que en las vistas es una proyección plana y en la axo una isométrica.
def _rect(ax, F, s0, s1, z0, z1, z, fc=CREMA, lw=LW_FINA, **kw):
    ax.add_patch(MPoly([F(s0, z0), F(s1, z0), F(s1, z1), F(s0, z1)], closed=True, fc=fc, ec=TINTA, lw=lw,
                       zorder=z, joinstyle="miter", **kw))


def _seg(ax, F, s0, z0, s1, z1, z, lw=LW_FINA, color=TINTA):
    A, B = F(s0, z0), F(s1, z1)
    ax.plot([A[0], B[0]], [A[1], B[1]], color=color, lw=lw, zorder=z, solid_capstyle="butt")


def pintar_cara(ax, mo: Modelo, i, F0, zb):
    m = mo.muros[i]
    cfg = mo.cfg
    F = lambda s_, z_: F0(s_, z_ + SEP_TIERRA)               # el módulo flota un poco sobre la tierra
    sa, sb = mo.extremos_cara(i)
    if sa > sb:
        sa, sb = sb, sa
    h = mo.altura_cara(i)
    zi, zs, ze = cfg["zingueria_inferior"], cfg["zingueria_superior"], cfg["zingueria_esquina"]
    _rect(ax, F, sa, sb, 0, h, zb + 1, lw=0)
    # revestimiento por tramos (trama muy fina)
    for mat, a, b in m.ext:
        a2 = sa if a <= 1e-6 else a
        b2 = sb if b >= m.largo - 1e-6 else b
        mt = mo.mats[mat]
        p, paso = mt.get("patron", "liso"), mt.get("paso", 0.2)
        if p in ("tablas", "chapa") and paso > 0.02:
            x = a2 + paso
            while x < b2 - 0.01:
                _seg(ax, F, x, zi, x, h - zs, zb + 2, lw=LW_V_FINO, color=TINTA_CLARA)
                if p == "chapa" and x + 0.035 < b2:
                    _seg(ax, F, x + 0.035, zi, x + 0.035, h - zs, zb + 2, lw=LW_V_FINO, color=TINTA_CLARA)
                x += paso
        if a2 > sa + 1e-3:
            _seg(ax, F, a2, zi, a2, h - zs, zb + 3, lw=LW_V_FINO)
    # zinguerías (trazo grueso): la inferior corre completa; las de esquina arrancan arriba de ella
    if zi > 0:
        _rect(ax, F, sa, sb, 0, zi, zb + 4, lw=LW_V_GRUESO)
    if ze > 0 and m.lado.convexo_ini:
        _rect(ax, F, sa, sa + ze, zi, h - zs, zb + 4, lw=LW_V_GRUESO)
    if ze > 0 and m.lado.convexo_fin:
        _rect(ax, F, sb - ze, sb, zi, h - zs, zb + 4, lw=LW_V_GRUESO)
    if zs > 0:
        _rect(ax, F, sa, sb, h - zs, h, zb + 4, lw=LW_V_GRUESO)
    # aberturas: las que llegan al piso arrancan justo arriba de la zinguería inferior
    piso = cfg["espesor_piso"]
    for it in mo.vanos:
        if it["muro"] != i:
            continue
        v = it["v"]
        if v.tipo in C.TIPOS_HASTA_PISO:
            z0 = max(piso, zi)
            z1 = piso + (v.alto or 2.0)
        else:
            z0 = piso + v.antepecho
            z1 = z0 + (v.alto or 1.0)
        _abertura(ax, F, v.tipo, it["a"], it["b"], z0, z1, zb + 5)
    ax.add_patch(MPoly([F(sa, 0), F(sb, 0), F(sb, h), F(sa, h)], closed=True, fc="none", ec=TINTA, lw=LW_V_GRUESO,
                       zorder=zb + 9, joinstyle="miter"))


def _abertura(ax, F, tipo, a, b, z0, z1, z):
    M, H = 0.05, 0.045                                      # marco general y marco de hoja
    _rect(ax, F, a, b, z0, z1, z, lw=LW_V_GRUESO)
    if tipo == "P":
        _rect(ax, F, a + M, b - M, z0, z1 - M, z + 1, lw=LW_V_FINO)
        x = b - M - 0.09
        _seg(ax, F, x, z0 + (z1 - z0) * 0.47, x + 0.05, z0 + (z1 - z0) * 0.47, z + 2, lw=LW_V_FINO)
        return
    zi0, zi1 = z0 + M, z1 - M
    if tipo in ("PV", "C") or b - a > 1.2:
        mid = (a + b) / 2
        hojas = [(a + M, mid + H / 2), (mid - H / 2, b - M)]
    else:
        hojas = [(a + M, b - M)]
    for k, (h0, h1) in enumerate(hojas):
        _rect(ax, F, h0, h1, zi0, zi1, z + 1 + k, lw=LW_V_FINO)
        _rect(ax, F, h0 + H, h1 - H, zi0 + H, zi1 - H, z + 1 + k, lw=LW_V_FINO)
        _puntos(ax, F, h0 + H, h1 - H, zi0 + H, zi1 - H, z + 1 + k)


def _puntos(ax, F, s0, s1, z0, z1, z, paso=0.07):
    """Trama liviana de puntos (vidrio), en tresbolillo."""
    xs, ys = [], []
    fila, zz = 0, z0 + paso / 2
    while zz < z1 - paso / 4:
        ss = s0 + paso / 2 + (paso / 2 if fila % 2 else 0)
        while ss < s1 - paso / 4:
            X, Y = F(ss, zz)
            xs.append(X)
            ys.append(Y)
            ss += paso
        zz += paso
        fila += 1
    if xs:
        ax.scatter(xs, ys, s=0.25, c=TINTA, marker="o", linewidths=0, zorder=z + 0.5)


def vistas_a_dibujar(mo: Modelo):
    todas = mo.cfg["vistas"] == "todas"
    out = []
    for dl in ORDEN_VISTAS:
        caras = [i for i, m in enumerate(mo.muros) if m.dir == dl]
        if caras and (todas or any(it["muro"] in caras for it in mo.vanos)):
            out.append((dl, caras))
    return out


def titulos_vistas(mo, vistas):
    """FRENTE es la cara con la puerta (o con más abertura); las demás, LATERAL o POSTERIOR."""
    def puntaje(item):
        dl, caras = item
        its = [it for it in mo.vanos if it["muro"] in caras]
        return (any(it["v"].tipo in C.TIPOS_HASTA_PISO for it in its), sum(it["b"] - it["a"] for it in its))
    if not vistas:
        return {}
    frente = max(vistas, key=puntaje)[0]
    nf = DIRS[frente]
    derecha = (-nf[1], nf[0])
    out = {frente: "VISTA FRENTE"}
    laterales = [dl for dl, _ in vistas if dl != frente and DIRS[dl] != (-nf[0], -nf[1])]
    for dl, _ in vistas:
        if dl == frente:
            continue
        n = DIRS[dl]
        if n == (-nf[0], -nf[1]):
            out[dl] = "VISTA POSTERIOR"
        elif len(laterales) == 1:
            out[dl] = "VISTA LATERAL"
        else:
            out[dl] = "VISTA LATERAL DERECHA" if n == derecha else "VISTA LATERAL IZQUIERDA"
    return out


def extension_vista(mo, dl):
    n = DIRS[dl]
    r = (-n[1], n[0])
    us = [x * r[0] + y * r[1] for x, y in mo.cara_ext.exterior.coords]
    return min(us), max(us)


def dibujar_vista(h: Hoja, mo: Modelo, dl, caras, x0, y0):
    n = DIRS[dl]
    r = (-n[1], n[0])
    umin, _ = extension_vista(mo, dl)
    k = h.k
    for rango, i in enumerate(sorted(caras, key=lambda i: mo.muros[i].p0[0] * n[0] + mo.muros[i].p0[1] * n[1])):
        m = mo.muros[i]

        def F(s, z, m=m):
            p = m.punto(s, 0)
            return (x0 + (p[0] * r[0] + p[1] * r[1] - umin) * k, y0 + z * k)
        pintar_cara(h.ax, mo, i, F, 20 * rango)
    _, umax = extension_vista(mo, dl)
    h.ax.plot([x0 - 5, x0 + (umax - umin) * k + 5], [y0, y0], color=TINTA, lw=LW_V_GRUESO, zorder=1)


# ---------------- axonometría
C30, S30 = math.cos(math.radians(30)), math.sin(math.radians(30))
CAMARAS = [(1, -1), (1, 1), (-1, 1), (-1, -1)]


def elegir_camara(mo):
    def puntaje(cam):
        vis = [i for i, m in enumerate(mo.muros) if m.n[0] * cam[0] + m.n[1] * cam[1] > 0]
        return (sum(1 for it in mo.vanos if it["muro"] in vis), sum(mo.muros[i].largo for i in vis))
    return max(CAMARAS, key=puntaje)


def _proy(cam, p, z):
    right = (-cam[1], cam[0])
    return ((p[0] * right[0] + p[1] * right[1]) * C30, -(p[0] * cam[0] + p[1] * cam[1]) * S30 + z)


def caja_axo(mo, cam):
    pts = []
    for x, y in mo.cara_ext.exterior.coords:
        for z in (0.0, mo.alto()):
            pts.append(_proy(cam, (x, y), z))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def dibujar_axo(h: Hoja, mo: Modelo, cam, ox, oy, k):
    ax = h.ax
    P = lambda p, z: (ox + _proy(cam, p, z)[0] * k, oy + _proy(cam, p, z)[1] * k)
    dep = lambda p: p[0] * cam[0] + p[1] * cam[1]
    nm = len(mo.muros)
    visibles = [i for i, m in enumerate(mo.muros) if m.n[0] * cam[0] + m.n[1] * cam[1] > 0]
    # 1) caras interiores de los muros del fondo que asoman sobre el techo
    for i, m in enumerate(mo.muros):
        if i in visibles:
            continue
        h_m = mo.altura_cara(i)
        a, b = m.punto(0, -ESP_SIP), m.punto(m.largo, -ESP_SIP)
        za, zb_ = mo.z_techo(a), mo.z_techo(b)
        if max(h_m - za, h_m - zb_) > 0.01:
            ax.add_patch(MPoly([P(a, min(za, h_m)), P(b, min(zb_, h_m)), P(b, h_m), P(a, h_m)], closed=True, fc=CREMA,
                               ec=TINTA, lw=LW_FINA, zorder=1, joinstyle="miter"))
    # 2) techo de chapa
    techo = mo.cara_sip
    ax.add_patch(MPoly([P(p, mo.z_techo(p)) for p in techo.exterior.coords], closed=True, fc=CREMA, ec=TINTA,
                       lw=LW_MEDIA, zorder=2, joinstyle="miter"))
    if mo.caida is not None:
        c = mo.caida
        w = (-c[1], c[0])
        ws = [p[0] * w[0] + p[1] * w[1] for p in techo.exterior.coords]
        cs = [p[0] * c[0] + p[1] * c[1] for p in techo.exterior.coords]
        x = min(ws) + 0.2
        while x < max(ws) - 0.05:
            ln = LineString([(w[0] * x + c[0] * (min(cs) - 1), w[1] * x + c[1] * (min(cs) - 1)),
                             (w[0] * x + c[0] * (max(cs) + 1), w[1] * x + c[1] * (max(cs) + 1))]).intersection(techo)
            for sg in getattr(ln, "geoms", [ln]):
                if sg.is_empty or sg.geom_type != "LineString":
                    continue
                A, B = sg.coords[0], sg.coords[-1]
                pa, pb = P(A, mo.z_techo(A)), P(B, mo.z_techo(B))
                ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color=TINTA, lw=0.18, zorder=2)
            x += 0.2
    # 3) coronamiento de los muros (espesor del muro visto desde arriba)
    for i, m in enumerate(mo.muros):
        q = mo.banda(i, -ESP_SIP, m.esp_max("EXT"))
        hm = mo.altura_cara(i)
        ax.add_patch(MPoly([P(p, hm) for p in q], closed=True, fc=CREMA, ec=TINTA, lw=LW_FINA, zorder=3,
                           joinstyle="miter"))
    # 4) caras exteriores visibles, de atrás hacia adelante
    orden = sorted(visibles, key=lambda i: dep(((mo.muros[i].p0[0] + mo.muros[i].p1[0]) / 2,
                                                  (mo.muros[i].p0[1] + mo.muros[i].p1[1]) / 2)))
    for rango, i in enumerate(orden):
        m = mo.muros[i]
        t = m.esp_max("EXT")

        def F(s, z, m=m, t=t):
            return P(m.punto(s, t), z)
        pintar_cara(ax, mo, i, F, 10 + 20 * rango)


# ---------------- rótulo
def dibujar_rotulo(h: Hoja, mo: Modelo, x, y, alto, fecha):
    """Logo, nombre del módulo, superficie y fecha de emisión."""
    ax = h.ax
    try:
        import numpy as np
        from matplotlib.colors import to_rgb
        from .logo_datos import logo_array
        im = logo_array().astype(float)
        im = im / (255.0 if im.max() > 1.5 else 1.0)
        blanco = (im[..., :3].min(axis=2) > 0.94)[..., None]        # fondo blanco del logo -> crema
        im = np.where(blanco, np.array(to_rgb(CREMA)), im[..., :3])
        wl = alto * im.shape[1] / im.shape[0]
        ax.imshow(im, extent=(x, x + wl, y, y + alto), aspect="auto", zorder=3, interpolation="antialiased")
        ax.set_xlim(0, HOJA_W)
        ax.set_ylim(0, HOJA_H)
    except Exception:                                        # noqa: BLE001
        ax.text(x, y + alto / 2, "HABITEC", fontsize=16, weight="bold", ha="left", va="center", color=TINTA)
        wl = 40
    tx = x + wl + 7
    ax.plot([tx - 3.5, tx - 3.5], [y + 2, y + alto - 2], color=TINTA, lw=LW_FINA)
    nombre = mo.plano.proyecto.strip()
    if not nombre.upper().startswith("MÓDULO") and not nombre.upper().startswith("MODULO"):
        nombre = f"MÓDULO {nombre}"
    ax.text(tx, y + alto * 0.70, nombre.upper(), fontsize=17, weight="bold", color=TINTA, ha="left", va="center")
    area = f"{mo.contorno.area:.2f}".replace(".", ",")
    ax.text(tx, y + alto * 0.40, f"Área: {area} m²", fontsize=11, color=TINTA, ha="left", va="center")
    ax.text(tx, y + alto * 0.14, f"Emisión {fecha}", fontsize=8.5, color=TINTA, ha="left", va="center")


# --------------------------------------------------------------------------------------------
def hoja_lamina(plano: Plano, cfg_usuario: dict | None, fecha: str):
    """Devuelve (figura A3, avisos)."""
    with plt.rc_context({"text.color": TINTA, "hatch.color": TINTA, "hatch.linewidth": 0.25,
                         "savefig.facecolor": CREMA, "font.family": FUENTE}):
        return _hoja_lamina(plano, cfg_usuario, fecha)


def _hoja_lamina(plano: Plano, cfg_usuario: dict | None, fecha: str):
    cfg = {**CONFIG_BASE, **{k: v for k, v in (cfg_usuario or {}).items() if v is not None}}
    for k in ("espesor_piso", "zingueria_inferior", "zingueria_superior", "zingueria_esquina"):
        cfg[k] = float(cfg[k])
    mo = Modelo(plano, cfg)
    vistas = vistas_a_dibujar(mo)
    cad = cadenas(mo)
    marg = margen_cotas(cad)
    minx, miny, maxx, maxy = mo.cara_ext.bounds
    pw = (maxx - minx) + marg.get("B", 0.3) + marg.get("D", 0.3)       # metros
    ph = (maxy - miny) + marg.get("A", 0.3) + marg.get("C", 0.3)
    anchos = [extension_vista(mo, dl)[1] - extension_vista(mo, dl)[0] for dl, _ in vistas]
    alto_v = mo.alto() + 0.25

    titulos = titulos_vistas(mo, vistas)
    # el frente primero
    vistas = sorted(vistas, key=lambda v: 0 if titulos.get(v[0]) == "VISTA FRENTE" else 1)
    anchos = [extension_vista(mo, dl)[1] - extension_vista(mo, dl)[0] for dl, _ in vistas]
    h = Hoja()
    M = 24.0
    ROT_H = 30.0
    TIT = 9.0                                         # lugar para el título debajo de cada vista (mm)
    GAP = 16.0                                        # aire entre dibujos (mm)
    zx0, zx1 = M, HOJA_W - M
    zy0, zy1 = M + ROT_H + 16, HOJA_H - M             # zona de dibujo, arriba del rótulo
    ancho, alto = zx1 - zx0, zy1 - zy0
    nv = len(vistas)
    # Un solo tamaño para planta y vistas. Se prueban varias disposiciones de las vistas (en columna,
    # en una fila, de a dos por fila) y se queda con la que deja todo más grande.
    def k_de(filas):
        if not filas:
            return min(ancho / pw, alto / ph)
        nf = len(filas)
        ks = [ancho / pw, (alto - nf * TIT - nf * GAP) / (ph + nf * alto_v)]
        for f in filas:
            ks.append((ancho - GAP * (len(f) - 1)) / sum(anchos[j] for j in f))
        return min(ks)
    idx = list(range(nv))
    opciones = [[[j] for j in idx], [idx]] if nv else [[]]
    if nv >= 3:
        opciones.append([idx[j:j + 2] for j in range(0, nv, 2)])
    filas = max(opciones, key=k_de)
    k = k_de(filas) * 0.92                            # un poco más de aire alrededor
    h.k = k
    plan_w, plan_h = pw * k, ph * k
    nf = len(filas)
    vh = nf * (alto_v * k + TIT) + GAP * (nf - 1) if nv else 0
    aire = (alto - plan_h - vh) / (3 if nv else 2)
    gy = zy1 - aire - plan_h
    gx = zx0 + (ancho - plan_w) / 2
    h.ox = gx + marg.get("D", 0.3) * k - minx * k
    h.oy = gy + marg.get("C", 0.3) * k - miny * k
    dibujar_planta(h, mo)
    dibujar_cotas(h, cad)

    def titulo(x, y, dl):
        h.ax.text(x, y, titulos.get(dl, "VISTA"), fontsize=9, weight="bold", color=TINTA, ha="left", va="top")

    vy = zy0 + aire + vh
    for f in filas:
        vy -= alto_v * k
        fila_w = sum(anchos[j] for j in f) * k + GAP * (len(f) - 1)
        vx = zx0 + (ancho - fila_w) / 2
        for j in f:
            dl, caras = vistas[j]
            x = vx
            if len(f) == 1 and dl == "C":            # sola en su fila y mirando desde abajo: alineada con la planta
                x = h.ox + extension_vista(mo, dl)[0] * k
            dibujar_vista(h, mo, dl, caras, x, vy + 0.15 * k)
            titulo(x, vy + 0.15 * k - 4, dl)
            vx += anchos[j] * k + GAP
        vy -= TIT + GAP
    dibujar_rotulo(h, mo, zx0, M, ROT_H, fecha)
    return h.fig, mo.avisos


def resumen_revestimientos(plano: Plano, materiales: dict | None = None, piel_exterior: str = "smart") -> dict:
    """Texto de la carátula sacado del plano (capas REV_EXT_* / REV_INT_*): {"interior": ..., "exterior": ...}.

    Cada material dibujado con los lados donde aparece, por ejemplo «WPC s/ clavaderas (C) · Smart panel en el resto».
    Si hay un solo material, va solo. Sin líneas: smart panel (u OSB) afuera y OSB visto adentro.
    """
    mo = Modelo(plano, {"materiales": materiales or {}})
    if piel_exterior == "osb":
        mo.mats[EXT_DEFECTO] = {**mo.mats[EXT_DEFECTO], "nombre": "OSB (sin smart panel)"}
    letras = [m.letra for m in mo.muros]

    def texto(usos: dict, defecto: str) -> str:
        if len(usos) == 1:
            return mo.mats[next(iter(usos))]["nombre"].split(" (sin capa")[0]
        partes = []
        for clave, donde in usos.items():
            nombre = mo.mats[clave]["nombre"].split(" (sin capa")[0]
            if clave == defecto:
                partes.append(f"{nombre} en el resto")
                continue
            lados = [x for x in letras if x in donde] + (["tabiques"] if "tabiques" in donde else [])
            partes.append(f"{nombre} ({', '.join(lados)})")
        return " · ".join(partes)

    ext, int_ = {}, {}
    for m in mo.muros:
        for clave, _a, _b in m.ext:
            ext.setdefault(clave, set()).add(m.letra)
        for clave, _a, _b in m.int_:
            int_.setdefault(clave, set()).add(m.letra)
    if not mo.tabiques.is_empty:
        for clave, p0, p1 in mo._sueltos:
            mid = Point((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            if mo.tabiques.distance(mid) <= 0.03:
                int_.setdefault(clave, set()).add("tabiques")
    # el material por defecto, al final (lo que se dibujó es lo que importa)
    orden = lambda d, defecto: dict(sorted(d.items(), key=lambda kv: kv[0] == defecto))
    return {"exterior": texto(orden(ext, EXT_DEFECTO), EXT_DEFECTO),
            "interior": texto(orden(int_, INT_DEFECTO), INT_DEFECTO)}


def lados_para_web(plano: Plano) -> list[dict]:
    nombres = {"A": "norte", "B": "este", "C": "sur", "D": "oeste"}
    return [{"letra": l.letra, "largo": round(l.largo, 3), "mira": nombres[l.dir]} for l in plano.lados]
