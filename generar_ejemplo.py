"""Genera la plantilla de AutoCAD (capas, bloques e instrucciones) con un módulo de ejemplo dibujado, que se borra antes de guardar el DXF final. Módulo de 3,05 x 4,88 m.

Caída hacia A (arriba). El techo son 8 paneles trabados (lado largo de 2,44 m en el sentido corto del módulo), por dentro del espesor de los muros en los lados sin caída. Incluye una ventana correcta, una puerta ventana con una
jamba justo sobre una junta (la trae el panel vecino), una corrediza hasta el piso que toma mitad en D-02 y mitad en D-03,
y una ventana puesta a propósito a 10 cm de una junta para
ver cómo aparece la alerta en el informe.

Uso:  python generar_ejemplo.py [ruta_salida.dxf] [--unidades m|cm|mm]
"""
import argparse

import ezdxf

INSTRUCCIONES = """\
PLANTILLA HABITEC - MODULO SIP (unidades: metros)
ANTES DE GUARDAR EL DXF FINAL: BORRAR TODO EL DIBUJO DE EJEMPLO
(Ctrl+A y Supr; las capas y los bloques quedan guardados en el archivo).
Dibujar un solo modulo por archivo, con rectangulos CERRADOS y sin girar.
MODULO: contorno exterior (multiplo de 0,61 m).
CAIDA: flecha hacia donde baja el techo.
PANEL: un rectangulo por panel de muro (ancho x 0,09), sobre el contorno.
TECHO: un rectangulo por panel de techo, en planta (max. 1,22 x 2,44; juntas trabadas).
VANO: rectangulo con la medida de la ABERTURA (sin huelgo) + bloque VANO_BLOQUE
  (TIPO V/PV/C/P; DINTEL = cota del borde superior de la abertura desde el piso, ej. 2.05;
  ANTEPECHO = cota del borde inferior). Insertar con la capa VANO como actual.
PANEL_REV (opcional): REV_BLOQUE solo para cambiar CARA (EXT/INT) o SENTIDO (V/H).
--- Solo para la lamina grafica (no van a las hojas de taller) ---
REV_EXT_CHAPA / REV_EXT_WPC: una linea sobre la cara EXTERIOR del muro, en el tramo que lleva
  ese revestimiento. Sin linea, el exterior es smart panel.
REV_INT_PLACA (yeso pegado), _OMEGA, _P35, _P70, _CERAMICO, _PVC: una linea sobre la cara
  INTERIOR del muro (o del tabique) en el tramo que lleva ese revestimiento. Sin linea: OSB visto.
TABIQUE_DURLOCK: un rectangulo por tabique de durlock, con su espesor real.
SANITARIOS: artefactos y equipamiento (lineas, circulos, bloques): se dibujan tal cual.
PISO: sombreado o lineas del piso: se dibujan tal cual, con linea muy fina.
ELECTRICIDAD: bloques ELEC_TOMA, ELEC_TOMA_ESPECIAL (aire acond.), ELEC_CENTRO, ELEC_LLAVE, ELEC_APLIQUE, ELEC_PASE (caja de pase)
  y ELEC_TABLERO, sobre la cara del muro o tabique donde va la caja. ALTURA = cota del eje de la
  caja desde el piso (ej. 0.30); vacio: valor tipico del tipo. ELEC_CENTRO va en el techo.
--- Solo para las laminas de obra in situ ---
ELEC_CANERIA: lineas de boca a boca y hasta el tablero (cañeria embutida). Solo se dibujan.
ELEC_CANERIA_VISTA: idem, para las cañerias que quedan vistas sobre el modulo.
SAN_EJE: bloque SAN_EJE en el eje de cada artefacto (ARTEFACTO = nombre, ej. Inodoro).
PUERTA_GIRO: hoja y arco de cada puerta (queda en el DXF; no sale en la lamina grafica).
Guardar: SAVEAS > AutoCAD DXF (2018 o anterior). La capa LEEME no se lee."""

FACTOR = {"m": 1, "cm": 100, "mm": 1000}


def definir_bloques_electricidad(doc, k: float = 1.0) -> None:
    """Bloques de bocas eléctricas (se insertan en la capa ELECTRICIDAD; la lámina los dibuja tal cual).
    Los de pared traen el atributo ALTURA (eje de la caja desde el piso) para las láminas de obra."""
    if "ELEC_TOMA" not in doc.blocks:
        b = doc.blocks.new("ELEC_TOMA")                     # tomacorriente: círculo con dos patas
        b.add_circle((0, 0), 0.05 * k)
        b.add_line((-0.02 * k, -0.05 * k), (-0.02 * k, -0.09 * k))
        b.add_line((0.02 * k, -0.05 * k), (0.02 * k, -0.09 * k))
    if "ELEC_CENTRO" not in doc.blocks:
        b = doc.blocks.new("ELEC_CENTRO")                   # boca de techo: círculo con cruz
        b.add_circle((0, 0), 0.08 * k)
        r = 0.08 * k * 0.707
        b.add_line((-r, -r), (r, r))
        b.add_line((-r, r), (r, -r))
    if "ELEC_LLAVE" not in doc.blocks:
        b = doc.blocks.new("ELEC_LLAVE")                    # llave de un punto
        b.add_circle((0, 0), 0.035 * k)
        b.add_line((0.025 * k, 0.025 * k), (0.09 * k, 0.09 * k))
        b.add_line((0.09 * k, 0.09 * k), (0.12 * k, 0.06 * k))
    if "ELEC_APLIQUE" not in doc.blocks:
        b = doc.blocks.new("ELEC_APLIQUE")                  # aplique de pared
        b.add_circle((0, 0), 0.06 * k)
        b.add_line((-0.06 * k, 0), (0.06 * k, 0))
        b.add_line((-0.08 * k, -0.06 * k), (0.08 * k, -0.06 * k))
    if "ELEC_TOMA_ESPECIAL" not in doc.blocks:
        b = doc.blocks.new("ELEC_TOMA_ESPECIAL")            # toma de uso especial (aire acondicionado, etc.)
        b.add_circle((0, 0), 0.05 * k)
        b.add_solid([(-0.035 * k, -0.035 * k), (0.035 * k, -0.035 * k), (-0.035 * k, 0.035 * k), (0.035 * k, 0.035 * k)])
    if "ELEC_PASE" not in doc.blocks:
        b = doc.blocks.new("ELEC_PASE")                     # caja de pase: cuadrado con cruz
        r = 0.05 * k
        b.add_lwpolyline([(-r, -r), (r, -r), (r, r), (-r, r)], close=True)
        b.add_line((-r, -r), (r, r))
        b.add_line((-r, r), (r, -r))
    if "ELEC_TABLERO" not in doc.blocks:
        b = doc.blocks.new("ELEC_TABLERO")                  # tablero: rectángulo con media diagonal rellena
        w, h = 0.12 * k, 0.07 * k
        b.add_lwpolyline([(-w, -h), (w, -h), (w, h), (-w, h)], close=True)
        b.add_solid([(-w, -h), (w, -h), (-w, h)])
    for nombre, defecto in (("ELEC_TOMA", "0.30"), ("ELEC_TOMA_ESPECIAL", "2.00"), ("ELEC_LLAVE", "1.10"), ("ELEC_APLIQUE", "2.00"),
                            ("ELEC_PASE", "2.20"), ("ELEC_TABLERO", "1.50")):
        b = doc.blocks[nombre]
        if not any(a.dxf.tag == "ALTURA" for a in b.query("ATTDEF")):
            b.add_attdef("ALTURA", (0.08 * k, 0.08 * k), defecto, dxfattribs={
                "height": 0.05 * k, "prompt": f"Altura del eje de la caja desde el piso (ej. {defecto})"})
    if "SAN_EJE" not in doc.blocks:
        b = doc.blocks.new("SAN_EJE")                       # eje de artefacto: círculo chico con cruz
        r = 0.04 * k
        b.add_circle((0, 0), r)
        b.add_line((-2 * r, 0), (2 * r, 0))
        b.add_line((0, -2 * r), (0, 2 * r))
        b.add_attdef("ARTEFACTO", (0.06 * k, 0.06 * k), "Inodoro", dxfattribs={
            "height": 0.05 * k, "prompt": "Artefacto (Inodoro, Lavatorio, Ducha, Pileta…)"})
INSUNITS = {"m": 6, "cm": 5, "mm": 4}


def crear(ruta: str, unidades: str = "m") -> None:
    k = FACTOR[unidades]
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = INSUNITS[unidades]
    for nombre, color in (("MODULO", 7), ("CAIDA", 1), ("PANEL", 3),
                          ("VANO", 5), ("PANEL_REV", 6), ("TECHO", 4), ("LEEME", 8),
                          ("REV_EXT_CHAPA", 250), ("REV_EXT_WPC", 32),
                          ("REV_INT_PLACA", 140), ("REV_INT_OMEGA", 150), ("REV_INT_P35", 160),
                          ("REV_INT_P70", 170), ("REV_INT_CERAMICO", 40), ("REV_INT_PVC", 90),
                          ("TABIQUE_DURLOCK", 8), ("SANITARIOS", 30), ("PISO", 9), ("ELECTRICIDAD", 2),
                          ("PUERTA_GIRO", 1), ("ELEC_CANERIA", 2), ("ELEC_CANERIA_VISTA", 1), ("SAN_EJE", 4)):
        doc.layers.add(nombre, color=color)
    definir_bloques_electricidad(doc, k)

    # Bloques con atributos
    b = doc.blocks.new("VANO_BLOQUE")
    b.add_attdef("TIPO", (0, 0), "V", dxfattribs={"height": 0.08 * k, "prompt": "Tipo de vano (V ventana, PV puerta ventana, C corrediza, P puerta)"})
    b.add_attdef("DINTEL", (0, -0.10 * k), "2.05", dxfattribs={"height": 0.08 * k, "prompt": "Cota del dintel desde el piso, sin huelgo (ej. 2.05)"})
    b.add_attdef("ANTEPECHO", (0, -0.20 * k), "0.90", dxfattribs={"height": 0.08 * k, "prompt": "Altura del antepecho desde el piso (0 si llega al piso)"})
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

    # Techo: va por dentro del espesor de los muros en los tres lados sin caída (B, C y D) y
    # llega al filo exterior del lado de la caída (A, donde se refila en obra). Zona: x de 0,09 a
    # 2,96 (2,87 = 2,44 + 0,43) e y de 0,09 a 4,88. El lado largo del panel (2,44) va en el sentido
    # corto del módulo (X) y las filas se traban alternando de qué lado va el ajuste.
    filas = [((3.66, 4.88), "largo_izq"), ((2.44, 3.66), "corto_izq"),
             ((1.22, 2.44), "largo_izq"), ((e, 1.22), "corto_izq")]
    for (y0, y1), tipo in filas:
        cortes = (e, e + 2.44, W - e) if tipo == "largo_izq" else (e, e + 0.43, W - e)
        for x0, x1 in zip(cortes, cortes[1:]):
            rect(x0, y0, x1, y1, "TECHO")

    # Vanos: rectángulo con la medida de la abertura + bloque con atributos
    def vano(x0, y0, x1, y1, tipo, alto, antepecho=None):
        rect(x0, y0, x1, y1, "VANO")
        att = {"TIPO": tipo, "DINTEL": f"{((antepecho or 0) + alto) * k:.3f}"}
        att["ANTEPECHO"] = f"{(antepecho or 0) * k:.3f}"
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ins = msp.add_blockref("VANO_BLOQUE", (cx * k, cy * k), dxfattribs={"layer": "VANO"})
        ins.add_auto_attribs(att)

    vano(1.52, H - e, 2.32, H, "V", 1.00, 0.90)        # ventana en A-02 (a 21 cm de las juntas)
    vano(0.61, 0, 1.31, e, "PV", 2.05)                 # puerta ventana con la jamba justo en la junta C-01/C-02
    vano(W - e, 2.54, W, 3.34, "V", 1.00, 0.90)        # ventana en B-02 a 10 cm de una junta (alerta)

    # Corrediza hasta el piso, mitad en D-02 y mitad en D-03 (junta en y = 2,44)
    vano(0, 1.84, e, 3.04, "C", 2.00)

    # Smart panel: todos los muros lo llevan salvo los ajustes. El bloque REV_BLOQUE es
    # opcional; aquí A-01 lo pide con el sentido horizontal para mostrar el cambio.
    ins = msp.add_blockref("REV_BLOQUE", (0.70 * k, (H - e / 2) * k), dxfattribs={"layer": "PANEL_REV"})
    ins.add_auto_attribs({"CARA": "EXT", "SENTIDO": "H"})

    # Lámina gráfica: ejemplos de revestimiento (exterior WPC en parte del lado C; interior con
    # placa sobre omega en A y B) y una boca de techo.
    def linea(capa, a, b):
        msp.add_line((a[0] * k, a[1] * k), (b[0] * k, b[1] * k), dxfattribs={"layer": capa})
    linea("REV_EXT_WPC", (1.40, 0.0), (W, 0.0))
    linea("REV_INT_OMEGA", (e, H - e), (W - e, H - e))
    linea("REV_INT_OMEGA", (W - e, H - e), (W - e, e))
    msp.add_blockref("ELEC_CENTRO", (W / 2 * k, H / 2 * k), dxfattribs={"layer": "ELECTRICIDAD"})

    # Obra in situ: bocas sobre la cara interior del SIP (con su altura), cañerías y un eje sanitario
    def boca(tipo, x, y, altura):
        ins = msp.add_blockref(f"ELEC_{tipo}", (x * k, y * k), dxfattribs={"layer": "ELECTRICIDAD"})
        ins.add_auto_attribs({"ALTURA": f"{altura * k:.3f}"})
    boca("TABLERO", 1.70, e, 1.50)
    boca("LLAVE", 1.45, e, 1.10)
    boca("PASE", 2.40, e, 2.20)
    boca("TOMA", e, 0.80, 0.30)
    boca("TOMA", W - e, 1.30, 0.30)
    boca("TOMA", 0.60, H - e, 0.30)
    boca("APLIQUE", W - e, 4.20, 2.00)
    boca("TOMA_ESPECIAL", 2.60, H - e, 2.00)                # aire acondicionado
    for pts, capa in (([(1.70, e), (W / 2, H / 2)], "ELEC_CANERIA"),
                      ([(1.45, e), (1.45, 0.30), (W / 2, H / 2)], "ELEC_CANERIA"),
                      ([(1.70, e), (2.40, e)], "ELEC_CANERIA"),
                      ([(2.40, e), (W - e, e), (W - e, 1.30)], "ELEC_CANERIA"),
                      ([(W / 2, H / 2), (W - e, 4.20)], "ELEC_CANERIA"),
                      ([(W / 2, H / 2), (0.60, H - e)], "ELEC_CANERIA"),
                      ([(1.70, e), (1.70, 0.20), (e, 0.20), (e, 0.80)], "ELEC_CANERIA"),
                      ([(1.70, 0.0), (1.70, -0.60)], "ELEC_CANERIA_VISTA")):
        msp.add_lwpolyline([(x * k, y * k) for x, y in pts], dxfattribs={"layer": capa})
    ins = msp.add_blockref("SAN_EJE", (1.00 * k, (H - e - 0.25) * k), dxfattribs={"layer": "SAN_EJE"})
    ins.add_auto_attribs({"ARTEFACTO": "Pileta de cocina"})

    msp.add_mtext(INSTRUCCIONES, dxfattribs={"layer": "LEEME", "char_height": 0.09 * k,
                                              "insert": (-6.5 * k, 4.9 * k), "width": 6.0 * k})
    doc.saveas(ruta)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("salida", nargs="?", default="ejemplo_modulo.dxf")
    ap.add_argument("--unidades", choices=list(FACTOR), default="m")
    a = ap.parse_args()
    crear(a.salida, a.unidades)
    print(f"DXF de ejemplo escrito en {a.salida} (unidades: {a.unidades})")
