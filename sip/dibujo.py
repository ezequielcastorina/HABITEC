"""Utilidades de dibujo sobre una hoja A3 apaisada, en milímetros de papel."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

PAG_W, PAG_H = 420.0, 297.0          # A3 apaisado (mm)
MM_A_PULG = 1 / 25.4

ESCALAS = (10, 12.5, 15, 20, 25, 30, 40, 50, 75, 100)

# Paleta (sobria, legible en impresión en blanco y negro)
NEGRO = "#111111"
GRIS = "#8a8a8a"
GRIS_CLARO = "#ececec"
AZUL = "#1f5fa8"
ROJO = "#c0281e"
MARRON = "#8a5a2b"
NARANJA = "#d97b1a"
AMBAR = "#f3e6c4"   # color crema del smart panel
VERDE = "#2f7d4f"


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
    def cota_h(self, u0, u1, v, desplaz_mm: float, texto: str, fs: float = 6.5):
        """Cota horizontal entre u0 y u1, desplazada en papel respecto de v."""
        y = self.Y(v) + desplaz_mm
        x0, x1 = self.X(u0), self.X(u1)
        sgn = 1 if desplaz_mm > 0 else -1
        self.ax.plot([x0, x0], [self.Y(v), y + sgn * 1.5], color=GRIS, lw=0.4)
        self.ax.plot([x1, x1], [self.Y(v), y + sgn * 1.5], color=GRIS, lw=0.4)
        self.ax.plot([x0, x1], [y, y], color=NEGRO, lw=0.6)
        for x in (x0, x1):
            self.ax.plot([x - 0.9, x + 0.9], [y - 0.9, y + 0.9], color=NEGRO, lw=0.8)
        self.ax.text((x0 + x1) / 2, y + sgn * 1.9, texto, fontsize=fs, ha="center",
                     va="bottom" if sgn > 0 else "top", color=NEGRO)

    def cota_v(self, v0, v1, u, desplaz_mm: float, texto: str, fs: float = 6.5):
        x = self.X(u) + desplaz_mm
        y0, y1 = self.Y(v0), self.Y(v1)
        sgn = 1 if desplaz_mm > 0 else -1
        self.ax.plot([self.X(u), x + sgn * 1.5], [y0, y0], color=GRIS, lw=0.4)
        self.ax.plot([self.X(u), x + sgn * 1.5], [y1, y1], color=GRIS, lw=0.4)
        self.ax.plot([x, x], [y0, y1], color=NEGRO, lw=0.6)
        for y in (y0, y1):
            self.ax.plot([x - 0.9, x + 0.9], [y - 0.9, y + 0.9], color=NEGRO, lw=0.8)
        self.ax.text(x + sgn * 1.9, (y0 + y1) / 2, texto, fontsize=fs, rotation=90,
                     ha="right" if sgn < 0 else "left", va="center", color=NEGRO)


def mm(x: float) -> str:
    """Metros -> milímetros enteros como texto."""
    return f"{round(x * 1000):d}"


def cuadro_titulo(ax, proyecto: str, codigo: str, subtitulo: str, escala: float | None,
                  fecha: str, pagina: str = ""):
    """Marco de la hoja y rótulo superior."""
    ax.add_patch(Rectangle((8, 8), PAG_W - 16, PAG_H - 16, fill=False, ec=NEGRO, lw=1.0))
    ax.add_patch(Rectangle((8, PAG_H - 30), PAG_W - 16, 22, fill=False, ec=NEGRO, lw=0.8))
    ax.text(14, PAG_H - 15, codigo, fontsize=24, fontweight="bold", va="center", ha="left")
    ax.text(14 + 12 * len(codigo) + 8, PAG_H - 15, subtitulo, fontsize=10.5, va="center", ha="left",
            color=NEGRO)
    ax.text(PAG_W - 14, PAG_H - 15, proyecto, fontsize=12, fontweight="bold", va="center", ha="right")
    pie = f"{fecha}"
    if escala:
        esc = f"{escala:g}"
        pie = f"Escala 1:{esc}   ·   " + pie
    if pagina:
        pie += f"   ·   {pagina}"
    ax.text(PAG_W - 14, 12, pie, fontsize=6.5, ha="right", va="center", color=GRIS)


def bloque_texto(ax, x: float, y: float, titulo: str, lineas: list[tuple[str, str]],
                 ancho: float = 140.0, fs: float = 7.5, interlinea: float = 4.6) -> float:
    """Dibuja un bloque de texto con título y líneas (texto, color). Devuelve la y final."""
    ax.text(x, y, titulo, fontsize=8.5, fontweight="bold", ha="left", va="top", color=NEGRO)
    ax.plot([x, x + ancho], [y - 5.2, y - 5.2], color=NEGRO, lw=0.6)
    y -= 8.2
    for txt, color in lineas:
        ax.text(x, y, txt, fontsize=fs, ha="left", va="top", color=color or NEGRO)
        y -= interlinea * (1 + txt.count("\n"))
    return y
