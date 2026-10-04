"""Genera las hojas de taller de los paneles SIP a partir de un plano de AutoCAD.

Uso:
    python generar_hojas.py plano.dxf --proyecto "Casa Pérez" [--unidades m|cm|mm|auto]
                            [--salida carpeta] [--solo-validar]

Si el plano está en DWG, convertirlo antes a DXF (Guardar como... DXF en AutoCAD).
Sin --salida, deja los archivos en una carpeta junto al DXF con el sufijo _hojas.
"""
import argparse

from sip.proceso import generar


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf")
    ap.add_argument("--proyecto", required=True, help="Nombre del proyecto (sale en cada hoja)")
    ap.add_argument("--unidades", choices=["auto", "m", "cm", "mm"], default="auto")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--solo-validar", action="store_true", help="Solo lee el plano y emite el informe")
    a = ap.parse_args(argv)
    generar(a.dxf, a.proyecto, a.unidades, a.salida, a.solo_validar)


if __name__ == "__main__":
    main()
