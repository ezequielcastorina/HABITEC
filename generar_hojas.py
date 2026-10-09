"""Genera las hojas de taller de los paneles SIP a partir de un plano de AutoCAD.

Uso:
    python generar_hojas.py plano.dxf --proyecto "Casa Pérez" [--unidades m|cm|mm|auto]
                            [--salida carpeta] [--solo-validar]
                            [--interior "…"] [--cielorraso "…"] [--exterior "…"] [--obs "…"] [--rev 00]
                            [--piel-exterior smart|osb]

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
    ap.add_argument("--interior", default="", help="Revestimiento interior (sale en la carátula)")
    ap.add_argument("--cielorraso", default="", help="Revestimiento de cielorraso (carátula)")
    ap.add_argument("--exterior", default="", help="Revestimiento exterior (carátula)")
    ap.add_argument("--obs", default="", help="Observaciones (carátula)")
    ap.add_argument("--rev", default="00", help="Número de revisión (carátula)")
    ap.add_argument("--piel-exterior", choices=["smart", "osb"], default="smart",
                    help="Cara exterior de los paneles de muro: smart panel (por defecto) u OSB")
    ap.add_argument("--esquina", default="NO",
                    help="Esquina donde arranca el montaje, por letras (A-F, A-B...) o NO/NE/SO/SE (define la secuencia de carga del camión)")
    ap.add_argument("--solo-validar", action="store_true", help="Solo lee el plano y emite el informe")
    a = ap.parse_args(argv)
    generar(a.dxf, a.proyecto, a.unidades, a.salida, a.solo_validar, caratula={
        "interior": a.interior, "cielorraso": a.cielorraso, "exterior": a.exterior,
        "observaciones": a.obs, "revision": a.rev, "piel_exterior": a.piel_exterior,
        "esquina": a.esquina})


if __name__ == "__main__":
    main()
