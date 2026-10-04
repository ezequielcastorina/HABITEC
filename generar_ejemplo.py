"""Genera un DXF de ejemplo con un módulo de 3,05 x 4,88 m.

Caída hacia A (arriba). El techo son 8 paneles trabados (lado largo de 2,44 m en el sentido corto del módulo). Incluye una ventana correcta, una puerta ventana que
cruza una junta, una corrediza hasta el piso que toma mitad en D-02 y mitad en D-03,
y una ventana puesta a propósito a 10 cm de una junta para
ver cómo aparece la alerta en el informe.

Uso:  python generar_ejemplo.py [ruta_salida.dxf] [--unidades m|cm|mm]
"""
import argparse

import ezdxf

FACTOR = {"m": 1, "cm": 100, "mm": 1000}
INSUNITS = {"m": 6, "cm": 5, "mm": 4}


def crear(ruta: str, unidades: str = "m") -> None:
    k = FACTOR[unidades]
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = INSUNITS[unidades]
    for nombre, color in (("MODULO", 7), ("CAIDA", 1), ("PANEL", 3),
                          ("VANO", 5), ("PANEL_REV", 6), ("TECHO", 4)):
        doc.layers.add(nombre, color=color)

    # Bloques con atributos
    b = doc.blocks.new("VANO_BLOQUE")
    b.add_attdef("TIPO", (0, 0), "V", dxfattribs={"height": 0.08 * k})
    b.add_attdef("ALTO", (0, -0.10 * k), "1.00", dxfattribs={"height": 0.08 * k})
    b.add_attdef("ANTEPECHO", (0, -0.20 * k), "0.90", dxfattribs={"height": 0.08 * k})
    r = doc.blocks.new("REV_BLOQUE")
    r.add_attdef("CARA", (0, 0), "EXT", dxfattribs={"height": 0.08 * k})
    r.add_attdef("SENTIDO", (0, -0.10 * k), "V", dxfattribs={"height": 0.08 * k})

    msp = doc.modelspace()

    def rect(x0, y0, x1, y1, capa):
        pts = [(x0 * k, y0 * k), (x1 * k, y0 * k), (x1 * k, y1 * k), (x0 * k, y1 * k)]
        return msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": capa})

    W, H, e = 3.05, 4.88, 0.09
    rect(0, 0, W, H, "MODULO")

    # Flecha de caída hacia A (arriba)
    msp.add_line((1.5 * k, 3.0 * k), (1.5 * k, 3.9 * k), dxfattribs={"layer": "CAIDA"})
    msp.add_line((1.5 * k, 3.9 * k), (1.44 * k, 3.80 * k), dxfattribs={"layer": "CAIDA"})
    msp.add_line((1.5 * k, 3.9 * k), (1.56 * k, 3.80 * k), dxfattribs={"layer": "CAIDA"})

    # Muros A y C (entre laterales): 1,22 + 1,22 + ajuste de 0,43
    tramos_x = [(0.09, 1.31), (1.31, 2.53), (2.53, 2.96)]
    for x0, x1 in tramos_x:
        rect(x0, H - e, x1, H, "PANEL")      # A
        rect(x0, 0, x1, e, "PANEL")          # C
    # Laterales B y D (toman las 4 esquinas): 4 x 1,22
    for y0 in (0, 1.22, 2.44, 3.66):
        rect(W - e, y0, W, y0 + 1.22, "PANEL")   # B
        rect(0, y0, e, y0 + 1.22, "PANEL")       # D

    # Techo: el lado largo del panel (2,44) va en el sentido corto del módulo (X) y las
    # filas se traban: 3,05 = 2,44 + 0,61 (ajuste), alternando de qué lado va el ajuste.
    filas = [(3.66, "largo_izq"), (2.44, "corto_izq"), (1.22, "largo_izq"), (0.0, "corto_izq")]
    for y0, tipo in filas:
        cortes = (0, 2.44, 3.05) if tipo == "largo_izq" else (0, 0.61, 3.05)
        for x0, x1 in zip(cortes, cortes[1:]):
            rect(x0, y0, x1, y0 + 1.22, "TECHO")

    # Vanos: rectángulo con la medida de la abertura + bloque con atributos
    def vano(x0, y0, x1, y1, tipo, alto, antepecho=None):
        rect(x0, y0, x1, y1, "VANO")
        att = {"TIPO": tipo, "ALTO": f"{alto * k:.3f}"}
        att["ANTEPECHO"] = f"{(antepecho or 0) * k:.3f}"
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ins = msp.add_blockref("VANO_BLOQUE", (cx * k, cy * k), dxfattribs={"layer": "VANO"})
        ins.add_auto_attribs(att)

    vano(1.52, H - e, 2.32, H, "V", 1.00, 0.90)        # ventana en A-02 (a 21 cm de las juntas)
    vano(0.71, 0, 1.91, e, "PV", 2.05)                 # puerta ventana que cruza la junta C-01/C-02
    vano(W - e, 2.54, W, 3.34, "V", 1.00, 0.90)        # ventana en B-02 a 10 cm de una junta (alerta)

    # Corrediza hasta el piso, mitad en D-02 y mitad en D-03 (junta en y = 2,44)
    vano(0, 1.84, e, 3.04, "C", 2.00)

    # Smart panel: todos los muros lo llevan salvo los ajustes. El bloque REV_BLOQUE es
    # opcional; aquí A-01 lo pide con el sentido horizontal para mostrar el cambio.
    ins = msp.add_blockref("REV_BLOQUE", (0.70 * k, (H - e / 2) * k), dxfattribs={"layer": "PANEL_REV"})
    ins.add_auto_attribs({"CARA": "EXT", "SENTIDO": "H"})

    doc.saveas(ruta)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("salida", nargs="?", default="ejemplo_modulo.dxf")
    ap.add_argument("--unidades", choices=list(FACTOR), default="m")
    a = ap.parse_args()
    crear(a.salida, a.unidades)
    print(f"DXF de ejemplo escrito en {a.salida} (unidades: {a.unidades})")
