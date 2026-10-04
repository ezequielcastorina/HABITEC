"""Lectura del DXF: convierte las capas en objetos del modelo."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import ezdxf

from . import config as C
from .modelo import MarcaRevestimiento, Plano, Rect, VanoLeido

FACTOR_UNIDAD = {"m": 1.0, "cm": 0.01, "mm": 0.001}
INSUNITS = {4: "mm", 5: "cm", 6: "m"}


def _num(texto: str) -> Optional[float]:
    """Convierte '1,00' o '1.00' en float; None si no se puede."""
    try:
        return float(str(texto).strip().replace(",", "."))
    except ValueError:
        return None


def _puntos(ent) -> list[tuple[float, float]]:
    if ent.dxftype() == "LWPOLYLINE":
        return [(p[0], p[1]) for p in ent.get_points("xy")]
    if ent.dxftype() == "POLYLINE":
        return [(v.dxf.location.x, v.dxf.location.y) for v in ent.vertices]
    return []


def _es_cerrada(ent) -> bool:
    if ent.dxftype() == "LWPOLYLINE":
        return bool(ent.closed)
    if ent.dxftype() == "POLYLINE":
        return bool(ent.is_closed)
    return False


def _rect(ent, f: float, avisos: list[str], etiqueta: str) -> Optional[Rect]:
    pts = _puntos(ent)
    if not _es_cerrada(ent):
        # Se acepta una polilínea de 5 puntos con el último igual al primero
        if not (len(pts) == 5 and pts[0] == pts[-1]):
            avisos.append(f"{etiqueta}: polilínea abierta (se ignora).")
            return None
        pts = pts[:-1]
    if len(pts) != 4:
        avisos.append(f"{etiqueta}: no es un rectángulo de 4 vértices (se ignora).")
        return None
    xs = [p[0] * f for p in pts]
    ys = [p[1] * f for p in pts]
    r = Rect(float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))
    # Verifica que cada vértice esté en una esquina del rectángulo
    for x, y in zip(xs, ys):
        en_x = abs(x - r.x0) < C.TOL or abs(x - r.x1) < C.TOL
        en_y = abs(y - r.y0) < C.TOL or abs(y - r.y1) < C.TOL
        if not (en_x and en_y):
            avisos.append(f"{etiqueta}: rectángulo girado o irregular (se usa su caja envolvente).")
            break
    return r


def _atributos(ins) -> dict[str, str]:
    return {a.dxf.tag.upper(): a.dxf.text for a in ins.attribs}


def _lado_caida(dx: float, dy: float) -> str:
    if abs(dy) >= abs(dx):
        return "A" if dy > 0 else "C"
    return "B" if dx > 0 else "D"


def leer_plano(ruta: str | Path, proyecto: str, unidades: str = "auto") -> Plano:
    doc = ezdxf.readfile(str(ruta))
    msp = doc.modelspace()
    avisos: list[str] = []

    if unidades == "auto":
        u = INSUNITS.get(int(doc.header.get("$INSUNITS", 0)))
        if u is None:
            u = "m"
            avisos.append("El DXF no declara unidades; se asumen METROS (usar --unidades cm o mm si no es así).")
        unidades = u
    f = FACTOR_UNIDAD[unidades]

    # --- Módulo -----------------------------------------------------------
    modulos = []
    for e in msp.query(f'LWPOLYLINE POLYLINE[layer=="{C.CAPA_MODULO}"]'):
        r = _rect(e, f, avisos, "Módulo")
        if r:
            modulos.append(r)
    if not modulos:
        raise ValueError(f"No hay un rectángulo cerrado en la capa {C.CAPA_MODULO}.")
    if len(modulos) > 1:
        avisos.append(f"Hay {len(modulos)} polilíneas en {C.CAPA_MODULO}; se usa la primera (un archivo = un módulo).")
    modulo = modulos[0]

    # --- Caída ---------------------------------------------------------------
    # Se toma el segmento más largo de la capa (el "cuerpo" de la flecha);
    # las líneas cortas de la punta no cuentan.
    caida = None
    mejor = 0.0
    for e in msp.query(f'LINE LWPOLYLINE[layer=="{C.CAPA_CAIDA}"]'):
        segmentos = []
        if e.dxftype() == "LINE":
            segmentos.append((e.dxf.end.x - e.dxf.start.x, e.dxf.end.y - e.dxf.start.y))
        else:
            pts = _puntos(e)
            segmentos += [(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
        for dx, dy in segmentos:
            largo = math.hypot(dx, dy)
            if largo > mejor:
                mejor = largo
                caida = _lado_caida(dx, dy)
    if caida is None:
        avisos.append(f"No hay flecha de caída en la capa {C.CAPA_CAIDA}; no se pueden calcular "
                      "las alturas de los muros ni las esquinas.")

    # --- Paneles de muro y de techo -------------------------------------------------
    paneles: list[Rect] = []
    for e in msp.query(f'LWPOLYLINE POLYLINE[layer=="{C.CAPA_PANEL}"]'):
        r = _rect(e, f, avisos, "Panel")
        if r:
            paneles.append(r)
    techos: list[Rect] = []
    for e in msp.query(f'LWPOLYLINE POLYLINE[layer=="{C.CAPA_TECHO}"]'):
        r = _rect(e, f, avisos, "Panel de techo")
        if r:
            techos.append(r)

    # --- Vanos ----------------------------------------------------------------------
    rect_vanos: list[Rect] = []
    for e in msp.query(f'LWPOLYLINE POLYLINE[layer=="{C.CAPA_VANO}"]'):
        r = _rect(e, f, avisos, "Vano")
        if r:
            rect_vanos.append(r)
    inserts_vano = list(msp.query(f'INSERT[layer=="{C.CAPA_VANO}"]'))

    vanos: list[VanoLeido] = []
    # Los vanos se numeran de izquierda a derecha y de arriba hacia abajo
    rect_vanos.sort(key=lambda r: (round(-r.centro[1], 3), r.centro[0]))
    for i, r in enumerate(rect_vanos, start=1):
        v = VanoLeido(id=f"V{i}", rect=r)
        cx, cy = r.centro
        marca = None
        for ins in inserts_vano:
            px, py = ins.dxf.insert.x * f, ins.dxf.insert.y * f
            if r.contiene(px, py):
                marca = ins
                break
        if marca is None:
            v.avisos.append("Sin bloque con atributos (TIPO, ALTO, ANTEPECHO) dentro del vano.")
        else:
            at = _atributos(marca)
            tipo = at.get("TIPO", "V").strip().upper()
            if tipo not in C.TIPOS_VANO:
                v.avisos.append(f"TIPO '{tipo}' desconocido (usar {', '.join(C.TIPOS_VANO)}); se toma ventana.")
                tipo = "V"
            v.tipo = tipo
            alto = _num(at.get("ALTO", ""))
            v.alto = alto * f if alto is not None else None
            ante = _num(at.get("ANTEPECHO", ""))
            if tipo in C.TIPOS_HASTA_PISO:
                v.antepecho = 0.0
            elif ante is not None:
                v.antepecho = ante * f
            else:
                v.avisos.append("Falta ANTEPECHO; se toma 0.")
        if v.alto is None:
            v.avisos.append("Falta ALTO del vano; no se puede calcular el vano de corte.")
        vanos.append(v)

    # --- Revestimiento (smart panel) -------------------------------------------------------
    marcas: list[MarcaRevestimiento] = []
    for ins in msp.query(f'INSERT[layer=="{C.CAPA_PANEL_REV}"]'):
        at = _atributos(ins)
        marcas.append(MarcaRevestimiento(
            x=ins.dxf.insert.x * f, y=ins.dxf.insert.y * f,
            cara=at.get("CARA", "EXT").strip().upper() or "EXT",
            sentido=at.get("SENTIDO", "V").strip().upper() or "V",
        ))
    for e in msp.query(f'LWPOLYLINE POLYLINE[layer=="{C.CAPA_PANEL_REV}"]'):
        r = _rect(e, f, avisos, "Marca de revestimiento")
        if r:
            cx, cy = r.centro
            marcas.append(MarcaRevestimiento(x=cx, y=cy))

    return Plano(proyecto=proyecto, modulo=modulo, caida_hacia=caida,
                 paneles=paneles, techos=techos, vanos=vanos,
                 marcas_rev=marcas, avisos=avisos)
