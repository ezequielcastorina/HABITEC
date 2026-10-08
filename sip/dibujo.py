"""Utilidades de dibujo sobre una hoja A4 apaisada, en milímetros de papel."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

MARCA = "HABITEC"
PAG_W, PAG_H = 297.0, 210.0          # A4 apaisado (mm)
ESCALA_PANEL = 20                    # escala fija de todas las hojas de panel (1:20)
MM_A_PULG = 1 / 25.4

ESCALAS = (10, 12.5, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 250)

# Todo en blanco y negro: cada elemento se distingue por su tipo de línea o trama, nunca por el color.
# Los nombres de color se conservan (el resto del código los usa) pero todos son negro o grises.
NEGRO = "#111111"
GRIS = "#555555"
GRIS_CLARO = "#ececec"
AZUL = NEGRO
ROJO = NEGRO
MARRON = NEGRO             # solo para textos
NARANJA = NEGRO
VERDE = NEGRO
TIRANTE = "#bdbdbd"        # relleno de los tirantes (gris claro, con contorno negro)
AMBAR = "#ffffff"          # smart panel: sin relleno (solo líneas)
AJUSTE = "#d3d3d3"         # pieza de ajuste (gris claro)
TABLAS = "#7d7d7d"         # líneas de las tablas del smart panel

# Líneas de trazos distintas entre sí (largo de trazo, hueco)
TR_PERIMETRAL = (0, (7, 3))            # rebaje perimetral de 30 mm
TR_VANO = (0, (6, 2, 1.2, 2))          # rebaje de 55 mm alrededor del vano (trazo y punto)
TR_LIBRE = (0, (1.2, 1.8))             # rebaje libre (punteado)

GUIA = dict(color="#8a8a8a", lw=0.5, ls=(0, (1.5, 1.5)))   # líneas guía de las cotas: punteadas y grises
plt.rcParams["hatch.linewidth"] = 0.5


def nueva_hoja():
    """Crea una figura A3 con un único eje en milímetros de papel."""
    fig = plt.figure(figsize=(PAG_W * MM_A_PULG, PAG_H * MM_A_PULG))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PAG_W)
    ax.set_ylim(0, PAG_H)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def elegir_escala(ancho_m: float, alto_m: float, disp_w_mm: float, disp_h_mm: float) -> float:
    """Menor denominador de escala (mayor dibujo) que entra en el espacio disponible."""
    for e in ESCALAS:
        if ancho_m * 1000 / e <= disp_w_mm and alto_m * 1000 / e <= disp_h_mm:
            return e
    return ESCALAS[-1]


class Lienzo:
    """Convierte coordenadas de modelo (m) a papel (mm) para un dibujo."""

    def __init__(self, ax, ox: float, oy: float, escala: float):
        self.ax, self.ox, self.oy, self.esc = ax, ox, oy, escala

    def X(self, u: float) -> float:
        return self.ox + u * 1000 / self.esc

    def Y(self, v: float) -> float:
        return self.oy + v * 1000 / self.esc

    def L(self, d: float) -> float:
        return d * 1000 / self.esc

    def rect(self, u0, v0, u1, v1, **kw):
        r = Rectangle((self.X(u0), self.Y(v0)), self.L(u1 - u0), self.L(v1 - v0), **kw)
        self.ax.add_patch(r)
        return r

    def linea(self, u0, v0, u1, v1, **kw):
        self.ax.plot([self.X(u0), self.X(u1)], [self.Y(v0), self.Y(v1)], **kw)

    def texto(self, u, v, s, **kw):
        kw.setdefault("fontsize", 7)
        kw.setdefault("color", NEGRO)
        kw.setdefault("ha", "center")
        kw.setdefault("va", "center")
        self.ax.text(self.X(u), self.Y(v), s, **kw)

    # --- Cotas ---------------------------------------------------------------
    def cota_h(self, u0, u1, v, desplaz_mm: float, texto: str, fs: float = 7.5, va=None, vb=None):
        """Cota horizontal entre u0 y u1, desplazada en papel respecto de v. Las líneas guía (punteadas,
        grises) salen de la arista que se mide: v por defecto, o va / vb si esa arista está más adentro."""
        y = self.Y(v) + desplaz_mm
        x0, x1 = self.X(u0), self.X(u1)
        sgn = 1 if desplaz_mm > 0 else -1
        ya = self.Y(v if va is None else va)
        yb = self.Y(v if vb is None else vb)
        self.ax.plot([x0, x0], [ya, y + sgn * 1.5], **GUIA)
        self.ax.plot([x1, x1], [yb, y + sgn * 1.5], **GUIA)
        self.ax.plot([x0, x1], [y, y], color=NEGRO, lw=0.7)
        for x in (x0, x1):
            self.ax.plot([x - 0.9, x + 0.9], [y - 0.9, y + 0.9], color=NEGRO, lw=0.8)
        self.ax.text((x0 + x1) / 2, y + sgn * 1.9, texto, fontsize=fs, ha="center",
                     va="bottom" if sgn > 0 else "top", color=NEGRO)

    def cota_v(self, v0, v1, u, desplaz_mm: float, texto: str, fs: float = 7.5, ua=None, ub=None):
        x = self.X(u) + desplaz_mm
        y0, y1 = self.Y(v0), self.Y(v1)
        sgn = 1 if desplaz_mm > 0 else -1
        xa = self.X(u if ua is None else ua)
        xb = self.X(u if ub is None else ub)
        self.ax.plot([xa, x + sgn * 1.5], [y0, y0], **GUIA)
        self.ax.plot([xb, x + sgn * 1.5], [y1, y1], **GUIA)
        self.ax.plot([x, x], [y0, y1], color=NEGRO, lw=0.7)
        for y in (y0, y1):
            self.ax.plot([x - 0.9, x + 0.9], [y - 0.9, y + 0.9], color=NEGRO, lw=0.8)
        self.ax.text(x + sgn * 1.9, (y0 + y1) / 2, texto, fontsize=fs, rotation=90,
                     ha="right" if sgn < 0 else "left", va="center", color=NEGRO)


def mm(x: float) -> str:
    """Metros -> milímetros enteros como texto."""
    return f"{round(x * 1000):d}"


_LOGO_GRIS = None


def logo_gris():
    """Logo en escala de grises (cacheado)."""
    global _LOGO_GRIS
    if _LOGO_GRIS is None:
        import numpy as np
        from .logo_datos import logo_array
        im = logo_array().astype(float)
        if im.max() > 1.5:
            im = im / 255.0
        g = im[..., :3] @ np.array([0.299, 0.587, 0.114])
        _LOGO_GRIS = np.dstack([g, g, g])
    return _LOGO_GRIS


def poner_logo(ax, x_der: float, y_sup: float, alto: float, zorder=3):
    """Logo (grises) con su borde derecho en x_der y su borde superior en y_sup."""
    im = logo_gris()
    ancho = alto * im.shape[1] / im.shape[0]
    ax.imshow(im, extent=(x_der - ancho, x_der, y_sup - alto, y_sup), aspect="auto", zorder=zorder)
    ax.set_xlim(0, PAG_W)
    ax.set_ylim(0, PAG_H)
    return ancho


def cuadro_titulo(ax, proyecto: str, codigo: str, subtitulo: str, escala: float | None,
                  fecha: str, pagina: str = ""):
    """Marco de la hoja y rótulo superior: código y proyecto a la izquierda; emisión y logo a la derecha."""
    ax.add_patch(Rectangle((6, 6), PAG_W - 12, PAG_H - 12, fill=False, ec=NEGRO, lw=1.0))
    ax.add_patch(Rectangle((6, PAG_H - 32), PAG_W - 12, 26, fill=False, ec=NEGRO, lw=0.8))
    ax.text(11, PAG_H - 14, codigo, fontsize=27, fontweight="bold", va="center", ha="left")
    ax.text(11, PAG_H - 26, f"Proyecto: {proyecto}", fontsize=10.5, va="center", ha="left", color=NEGRO)
    ancho = poner_logo(ax, PAG_W - 10, PAG_H - 8.5, 21)
    ax.text(PAG_W - 10 - ancho - 5, PAG_H - 19, f"Emisión {fecha}", fontsize=9, va="center", ha="right", color=NEGRO)
    pie_hoja(ax, fecha, pagina, escala, subtitulo)


def pie_hoja(ax, fecha: str, pagina: str = "", escala: float | None = None, extra: str = ""):
    """Pie, abajo a la derecha: solo la escala y el número de hoja."""
    partes = []
    if escala:
        partes.append(f"Escala 1:{escala:g}")
    if extra:
        partes.append(extra)
    if pagina:
        partes.append(pagina)
    if partes:
        ax.text(PAG_W - 10, 10, "   ·   ".join(partes), fontsize=8, ha="right", va="center", color=GRIS)


def partir(txt: str, n: int, sangria: str = "   ") -> list[str]:
    """Parte un texto en líneas de n caracteres como máximo; respeta los saltos de línea."""
    out: list[str] = []
    for k, linea in enumerate(txt.split("\n")):
        actual = ""
        pref = ""
        for w in linea.split(" "):
            if actual.strip() and len(actual) + 1 + len(w) > n:
                out.append(actual)
                actual = sangria + w
            else:
                actual = (actual + " " + w) if actual else (pref + w)
        out.append(actual)
    return out


def bloque_texto(ax, x: float, y: float, titulo: str, lineas: list[tuple[str, str]],
                 ancho: float = 110.0, fs: float = 8.2, interlinea: float = 4.3) -> float:
    """Dibuja un bloque de texto con título y líneas (texto, color); las líneas largas se parten
    para entrar en `ancho`. Devuelve la y final."""
    ax.text(x, y, titulo, fontsize=9.5, fontweight="bold", ha="left", va="top", color=NEGRO)
    ax.plot([x, x + ancho], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    y -= 8.0
    n = int(ancho / (fs * 0.2))
    for txt, color in lineas:
        for ln in partir(txt, n):
            ax.text(x, y, ln, fontsize=fs, ha="left", va="top", color=color or NEGRO)
            y -= interlinea
    return y
