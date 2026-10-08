"""Hojas de taller (una por panel) y plano de nomenclatura."""
from __future__ import annotations

from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle

from . import config as C
from .dibujo import (AJUSTE, AMBAR, AZUL, GRIS, TABLAS, TR_LIBRE, TR_PERIMETRAL, TR_VANO, GRIS_CLARO, MARRON, NARANJA, NEGRO, ROJO,
                     TIRANTE, VERDE, ESCALA_PANEL, Lienzo, bloque_texto, cuadro_titulo, elegir_escala, mm, partir,
                     nueva_hoja, PAG_H, PAG_W)
from .contorno import punto_interior, texto_caida
from .modelo import Despiece, PanelMuro, PanelTecho

HATCH_REBAJE = "////"        # rebaje de 30 mm: rayado a 45°
HATCH_MIXTA = "\\\\\\\\"          # unión mixta (techo): rayado en el otro sentido
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
            L.rect(u0, v0, u1, v1, fill=False, ls=(0, (6, 3)), ec=GRIS, lw=0.7, zorder=1)
            cx, cy = (u0 + u1) / 2, (v0 + v1) / 2
            L.texto(cx, cy, t.codigo, fontsize=8.5, color=GRIS, fontweight="bold")
    elif resaltar and resaltar.startswith("T-"):
        for t in d.techos:
            u0, v0, u1, v1 = uv(t.rect)
            L.rect(u0, v0, u1, v1, fill=(t.codigo == resaltar),
                   fc="#9a9a9a" if t.codigo == resaltar else "none", ec=ROJO if t.codigo == resaltar else GRIS,
                   lw=0.8, ls="-" if t.codigo == resaltar else "--", zorder=1)

    contorno = d.plano.contorno or [(m.x0, m.y0), (m.x1, m.y0), (m.x1, m.y1), (m.x0, m.y1)]
    ax.add_patch(Polygon([(L.X(x - m.x0), L.Y(y - m.y0)) for x, y in contorno], closed=True,
                         fill=False, ec=GRIS, lw=0.5, zorder=1))
    for p in d.muros:
        u0, v0, u1, v1 = uv(p.rect)
        activo = (resaltar == p.codigo)
        fc = "#7a7a7a" if activo else (AJUSTE if p.es_ajuste else (AMBAR if p.smart else "white"))
        L.rect(u0, v0, u1, v1, fc=fc, ec=ROJO if activo else NEGRO, lw=2.0 if activo else 0.6, zorder=3)
    if detalle:
        for v in d.plano.vanos:
            u0, v0, u1, v1 = uv(v.rect)
            L.rect(u0, v0, u1, v1, fc="white", ec=NEGRO, hatch="////", lw=0.8, zorder=4)

    # Letras de los lados (círculos que no se pisan entre sí)
    r = 3.9 if detalle else 2.0
    off = 12.5 if detalle else 5.0
    circ = []
    for l in d.plano.lados:
        cx_, cy_ = l.centro
        u, v = cx_ - m.x0, cy_ - m.y0
        dx, dy = {"A": (0, 1), "B": (1, 0), "C": (0, -1), "D": (-1, 0)}[l.dir]
        if l.largo < 1.0 and l.convexo_ini != l.convexo_fin:
            # lado corto con un extremo convexo: la letra se corre hacia ese extremo para no pisar los códigos
            extremo = l.ini if l.convexo_ini else l.fin
            otro = l.fin if l.convexo_ini else l.ini
            u, v = extremo[0] - m.x0, extremo[1] - m.y0
            ex, ey = extremo[0] - otro[0], extremo[1] - otro[1]
            n_ = (ex * ex + ey * ey) ** 0.5 or 1.0
            circ.append([L.X(u) + dx * off * 0.5 + ex / n_ * (r + 1.5), L.Y(v) + dy * off * 0.5 + ey / n_ * (r + 1.5),
                         l.letra, (dx, dy)])
            continue
        circ.append([L.X(u) + dx * off, L.Y(v) + dy * off, l.letra, (dx, dy)])
    for _ in range(60):
        mov = False
        for i in range(len(circ)):
            for j in range(i + 1, len(circ)):
                ddx, ddy = circ[j][0] - circ[i][0], circ[j][1] - circ[i][1]
                dist = (ddx * ddx + ddy * ddy) ** 0.5
                if dist < 2 * r + 1.2:
                    if dist < 1e-6:
                        ddx, ddy, dist = 1.0, 0.0, 1.0
                    f = (2 * r + 1.2 - dist) / 2 / dist
                    circ[i][0] -= ddx * f; circ[i][1] -= ddy * f
                    circ[j][0] += ddx * f; circ[j][1] += ddy * f
                    mov = True
        if not mov:
            break
    for x, y, letra, _ in circ:
        ax.add_patch(Circle((x, y), r, fc="white", ec=NEGRO, lw=0.8, zorder=5))
        ax.text(x, y - 0.05, letra, ha="center", va="center", fontsize=(11 if detalle else 7.5),
                fontweight="bold", zorder=6)

    # Flecha de caída
    if d.plano.caida_hacia:
        dirs = {"A": (0, 1), "B": (1, 0), "C": (0, -1), "D": (-1, 0)}[d.plano.caida_hacia]
        pix, piy = punto_interior(d)
        cx, cy = L.X(pix - m.x0), L.Y(piy - m.y0)
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
        kw = dict(fontsize=8, fontweight="bold", zorder=7)
        r = p.rect
        if p.lado == "I":                      # tabique interior: el código va junto al panel, sobre fondo blanco
            L.ax.text(L.X(u), L.Y(v), txt, ha="center", va="center", fontsize=7.2, fontweight="bold", zorder=7,
                      bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))
        elif p.dir == "A":
            L.ax.text(L.X(u), L.Y(r.y1 - m.y0) + 3.2, txt, ha="center", va="bottom", **kw)
        elif p.dir == "C":
            L.ax.text(L.X(u), L.Y(r.y0 - m.y0) - 3.2, txt, ha="center", va="top", **kw)
        elif p.dir == "B":
            L.ax.text(L.X(r.x1 - m.x0) + 3.2, L.Y(v), txt, ha="left", va="center", **kw)
        else:
            if p.largo < 0.8:                  # panel corto: el código va hacia el interior, pegado a su extremo
                L.ax.text(L.X(r.x1 - m.x0) + 3.2, L.Y(r.y0 - m.y0 + 0.30), txt, ha="left", va="center", **kw)
            else:
                L.ax.text(L.X(r.x0 - m.x0) - 3.2, L.Y(v), txt, ha="right", va="center", **kw)
    for i, vn in enumerate(d.plano.vanos):
        cx, cy = vn.rect.centro
        # etiqueta del vano hacia el interior del módulo
        lado_dentro = {"A": (0, -1), "B": (-1, 0), "C": (0, 1), "D": (1, 0)}
        lado = None
        for p in d.muros:
            if any(x.vano_id == vn.id for x in p.vanos):
                lado = p.dir if p.lado != "I" else None
                break
        dx, dy = lado_dentro.get(lado, (0, 0))
        L.ax.text(L.X(cx - m.x0) + dx * 6, L.Y(cy - m.y0) + dy * 6, vn.id, fontsize=7.5, color=AZUL,
                  ha="center", va="center", zorder=7, fontweight="bold",
                  bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.85))


XR = 190.0                 # columna derecha de las hojas (mm de papel)
WR = 97.0                  # ancho de la columna derecha


def plano_nomenclatura(d: Despiece, fecha: str, pagina: str = "Hoja 2"):
    fig, ax = nueva_hoja()
    m = d.plano.modulo
    W, H = m.ancho_x, m.alto_y
    esc = elegir_escala(W, H, 122, 105)
    ox = 47 + (122 - W * 1000 / esc) / 2
    oy = 56 + (105 - H * 1000 / esc) / 2
    L = dibujar_planta(ax, d, ox, oy, esc, detalle=True)
    _etiquetas_planta(ax, L, d)
    # Cotas generales
    xs = sorted({round(x - m.x0, 4) for x, _ in d.plano.contorno})
    ys = sorted({round(y - m.y0, 4) for _, y in d.plano.contorno})
    if len(xs) > 2:                                  # contorno con escalones: cotas parciales
        for a, b in zip(xs, xs[1:]):
            L.cota_h(a, b, 0, -20, mm(b - a))
    if len(ys) > 2:
        for a, b in zip(ys, ys[1:]):
            L.cota_v(a, b, 0, -20, mm(b - a))
    L.cota_h(0, W, 0, -31, f"{mm(W)}")
    L.cota_v(0, H, 0, -31, f"{mm(H)}")
    cuadro_titulo(ax, d.plano.proyecto, "PLANTA", "",
                  esc, fecha, pagina)

    # Tabla de paneles a la derecha, en dos columnas
    x0, y = XR, PAG_H - 40
    filas = []
    for p in d.muros:
        obs = []
        if p.es_ajuste:
            obs.append("ajuste")
        if p.vanos:
            obs.append(",".join(v.vano_id for v in p.vanos))
        filas.append(f"{p.codigo:<5}{mm(p.largo):>5}×{mm(p.alto):<5}{' '.join(obs)}"[:33])
    for t in d.techos:
        filas.append(f"{t.codigo:<5}{mm(t.ancho):>5}×{mm(t.largo):<5}{'ajuste' if t.es_ajuste else ''}"[:33])
    ax.text(x0, y, "PANELES (mm)", fontsize=9.5, fontweight="bold", ha="left", va="top")
    ax.plot([x0, x0 + WR], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    y -= 8.2
    mitad = (len(filas) + 1) // 2
    paso = 3.9
    for k, txt in enumerate(filas):
        col, fila = divmod(k, mitad)
        ax.text(x0 + col * (WR / 2 + 1), y - fila * paso, txt, fontsize=7.2, ha="left", va="top",
                family="DejaVu Sans Mono")
    y -= mitad * paso + 5
    n_muros, n_techo = len(d.muros), len(d.techos)
    resumen = [(f"Muros: {n_muros}  ·  Techo: {n_techo}", NEGRO),
               (f"Caída hacia el lado {texto_caida(d.plano)} "
                f"(muro bajo {mm(C.ALTO_PANEL_BAJO)} mm, el resto {mm(C.ALTO_PANEL)} mm)", NEGRO)]
    y = bloque_texto(ax, x0, y, "RESUMEN", resumen, ancho=WR)
    _leyenda_plano(ax, XR, 57)
    return fig


def _bloque_mono(ax, x, y, titulo, lineas):
    ax.text(x, y, titulo, fontsize=9.5, fontweight="bold", ha="left", va="top")
    ax.plot([x, x + WR], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    y -= 8.2
    for txt, color in lineas:
        ax.text(x, y, txt, fontsize=7.2, ha="left", va="top", color=color, family="DejaVu Sans Mono")
        y -= 3.9
    return y


def _bloque_alertas(ax, x, y, alertas, max_lineas=8):
    ax.text(x, y, f"ALERTAS ({len(alertas)})", fontsize=9.5, fontweight="bold", ha="left", va="top", color=NEGRO)
    ax.plot([x, x + WR], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    y -= 8.0
    for a in alertas[:max_lineas]:
        for k, ln in enumerate(partir("• " + a, 58, "   ")):
            ax.text(x, y, ln, fontsize=8, ha="left", va="top", color=NEGRO)
            y -= 4.0
    if len(alertas) > max_lineas:
        ax.text(x, y, f"… y {len(alertas) - max_lineas} más (ver informe de validación)", fontsize=7.5,
                color=NEGRO, ha="left", va="top")
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
    """Qué hay a la izquierda y a la derecha del panel en la vista interior."""
    def texto(borde: str) -> str:
        clase, dato = p.bordes.get(borde, ("", ""))
        if clase in ("tirante", "recibe"):
            return dato
        if clase == "tapa":
            return f"esquina {p.lado}-{dato}"
        return "extremo libre"
    return texto("izq"), texto("der")


def hoja_muro(d: Despiece, p: PanelMuro, fecha: str, pagina: str = ""):
    fig, ax = nueva_hoja()
    esc = ESCALA_PANEL
    anc, alt = p.largo * 1000 / esc, p.alto * 1000 / esc
    ox = max(34.0, 172.0 - anc)           # dibujo pegado a la derecha de su zona; a la izquierda va la miniatura
    oy = 34.0
    L = Lienzo(ax, ox, oy, esc)

    cuadro_titulo(ax, d.plano.proyecto, p.codigo, "Vista interior", esc, fecha, pagina)

    # Base del panel
    L.rect(0, 0, p.largo, p.alto, fc="white", ec="none", lw=0, zorder=2)
    if p.smart:
        paso = 0.15
        if p.sentido_rev == "vertical":
            u = paso
            while u < p.largo:
                L.linea(u, 0, u, p.alto, color="#7d7d7d", lw=0.5, zorder=2)
                u += paso
        else:
            v = paso
            while v < p.alto:
                L.linea(0, v, p.largo, v, color="#7d7d7d", lw=0.5, zorder=2)
                v += paso
    # Rebaje perimetral
    r = C.REBAJE_PERIMETRAL
    L.rect(r, r, p.largo - r, p.alto - r, fill=False, ls=TR_PERIMETRAL, ec=AZUL, lw=1.0, zorder=3)
    # Bordes verticales: tirante clavado en este panel, rebaje libre que lo recibe, o tapa de esquina
    tw = C.TIRANTE_CHICO[0]
    for borde, (clase, dato) in p.bordes.items():
        u0 = 0.0 if borde == "izq" else p.largo - tw
        if clase == "tirante":
            # tirante 50×70: 25 mm dentro de este panel y 25 mm que sobresalen hacia el vecino
            ua = -tw if borde == "izq" else p.largo - tw
            hueco = sorted((v.v0 - (R55 if v.tiene_antepecho else 0.0), v.v1 + R55) for v in p.vanos
                           if (v.u0 <= C.TOL if borde == "izq" else v.u1 >= p.largo - C.TOL))
            cur = 0.0
            for h0, h1 in hueco + [(p.alto, p.alto)]:       # el tirante no cruza la abertura de un vano
                if h0 > cur + 1e-6:
                    L.rect(ua, max(cur, 0.0), ua + 2 * tw, h0, fc=TIRANTE, ec=NEGRO, lw=0.6, zorder=4)
                cur = max(cur, h1)
            largo_t, corto_t, color = f"tirante 50×70 clavado · junta con {dato}", f"tirante 50×70 · junta {dato}", NEGRO
        elif clase == "recibe":
            L.rect(u0, 0, u0 + tw, p.alto, fc="white", ec=NEGRO, hatch=HATCH_REBAJE, lw=0.8, zorder=4)
            largo_t, corto_t, color = "rebaje 30 mm", "rebaje 30 mm", NEGRO
        elif clase == "libre":
            L.rect(u0, 0, u0 + tw, p.alto, fc="white", ec=NEGRO, hatch=HATCH_REBAJE, lw=0.8, zorder=4)
            largo_t, corto_t, color = "rebaje 30 mm · se une en obra", "rebaje 30 mm", NEGRO
        else:
            L.rect(u0, 0, u0 + tw, p.alto, fc=TIRANTE, ec=NEGRO, lw=0.6, zorder=4)
            largo_t, corto_t, color = f"tapa 25×70 · esquina {p.lado}-{dato}", f"tapa 25×70 · esq. {p.lado}-{dato}", NEGRO
        # Tramos del borde que no están ocupados por un vano
        zona = (u0 - 0.17, u0 + tw + 0.17)
        ocupados = sorted((vp.v0 - R55, vp.v1 + R55) for vp in p.vanos
                          if vp.u0 - R55 < zona[1] and vp.u1 + R55 > zona[0])
        ocupados += [(jj.v_ini - GAP, jj.v_fin + GAP) for jj in p.jambas_junta if jj.borde == borde]
        ocupados.sort()
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
            if _largo_txt(txt, 7) * esc / 1000 <= (b - a) - 0.04:
                L.texto(u0 + (0.065 if borde == "izq" else -0.04), (a + b) / 2, txt, rotation=90,
                        fontsize=7, color=color, zorder=6, ha="center")
                break
        # Machimbrado del smart panel (convención: borde derecho macho, borde izquierdo hembra)
        if p.smart and clase in ("tirante", "recibe"):
            txt = "smart panel " + ("macho" if borde == "der" else "hembra")
            if _largo_txt(txt, 7) * esc / 1000 <= (b - a) - 0.04:
                L.texto(u0 + (0.14 if borde == "izq" else -0.12), (a + b) / 2, txt, rotation=90,
                        fontsize=7, color=NEGRO, zorder=6, ha="center")

    # Tirantes de jamba (50×70) que este panel trae para un vano del panel vecino
    hg = C.HUELGO_VANO
    for jj in p.jambas_junta:
        izq = jj.borde == "izq"
        r0 = hg if izq else p.largo - hg - R55
        rv0 = jj.v_ini - (GAP if jj.tiene_antepecho else 0.0)
        rv1 = jj.v_fin + GAP
        L.rect(0 if izq else p.largo - hg, jj.v0, hg if izq else p.largo, jj.v1,
               fc="white", ec=ROJO, lw=1.2, zorder=5)
        L.rect(r0, rv0, r0 + R55, rv1, fc="white", ec=NARANJA,
               ls=TR_VANO, lw=1.0, zorder=5)
        L.rect(r0 + GAP, jj.v_ini, r0 + GAP + TIR, jj.v_fin, fc=TIRANTE, ec=NEGRO, lw=0.6, zorder=6)
        for txt in (f"tirante 50×70 · jamba de {jj.vano_id} · encastrado", f"tirante 50×70 · {jj.vano_id}"):
            if _largo_txt(txt, 7) * esc / 1000 <= (jj.v_fin - jj.v_ini) - 0.04:
                L.texto(r0 + R55 + 0.035 if izq else r0 - 0.035,
                        (jj.v_ini + jj.v_fin) / 2, txt, rotation=90, fontsize=7, color=MARRON, zorder=6)
                break

    # Vanos
    for vp in p.vanos:
        ru0 = vp.u0 - (R55 if vp.jamba_izq else 0)
        ru1 = vp.u1 + (R55 if vp.jamba_der else 0)
        rv0 = vp.v0 - (R55 if vp.tiene_antepecho else 0)
        rv1 = vp.v1 + R55
        L.rect(ru0, rv0, ru1, rv1, fc="white", ec=NARANJA, ls=TR_VANO, lw=1.0, zorder=4)
        # Vano: hueco rayado en diagonal, con contorno grueso
        L.rect(vp.u0, vp.v0, vp.u1, vp.v1, fc="white", ec="white", lw=0, zorder=5)
        tb = C.TOL
        lados_vano = [(vp.u0, vp.v0, vp.u1, vp.v0, vp.v0 <= tb), (vp.u0, vp.v1, vp.u1, vp.v1, vp.v1 >= p.alto - tb),
                      (vp.u0, vp.v0, vp.u0, vp.v1, vp.u0 <= tb), (vp.u1, vp.v0, vp.u1, vp.v1, vp.u1 >= p.largo - tb)]
        for ua, va, ub, vb, en_borde in lados_vano:
            if not en_borde:                         # los lados sobre el borde los resuelve el contorno (línea fina)
                L.linea(ua, va, ub, vb, color=NEGRO, lw=1.8, zorder=5.1, solid_capstyle="projecting")
        tir = dict(fc=TIRANTE, ec=NEGRO, lw=0.6, zorder=5)
        libre = dict(fc="white", ec=NEGRO, hatch=HATCH_REBAJE, lw=0.8, zorder=5)
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
        if not vp.tirante_dintel_taller and L.L(vp.u1 - vp.u0) > 24:
            L.texto((vp.u0 + vp.u1) / 2, vp.v1 + R55 + 0.03, "rebaje 55 mm · dintel", fontsize=7, color=NEGRO,
                    va="bottom", zorder=6)
        if vp.tiene_antepecho and not vp.tirante_antepecho_taller and L.L(vp.u1 - vp.u0) > 26:
            L.texto((vp.u0 + vp.u1) / 2, vp.v0 - R55 - 0.03, "rebaje 55 mm · antepecho", fontsize=7, color=NEGRO,
                    va="top", zorder=6)
        cx, cy = (vp.u0 + vp.u1) / 2, (vp.v0 + vp.v1) / 2
        disp = L.L(vp.u1 - vp.u0) - 2                       # ancho útil en papel (mm)
        fs_id = 13 if disp >= 16 else 9
        caja = dict(fc="white", ec="none", pad=1.5)
        L.texto(cx, cy + 0.03, vp.vano_id, fontsize=fs_id, fontweight="bold", color=ROJO, zorder=6, bbox=caja, va="bottom")
        det = f"{mm(vp.ancho_total)} × {mm(vp.alto_total)}"
        if not vp.completo:
            otros = [q.codigo for q in d.muros if q is not p and any(x.vano_id == vp.vano_id for x in q.vanos)]
            det += "\ncontinúa en " + ", ".join(otros)
        L.texto(cx, cy - 0.03, _encajar(det, 7.5, disp), fontsize=7.5, color=ROJO, zorder=6, linespacing=1.3, bbox=caja, va="top")

    _contorno_panel(L, p)                                                   # contorno por encima de todo

    # Vecinos arriba
    izq, der = _vecinos(d, p)
    if anc < 85:
        izq, der = izq.replace("esquina ", "esq. "), der.replace("esquina ", "esq. ")
    L.ax.text(L.X(0), L.Y(p.alto) + 3, f"◄ {izq}", fontsize=8, ha="left", va="bottom", color=GRIS)
    L.ax.text(L.X(p.largo), L.Y(p.alto) + 3, f"{der} ►", fontsize=8, ha="right", va="bottom", color=GRIS)

    # Cotas horizontales (cadena + total). Las guías de un borde de vano salen de la arista del vano.
    guia_u = {}
    for vp in p.vanos:
        for x in (vp.u0, vp.u1):
            guia_u[round(x, 4)] = min(guia_u.get(round(x, 4), vp.v0), vp.v0)
    us = sorted({0.0, p.largo} | {x for vp in p.vanos for x in (vp.u0, vp.u1)})
    if len(us) > 2:
        for a, b in zip(us, us[1:]):
            if b - a > 0.0005:
                L.cota_h(a, b, 0, -7, mm(b - a), va=guia_u.get(round(a, 4), 0.0), vb=guia_u.get(round(b, 4), 0.0))
        L.cota_h(0, p.largo, 0, -16, mm(p.largo), fs=7.5)
    else:
        L.cota_h(0, p.largo, 0, -7, mm(p.largo), fs=7.5)
    # Cotas verticales
    guia_v = {}
    for vp in p.vanos:
        for y in (vp.v0, vp.v1):
            guia_v[round(y, 4)] = min(guia_v.get(round(y, 4), vp.u0), vp.u0)
    vs = sorted({0.0, p.alto} | {x for vp in p.vanos for x in (vp.v0, vp.v1)})
    if len(vs) > 2:
        for a, b in zip(vs, vs[1:]):
            if b - a > 0.0005:
                L.cota_v(a, b, 0, -7, mm(b - a), ua=guia_v.get(round(a, 4), 0.0), ub=guia_v.get(round(b, 4), 0.0))
        L.cota_v(0, p.alto, 0, -16, mm(p.alto), fs=7.5)
    else:
        L.cota_v(0, p.alto, 0, -7, mm(p.alto), fs=7.5)

    # ----- Bloque derecho -----------------------------------------------------------
    x0, y = XR, PAG_H - 40
    datos = [
        (f"Dimensiones: {mm(p.largo)} × {mm(p.alto)} mm", NEGRO),
        ("Composición: " + ("smart panel 9 mm + EPS 70 mm + OSB 9 mm" if p.smart else "OSB 9 mm + EPS 70 mm + OSB 9 mm"), NEGRO),
        ("Tipo: " + ("pieza de AJUSTE (cortar a medida)" if p.es_ajuste else "estándar"), NEGRO),
    ]
    if p.smart:
        datos.append((f"Smart panel: sentido {p.sentido_rev}", NEGRO))
    y = bloque_texto(ax, x0, y, "DATOS DEL PANEL", datos, ancho=WR)
    y -= 3

    if p.vanos:
        h = C.HUELGO_VANO
        lin = []
        for vp in p.vanos:
            aw = vp.ancho_total - 2 * h
            ah = vp.alto_total - h * (2 if vp.tiene_antepecho else 1)
            ante = (vp.v0 + h) if vp.tiene_antepecho else 0.0
            lin.append((f"{vp.vano_id} · {C.TIPOS_VANO[vp.tipo]}: abertura {mm(aw)} × {mm(ah)}", NEGRO))
            lin.append((f"   Corte {mm(vp.ancho_total)} × {mm(vp.alto_total)}"
                        + (f" · antepecho {mm(ante)}" if vp.tiene_antepecho else ""), NEGRO))
            if not vp.completo:
                otros = [q.codigo for q in d.muros if q is not p and any(x.vano_id == vp.vano_id for x in q.vanos)]
                lin.append((f"   Compartido con {', '.join(otros)}; se completa in situ.", NEGRO))
        y = bloque_texto(ax, x0, y, "VANOS", lin, ancho=WR, fs=8.2, interlinea=4.2)
        y -= 3
    if y < 58:
        print(f"  (aviso de diseño: el texto de {p.codigo} llega a y={y:.0f} mm y puede pisar las referencias)")

    _leyenda(ax, XR, 56)
    _miniatura(ax, d, p.codigo, 12, PAG_H - 38, min(ox - 30, 62), 52)
    return fig


def _contorno_panel(L: Lienzo, p: PanelMuro):
    """Contorno del panel: grueso donde hay material; donde un vano llega al borde no se dibuja (panel en L)."""
    tb = C.TOL
    def tramos(a, b, cubiertos):
        out, cur = [], a
        for c0, c1 in sorted(cubiertos):
            if c0 > cur:
                out.append((cur, c0, True))
            out.append((max(c0, cur), c1, False))
            cur = max(cur, c1)
        if cur < b:
            out.append((cur, b, True))
        return out
    lados = [  # (coordenada fija, a lo largo, es horizontal, vanos que tocan ese borde)
        (0.0, p.largo, True, 0.0, [(v.u0, v.u1) for v in p.vanos if v.v0 <= tb]),
        (0.0, p.largo, True, p.alto, [(v.u0, v.u1) for v in p.vanos if v.v1 >= p.alto - tb]),
        (0.0, p.alto, False, 0.0, [(v.v0, v.v1) for v in p.vanos if v.u0 <= tb]),
        (0.0, p.alto, False, p.largo, [(v.v0, v.v1) for v in p.vanos if v.u1 >= p.largo - tb]),
    ]
    for a, b, horiz, fija, cub in lados:
        for t0, t1, grueso in tramos(a, b, cub):
            if not grueso:
                continue                                  # sobre la abertura no se dibuja el borde
            kw = dict(color=NEGRO, lw=1.8, zorder=20, solid_capstyle="projecting")
            if horiz:
                L.linea(t0, fija, t1, fija, **kw)
            else:
                L.linea(fija, t0, fija, t1, **kw)


def _miniatura(ax, d: Despiece, codigo: str, x: float, y_sup: float, w: float, h: float):
    """Ubicación del panel en el módulo: dibujo chico (sin título) que entra en el recuadro w × h."""
    m = d.plano.modulo
    w = max(w, 40.0)
    mg = 8.0                         # lugar para los círculos de las letras
    esc_m = elegir_escala(m.ancho_x, m.alto_y, w - 2 * mg, h - 2 * mg)
    mw, mh = m.ancho_x * 1000 / esc_m, m.alto_y * 1000 / esc_m
    dibujar_planta(ax, d, x + mg + (w - 2 * mg - mw) / 2, y_sup - mg - mh - (h - 2 * mg - mh) / 2, esc_m,
                   resaltar=codigo, detalle=False)


def _leyenda(ax, x, y):
    """Referencias en dos columnas (columna derecha, abajo). Cada elemento se distingue por su
    tipo de línea o trama, así se lee igual impreso en blanco y negro."""
    ax.text(x, y, "REFERENCIAS", fontsize=9.5, fontweight="bold", ha="left", va="top")
    ax.plot([x, x + WR], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    items = [
        ("linea", NEGRO, "-", 1.8, "Contorno del panel"),
        ("linea", NEGRO, TR_PERIMETRAL, 1.0, "Rebaje perimetral 30 mm"),
        ("vano", NEGRO, None, 0, "Vano de corte"),
        ("linea", NEGRO, TR_VANO, 1.0, "Rebaje 55 mm del vano"),
        ("caja", TIRANTE, None, 0, "Tirante 50×70 o 25×70"),
        ("libre", NEGRO, "-", 0, "Rebaje libre"),
    ]
    for k, (tipo, color, ls, lw, txt) in enumerate(items):
        c, f = divmod(k, 4)
        xx, yy = x + c * (WR / 2 + 1), y - 11.5 - f * 6.0
        if tipo == "linea":
            ax.plot([xx, xx + 9], [yy, yy], color=color, lw=lw, ls=ls)
        elif tipo == "libre":
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc="white", ec=NEGRO, hatch=HATCH_REBAJE, lw=0.8))
        elif tipo == "vano":
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc="white", ec=color, lw=1.8))
        elif tipo == "tapa":
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc="white", ec=NEGRO, hatch="xxxx", lw=0.5))
        elif tipo == "mach":
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc="white", ec=color, hatch="||||", lw=0))
        else:
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc=color, ec=NEGRO, lw=0.6))
        ax.text(xx + 11.5, yy, txt, fontsize=7.6, ha="left", va="center")


def _leyenda_plano(ax, x, y):
    ax.text(x, y, "REFERENCIAS", fontsize=9.5, fontweight="bold", ha="left", va="top")
    ax.plot([x, x + WR], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    items = [("panel", "Panel de muro"), ("ajuste", "Pieza de ajuste"), ("vano", "Vano"), ("techo", "Panel de techo")]
    for k, (tipo, txt) in enumerate(items):
        c, f = divmod(k, 2)
        xx, yy = x + c * (WR / 2 + 1), y - 11.5 - f * 6.0
        if tipo == "techo":
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fill=False, ec=GRIS, ls=(0, (4, 2)), lw=0.8))
        else:
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc=AJUSTE if tipo == "ajuste" else "white", ec=NEGRO,
                                   hatch="////" if tipo == "vano" else None, lw=0.6 if tipo != "vano" else 0.8))
        ax.text(xx + 11.5, yy, txt, fontsize=7.6, ha="left", va="center")


# ----------------------------------------------------------------------------------
# Hoja de un panel de techo
# ----------------------------------------------------------------------------------
def hoja_techo(d: Despiece, t: PanelTecho, fecha: str, pagina: str = ""):
    fig, ax = nueva_hoja()
    esc = ESCALA_PANEL
    anc, alt = t.largo * 1000 / esc, t.ancho * 1000 / esc
    ox = 22 + max(0.0, (140 - anc) / 2)
    oy = 84.0 + max(0.0, (86 - alt) / 2)
    L = Lienzo(ax, ox, oy, esc)
    cuadro_titulo(ax, d.plano.proyecto, t.codigo, "", esc, fecha, pagina)

    # El panel se dibuja girado: el sentido de la caída va en horizontal y la caída queda a la derecha.
    # Posición de cada lado de planta en la hoja (giro puro, sin espejo):
    idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    pos = {l: ("derecha", "abajo", "izquierda", "arriba")[(idx[l] - idx[t.caida_hacia]) % 4] for l in idx}
    lado_en = {v: k for k, v in pos.items()}                  # "derecha" -> lado de planta

    L.rect(0, 0, t.largo, t.ancho, fc="white", ec="none", lw=0, zorder=2)
    r = C.REBAJE_PERIMETRAL
    tw, th = C.TIRANTE_CHICO
    trazo = dict(color=AZUL, lw=1.0, ls=TR_PERIMETRAL, zorder=3)
    tir = dict(fc=TIRANTE, ec=NEGRO, lw=0.6, zorder=4)

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
            # tirante 50×70: 25 mm dentro del panel y 25 mm que sobresalen hacia el vecino
            u0_, v0_, u1_, v1_ = banda
            if lugar == "izquierda":
                u0_ = -tw
            elif lugar == "derecha":
                u1_ = t.largo + tw
            elif lugar == "abajo":
                v0_ = -tw
            else:
                v1_ = t.ancho + tw
            L.rect(u0_, v0_, u1_, v1_, **tir)
        elif estado == "recibe":
            L.rect(*banda, fc="white", ec=NEGRO, hatch=HATCH_REBAJE, lw=0.8, zorder=4)
        elif estado == "mixto":
            L.rect(*banda, fc="white", hatch=HATCH_MIXTA, ec=GRIS, lw=0.6, zorder=4)
    if t.en_caida:
        cartel = next((c for c in (f"LADO {texto_caida(d.plano)} (CAÍDA)\nsin rebaje\nse refila in situ",
                                   f"LADO {texto_caida(d.plano)} (CAÍDA)\nsin rebaje",
                                   f"LADO {texto_caida(d.plano)}\n(CAÍDA)")
                       if _largo_txt(c, 7.5) * esc / 1000 <= t.largo - 0.1
                       and (c.count("\n") + 1) * 7.5 * 0.45 * esc / 1000 <= t.ancho - 0.08), None)
        if cartel:
            L.texto(t.largo - 0.03, t.ancho / 2, cartel, fontsize=7.5, color=VERDE, ha="right",
                    fontweight="bold", zorder=5)
    # Etiquetas de las uniones
    for lugar, (linea, banda) in seg.items():
        lado = lado_en[lugar]
        if lado not in t.uniones:
            continue
        txt = "+".join(t.uniones[lado])
        estado = t.tirantes.get(lado)
        cx, cy = (banda[0] + banda[2]) / 2, (banda[1] + banda[3]) / 2
        if estado == "lleva":
            opciones = [f"tirante 50×70 clavado · junta con {txt}", f"tirante 50×70 · {txt}", "tirante 50×70"]
        elif estado == "recibe":
            opciones = ["rebaje 30 mm"]
        else:
            opciones = [f"unión con {txt}", f"unión {txt}"]
        color = NEGRO if estado in ("lleva", "recibe") else GRIS
        vertical = lugar in ("izquierda", "derecha")
        espacio = (t.ancho if vertical else t.largo) - 0.06          # lo que mide el lado donde va el texto
        etiqueta = next((o for o in opciones if _largo_txt(o, 7.5) * esc / 1000 <= espacio), None)
        if etiqueta is None:
            continue
        if vertical:
            L.texto(cx + (0.08 if lugar == "izquierda" else -0.08), cy, etiqueta, fontsize=7.5, color=color,
                    rotation=90, zorder=5)
        else:
            L.texto(cx, cy + (0.07 if lugar == "abajo" else -0.07), etiqueta, fontsize=7.5, color=color, zorder=5)
    L.ax.add_patch(FancyArrowPatch((L.X(t.largo) + 4, L.Y(t.ancho / 2) - 14), (L.X(t.largo) + 22, L.Y(t.ancho / 2) - 14),
                                   arrowstyle="-|>", mutation_scale=9, color=VERDE, lw=1.3))
    L.ax.text(L.X(t.largo) + 13, L.Y(t.ancho / 2) - 19, "caída", fontsize=8, color=VERDE, ha="center")
    L.rect(0, 0, t.largo, t.ancho, fill=False, ec=NEGRO, lw=1.8, zorder=20)   # contorno por encima de todo
    L.cota_h(0, t.largo, 0, -9, mm(t.largo), fs=7.5)
    L.cota_v(0, t.ancho, 0, -9, mm(t.ancho), fs=7.5)

    x0, y = XR, PAG_H - 40
    datos = [
        (f"Dimensiones: {mm(t.largo)} × {mm(t.ancho)} mm", NEGRO),
        ("Composición: OSB 9 mm + EPS 70 mm + OSB 9 mm", NEGRO),
        ("Tipo: " + ("pieza de AJUSTE (cortar a medida)" if t.es_ajuste else "estándar"), NEGRO),
    ]
    y = bloque_texto(ax, x0, y, "DATOS DEL PANEL", datos, ancho=WR)
    if y < 58:
        print(f"  (aviso de diseño: el texto de {t.codigo} llega a y={y:.0f} mm y puede pisar las referencias)")
    _leyenda_techo(ax, XR, 56)
    _miniatura(ax, d, t.codigo, 12, 70, 62, 52)
    return fig


def _leyenda_techo(ax, x, y):
    ax.text(x, y, "REFERENCIAS", fontsize=9.5, fontweight="bold", ha="left", va="top")
    ax.plot([x, x + WR], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    items = [("linea", TR_PERIMETRAL, "Rebaje perimetral 30 mm"), ("caja", None, "Tirante 50×70"),
             ("libre", TR_LIBRE, "Rebaje libre"), ("mixto", None, "Unión mixta")]
    for k, (tipo, ls, txt) in enumerate(items):
        c, f = divmod(k, 2)
        xx, yy = x + c * (WR / 2 + 1), y - 11.5 - f * 6.0
        if tipo == "linea":
            ax.plot([xx, xx + 9], [yy, yy], color=NEGRO, lw=1.0, ls=ls)
        elif tipo == "caja":
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc=TIRANTE, ec=NEGRO, lw=0.6))
        elif tipo == "libre":
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc="white", ec=NEGRO, hatch=HATCH_REBAJE, lw=0.8))
        else:
            ax.add_patch(Rectangle((xx, yy - 1.8), 9, 3.6, fc="white", ec=GRIS, hatch=HATCH_MIXTA, lw=0.6))
        ax.text(xx + 11.5, yy, txt, fontsize=7.6, ha="left", va="center")
