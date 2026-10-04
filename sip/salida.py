"""Salidas no gráficas: planilla de paneles (xlsx) e informe de validación (txt)."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import config as C
from .modelo import Despiece


def planilla_xlsx(d: Despiece, ruta: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Paneles"
    ws["A1"] = "Proyecto"
    ws["B1"] = d.plano.proyecto
    ws["A1"].font = Font(bold=True)
    ws["B1"].font = Font(bold=True)
    ws["A2"] = f"Caída hacia el lado {d.plano.caida_hacia or '-'}"
    cab = ["Código", "Tipo", "Lado", "N°", "Ancho (mm)", "Alto/Largo (mm)", "Espesor (mm)", "Ajuste",
           "Revestimiento", "Cara", "Sentido", "Vanos", "Rebaje perimetral", "Tirantes y tapas", "Alertas"]
    fila0 = 4
    for j, h in enumerate(cab, start=1):
        c = ws.cell(row=fila0, column=j, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="333333")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    r = fila0 + 1
    for p in d.muros:
        ws.append([])
        vanos = "; ".join(f"{v.vano_id} ({C.TIPOS_VANO[v.tipo]}"
                          f"{'' if v.completo else ', compartido'})" for v in p.vanos)
        vals = [p.codigo, "Muro", p.lado, p.numero, round(p.largo * 1000), round(p.alto * 1000),
                round(p.espesor * 1000), "sí" if p.es_ajuste else "",
                "Smart panel" if p.smart else "No", p.cara_rev, p.sentido_rev, vanos,
                "30 mm, 4 lados", _bordes_txt(p), "; ".join(p.alertas)]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
        r += 1
    for t in d.techos:
        vals = [t.codigo, "Techo", "", t.numero, round(t.ancho * 1000), round(t.largo * 1000),
                round(C.ESPESOR_PANEL * 1000), "sí" if t.es_ajuste else "", "", "", "", "",
                ((f"30 mm, 3 lados (sin lado {t.caida_hacia})" if t.en_caida else "30 mm, 4 lados")
                 ), _tirantes_techo(t), "; ".join(t.alertas)]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
        r += 1
    # Filas con alertas resaltadas
    rojo = PatternFill("solid", fgColor="F8D7D3")
    for fila in ws.iter_rows(min_row=fila0 + 1, max_row=r - 1):
        if fila[-1].value:
            for c in fila:
                c.fill = rojo
    anchos = [9, 8, 6, 5, 11, 15, 12, 8, 14, 10, 11, 36, 28, 50, 60]
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a
    ws.freeze_panes = ws.cell(row=fila0 + 1, column=1)
    wb.save(ruta)


def informe_txt(d: Despiece, ruta: Path) -> None:
    L = [f"INFORME DE VALIDACIÓN — {d.plano.proyecto}", "=" * 60,
         f"Módulo: {d.plano.modulo.ancho_x:.3f} × {d.plano.modulo.alto_y:.3f} m",
         f"Caída hacia el lado: {d.plano.caida_hacia or 'no definida'}",
         f"Paneles de muro: {len(d.muros)} · Paneles de techo: {len(d.techos)} · Vanos: {len(d.plano.vanos)}",
         ""]
    if d.alertas:
        L.append(f"ALERTAS ({len(d.alertas)}):")
        L += [f"  - {a}" for a in d.alertas]
    else:
        L.append("Sin alertas: el dibujo cumple todas las reglas verificadas.")
    ruta.write_text("\n".join(L) + "\n", encoding="utf-8")


def _bordes_txt(p) -> str:
    nombres = {"izq": "izq.", "der": "der."}
    partes = []
    for b, (clase, dato) in p.bordes.items():
        if clase == "tirante":
            partes.append(f"{nombres[b]}: trae tirante 25x50 (junta con {dato})")
        elif clase == "recibe":
            partes.append(f"{nombres[b]}: rebaje libre (recibe de {dato})")
        else:
            partes.append(f"{nombres[b]}: tapa 25x50 (esquina {dato})")
    return "; ".join(partes)


def _tirantes_techo(t) -> str:
    lleva = [f"{'+'.join(v)}" for l, v in t.uniones.items() if t.tirantes.get(l) == "lleva"]
    recibe = [f"{'+'.join(v)}" for l, v in t.uniones.items() if t.tirantes.get(l) == "recibe"]
    partes = []
    if lleva:
        partes.append("trae tirante 25x50 hacia " + ", ".join(lleva))
    if recibe:
        partes.append("recibe tirante de " + ", ".join(recibe))
    return "; ".join(partes)
