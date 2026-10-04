"""Hojas de taller (una por panel) y plano de nomenclatura."""
from __future__ import annotations

from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

from . import config as C
from .dibujo import (AMBAR, AZUL, GRIS, GRIS_CLARO, MARRON, NARANJA, NEGRO, ROJO,
                     VERDE, Lienzo, bloque_texto, cuadro_titulo, elegir_escala, mm,
                     nueva_hoja, PAG_H, PAG_W)
from .modelo import Despiece, PanelMuro, PanelTecho

R55 = C.REBAJE_VANO
TIR = C.TIRANTE_VANO[0]          # 50 mm
GAP = (R55 - TIR) / 2


# ----------------------------------------------------------------------------------
# Planta del módulo (se usa en el plano de nomenclatura y como miniatura)
# ----------------------------------------------------------------------------------
def dibujar_planta(ax, d: Despiece, ox: float, oy: float, esc: float, *,
                   resaltar: str | None = None, detalle: bool = True) -> Lienzo:
    """Dibuja el módulo en planta. ox, oy = posición en papel (mm) de la esquina inferior izquierda."""
    L = Lienzo(ax, ox, oy, esc)
    m = d.plano.modulo
    W, H = m.ancho_x, m.alto_y

    def uv(r):
        return r.x0 - m.x0, r.y0 - m.y0, r.x1 - m.x0, r.y1 - m.y0

    # Techo (línea de trazos por detrás)
    if detalle:
        for t in d.techos:
            u0, v0, u1, v1 = uv(t.rect)
            L.rect(u0, v0, u1, v1, fill=False, ls=(0, (6, 3)), ec=GRIS, lw=0.6, zorder=1)
            cx, cy = (u0 + u1) / 2, (v0 + v1) / 2
            L.texto(cx, cy, t.codigo, fontsize=7, color=GRIS, fontweight="bold")
    elif resaltar and resaltar.startswith("T-"):
        for t in d.techos:
            u0, v0, u1, v1 = uv(t.rect)
            L.rect(u0, v0, u1, v1, fill=(t.codigo == resaltar),
                   fc="#f6c9c4" if t.codigo == resaltar else "none", ec=ROJO if t.codigo == resaltar else GRIS,
                   lw=0.8, ls="-" if t.codigo == resaltar else "--", zorder=1)

    L.rect(0, 0, W, H, fill=False, ec=GRIS, lw=0.5, zorder=1)
    for p in d.muros:
        u0, v0, u1, v1 = uv(p.rect)
        activo = (resaltar == p.codigo)
        fc = "#f2a49c" if activo else ("#cfd8e8" if p.es_ajuste else (AMBAR if p.smart else "#dcdcdc"))
        L.rect(u0, v0, u1, v1, fc=fc, ec=ROJO if activo else NEGRO, lw=1.0 if activo else 0.6, zorder=3)
    if detalle:
        for v in d.plano.vanos:
            u0, v0, u1, v1 = uv(v.rect)
            L.rect(u0, v0, u1, v1, fill=False, hatch="////", ec=AZUL, lw=0.8, zorder=4)

    # Lados A-D
    for lado, (u, v, dx, dy) in {"A": (W / 2, H, 0, 1), "B": (W, H / 2, 1, 0),
                                 "C": (W / 2, 0, 0, -1), "D": (0, H / 2, -1, 0)}.items():
        off = 16 if detalle else 7
        x, y = L.X(u) + dx * off, L.Y(v) + dy * off
        r = 5.0 if detalle else 3.2
        ax.add_patch(Circle((x, y), r, fc="white", ec=NEGRO, lw=0.8, zorder=5))
        ax.text(x, y, lado, ha="center", va="center", fontsize=13 if detalle else 7,
                fontweight="bold", zorder=6)

    # Flecha de caída
    if d.plano.caida_hacia:
        dirs = {"A": (0, 1), "B": (1, 0), "C": (0, -1), "D": (-1, 0)}[d.plano.caida_hacia]
        cx, cy = L.X(W / 2), L.Y(H / 2)
        largo = 14 if detalle else 7
        ax.add_patch(FancyArrowPatch((cx - dirs[0] * largo / 2, cy - dirs[1] * largo / 2),
                                     (cx + dirs[0] * largo / 2, cy + dirs[1] * largo / 2),
                                     arrowstyle="-|>", mutation_scale=9 if detalle else 6,
                                     color=VERDE, lw=1.3, zorder=6))
        if detalle:
            # El texto va al costado de la flecha, perpendicular a ella
            px, py = dirs[1], -dirs[0]
            if px == 0 and py == 0:
                px = 1
            ax.text(cx + (px or 1) * 9 if dirs[0] == 0 else cx, cy + (py * 8 if dirs[0] != 0 else 0) + (0 if dirs[0] != 0 else 0),
                    "CAÍDA", ha="center", va="center", fontsize=7, color=VERDE, fontweight="bold", zorder=6,
                    bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.85))
    return L


def _etiquetas_planta(ax, L: Lienzo, d: Despiece):
    m = d.plano.modulo
    W, H = m.ancho_x, m.alto_y
    for p in d.muros:
        cx, cy = p.rect.centro
        u, v = cx - m.x0, cy - m.y0
        txt = p.codigo
        kw = dict(fontsize=6.8, fontweight="bold", zorder=7)
        if p.lado == "A":
            L.ax.text(L.X(u), L.Y(H) + 3.2, txt, ha="center", va="bottom", **kw)
        elif p.lado == "C":
            L.ax.text(L.X(u), L.Y(0) - 3.2, txt, ha="center", va="top", **kw)
        elif p.lado == "B":
            L.ax.text(L.X(W) + 3.2, L.Y(v), txt, ha="left", va="center", **kw)
        else:
            L.ax.text(L.X(0) - 3.2, L.Y(v), txt, ha="right", va="center", **kw)
    for i, vn in enumerate(d.plano.vanos):
        cx, cy = vn.rect.centro
        # etiqueta del vano hacia el interior del módulo
        lado_dentro = {"A": (0, -1), "B": (-1, 0), "C": (0, 1), "D": (1, 0)}
        lado = None
        for p in d.muros:
            if any(x.vano_id == vn.id for x in p.vanos):
                lado = p.lado
                break
        dx, dy = lado_dentro.get(lado, (0, 0))
        L.ax.text(L.X(cx - m.x0) + dx * 6, L.Y(cy - m.y0) + dy * 6, vn.id, fontsize=6.5, color=AZUL,
                  ha="center", va="center", zorder=7, fontweight="bold",
                  bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.85))


def plano_nomenclatura(d: Despiece, fecha: str):
    fig, ax = nueva_hoja()
    m = d.plano.modulo
    W, H = m.ancho_x, m.alto_y
    esc = elegir_escala(W, H, 175, 180)
    ox = 15 + 40 + (190 - W * 1000 / esc) / 2 - 10
    oy = 22 + 25 + (200 - H * 1000 / esc) / 2 - 8
    L = dibujar_planta(ax, d, ox, oy, esc, detalle=True)
    _etiquetas_planta(ax, L, d)
    # Cotas generales
    L.cota_h(0, W, 0, -34, f"{mm(W)}")
    L.cota_v(0, H, 0, -34, f"{mm(H)}")
    cuadro_titulo(ax, d.plano.proyecto, "PLANTA", "Nomenclatura de paneles · vista en planta",
                  esc, fecha, "Plano de nomenclatura")

    # Tabla de paneles a la derecha
    x0, y = 262, PAG_H - 40
    lineas = []
    lineas.append(("Cód.   Ancho  Alto   Observaciones", GRIS))
    for p in d.muros:
        obs = []
        if p.es_ajuste:
            obs.append("ajuste")
        if p.smart:
            obs.append("smart")
        if p.vanos:
            obs.append("vanos " + ",".join(v.vano_id for v in p.vanos))
        lineas.append((f"{p.codigo:<6} {mm(p.largo):>5} {mm(p.alto):>5}  {' · '.join(obs)}", NEGRO))
    for t in d.techos:
        obs = "ajuste" if t.es_ajuste else ""
        lineas.append((f"{t.codigo:<6} {mm(t.ancho):>5} {mm(t.largo):>5}  techo {obs}".rstrip(), NEGRO))
    y = _bloque_mono(ax, x0, y, "PANELES (medidas en mm)", lineas)
    y -= 4
    n_muros, n_techo = len(d.muros), len(d.techos)
    resumen = [(f"Paneles de muro: {n_muros}   ·   Paneles de techo: {n_techo}", NEGRO),
               (f"Caída hacia el lado {d.plano.caida_hacia or '—'}  "
                f"(muro bajo {mm(C.ALTO_PANEL_BAJO)} mm, el resto {mm(C.ALTO_PANEL)} mm)", NEGRO)]
    y = bloque_texto(ax, x0, y, "RESUMEN", resumen, ancho=145)
    y -= 4
    if d.alertas:
        y = _bloque_alertas(ax, x0, y, d.alertas, max_lineas=9)
    # Referencias, en la columna derecha, abajo
    ley_x, ley_y = 262, 58
    ax.text(ley_x, ley_y + 8, "REFERENCIAS", fontsize=7.5, fontweight="bold", ha="left", va="center")
    for i, (txt, fc, hatch) in enumerate([("Panel SIP", "#dcdcdc", None), ("Pieza de ajuste (también con smart panel)", "#cfd8e8", None),
                                          ("Con smart panel", AMBAR, None), ("Vano", "white", "////")]):
        yy = ley_y - i * 6
        ax.add_patch(Rectangle((ley_x, yy - 2), 9, 4.5, fc=fc, ec=AZUL if hatch else NEGRO, lw=0.6, hatch=hatch))
        ax.text(ley_x + 12, yy + 0.2, txt, fontsize=6.8, ha="left", va="center")
    ax.text(ley_x, ley_y - 28,
            "Lados vistos en planta: A arriba, B derecha, C abajo, D izquierda.\n"
            "Numeración: A y C de izquierda a derecha; B y D de arriba hacia abajo.",
            fontsize=6.5, color=GRIS, ha="left", va="top")
    return fig


def _bloque_mono(ax, x, y, titulo, lineas):
    ax.text(x, y, titulo, fontsize=8.5, fontweight="bold", ha="left", va="top")
    ax.plot([x, x + 145], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    y -= 8.2
    for txt, color in lineas:
        ax.text(x, y, txt, fontsize=6.8, ha="left", va="top", color=color, family="DejaVu Sans Mono")
        y -= 3.9
    return y


def _bloque_alertas(ax, x, y, alertas, max_lineas=8):
    ax.text(x, y, f"ALERTAS ({len(alertas)})", fontsize=8.5, fontweight="bold", ha="left", va="top", color=ROJO)
    ax.plot([x, x + 145], [y - 5.2, y - 5.2], color=ROJO, lw=0.6)
    y -= 8.2
    for a in alertas[:max_lineas]:
        txt = _ajustar(a, 78)
        ax.text(x, y, "• " + txt, fontsize=6.8, ha="left", va="top", color=ROJO)
        y -= 4.0 * (1 + txt.count("\n"))
    if len(alertas) > max_lineas:
        ax.text(x, y, f"… y {len(alertas) - max_lineas} más (ver informe de validación)", fontsize=6.5,
                color=ROJO, ha="left", va="top")
        y -= 4
    return y


def _ajustar(txt: str, n: int) -> str:
    """Parte un texto en líneas de n caracteres como máximo."""
    palabras, lineas, actual = txt.split(), [], ""
    for w in palabras:
        if len(actual) + len(w) + 1 > n:
            lineas.append(actual)
            actual = w
        else:
            actual = (actual + " " + w).strip()
    lineas.append(actual)
    return "\n  ".join(lineas)


# ----------------------------------------------------------------------------------
# Hoja de un panel de muro
# ----------------------------------------------------------------------------------
def _largo_txt(txt: str, fs: float) -> float:
    """Largo aproximado en papel (mm) de la línea más larga de un texto."""
    return max(len(l) for l in txt.split("\n")) * fs * 0.2


def _encajar(txt: str, fs: float, disp: float) -> str:
    """Parte el texto en líneas para que entre en `disp` mm de papel."""
    n = max(6, int(disp / (fs * 0.2)))
    out = []
    for linea in txt.split("\n"):
        actual = ""
        for w in linea.split(" "):
            if actual and len(actual) + 1 + len(w) > n:
                out.append(actual)
                actual = w
            else:
                actual = (actual + " " + w).strip()
        out.append(actual)
    return "\n".join(out)


def _vecinos(d: Despiece, p: PanelMuro) -> tuple[str, str]:
    """Panel vecino a izquierda y derecha en la vista interior."""
    mismos = [q for q in d.muros if q.lado == p.lado]
    n = len(mismos)
    # A y B: la numeración coincide con la lectura de izquierda a derecha.
    # C y D: la numeración corre al revés.
    coincide = p.lado in ("A", "B")
    esquinas = {"A": ("D", "B"), "B": ("A", "C"), "C": ("B", "D"), "D": ("C", "A")}[p.lado]

    def codigo(num: int, lado_esq: str) -> str:
        if 1 <= num <= n:
            return f"{p.lado}-{num:02d}"
        return f"esquina {lado_esq}"

    if coincide:
        return codigo(p.numero - 1, esquinas[0]), codigo(p.numero + 1, esquinas[1])
    return codigo(p.numero + 1, esquinas[0]), codigo(p.numero - 1, esquinas[1])


def hoja_muro(d: Despiece, p: PanelMuro, fecha: str, pagina: str = ""):
    fig, ax = nueva_hoja()
    esc = elegir_escala(p.largo, p.alto, 190, 188)
    anc, alt = p.largo * 1000 / esc, p.alto * 1000 / esc
    ox = 15 + 34 + (190 - anc) / 2
    oy = 20 + 30 + (188 - alt) / 2
    L = Lienzo(ax, ox, oy, esc)

    tipo = "SIP con smart panel" if p.smart else "SIP simple"
    cuadro_titulo(ax, d.plano.proyecto, p.codigo, f"Lado {p.lado} · panel {p.numero} · {tipo} · vista interior",
                  esc, fecha, pagina)

    # Base del panel
    L.rect(0, 0, p.largo, p.alto, fc=AMBAR if p.smart else "white", ec=NEGRO, lw=1.8, zorder=2)
    if p.smart:
        paso = 0.15
        if p.sentido_rev == "vertical":
            u = paso
            while u < p.largo:
                L.linea(u, 0, u, p.alto, color="#d9b86a", lw=0.4, zorder=2)
                u += paso
        else:
            v = paso
            while v < p.alto:
                L.linea(0, v, p.largo, v, color="#d9b86a", lw=0.4, zorder=2)
                v += paso
    # Rebaje perimetral
    r = C.REBAJE_PERIMETRAL
    L.rect(r, r, p.largo - r, p.alto - r, fill=False, ls=(0, (5, 2.5)), ec=AZUL, lw=0.9, zorder=3)
    # Machimbrado en bordes verticales
    for u0 in (0, p.largo - C.MACHIMBRE_ANCHO):
        L.rect(u0, 0, u0 + C.MACHIMBRE_ANCHO, p.alto, fill=False, hatch="////", ec=GRIS, lw=0, zorder=3)

    # Bordes verticales: tirante clavado en este panel, rebaje libre que lo recibe, o tapa de esquina
    tw = C.TIRANTE_CHICO[0]
    for borde, (clase, dato) in p.bordes.items():
        u0 = 0.0 if borde == "izq" else p.largo - tw
        if clase == "tirante":
            L.rect(u0, 0, u0 + tw, p.alto, fc=MARRON, ec=MARRON, alpha=0.8, lw=0.5, zorder=4)
            largo_t, corto_t, color = f"tirante 25×50 clavado · junta con {dato}", f"tirante · junta {dato}", MARRON
        elif clase == "recibe":
            L.rect(u0, 0, u0 + tw, p.alto, fc=AMBAR, ec=NARANJA, ls=(0, (3, 2)), lw=0.9, zorder=4)
            largo_t, corto_t, color = f"rebaje libre · recibe el tirante de {dato}", f"rebaje libre · {dato}", NARANJA
        else:
            L.rect(u0, 0, u0 + tw, p.alto, fc="#5b3a1a", ec="#5b3a1a", hatch="////", alpha=0.85, lw=0.5, zorder=4)
            largo_t, corto_t, color = f"tapa 25×50 · esquina {dato}", f"tapa · esq. {dato}", "#5b3a1a"
        # Tramos del borde que no están ocupados por un vano
        zona = (u0 - R55, u0 + tw + 0.10)
        ocupados = sorted((vp.v0 - R55, vp.v1 + R55) for vp in p.vanos
                          if vp.u0 - R55 < zona[1] and vp.u1 + R55 > zona[0])
        libres, cur = [], 0.0
        for a, b in ocupados:
            if a > cur:
                libres.append((cur, a))
            cur = max(cur, b)
        if cur < p.alto:
            libres.append((cur, p.alto))
        if not libres:
            continue
        a, b = max(libres, key=lambda t: t[1] - t[0])
        for txt in (largo_t, corto_t):
            if _largo_txt(txt, 6) * esc / 1000 <= (b - a) - 0.04:
                L.texto(u0 + (0.065 if borde == "izq" else -0.04), (a + b) / 2, txt, rotation=90,
                        fontsize=6, color=color, zorder=6, ha="center")
                break

    # Vanos
    for vp in p.vanos:
        ru0 = vp.u0 - (R55 if vp.jamba_izq else 0)
        ru1 = vp.u1 + (R55 if vp.jamba_der else 0)
        rv0 = vp.v0 - (R55 if vp.tiene_antepecho else 0)
        rv1 = vp.v1 + R55
        L.rect(ru0, rv0, ru1, rv1, fc=AMBAR if p.smart else "white", ec=NARANJA, ls=(0, (4, 2)), lw=0.9, zorder=4)
        L.rect(vp.u0, vp.v0, vp.u1, vp.v1, fc="white", ec=ROJO, lw=1.5, zorder=5)
        tir = dict(fc=MARRON, ec=MARRON, alpha=0.75, lw=0.5, zorder=5)
        libre = dict(fc=AMBAR if p.smart else "white", ec=NARANJA, ls=(0, (2, 1.5)), lw=0.7, zorder=5)
        v_ini = rv0 + (GAP if vp.tiene_antepecho else 0)
        v_fin = rv1 - GAP
        if vp.jamba_izq:
            L.rect(vp.u0 - R55 + GAP, v_ini, vp.u0 - GAP, v_fin, **tir)
        if vp.jamba_der:
            L.rect(vp.u1 + GAP, v_ini, vp.u1 + R55 - GAP, v_fin, **tir)
        L.rect(vp.u0, vp.v1 + GAP, vp.u1, vp.v1 + GAP + TIR,
               **(tir if vp.tirante_dintel_taller else libre))
        if vp.tiene_antepecho:
            L.rect(vp.u0, vp.v0 - R55 + GAP, vp.u1, vp.v0 - GAP,
                   **(tir if vp.tirante_antepecho_taller else libre))
        cx, cy = (vp.u0 + vp.u1) / 2, (vp.v0 + vp.v1) / 2
        disp = L.L(vp.u1 - vp.u0) - 2                       # ancho útil en papel (mm)
        fs_id = 11 if disp >= 14 else 8
        L.texto(cx, cy + 0.08, vp.vano_id, fontsize=fs_id, fontweight="bold", color=ROJO, zorder=6)
        det = f"{mm(vp.ancho_total)} × {mm(vp.alto_total)}"
        if not vp.completo:
            det += "\n(continúa en el panel vecino)"
        L.texto(cx, cy - 0.06, _encajar(det, 6.3, disp), fontsize=6.3, color=ROJO, zorder=6, linespacing=1.3)

    # Vecinos arriba (en paneles angostos, "INTERIOR" sube a una segunda fila)
    izq, der = _vecinos(d, p)
    if anc < 70:
        izq, der = izq.replace("esquina ", "esq. "), der.replace("esquina ", "esq. ")
    L.ax.text(L.X(0), L.Y(p.alto) + 3, f"◄ {izq}", fontsize=7, ha="left", va="bottom", color=GRIS)
    L.ax.text(L.X(p.largo), L.Y(p.alto) + 3, f"{der} ►", fontsize=7, ha="right", va="bottom", color=GRIS)
    L.ax.text(L.X(p.largo / 2), L.Y(p.alto) + (3 if anc >= 70 else 8), "INTERIOR", fontsize=7, ha="center",
              va="bottom", color=GRIS, fontweight="bold")

    # Cotas horizontales (cadena + total)
    us = sorted({0.0, p.largo} | {x for vp in p.vanos for x in (vp.u0, vp.u1)})
    if len(us) > 2:
        for a, b in zip(us, us[1:]):
            if b - a > 0.0005:
                L.cota_h(a, b, 0, -7, mm(b - a))
        L.cota_h(0, p.largo, 0, -16, mm(p.largo), fs=7.5)
    else:
        L.cota_h(0, p.largo, 0, -7, mm(p.largo), fs=7.5)
    # Cotas verticales
    vs = sorted({0.0, p.alto} | {x for vp in p.vanos for x in (vp.v0, vp.v1)})
    if len(vs) > 2:
        for a, b in zip(vs, vs[1:]):
            if b - a > 0.0005:
                L.cota_v(a, b, 0, -7, mm(b - a))
        L.cota_v(0, p.alto, 0, -16, mm(p.alto), fs=7.5)
    else:
        L.cota_v(0, p.alto, 0, -7, mm(p.alto), fs=7.5)

    # ----- Bloque derecho -----------------------------------------------------------
    x0, y = 262, PAG_H - 40
    datos = [
        (f"Dimensiones: {mm(p.largo)} × {mm(p.alto)} × {mm(p.espesor)} mm", NEGRO),
        ("Composición: OSB 9 mm + EPS 70 mm + OSB 9 mm", NEGRO),
        (f"Tipo de panel: {'pieza de AJUSTE (cortar a medida)' if p.es_ajuste else 'estándar'}", NEGRO),
        (f"Revestimiento: " + (f"smart panel, cara {p.cara_rev}, sentido {p.sentido_rev}" if p.smart else "no"), NEGRO),
        (f"Rebaje perimetral: {mm(C.REBAJE_PERIMETRAL)} mm de EPS en los 4 bordes", NEGRO),
        (f"Machimbrado: bordes verticales, cara exterior\n"
         f"   (aprox. {C.MACHIMBRE_PROF * 1000:g} mm de prof. × {C.MACHIMBRE_ANCHO * 1000:g} mm — a confirmar)", NEGRO),
    ]
    def _txt_borde(clase, dato):
        return {"tirante": f"trae el tirante 25×50 clavado (junta con {dato})",
                "recibe": f"rebaje libre: recibe el tirante de {dato}",
                "tapa": f"trae la tapa 25×50 (esquina {dato})"}[clase]
    for borde, nombre in (("izq", "izquierdo"), ("der", "derecho")):
        if borde in p.bordes:
            clase, dato = p.bordes[borde]
            datos.append((f"Borde {nombre}: {_txt_borde(clase, dato)}", MARRON if clase != "recibe" else NARANJA))
    if p.alto < C.ALTO_PANEL - C.TOL:
        datos.append((f"Alto reducido: lado de la caída ({mm(C.ALTO_PANEL)} − "
                      f"{mm(C.ALTO_PANEL - C.ALTO_PANEL_BAJO)} mm)", NEGRO))
    y = bloque_texto(ax, x0, y, "DATOS DEL PANEL", datos, ancho=145)
    y -= 3

    if p.vanos:
        h = C.HUELGO_VANO
        lin = []
        for vp in p.vanos:
            aw = vp.ancho_total - 2 * h
            ah = vp.alto_total - h * (2 if vp.tiene_antepecho else 1)
            ante = (vp.v0 + h) if vp.tiene_antepecho else 0.0
            lin.append((f"{vp.vano_id} · {C.TIPOS_VANO[vp.tipo]}", NEGRO))
            lin.append((f"   Abertura {mm(aw)} × {mm(ah)}  →  vano de corte {mm(vp.ancho_total)} × {mm(vp.alto_total)} "
                        f"(+{h * 1000:g} mm por lado" + ("" if vp.tiene_antepecho else ", sin huelgo contra el piso") + ")", NEGRO))
            if vp.tiene_antepecho:
                lin.append((f"   Antepecho (a abertura): {mm(ante)} mm", NEGRO))
            otros = [q.codigo for q in d.muros if q is not p and any(x.vano_id == vp.vano_id for x in q.vanos)]
            if vp.completo:
                lin.append(("   Vano completo en este panel. Tirantes 50×70 en taller:", NEGRO))
                lin.append(("   jambas, dintel" + (" y antepecho." if vp.tiene_antepecho else "."), MARRON))
            else:
                lado_j = "izquierda" if vp.jamba_izq else "derecha"
                lin.append((f"   Vano compartido con {', '.join(otros)}. En taller: solo la jamba {lado_j}.", NEGRO))
                lin.append(("   Dintel" + (" y antepecho" if vp.tiene_antepecho else "") +
                            f": rebaje de {mm(R55)} mm libre, se completa in situ.", NARANJA))
        y = bloque_texto(ax, x0, y, "VANOS", lin, ancho=145, fs=7)
        y -= 3
    if p.alertas:
        y = _bloque_alertas(ax, x0, y, p.alertas, max_lineas=6)
        y -= 3

    # Leyenda
    _leyenda(ax, 15, 19)
    # Miniatura
    esc_m = elegir_escala(d.plano.modulo.ancho_x, d.plano.modulo.alto_y, 70, 72)
    mw = d.plano.modulo.ancho_x * 1000 / esc_m
    ax.text(262, 112, "UBICACIÓN EN EL MÓDULO", fontsize=7.5, fontweight="bold", ha="left", va="top")
    dibujar_planta(ax, d, 272, 22, esc_m, resaltar=p.codigo, detalle=False)
    return fig


def _leyenda(ax, x, y):
    """Leyenda en tres filas, por debajo del dibujo del panel."""
    ax.text(x, y + 8, "REFERENCIAS", fontsize=7, fontweight="bold", ha="left", va="center")
    items = [
        ("línea", NEGRO, "-", "Contorno del panel"),
        ("línea", AZUL, (0, (5, 2.5)), "Rebaje perimetral 30 mm (EPS)"),
        ("línea", ROJO, "-", "Vano de corte (abertura + huelgo)"),
        ("línea", NARANJA, (0, (4, 2)), "Rebaje de 55 mm alrededor del vano"),
        ("caja", MARRON, None, "Tirante colocado en taller (50×70 o 25×50)"),
        ("libre", NARANJA, (0, (3, 2)), "Rebaje libre (sin EPS): recibe tirante en obra"),
        ("caja", "#5b3a1a", None, "Tapa 25×50 de esquina"),
    ]
    pos = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2)]
    for (tipo, color, ls, txt), (c, f) in zip(items, pos):
        xx, yy = x + 24 + c * 78, y + 9 - f * 5.5 - 3
        if tipo == "línea":
            ax.plot([xx, xx + 10], [yy, yy], color=color, lw=1.1, ls=ls)
        elif tipo == "libre":
            ax.add_patch(Rectangle((xx + 1, yy - 1.5), 8, 3, fc=AMBAR, ec=color, ls=ls, lw=0.9))
        else:
            ax.add_patch(Rectangle((xx + 1, yy - 1.5), 8, 3, fc=color, ec=color, alpha=0.8))
        ax.text(xx + 12, yy, txt, fontsize=6.3, ha="left", va="center")


# ----------------------------------------------------------------------------------
# Hoja de un panel de techo
# ----------------------------------------------------------------------------------
def hoja_techo(d: Despiece, t: PanelTecho, fecha: str, pagina: str = ""):
    fig, ax = nueva_hoja()
    esc = elegir_escala(t.largo, t.ancho, 215, 170)
    anc, alt = t.largo * 1000 / esc, t.ancho * 1000 / esc
    ox = 15 + 22 + (215 - anc) / 2
    oy = 52 + (180 - alt) / 2
    L = Lienzo(ax, ox, oy, esc)
    cuadro_titulo(ax, d.plano.proyecto, t.codigo,
                  f"Panel de techo {t.numero} · SIP · vista desde arriba", esc, fecha, pagina)

    # El panel se dibuja girado: el sentido de la caída va en horizontal y la caída queda a la derecha.
    # Posición de cada lado de planta en la hoja (giro puro, sin espejo):
    idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    pos = {l: ("derecha", "abajo", "izquierda", "arriba")[(idx[l] - idx[t.caida_hacia]) % 4] for l in idx}
    lado_en = {v: k for k, v in pos.items()}                  # "derecha" -> lado de planta

    L.rect(0, 0, t.largo, t.ancho, fc="white", ec=NEGRO, lw=1.8, zorder=2)
    r = C.REBAJE_PERIMETRAL
    tw, th = C.TIRANTE_CHICO
    trazo = dict(color=AZUL, lw=0.9, ls=(0, (5, 2.5)), zorder=3)
    tir = dict(fc=MARRON, ec=MARRON, alpha=0.75, lw=0.5, zorder=4)

    # (posición en la hoja) -> (segmento de rebaje, banda del tirante)
    seg = {"izquierda": ((r, r, r, t.ancho - r), (0, 0, tw, t.ancho)),
           "derecha": ((t.largo - r, r, t.largo - r, t.ancho - r), (t.largo - tw, 0, t.largo, t.ancho)),
           "abajo": ((r, r, t.largo - r, r), (0, 0, t.largo, tw)),
           "arriba": ((r, t.ancho - r, t.largo - r, t.ancho - r), (0, t.ancho - tw, t.largo, t.ancho))}
    for lugar, (linea, banda) in seg.items():
        lado = lado_en[lugar]
        if t.en_caida and lado == t.caida_hacia:
            continue                                   # el lado de la caída no lleva rebaje
        L.linea(*linea, **trazo)
        estado = t.tirantes.get(lado)
        if estado == "lleva":
            L.rect(*banda, **tir)
        elif estado == "recibe":
            L.rect(*banda, fill=False, ec=NARANJA, ls=(0, (3, 2)), lw=0.9, zorder=4)
        elif estado == "mixto":
            L.rect(*banda, fill=False, hatch="////", ec=GRIS, lw=0.5, zorder=4)
    if t.en_caida:
        L.texto(t.largo - 0.03, t.ancho / 2, f"LADO {t.caida_hacia} (CAÍDA)\nsin rebaje\nse refila in situ",
                fontsize=6.5, color=VERDE, ha="right", fontweight="bold", zorder=5)
    # Etiquetas de las uniones
    for lugar, (linea, banda) in seg.items():
        lado = lado_en[lugar]
        if lado not in t.uniones:
            continue
        txt = "+".join(t.uniones[lado])
        estado = t.tirantes.get(lado)
        cx, cy = (banda[0] + banda[2]) / 2, (banda[1] + banda[3]) / 2
        if estado == "lleva":
            etiqueta, color = f"tirante 25×50 clavado · junta con {txt}", MARRON
        elif estado == "recibe":
            etiqueta, color = f"rebaje libre · recibe el tirante de {txt}", NARANJA
        else:
            etiqueta, color = f"unión con {txt}", GRIS
        if lugar in ("izquierda", "derecha"):
            L.texto(cx + (0.08 if lugar == "izquierda" else -0.08), cy, etiqueta, fontsize=6, color=color,
                    rotation=90, zorder=5)
        else:
            L.texto(cx, cy + (0.07 if lugar == "abajo" else -0.07), etiqueta, fontsize=6, color=color, zorder=5)
    L.ax.add_patch(FancyArrowPatch((L.X(t.largo) + 4, L.Y(t.ancho / 2) - 14), (L.X(t.largo) + 22, L.Y(t.ancho / 2) - 14),
                                   arrowstyle="-|>", mutation_scale=9, color=VERDE, lw=1.3))
    L.ax.text(L.X(t.largo) + 13, L.Y(t.ancho / 2) - 19, "caída", fontsize=6.5, color=VERDE, ha="center")
    L.cota_h(0, t.largo, 0, -9, mm(t.largo), fs=7.5)
    L.cota_v(0, t.ancho, 0, -9, mm(t.ancho), fs=7.5)

    x0, y = 262, PAG_H - 40
    lados_rebaje = 3 if t.en_caida else 4
    datos = [
        (f"Dimensiones: {mm(t.largo)} (en el sentido de la caída) × {mm(t.ancho)} (a lo ancho) × {mm(C.ESPESOR_PANEL)} mm", NEGRO),
        ("Composición: OSB 9 mm + EPS 70 mm + OSB 9 mm", NEGRO),
        (f"Tipo de panel: {'pieza de AJUSTE (cortar a medida)' if t.es_ajuste else 'estándar'}", NEGRO),
        (f"Rebaje perimetral: {mm(C.REBAJE_PERIMETRAL)} mm de EPS en {lados_rebaje} lados" +
         (f";\n   el lado de la caída ({t.caida_hacia}) no lleva: sobresale del filo del muro" if t.en_caida else ""), NEGRO),
    ]
    lleva = [v for l, v in t.uniones.items() if t.tirantes.get(l) == "lleva"]
    recibe = [v for l, v in t.uniones.items() if t.tirantes.get(l) == "recibe"]
    if lleva:
        datos.append((f"Trae el tirante 25×50 clavado hacia: {'; '.join('+'.join(v) for v in lleva)}", MARRON))
    if recibe:
        datos.append((f"Rebaje libre (recibe el tirante de): {'; '.join('+'.join(v) for v in recibe)}", NARANJA))
    datos += [("Las medidas son las del plano de planta.", GRIS),
              ("El panel se dibuja girado: la caída queda a la derecha.", GRIS)]
    y = bloque_texto(ax, x0, y, "DATOS DEL PANEL", datos, ancho=145)
    if t.alertas:
        y -= 3
        _bloque_alertas(ax, x0, y, t.alertas, max_lineas=6)
    esc_m = elegir_escala(d.plano.modulo.ancho_x, d.plano.modulo.alto_y, 70, 72)
    ax.text(262, 112, "UBICACIÓN EN EL MÓDULO", fontsize=7.5, fontweight="bold", ha="left", va="top")
    dibujar_planta(ax, d, 272, 22, esc_m, resaltar=t.codigo, detalle=False)
    return fig
