"""Cómputo de materiales de durlock (placas de yeso, perfiles y tornillería) de un módulo.

Del DXF sale solo la geometría (contorno, caída, vanos y el rectángulo de cada tabique de la capa
TABIQUE_DURLOCK). Lo demás lo define la web (o un dict de configuración):

* caras: {"A": {"int": "p35", "ext": "wpc"}, ...}: revestimiento interior de cada muro, en toda la cara.
  Interiores con durlock: "placa" (pegada al SIP), "omega", "p35", "p70". "sip" = OSB visto (sin durlock).
  "plano" o vacío: lo que dibujan las capas REV_INT_* del DXF (tramos).
* cielorraso: "sip" (sin cielorraso), "placa", "omega", "p35" o "p70". Uno solo por módulo.
* tabiques: {"T01": {"estructura": "35"|"70", "placas": 1|2, "tipo": "estandar"|"verde"|"ignifuga",
  "alto": m o None}}: los tabiques de durlock, con el mismo código que en las láminas de obra in situ.
* reglas: medidas comerciales, separaciones, tornillos por m², desperdicio… (REGLAS_BASE).

Criterio de cálculo (todo editable en `reglas`):

* Alturas: la altura libre bajo el techo (C.ALTO_INTERIOR_ALTO junto al muro alto, C.ALTO_PANEL_BAJO
  junto al de la caída); los muros laterales y los tabiques, en trapecio.
* Largo de cada cara: la cara interior del SIP (de esquina a esquina interior).
* Vanos: se descuentan solo los de más de `umbral_vano` m² (placa, montantes cortados y solera inferior
  en los que llegan al piso). Se suman las jambas (dos montantes enteros) y el dintel y el antepecho
  (solera). Los más chicos se toman como lleno.
* Montantes y omegas: uno cada `sep_muro` (más el del extremo); cada pieza sale de una barra entera si
  entra, y los recortes (sobre el dintel, bajo el antepecho) se suman por metro lineal.
  Los cortos salen primero de los recortes de las barras; lo que no entra, por metro lineal.
  Soleras: por metro lineal (dos por cara). Cielorraso: soleras perimetrales y montantes cada
  `sep_cielorraso` cruzando la luz corta, por metro lineal (se admiten empalmes).
* Perfil de ajuste: del lado interior de cada vano de una cara con durlock, en todo su perímetro (sin el lado
  de abajo si el vano llega al piso), por metro lineal.
* Tornillos: T2 placa-perfil por m² de placa y por capa; T1 solo perfil-perfil (por cada pieza de montante);
  T2 también en la fijación de perfiles al SIP (soleras, montantes y omegas apoyados en el SIP) uno cada `fijacion_cada`
  (en el cielorraso, cada `fijacion_cielorraso`).
* Al final se suma el desperdicio (uno para placas y tornillos y otro para perfiles) y se redondea hacia
  arriba, por unidad.
"""
from __future__ import annotations

import math
from collections import OrderedDict

from shapely.geometry import LineString

from . import config as C
from .lamina import CONFIG_BASE, ESP_SIP

REGLAS_BASE = {
    "placa_ancho": 1.20,            # m
    "placa_largo": 2.40,            # m
    "perfil_largo": 2.60,           # m (soleras, montantes y omegas)
    "sep_muro": 0.40,               # m entre montantes u omegas de muros y tabiques
    "sep_cielorraso": 0.40,         # m entre montantes u omegas del cielorraso (omega directo al SIP)
    "placa_muro": 12.5,             # mm
    "placa_cielorraso": 9.5,        # mm
    "t2_m2": 15,                    # tornillos T2 por m² de placa (por capa)
    "t1_montante": 4,               # tornillos T1 por pieza de montante (dos en cada punta)
    "fijacion_cada": 0.60,          # m entre fijaciones de los perfiles de muros al SIP
    "fijacion_cielorraso": 0.30,    # m entre fijaciones de los perfiles del cielorraso al SIP
    "tornillo_t2": "Tornillo T2",
    "tornillo_t1": "Tornillo T1 punta mecha (perfil-perfil)",
    "tornillo_fijacion": "Tornillo T2",
    "desperdicio_placas": 10,       # % sobre las placas y los tornillos (siempre se pierden)
    "desperdicio_perfiles": 5,      # % sobre los perfiles
    "umbral_vano": 1.0,             # m²: se descuentan los vanos más grandes que esto
}

SISTEMAS = {
    "sip": "OSB visto (sin durlock)",
    "placa": "Durlock pegado",
    "omega": "Durlock sobre omega",
    "p35": "Durlock sobre perfil de 35",
    "p70": "Durlock sobre perfil de 70",
}
CIELORRASOS = {"sip": "Sin cielorraso (SIP visto)", **{k: v for k, v in SISTEMAS.items() if k != "sip"}}
TIPOS_PLACA = {"estandar": "estándar", "verde": "verde (resistente a la humedad)", "ignifuga": "roja (resistente al fuego)"}
PERFILES = {"35": ("Solera 35 mm", "Montante 34 mm"), "70": ("Solera 70 mm", "Montante 69 mm")}


def _n(v, nd=2):
    return f"{v:.{nd}f}".replace(".", ",")


def _esp_txt(mm):
    return (f"{mm:g}").replace(".", ",")


class Computo:
    """Acumula cantidades brutas por material (antes del desperdicio) y el detalle por elemento."""

    def __init__(self, R):
        self.R = R
        self.bruto: "OrderedDict[str, float]" = OrderedDict()
        self.detalle: list[dict] = []
        self.notas: list[str] = []
        self.avisos: list[str] = []

    def sumar(self, material, cant):
        if cant > 1e-9:
            self.bruto[material] = self.bruto.get(material, 0.0) + cant

    def barra(self):
        return f"× {_n(self.R['perfil_largo'])} m"

    def placa(self, esp_mm, tipo="estandar"):
        R = self.R
        return f"Placa de yeso {_esp_txt(esp_mm)} mm {TIPOS_PLACA.get(tipo, tipo)} {_n(R['placa_ancho'])} × {_n(R['placa_largo'])} m"

    def sumar_placa(self, m2, esp_mm, tipo="estandar"):
        R = self.R
        self.sumar(self.placa(esp_mm, tipo), m2 / (R["placa_ancho"] * R["placa_largo"]))

    def lista(self):
        fp = 1 + float(self.R["desperdicio_placas"]) / 100
        fr = 1 + float(self.R["desperdicio_perfiles"]) / 100
        orden = ("Placa", "Solera", "Montante", "Omega", "Perfil de ajuste")
        clave = lambda k: next((j for j, o in enumerate(orden) if k.startswith(o)), len(orden))
        return [(math.ceil(v * (fp if k.startswith(("Placa", "Tornillo")) else fr) - 1e-6), k)
                for k, v in sorted(self.bruto.items(), key=lambda kv: clave(kv[0]))]


# --------------------------------------------------------------------------------------------
# Estructura de una cara plana (muro revestido o tabique)
def _estructura(cp: Computo, L, h0, h1, vanos, sistema, con_soleras, contra_sip, nombre_perfil=("Solera 35 mm", "Montante 34 mm")):
    """Montantes (u omegas) cada sep_muro y soleras de una cara de largo L, alto h0 → h1 (trapecio).
    vanos: [(a, b, z0, z1)] ya filtrados (los que se descuentan). Devuelve (piezas, ml de perfil)."""
    R = cp.R
    PL = R["perfil_largo"]
    sep = max(0.05, float(R["sep_muro"]))
    solera, montante = nombre_perfil
    if sistema == "omega":
        montante = solera = "Omega"
    h = (lambda s: h0 + (h1 - h0) * (s / L if L else 0))
    n = max(1, math.ceil(L / sep - 1e-6))
    pos = [min(k * sep, L) for k in range(n + 1)]
    barras, piezas = 0, 0
    cortos, recortes = [], []                            # piezas sobre dinteles / bajo antepechos; sobrantes de barra

    def entero(alto):
        nonlocal barras, piezas
        nb = math.ceil(alto / PL - 1e-6)
        barras += nb
        piezas += 1
        recortes.append(nb * PL - alto)
    for s in pos:
        dentro = [v for v in vanos if v[0] + 1e-3 < s < v[1] - 1e-3]
        if dentro:
            a, b, z0, z1 = dentro[0]
            if h(s) - z1 > 0.05:
                cortos.append(h(s) - z1)
            if z0 > 0.05:
                cortos.append(z0)
        else:
            entero(h(s))
    for a, b, z0, z1 in vanos:                           # jambas: dos montantes enteros
        for s in (a, b):
            entero(h(s))
    # los cortos salen primero de los recortes de las barras (el más largo en el recorte más chico que lo admite);
    # lo que no entra se pide por metro lineal
    ml_corto, ml_corto_nuevo = sum(cortos), 0.0
    for c in sorted(cortos, reverse=True):
        piezas += 1
        sirve = [r for r in recortes if r >= c - 1e-6]
        if sirve:
            r = min(sirve)
            recortes.remove(r)
            recortes.append(r - c)
        else:
            ml_corto_nuevo += c
    ml_solera = 0.0
    if con_soleras:
        ml_solera = 2 * L
    for a, b, z0, z1 in vanos:
        ml_solera += (b - a) * (1 if z0 <= 0.01 else 2)  # dintel (y antepecho)
        if z0 <= 0.01 and con_soleras:
            ml_solera -= (b - a)                           # la solera inferior se corta en la puerta
    cp.sumar(f"{montante} {cp.barra()}", barras + ml_corto_nuevo / PL)
    cp.sumar(f"{solera} {cp.barra()}", ml_solera / PL)
    ml_total = sum(h(s) for s in pos) + ml_corto + ml_solera
    if sistema != "omega":
        cp.sumar(R["tornillo_t1"], piezas * R["t1_montante"])
    if contra_sip:
        cp.sumar(R["tornillo_fijacion"], ml_total / max(0.1, float(R["fijacion_cada"])))
    elif con_soleras:                                     # tabique: las soleras se fijan a piso y techo
        cp.sumar(R["tornillo_fijacion"], ml_solera / max(0.1, float(R["fijacion_cada"])))
    return piezas, ml_total


def _vanos_cara(cp, lista, umbral):
    """[(a, b, z0, z1, area)] → (descontados [(a, b, z0, z1)], texto)."""
    desc, txt = [], []
    for a, b, z0, z1, vid in lista:
        area = (b - a) * (z1 - z0)
        if area > umbral + 1e-9:
            desc.append((a, b, z0, z1))
            txt.append(f"{vid} ({_n(area)} m²)")
    return desc, ", ".join(txt)


def _cota_vano(v):
    z0 = 0.0 if v.tipo in C.TIPOS_HASTA_PISO else float(v.antepecho or 0.0)
    z1 = v.dintel if v.dintel is not None else (z0 + (v.alto or 2.05))
    return z0, float(z1)


# --------------------------------------------------------------------------------------------
def calcular_materiales(plano, cfg: dict | None = None) -> dict:
    from .obra import Obra
    cfg = dict(cfg or {})
    rg = dict(cfg.get("reglas") or {})
    if rg.get("desperdicio") not in (None, ""):          # un solo valor (versión anterior): vale para los dos
        rg.setdefault("desperdicio_placas", rg["desperdicio"])
        rg.setdefault("desperdicio_perfiles", rg["desperdicio"])
    rg.pop("desperdicio", None)
    R = {**REGLAS_BASE, **{k: v for k, v in rg.items() if v not in (None, "")}}
    for k, v in REGLAS_BASE.items():
        if isinstance(v, (int, float)):
            R[k] = float(R[k])
    cp = Computo(R)
    cfg_mo = {**CONFIG_BASE, **{k: v for k, v in cfg.items() if k in ("materiales", "caras")}}
    obra = Obra(plano, cfg_mo)
    mo = obra.mo
    cp.avisos += [a for a in mo.avisos]
    umbral = R["umbral_vano"]

    # ---- muros (cara interior) ----
    for i, m in enumerate(mo.muros):
        P0 = mo.esq_ini(i, -ESP_SIP, -ESP_SIP)
        P1 = mo.esq_fin(i, -ESP_SIP, -ESP_SIP)
        s0, s1 = sorted((m.s_de(P0), m.s_de(P1)))
        vanos_m = []
        for it in mo.vanos:
            if it["muro"] == i:
                z0, z1 = _cota_vano(it["v"])
                vanos_m.append((it["a"], it["b"], z0, z1, it["v"].id))
        for mat, a, b in m.int_:
            a, b = max(a, s0), min(b, s1)
            if b - a < 0.02 or mat not in SISTEMAS or mat == "sip":
                continue
            L = b - a
            h0 = obra.z_interior(m.punto(a, -ESP_SIP))
            h1 = obra.z_interior(m.punto(b, -ESP_SIP))
            vv = [(max(va, a) - a, min(vb, b) - a, z0, z1, vid) for va, vb, z0, z1, vid in vanos_m
                  if min(vb, b) - max(va, a) > 0.01]
            desc, txt = _vanos_cara(cp, vv, umbral)
            bruta = L * (h0 + h1) / 2
            neta = bruta - sum((vb - va) * (z1 - z0) for va, vb, z0, z1 in desc)
            cp.sumar_placa(neta, R["placa_muro"])
            if mat != "placa":
                cp.sumar(R["tornillo_t2"], neta * R["t2_m2"])
                _estructura(cp, L, h0, h1, desc, mat, con_soleras=(mat != "omega"), contra_sip=True,
                            nombre_perfil=PERFILES["70" if mat == "p70" else "35"])
            # perfil de ajuste: del lado interior de cada vano (de cualquier tamaño), en todo su perímetro;
            # sin el lado de abajo si el vano llega al piso
            ml_aj = sum(2 * (z1 - z0) + (vb - va) * (1 if z0 <= 0.01 else 2) for va, vb, z0, z1, _ in vv)
            cp.sumar(f"Perfil de ajuste {cp.barra()}", ml_aj / R["perfil_largo"])
            cp.detalle.append({"elemento": f"Muro {m.letra}", "sistema": SISTEMAS[mat],
                               "largo": L, "alto": (h0 + h1) / 2, "bruta": bruta, "vanos": txt or "—",
                               "neta": neta, "capas": 1, "ajuste_ml": ml_aj})

    # ---- cielorraso ----
    cie = str(cfg.get("cielorraso") or "sip").lower()
    if cie in CIELORRASOS and cie != "sip":
        pol = mo.cara_sip
        incl = 1.0
        if mo.caida is not None:
            c = mo.caida
            pr = [x * c[0] + y * c[1] for x, y in pol.exterior.coords]
            luz = max(pr) - min(pr)
            if luz > 0:
                incl = math.hypot(1.0, (C.ALTO_INTERIOR_ALTO - C.ALTO_PANEL_BAJO) / luz)
        area = pol.area * incl
        cp.sumar_placa(area, R["placa_cielorraso"])
        if cie != "placa":
            cp.sumar(R["tornillo_t2"], area * R["t2_m2"])
            x0, y0, x1, y1 = pol.bounds
            sep = max(0.05, R["sep_cielorraso"])
            # los montantes cruzan la luz corta y se reparten a lo largo del lado largo
            largo_x = (x1 - x0) >= (y1 - y0)
            a0, a1 = (x0, x1) if largo_x else (y0, y1)
            n = max(1, math.ceil((a1 - a0) / sep - 1e-6))
            ml_m, piezas = 0.0, 0
            for k in range(n + 1):
                t = min(a0 + k * sep, a1)
                t = min(max(t, a0 + 0.005), a1 - 0.005)
                ln = LineString([(t, y0 - 1), (t, y1 + 1)] if largo_x else [(x0 - 1, t), (x1 + 1, t)])
                g = ln.intersection(pol)
                for q in getattr(g, "geoms", [g]):
                    if q.length > 0.02:
                        ml_m += q.length * incl
                        piezas += 1
            PL = R["perfil_largo"]
            if cie == "omega":
                cp.sumar(f"Omega {cp.barra()}", ml_m / PL)
                ml_sol = 0.0
            else:
                sol, mon = PERFILES["70" if cie == "p70" else "35"]
                ml_sol = pol.exterior.length
                cp.sumar(f"{mon} {cp.barra()}", ml_m / PL)
                cp.sumar(f"{sol} {cp.barra()}", ml_sol / PL)
                cp.sumar(R["tornillo_t1"], piezas * R["t1_montante"])
            cp.sumar(R["tornillo_fijacion"], (ml_m + ml_sol) / max(0.1, R["fijacion_cielorraso"]))
        cp.detalle.append({"elemento": "Cielorraso", "sistema": CIELORRASOS[cie], "largo": None, "alto": None,
                           "bruta": area, "vanos": "—", "neta": area, "capas": 1})
    elif cie not in CIELORRASOS:
        cp.avisos.append(f"Cielorraso «{cie}» desconocido: no se computa.")

    # ---- tabiques de durlock ----
    cfg_tab = cfg.get("tabiques") or {}
    for t in obra.tabs:
        if t["tipo"] != "DURLOCK":
            continue
        g = t["geom"]
        x0, y0, x1, y1 = g.bounds
        horiz = (x1 - x0) >= (y1 - y0)
        L = t["largo"]
        p0 = (x0, (y0 + y1) / 2) if horiz else ((x0 + x1) / 2, y0)
        p1 = (x1, (y0 + y1) / 2) if horiz else ((x0 + x1) / 2, y1)
        ct = cfg_tab.get(t["codigo"]) or {}
        est = str(ct.get("estructura") or ("70" if t["esp"] >= 0.09 else "35"))
        est = est if est in PERFILES else "35"
        capas = int(ct.get("placas") or 1)
        capas = 2 if capas >= 2 else 1
        tipo = str(ct.get("tipo") or "estandar")
        alto = ct.get("alto")
        if alto not in (None, "", 0):
            h0 = h1 = float(alto)
        else:
            h0, h1 = obra.z_interior(p0), obra.z_interior(p1)
        vv = []
        for it in mo.vanos:
            r = it["rect"]
            if it["muro"] is None and r.intersects(g.buffer(0.02)):
                a = (r.bounds[0] if horiz else r.bounds[1]) - (x0 if horiz else y0)
                b = (r.bounds[2] if horiz else r.bounds[3]) - (x0 if horiz else y0)
                z0, z1 = _cota_vano(it["v"])
                vv.append((max(0.0, a), min(L, b), z0, z1, it["v"].id))
        desc, txt = _vanos_cara(cp, vv, umbral)
        bruta = L * (h0 + h1) / 2
        neta = bruta - sum((vb - va) * (z1 - z0) for va, vb, z0, z1 in desc)
        cp.sumar_placa(neta * 2 * capas, R["placa_muro"], tipo)
        cp.sumar(R["tornillo_t2"], neta * 2 * capas * R["t2_m2"])
        _estructura(cp, L, h0, h1, desc, "p" + est, con_soleras=True, contra_sip=False, nombre_perfil=PERFILES[est])
        cp.detalle.append({"elemento": f"Tabique {t['codigo']}",
                           "sistema": f"Durlock perfil {est}, {capas} placa{'s' if capas > 1 else ''} por cara, {TIPOS_PLACA.get(tipo, tipo)}",
                           "largo": L, "alto": (h0 + h1) / 2, "bruta": bruta * 2, "vanos": txt or "—",
                           "neta": neta * 2, "capas": capas})

    if not cp.detalle:
        cp.avisos.append("No hay ninguna cara con durlock: elegí el revestimiento interior de las caras o el cielorraso.")
    cp.notas = [
        f"Desperdicio {R['desperdicio_placas']:g} % en placas y tornillos y {R['desperdicio_perfiles']:g} % en perfiles, "
        "redondeado por unidad.",
        f"Se descuentan los vanos de más de {_n(R['umbral_vano'])} m²; los más chicos se toman como lleno.",
        f"Montantes y omegas cada {_n(R['sep_muro'])} m (cielorraso cada {_n(R['sep_cielorraso'])} m); perfiles de {_n(R['perfil_largo'])} m.",
        f"{R['tornillo_t2']}: {R['t2_m2']:g} por m² de placa · {R['tornillo_t1']}: {R['t1_montante']:g} por montante · "
        f"fijación de perfiles al SIP y de tabiques a piso y techo ({R['tornillo_fijacion']}): uno cada {_n(R['fijacion_cada'])} m "
        f"en muros y cada {_n(R['fijacion_cielorraso'])} m en el cielorraso.",
        "Montantes: cada cara con los suyos (dos en cada esquina) y dos jambas por vano descontado; los cortos sobre "
        "dinteles y bajo antepechos salen de los recortes de las barras.",
        "Perfil de ajuste del lado interior de todos los vanos de las caras con durlock, en todo su perímetro "
        "(sin el lado de abajo en los que llegan al piso).",
        "Alturas libres bajo el techo; largos a la cara interior del SIP. Durlock pegado: solo placas (sin adhesivo).",
    ]
    return {"lista": cp.lista(), "detalle": cp.detalle, "notas": cp.notas, "avisos": cp.avisos, "reglas": R,
            "proyecto": plano.proyecto}


# --------------------------------------------------------------------------------------------
# Salidas: PDF (A4 vertical, blanco y negro) y Excel
def pdf_materiales(res: dict, ruta, fecha: str = ""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from .dibujo import GRIS, NEGRO, logo_gris

    W, H = 210.0, 297.0
    filas_lista = [(str(c), m) for c, m in res["lista"]]
    filas_det = []
    for d in res["detalle"]:
        filas_det.append([d["elemento"], d["sistema"], _n(d["largo"]) if d["largo"] else "—",
                          _n(d["alto"]) if d["alto"] else "—", _n(d["bruta"]), d["vanos"], _n(d["neta"])])

    def hoja():
        fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        ax.axis("off")
        im = logo_gris()
        al = 13.0
        an = al * im.shape[1] / im.shape[0]
        ax.imshow(im, extent=(14, 14 + an, H - 12 - al, H - 12), aspect="auto")
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        ax.text(14 + an + 5, H - 16.5, res.get("proyecto") or "", fontsize=14, weight="bold", va="center", color=NEGRO)
        ax.text(14 + an + 5, H - 22, "Materiales de durlock · placas, perfiles y tornillería", fontsize=9, color=GRIS, va="center")
        ax.text(W - 14, H - 16.5, f"Emisión {fecha}" if fecha else "", fontsize=8.5, ha="right", va="center", color=GRIS)
        ax.plot([14, W - 14], [H - 29, H - 29], color=NEGRO, lw=0.8)
        return fig, ax

    figs = []
    fig, ax = hoja()
    figs.append(fig)
    y = H - 38

    def titulo(ax, y, t):
        ax.text(14, y, t, fontsize=10, weight="bold", va="top")
        ax.plot([14, W - 14], [y - 5.5, y - 5.5], color=NEGRO, lw=0.5)
        return y - 9

    y = titulo(ax, y, "LISTA DE COMPRA")
    ax.text(14, y, "Cantidad", fontsize=8, color=GRIS, va="top")
    ax.text(38, y, "Material", fontsize=8, color=GRIS, va="top")
    y -= 5.5
    for c, m in filas_lista:
        ax.text(32, y, c, fontsize=9.5, ha="right", va="top", weight="bold")
        ax.text(38, y, m, fontsize=9.5, va="top")
        ax.plot([14, W - 14], [y - 4.6, y - 4.6], color="#cfcfcf", lw=0.4)
        y -= 6.2
    y -= 6
    y = titulo(ax, y, "DETALLE POR CARA")
    cols = [(14, "Elemento", "left"), (40, "Sistema", "left"), (112, "Largo m", "right"), (127, "Alto m", "right"),
            (144, "Bruta m²", "right"), (147, "Vanos descontados", "left"), (W - 14, "Neta m²", "right")]
    for x, t, ha in cols:
        ax.text(x, y, t, fontsize=7.5, color=GRIS, va="top", ha=ha)
    y -= 5.5
    for f in filas_det:
        if y < 60:
            fig, ax = hoja()
            figs.append(fig)
            y = H - 38
        for (x, _, ha), v in zip(cols, f):
            txt = v if len(v) <= 42 else v[:40] + "…"
            ax.text(x, y, txt, fontsize=7.8, va="top", ha=ha)
        ax.plot([14, W - 14], [y - 4.4, y - 4.4], color="#cfcfcf", lw=0.4)
        y -= 6
    y -= 6
    y = titulo(ax, y, "CRITERIO")
    for t in res["notas"] + [f"Aviso: {a}" for a in res["avisos"]]:
        for ln in _envolver(t, 110):
            ax.text(14, y, ln, fontsize=7.5, va="top", color=NEGRO)
            y -= 4.2
        y -= 1
    for k, f in enumerate(figs, start=1):
        f.axes[0].text(W - 14, 10, f"Hoja {k} de {len(figs)}", fontsize=8, ha="right", color=GRIS)
    with PdfPages(ruta) as pdf:
        for f in figs:
            pdf.savefig(f)
            plt.close(f)


def _envolver(txt, n):
    out, act = [], ""
    for w in txt.split():
        if act and len(act) + 1 + len(w) > n:
            out.append(act)
            act = w
        else:
            act = (act + " " + w).strip()
    return out + ([act] if act else [])


def hoja_xlsx(wb, res: dict, titulo="Materiales"):
    from openpyxl.styles import Alignment, Font, PatternFill
    ws = wb.create_sheet(titulo)
    ws["A1"] = "Durlock"
    ws["A1"].font = Font(bold=True)
    ws["B1"] = res.get("proyecto") or ""
    ws.append(["Cantidad", "Material"])
    for c in ws[2]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="333333")
    for c, m in res["lista"]:
        ws.append([c, m])
    if res["avisos"]:                                  # solo la lista de compra; el detalle queda en el PDF
        ws.append([])
        for t in res["avisos"]:
            ws.append([f"Aviso: {t}"])
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 58
    for row in ws.iter_rows(min_row=3, max_col=1):
        for c in row:
            c.alignment = Alignment(horizontal="left")
    return ws


def xlsx_materiales(res: dict, ruta):
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    hoja_xlsx(wb, res)
    wb.save(ruta)
