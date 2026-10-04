"""Crea plantilla/plantilla_modulo.dxf: capas y bloques listos para dibujar un módulo.

Abrir en AutoCAD, guardar como DWG y usarla como plantilla de dibujo. Está en metros.
"""
from pathlib import Path

import ezdxf

CAPAS = [("MODULO", 7), ("CAIDA", 1), ("PANEL", 3), ("TECHO", 4), ("VANO", 5), ("PANEL_REV", 6),
         ("LEEME", 8)]

INSTRUCCIONES = """\
PLANTILLA DE MODULO SIP (unidades: metros)
Un archivo = un modulo. Todo con rectangulos CERRADOS, sin girar.
MODULO: rectangulo del contorno exterior (multiplo de 0,61 m).
CAIDA: flecha hacia donde baja el techo (linea mas larga = cuerpo de la flecha).
PANEL: un rectangulo por panel de muro (ancho x 0,09), sobre el contorno. Las juntas se superponen.
TECHO: un rectangulo por panel de techo, en planta (max. 1,22 x 2,44; juntas trabadas).
VANO: rectangulo con la medida de la ABERTURA (sin huelgo) + bloque VANO_BLOQUE dentro.
PANEL_REV: bloque REV_BLOQUE dentro de cada panel con smart panel.
Para insertar un bloque: poner como capa actual VANO (o PANEL_REV) y usar INSERT.
Guardar para el programa: SAVEAS > AutoCAD DXF (2018 o anterior).
Esta capa (LEEME) no se lee."""


def crear(ruta: Path) -> None:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6          # metros
    for nombre, color in CAPAS:
        doc.layers.add(nombre, color=color)

    b = doc.blocks.new("VANO_BLOQUE")
    b.add_attdef("TIPO", (0, 0), "V", dxfattribs={
        "height": 0.08, "prompt": "Tipo de vano (V ventana, PV puerta ventana, C corrediza, P puerta)"})
    b.add_attdef("ALTO", (0, -0.10), "1.00", dxfattribs={
        "height": 0.08, "prompt": "Alto de la abertura en metros (sin huelgo)"})
    b.add_attdef("ANTEPECHO", (0, -0.20), "0.90", dxfattribs={
        "height": 0.08, "prompt": "Altura del antepecho en metros (0 si llega al piso)"})

    r = doc.blocks.new("REV_BLOQUE")
    r.add_attdef("CARA", (0, 0), "EXT", dxfattribs={
        "height": 0.08, "prompt": "Cara con revestimiento (EXT o INT)"})
    r.add_attdef("SENTIDO", (0, -0.10), "V", dxfattribs={
        "height": 0.08, "prompt": "Sentido del revestimiento (V vertical, H horizontal)"})

    msp = doc.modelspace()
    msp.add_mtext(INSTRUCCIONES, dxfattribs={"layer": "LEEME", "char_height": 0.08,
                                              "insert": (-6.0, 5.0), "width": 5.5})
    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(ruta))


if __name__ == "__main__":
    destino = Path(__file__).parent / "plantilla" / "plantilla_modulo.dxf"
    crear(destino)
    print(f"Plantilla escrita en {destino}")
