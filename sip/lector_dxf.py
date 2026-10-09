"""Lectura del DXF: convierte las capas en objetos del modelo."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import ezdxf

from . import config as C
from .contorno import construir
from .modelo import Boca, EjeSanitario, MarcaRevestimiento, Plano, Rect, VanoLeido

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

    # --- Módulo (contorno de lados horizontales y verticales) -----------------------------
    contornos = []
    for e in msp.query(f'LWPOLYLINE POLYLINE[layer=="{C.CAPA_MODULO}"]'):
        pts = [(x * f, y * f) for x, y in _puntos(e)]
        if not _es_cerrada(e):
            if len(pts) > 3 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
                pts = pts[:-1]
            else:
                avisos.append("Módulo: polilínea abierta (se ignora).")
                continue
        if len(pts) >= 4:
            contornos.append(pts)
    if not contornos:
        raise ValueError(f"No hay una polilínea cerrada en la capa {C.CAPA_MODULO}.")
    if len(contornos) > 1:
        avisos.append(f"Hay {len(contornos)} polilíneas en {C.CAPA_MODULO}; se usa la primera (un archivo = un módulo).")
    contorno, lados = construir(contornos[0])
    xs = [p[0] for p in contorno]
    ys = [p[1] for p in contorno]
    modulo = Rect(min(xs), min(ys), max(xs), max(ys))

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

    durlock: list[Rect] = []
    for e in msp.query(f'LWPOLYLINE POLYLINE[layer=="{C.CAPA_TABIQUE_DURLOCK}"]'):
        r = _rect(e, f, avisos, "Tabique de durlock")
        if r:
            durlock.append(r)

    # Lámina gráfica: sanitarios, puertas (hoja y arco) y electricidad se dibujan tal cual
    # (cualquier entidad o bloque; se aplana a polilíneas).
    from ezdxf import path as _path

    def _aplanar(ent, destino):
        if ent.dxftype() == "INSERT":
            for sub in ent.virtual_entities():
                _aplanar(sub, destino)
            return
        if ent.dxftype() in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "HATCH", "DIMENSION", "POINT"):
            return
        try:
            pa = _path.make_path(ent)
        except Exception:                                      # noqa: BLE001
            return
        for sub in pa.sub_paths():
            pts = [(q.x * f, q.y * f) for q in sub.flattening(0.01 / f)]
            if len(pts) >= 2:
                cerrado = sub.is_closed or (len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6)
                destino.append((pts, cerrado))
    sanitarios, puertas, electricidad, piso = [], [], [], []
    for e in msp.query(f'*[layer=="{C.CAPA_PISO}"]'):
        if e.dxftype() == "HATCH":
            if e.dxf.solid_fill:
                continue
            try:
                from ezdxf.render import hatching as _hatching
                for a_, b_ in _hatching.hatch_entity(e):
                    piso.append((((a_.x * f, a_.y * f), (b_.x * f, b_.y * f)), False))
            except Exception:                                  # noqa: BLE001
                avisos.append("No se pudo leer un sombreado de la capa PISO (se ignora).")
        else:
            _aplanar(e, piso)
    piso = [(list(pts), c) for pts, c in piso]
    for capa, destino in ((C.CAPA_SANITARIOS, sanitarios), (C.CAPA_PUERTA_GIRO, puertas),
                          (C.CAPA_ELECTRICIDAD, electricidad)):
        for e in msp.query(f'*[layer=="{capa}"]'):
            _aplanar(e, destino)
    # Obra in situ: bocas (bloques ELEC_<TIPO> con ALTURA), cañerías y ejes sanitarios
    bocas = []
    for ins in msp.query(f'INSERT[layer=="{C.CAPA_ELECTRICIDAD}"]'):
        nombre = ins.dxf.name.upper()
        tipo = nombre[5:] if nombre.startswith("ELEC_") else nombre
        defecto = C.BOCAS.get(tipo, (None, None, 1.10))[2]
        alt = _num(_atributos(ins).get("ALTURA", ""))
        b = Boca(tipo=tipo, x=ins.dxf.insert.x * f, y=ins.dxf.insert.y * f,
                 altura=alt * f if alt is not None else defecto, por_defecto=alt is None and defecto is not None)
        if tipo == "CENTRO":
            b.altura, b.por_defecto = None, False
        bocas.append(b)
    canerias = []
    for capa, vista in ((C.CAPA_CANERIA, False), (C.CAPA_CANERIA_VISTA, True)):
        tmp = []
        for e in msp.query(f'*[layer=="{capa}"]'):
            _aplanar(e, tmp)
        canerias += [(list(pts), vista) for pts, _ in tmp]
    ejes = []
    for ins in msp.query(f'INSERT[layer=="{C.CAPA_SAN_EJE}"]'):
        art = _atributos(ins).get("ARTEFACTO", "").strip() or "Artefacto"
        ejes.append(EjeSanitario(artefacto=art, x=ins.dxf.insert.x * f, y=ins.dxf.insert.y * f))

    # Revestimientos: líneas en capas REV_EXT_<material> / REV_INT_<material>
    revestimientos = []
    for e in msp.query("LINE LWPOLYLINE POLYLINE"):
        capa = e.dxf.layer.upper()
        for pref, cara in ((C.PREFIJO_REV_EXT, "EXT"), (C.PREFIJO_REV_INT, "INT")):
            if capa.startswith(pref) and len(capa) > len(pref):
                clave = capa[len(pref):].lower()
                if e.dxftype() == "LINE":
                    segs = [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
                else:
                    pts = _puntos(e)
                    if _es_cerrada(e) and pts:
                        pts = pts + [pts[0]]
                    segs = list(zip(pts, pts[1:]))
                for a_, b_ in segs:
                    revestimientos.append((cara, clave, (a_[0] * f, a_[1] * f), (b_[0] * f, b_[1] * f)))

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
    # Cada bloque con atributos se asocia al vano que lo contiene; si el punto de inserción quedó
    # al costado (los vanos en muros son franjas de 9 cm y es fácil errar), al más cercano que
    # esté a menos de 30 cm y todavía no tenga bloque.
    def distancia(r: Rect, x: float, y: float) -> float:
        return math.hypot(max(r.x0 - x, 0.0, x - r.x1), max(r.y0 - y, 0.0, y - r.y1))
    pares = sorted(((distancia(r, ins.dxf.insert.x * f, ins.dxf.insert.y * f), i, j)
                    for i, r in enumerate(rect_vanos) for j, ins in enumerate(inserts_vano)))
    marca_de: dict[int, object] = {}
    usados: set[int] = set()
    for dist, i, j in pares:
        if dist > 0.30 or i in marca_de or j in usados:
            continue
        marca_de[i] = inserts_vano[j]
        usados.add(j)
    alto_legado = False
    for i, r in enumerate(rect_vanos, start=1):
        v = VanoLeido(id=f"V{i}", rect=r)
        marca = marca_de.get(i - 1)
        if marca is None:
            v.avisos.append("Sin bloque con atributos (TIPO, DINTEL, ANTEPECHO) dentro del vano.")
        else:
            at = _atributos(marca)
            tipo = at.get("TIPO", "V").strip().upper()
            if tipo not in C.TIPOS_VANO:
                v.avisos.append(f"TIPO '{tipo}' desconocido (usar {', '.join(C.TIPOS_VANO)}); se toma ventana.")
                tipo = "V"
            v.tipo = tipo
            texto_dintel = at.get("DINTEL")
            if texto_dintel is None and "ALTO" in at:
                # Bloques con el atributo viejo: se carga ahí la cota del dintel (ej. 2.05)
                texto_dintel = at["ALTO"]
                alto_legado = True
            dintel = _num(texto_dintel or "")
            v.dintel = dintel * f if dintel is not None else None
            ante = _num(at.get("ANTEPECHO", ""))
            if tipo in C.TIPOS_HASTA_PISO:
                v.antepecho = 0.0
            elif ante is not None:
                v.antepecho = ante * f
            else:
                v.avisos.append("Falta ANTEPECHO; se toma 0.")
            if v.dintel is not None:
                v.alto = v.dintel - v.antepecho
                if v.alto <= C.TOL:
                    v.avisos.append(f"El dintel ({v.dintel:.3f} m) no queda por encima del antepecho ({v.antepecho:.3f} m).")
                    v.alto = None
        if v.alto is None and marca is not None and v.dintel is None:
            v.avisos.append("Falta DINTEL (cota del borde superior de la abertura); no se puede calcular el vano de corte.")
        vanos.append(v)

    notas: list[str] = []
    if alto_legado:
        notas.append("Los bloques de vano usan el atributo ALTO; se toma como cota del dintel (altura del borde superior "
                     "de la abertura desde el piso). Conviene renombrarlo DINTEL en la definición del bloque.")

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
                 marcas_rev=marcas, avisos=avisos, notas=notas, contorno=contorno, lados=lados,
                 tabiques_durlock=durlock, sanitarios=sanitarios, puertas=puertas,
                 electricidad=electricidad, revestimientos=revestimientos, piso=piso,
                 bocas=bocas, canerias=canerias, ejes_sanitarios=ejes)
