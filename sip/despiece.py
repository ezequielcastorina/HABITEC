"""Despiece: asigna paneles a lados, numera, resuelve vanos y valida reglas."""
from __future__ import annotations

from . import config as C
from . import contorno as K
from .modelo import (Despiece, Lado, JambaJunta, PanelMuro, PanelTecho, Plano, Rect, VanoEnPanel,
                     VanoLeido)


REFILADO_MAX = 0.50          # lo máximo que puede sobresalir el techo del lado de la caída (se refila en obra)


def _cm(x: float) -> str:
    return f"{x * 100:.1f} cm"


def _fmt(x: float) -> str:
    return f"{x:.3f} m".replace(".", ",")


# ----------------------------------------------------------------------------------
# Geometría auxiliar por lado
# ----------------------------------------------------------------------------------
def _coord_a_lo_largo(direccion: str, r: Rect) -> tuple[float, float]:
    """Intervalo (mín, máx) del rectángulo a lo largo del muro."""
    return (r.x0, r.x1) if direccion in ("A", "C") else (r.y0, r.y1)


def _asignar_lado(r: Rect, lados: list[Lado], e: float) -> tuple[Lado | None, float]:
    """Lado del contorno sobre el que apoya el panel `r` y desfasaje respecto de su posición ideal.
    Devuelve (None, distancia) si no apoya sobre ningún lado (tabique interior)."""
    cx, cy = r.centro
    mejor, dmin = None, 1e9
    for l in lados:
        ideal = l.coord + {"A": -e / 2, "B": -e / 2, "C": e / 2, "D": e / 2}[l.dir]
        centro_perp = cy if l.dir in ("A", "C") else cx
        lo, hi = _coord_a_lo_largo(l.dir, r)
        if min(hi, l.hi + e) - max(lo, l.lo - e) < C.TOL:
            continue
        d = abs(centro_perp - ideal)
        if d < dmin:
            mejor, dmin = l, d
    return mejor, dmin


def _a_vista(lado: str, p: Rect, s: float) -> float:
    """Convierte una coordenada a lo largo del muro (x o y del plano) en la
    coordenada 'u' de la vista interior del panel (0 = borde izquierdo)."""
    if lado == "A":
        return s - p.x0          # izquierda -> derecha = +x
    if lado == "B":
        return p.y1 - s          # izquierda -> derecha = -y
    if lado == "C":
        return p.x1 - s          # izquierda -> derecha = -x
    return s - p.y0              # D: izquierda -> derecha = +y


def _tiene_muro_lateral(caida: str | None) -> dict[str, bool]:
    """Los laterales (los que toman las 4 esquinas) son perpendiculares a la caída."""
    if caida in ("A", "C"):
        return {"B": True, "D": True, "A": False, "C": False}
    if caida in ("B", "D"):
        return {"A": True, "C": True, "B": False, "D": False}
    return {l: False for l in C.LADOS}


# ----------------------------------------------------------------------------------
# Despiece principal
# ----------------------------------------------------------------------------------
def calcular(plano: Plano, piel_exterior: str = "smart") -> Despiece:
    alertas: list[str] = list(plano.avisos)
    avisos: list[str] = list(plano.notas)
    m = plano.modulo
    W, H = m.ancho_x, m.alto_y

    # --- Módulo múltiplo de 61 cm (aviso suave: no cuenta como alerta) ---------------------
    for nombre, dim in (("ancho (X)", W), ("largo (Y)", H)):
        k = round(dim / C.MODULO_BASE)
        if k == 0 or abs(dim - k * C.MODULO_BASE) > C.TOL_MODULO:
            avisos.append(
                f"Módulo: {nombre} = {_fmt(dim)} no es múltiplo de 61 cm "
                f"(más cercano: {_fmt(max(k, 1) * C.MODULO_BASE)}).")

    caida = plano.caida_hacia
    e = C.ESPESOR_PANEL
    lados = plano.lados
    if not lados:                                  # plano armado a mano (sin contorno): rectángulo
        _, lados = K.construir([(m.x0, m.y1), (m.x1, m.y1), (m.x1, m.y0), (m.x0, m.y0)])
        plano.lados = lados
    por_letra = {l.letra: l for l in lados}

    # --- Paneles de muro por lado -----------------------------------------------------------
    por_lado: dict[str, list[Rect]] = {l.letra: [] for l in lados}
    desfase: dict[int, float] = {}
    interiores: list[Rect] = []
    for r in plano.paneles:
        l, dist = _asignar_lado(r, lados, e)
        if l is None or dist > 0.20:
            interiores.append(r)
        else:
            por_lado[l.letra].append(r)
            desfase[id(r)] = dist

    muros: list[PanelMuro] = []
    for l in lados:
        rects = por_lado[l.letra]
        lado = l.letra
        if not rects:
            alertas.append(f"Lado {lado}: no tiene paneles dibujados.")
            continue
        nx, ny = C.NUMERACION[l.dir]
        # dirección A y C se numeran en +x; B y D en -y
        rects.sort(key=lambda r: r.centro[0] if nx else -r.centro[1])
        alto = C.ALTO_PANEL_BAJO if (caida == l.dir) else C.ALTO_PANEL
        n_ajustes = 0
        pos_prev = None
        for i, r in enumerate(rects, start=1):
            horiz = l.dir in ("A", "C")
            largo = r.ancho_x if horiz else r.alto_y
            esp = r.alto_y if horiz else r.ancho_x
            p = PanelMuro(codigo=f"{lado}-{i:02d}", lado=lado, numero=i, rect=r,
                          largo=largo, espesor=esp, alto=alto, dir=l.dir)
            if abs(esp - e) > C.TOL:
                p.alertas.append(f"Espesor en planta {_fmt(esp)}; debería ser {_fmt(e)}.")
            if largo > C.ANCHO_PANEL + C.TOL:
                p.alertas.append(f"Ancho {_fmt(largo)} supera el estándar de {_fmt(C.ANCHO_PANEL)}.")
            elif largo < C.ANCHO_PANEL - C.TOL:
                p.es_ajuste = True
                n_ajustes += 1
            # Apoya sobre el contorno del módulo
            dist = desfase.get(id(r), 0.0)
            if dist > 0.02:
                p.alertas.append("No apoya sobre el contorno del módulo "
                                 f"(desfasado {_cm(dist)}).")
            # Continuidad con el panel anterior
            lo, hi = _coord_a_lo_largo(l.dir, r)
            ini, fin = (lo, hi) if nx else (hi, lo)
            if pos_prev is not None:
                salto = (ini - pos_prev) if nx else (pos_prev - ini)
                if salto > C.TOL:
                    alertas.append(f"Lado {lado}: hueco de {_cm(salto)} entre {muros[-1].codigo} y {p.codigo}.")
                elif salto < -C.TOL:
                    alertas.append(f"Lado {lado}: {muros[-1].codigo} y {p.codigo} se pisan {_cm(-salto)}.")
            pos_prev = fin
            muros.append(p)
        if n_ajustes > 1:
            alertas.append(f"Lado {lado}: hay {n_ajustes} paneles de ajuste (se espera uno como máximo).")

        # Largo total esperado del lado
        if caida is not None:
            lateral = l.dir not in (caida, {"A": "C", "B": "D", "C": "A", "D": "B"}[caida])
            a0, a1 = K.extremos_esperados(l, lateral, e)
            los = [_coord_a_lo_largo(l.dir, r) for r in rects]
            c0 = min(x[0] for x in los)
            c1 = max(x[1] for x in los)
            if abs(c0 - a0) > C.TOL or abs(c1 - a1) > C.TOL:
                tipo = "lateral (toma las esquinas)" if lateral else "entre laterales"
                alertas.append(
                    f"Lado {lado} ({tipo}): los paneles cubren {_fmt(c1 - c0)} y se esperan {_fmt(a1 - a0)}.")

    # --- Tabiques interiores (paneles que no apoyan sobre el contorno) --------------------------
    muros += _tabiques(interiores, caida, e, alertas)

    _bordes_muros(muros, por_letra)

    # --- Revestimiento ---------------------------------------------------------------------------
    # Cara exterior de los muros. Con smart panel (por defecto) lo llevan todos, ajustes incluidos
    # (cara exterior, tablas verticales; un bloque REV_BLOQUE cambia la cara o el sentido).
    # Con piel "osb" ningún muro lleva smart panel: OSB en las dos caras.
    if piel_exterior == "smart":
        for p in muros:
            if p.lado == "I":                  # los tabiques interiores no llevan smart panel
                continue
            p.smart, p.cara_rev, p.sentido_rev = True, "exterior", "vertical"
            for mk in plano.marcas_rev:
                if p.rect.contiene(mk.x, mk.y):
                    p.cara_rev = "exterior" if mk.cara.startswith("E") else "interior"
                    p.sentido_rev = "horizontal" if mk.sentido.startswith("H") else "vertical"
                    break

    # --- Vanos --------------------------------------------------------------------------------------------
    for v in plano.vanos:
        _resolver_vano(v, muros, alertas, plano.tabiques_durlock)

    # --- Techo ------------------------------------------------------------------------------------------------
    techos = _despiece_techo(plano, caida, alertas)

    # Alertas por panel hacia la lista general
    for p in muros:
        for a in p.alertas:
            alertas.append(f"{p.codigo}: {a}")
    for t in techos:
        for a in t.alertas:
            alertas.append(f"{t.codigo}: {a}")
    return Despiece(plano=plano, muros=muros, techos=techos, alertas=alertas, avisos=avisos)


# ----------------------------------------------------------------------------------
def _resolver_vano(v: VanoLeido, muros: list[PanelMuro], alertas: list[str], durlock=()) -> None:
    tocados = [p for p in muros if p.rect.interseca(v.rect, tol=1e-4)]
    if not tocados and any(t.interseca(v.rect, tol=1e-4) for t in durlock):
        return                                  # puerta en un tabique de durlock: se resuelve en obra
    for a in v.avisos:
        alertas.append(f"{v.id}: {a}")
    if not tocados:
        alertas.append(f"{v.id}: el rectángulo no toca ningún panel.")
        return
    lados = {p.lado for p in tocados}
    if len(lados) > 1:
        alertas.append(f"{v.id}: toca paneles de más de un lado ({', '.join(sorted(lados))}); revisar la posición.")
        return
    direc = tocados[0].dir
    if v.alto is None:
        return

    h = C.HUELGO_VANO
    s0, s1 = _coord_a_lo_largo(direc, v.rect)
    s0 -= h
    s1 += h                                     # vano de corte, a lo largo del muro
    hasta_piso = v.tipo in C.TIPOS_HASTA_PISO
    v0 = 0.0 if hasta_piso else v.antepecho - h
    v1 = v.antepecho + v.alto + h
    ancho_total = s1 - s0
    alto_total = v1 - v0

    tocados.sort(key=lambda p: p.numero)
    if len(tocados) > 2:
        alertas.append(f"{v.id}: atraviesa {len(tocados)} paneles; la regla de taller cubre hasta 2.")
    completo = len(tocados) == 1

    for p in tocados:
        lo, hi = _coord_a_lo_largo(direc, p.rect)
        c0, c1 = max(s0, lo), min(s1, hi)
        if c1 - c0 < C.TOL:
            continue
        u_a, u_b = _a_vista(direc, p.rect, s0), _a_vista(direc, p.rect, s1)
        u_ini, u_fin = min(u_a, u_b), max(u_a, u_b)
        jamba_izq = u_ini >= -C.TOL - 1e-6
        jamba_der = u_fin <= p.largo + C.TOL + 1e-6
        # Parte contenida en este panel
        cu0, cu1 = max(u_ini, 0.0), min(u_fin, p.largo)

        # Distancia de la abertura (sin huelgo) a los bordes del panel, en los lados que son jambas.
        d_izq = (u_ini + h) if jamba_izq else None
        d_der = (p.largo - (u_fin - h)) if jamba_der else None
        # Jamba justo sobre la junta con el panel vecino: se admite. El tirante de la jamba lo
        # trae el vecino, encastrado desde taller, y este panel no lleva tirante de ese lado.
        junta_izq = junta_der = ""
        if d_izq is not None and abs(d_izq) <= C.TOL and p.bordes.get("izq", ("",))[0] in ("tirante", "recibe"):
            junta_izq = p.bordes["izq"][1]
            jamba_izq = False
        if d_der is not None and abs(d_der) <= C.TOL and p.bordes.get("der", ("",))[0] in ("tirante", "recibe"):
            junta_der = p.bordes["der"][1]
            jamba_der = False

        # Tirantes: verticales (jambas) siempre en taller. Dintel y antepecho en
        # taller solo si el vano entero está dentro de un panel.
        vp = VanoEnPanel(
            vano_id=v.id, tipo=v.tipo, u0=cu0, u1=cu1, v0=v0, v1=v1,
            completo=completo, jamba_izq=jamba_izq, jamba_der=jamba_der,
            tirante_dintel_taller=completo,
            tirante_antepecho_taller=completo and not hasta_piso,
            tiene_antepecho=not hasta_piso,
            ancho_total=ancho_total, alto_total=alto_total,
            junta_izq=junta_izq, junta_der=junta_der)
        p.vanos.append(vp)

        for borde, vecino in (("izq", junta_izq), ("der", junta_der)):
            if not vecino:
                continue
            q = next((m for m in muros if m.codigo == vecino), None)
            if q is None:
                continue
            borde_q = next((b for b, (cl, dato) in q.bordes.items() if dato == p.codigo), None)
            if borde_q is None:
                continue
            rv0 = v0 - (C.REBAJE_VANO if not hasta_piso else 0.0)
            rv1 = v1 + C.REBAJE_VANO
            gap = (C.REBAJE_VANO - C.TIRANTE_VANO[0]) / 2
            q.jambas_junta.append(JambaJunta(
                vano_id=v.id, borde=borde_q, con_panel=p.codigo,
                v_ini=rv0 + (gap if not hasta_piso else 0.0), v_fin=rv1 - gap,
                v0=v0, v1=v1, tiene_antepecho=not hasta_piso))

        # Altura
        if v1 > p.alto + C.TOL:
            p.alertas.append(f"{v.id}: el vano llega a {_fmt(v1)} del piso y el panel mide {_fmt(p.alto)} de alto; "
                             "revisar DINTEL y ANTEPECHO del bloque.")
        elif p.alto - v1 < C.REBAJE_VANO - C.TOL:
            p.alertas.append(f"{v.id}: queda {_cm(p.alto - v1)} sobre el vano; el rebaje del dintel necesita "
                             f"{_cm(C.REBAJE_VANO)}.")
        if v0 < -C.TOL:
            p.alertas.append(f"{v.id}: antepecho menor al huelgo.")


# ----------------------------------------------------------------------------------
def _despiece_techo(plano: Plano, caida: str | None, alertas: list[str]) -> list[PanelTecho]:
    if not plano.techos:
        alertas.append(f"Techo: no hay paneles en la capa {C.CAPA_TECHO}.")
        return []
    if caida is None:
        alertas.append("Techo: sin dirección de caída no se puede orientar ni numerar los paneles.")
        return []
    horizontal = caida in ("A", "C")    # la caída corre en Y; el ancho del panel va en X
    rects = list(plano.techos)
    m = plano.modulo
    # Zona que cubre el techo: en los lados sin caída va por dentro del espesor de los muros
    # (apoya en el cordón de tirantes); del lado de la caída apoya sobre el muro bajo y
    # llega hasta el filo exterior, donde se refila en obra (puede sobresalir hasta REFILADO_MAX).
    e = C.ESPESOR_PANEL
    lados = plano.lados
    zona = K.desplazar(lados, {i: (0.0 if l.dir == caida else e) for i, l in enumerate(lados)})
    permitida = K.desplazar(lados, {i: (-REFILADO_MAX if l.dir == caida else e) for i, l in enumerate(lados)})
    zx0, zx1 = min(q[0] for q in zona), max(q[0] for q in zona)
    zy0, zy1 = min(q[1] for q in zona), max(q[1] for q in zona)

    # --- Numeración: de izquierda a derecha y de arriba hacia abajo (filas) ---------------
    def fila(r):
        return round(-r.centro[1] / 0.05)       # agrupa por filas con 5 cm de tolerancia
    rects.sort(key=lambda r: (fila(r), r.centro[0]))

    def toca_caida(r):
        for l in lados:
            if l.dir != caida:
                continue
            lo, hi = _coord_a_lo_largo(l.dir, r)
            if min(hi, l.hi) - max(lo, l.lo) < C.TOL:
                continue
            borde = {"A": r.y1, "C": r.y0, "B": r.x1, "D": r.x0}[l.dir]
            if (l.dir in ("A", "B") and borde >= l.coord - C.TOL) or (l.dir in ("C", "D") and borde <= l.coord + C.TOL):
                return True
        return False

    out: list[PanelTecho] = []
    for i, r in enumerate(rects, start=1):
        ancho = r.ancho_x if horizontal else r.alto_y      # perpendicular a la caída
        largo = r.alto_y if horizontal else r.ancho_x      # en el sentido de la caída
        t = PanelTecho(codigo=f"T-{i:02d}", numero=i, rect=r, ancho=ancho, largo=largo,
                       caida_hacia=caida, en_caida=toca_caida(r))
        menor, mayor = sorted((r.ancho_x, r.alto_y))
        if menor > C.ANCHO_PANEL + C.TOL or mayor > C.LARGO_MAX_PANEL + C.TOL:
            t.alertas.append(
                f"Mide {_fmt(menor)} × {_fmt(mayor)}; el máximo es {_fmt(C.ANCHO_PANEL)} × {_fmt(C.LARGO_MAX_PANEL)}.")
        # El lado largo del panel debe ir en el sentido corto del módulo
        W, H = zx1 - zx0, zy1 - zy0
        if abs(W - H) > C.TOL_MODULO and abs(mayor - menor) > C.TOL:
            lado_largo_en_x = r.ancho_x > r.alto_y
            modulo_corto_en_x = W < H
            if mayor > C.ANCHO_PANEL + C.TOL and lado_largo_en_x != modulo_corto_en_x:
                t.alertas.append("El lado largo del panel va en el sentido largo del módulo; "
                                 "debería ir en el sentido corto.")
        t.es_ajuste = not (abs(menor - C.ANCHO_PANEL) <= C.TOL and abs(mayor - C.LARGO_MAX_PANEL) <= C.TOL)
        out.append(t)

    # --- Uniones internas (llevan tirante) -------------------------------------------------------
    def solapan(a0, a1, b0, b1):
        return min(a1, b1) - max(a0, b0) > C.TOL
    for i, a in enumerate(out):
        for b in out[i + 1:]:
            ra, rb = a.rect, b.rect
            if abs(ra.x1 - rb.x0) <= C.TOL and solapan(ra.y0, ra.y1, rb.y0, rb.y1):
                a.uniones.setdefault("B", []).append(b.codigo)
                b.uniones.setdefault("D", []).append(a.codigo)
            elif abs(rb.x1 - ra.x0) <= C.TOL and solapan(ra.y0, ra.y1, rb.y0, rb.y1):
                a.uniones.setdefault("D", []).append(b.codigo)
                b.uniones.setdefault("B", []).append(a.codigo)
            if abs(ra.y1 - rb.y0) <= C.TOL and solapan(ra.x0, ra.x1, rb.x0, rb.x1):
                a.uniones.setdefault("A", []).append(b.codigo)
                b.uniones.setdefault("C", []).append(a.codigo)
            elif abs(rb.y1 - ra.y0) <= C.TOL and solapan(ra.x0, ra.x1, rb.x0, rb.x1):
                a.uniones.setdefault("C", []).append(b.codigo)
                b.uniones.setdefault("A", []).append(a.codigo)

    # --- Tirante de unión: lo trae clavado el panel de menor número -----------------------------
    for t in out:
        for lado, vecinos in t.uniones.items():
            nums = [int(v.split("-")[1]) for v in vecinos]
            if all(t.numero < n for n in nums):
                t.tirantes[lado] = "lleva"
            elif all(t.numero > n for n in nums):
                t.tirantes[lado] = "recibe"
            else:
                t.tirantes[lado] = "mixto"

    # --- Juntas trabadas: las juntas verticales de filas contiguas no deben coincidir ----------
    filas: dict[int, list[Rect]] = {}
    for r in rects:
        filas.setdefault(fila(r), []).append(r)
    claves = sorted(filas)
    def juntas(rs):
        rs = sorted(rs, key=lambda r: r.x0)
        return [r.x1 for r in rs[:-1]]
    for k0, k1 in zip(claves, claves[1:]):
        comunes = [x for x in juntas(filas[k0]) for y in juntas(filas[k1]) if abs(x - y) <= C.TOL]
        if comunes:
            alertas.append("Techo: las juntas de dos filas contiguas coinciden en "
                           + ", ".join(f"x = {_fmt(x - m.x0)}" for x in comunes)
                           + "; los paneles deberían trabarse.")

    # --- Superposiciones --------------------------------------------------------------------
    for i, a in enumerate(out):
        for b in out[i + 1:]:
            if a.rect.interseca(b.rect, tol=C.TOL):
                alertas.append(f"Techo: {a.codigo} y {b.codigo} se pisan.")

    # --- Cobertura: el techo debe cubrir toda su zona (por dentro de los muros) --------------
    xs = sorted({round(v, 6) for q in (zona + permitida) for v in (q[0],)} |
                {round(v, 6) for r in rects for v in (r.x0, r.x1)})
    ys = sorted({round(v, 6) for q in (zona + permitida) for v in (q[1],)} |
                {round(v, 6) for r in rects for v in (r.y0, r.y1)})
    huecos, sobran = [], []
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            dx, dy = x1 - x0, y1 - y0
            if dx < C.TOL or dy < C.TOL:
                continue
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            cubiertos = [t for t in out if t.rect.contiene(cx, cy)]
            if K.punto_en_poligono(cx, cy, zona) and not cubiertos:
                huecos.append((x0, y0, x1, y1))
            if cubiertos and not K.punto_en_poligono(cx, cy, permitida):
                sobran.append((x0, y0, x1, y1, cubiertos))
    if huecos:
        area = sum((a[2] - a[0]) * (a[3] - a[1]) for a in huecos)
        bx0, by0 = min(a[0] for a in huecos), min(a[1] for a in huecos)
        bx1, by1 = max(a[2] for a in huecos), max(a[3] for a in huecos)
        alertas.append(f"Techo: hay huecos sin cubrir ({area:.2f} m²) dentro de la zona del techo, "
                       f"entre x = {_fmt(bx0 - m.x0)} y {_fmt(bx1 - m.x0)} e y = {_fmt(by0 - m.y0)} y {_fmt(by1 - m.y0)}.")
    por_panel: dict[str, tuple[str, float]] = {}
    for x0, y0, x1, y1, cubiertos in sobran:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

        def dist(l):
            if l.dir in ("A", "C"):
                return abs(cy - l.coord) + max(0.0, l.lo - cx, cx - l.hi)
            return abs(cx - l.coord) + max(0.0, l.lo - cy, cy - l.hi)
        letra = min(lados, key=dist).letra
        prof = min(x1 - x0, y1 - y0)
        for t in cubiertos:
            ant = por_panel.get(t.codigo)
            if ant is None or prof > ant[1]:
                por_panel[t.codigo] = (letra, prof)
    for codigo, (letra, prof) in por_panel.items():
        alertas.append(f"Techo: {codigo} entra en el espesor del muro del lado {letra} ({_cm(prof)} de más); "
                       "en los lados sin caída el techo va por dentro de los muros.")
    return out


def _tabiques(rects: list[Rect], caida, e: float, alertas: list[str]) -> list[PanelMuro]:
    """Paneles de la capa PANEL que no apoyan sobre el contorno: tabiques interiores I-01, I-02…

    Se agrupan en tiras (paneles alineados y contiguos); dentro de cada tira se numeran como los
    muros (horizontales de izquierda a derecha, verticales de arriba hacia abajo)."""
    if not rects:
        return []
    items = []
    for r in rects:
        horiz = r.ancho_x >= r.alto_y
        direc = "A" if horiz else "B"
        eje = (r.y0 + r.y1) / 2 if horiz else (r.x0 + r.x1) / 2
        items.append((direc, round(eje, 3), r))
    # tiras: misma dirección y mismo eje, y se tocan a lo largo del muro
    items.sort(key=lambda t: (t[0], t[1], _coord_a_lo_largo(t[0], t[2])[0]))
    tiras: list[list] = []
    for it in items:
        if tiras:
            ult = tiras[-1][-1]
            if (ult[0] == it[0] and abs(ult[1] - it[1]) <= 0.02 and
                    _coord_a_lo_largo(it[0], it[2])[0] - _coord_a_lo_largo(ult[0], ult[2])[1] <= C.TOL):
                tiras[-1].append(it)
                continue
        tiras.append([it])
    # orden de las tiras: de arriba hacia abajo y de izquierda a derecha
    tiras.sort(key=lambda t: (-max(x[2].y1 for x in t), min(x[2].x0 for x in t)))
    out: list[PanelMuro] = []
    n = 0
    for tira in tiras:
        direc = tira[0][0]
        tira.sort(key=lambda x: x[2].centro[0] if direc == "A" else -x[2].centro[1])
        for _, _, r in tira:
            n += 1
            horiz = direc == "A"
            largo = r.ancho_x if horiz else r.alto_y
            esp = r.alto_y if horiz else r.ancho_x
            p = PanelMuro(codigo=f"I-{n:02d}", lado="I", numero=n, rect=r, largo=largo, espesor=esp,
                          alto=C.ALTO_PANEL, dir=direc)
            if abs(esp - e) > C.TOL:
                p.alertas.append(f"Espesor en planta {_fmt(esp)}; debería ser {_fmt(e)}.")
            if largo > C.ANCHO_PANEL + C.TOL:
                p.alertas.append(f"Ancho {_fmt(largo)} supera el estándar de {_fmt(C.ANCHO_PANEL)}.")
            elif largo < C.ANCHO_PANEL - C.TOL:
                p.es_ajuste = True
            out.append(p)
    return out


def _bordes_muros(muros: list[PanelMuro], por_letra: dict[str, Lado]) -> None:
    """Define, para cada panel de muro, qué trae en sus bordes verticales:

    * En cada junta entre dos paneles de un lado, el de menor número trae el tirante
      de 50 x 70 mm clavado (25 mm en cada panel); el otro deja el rebaje libre para recibirlo.
    * Los paneles de esquina (primero y último de cada lado) traen la tapa de 25 x 70 mm (medio tirante)
      en el borde que da a la esquina. Lo hacen los dos paneles que se encuentran en ella.
    * Tabiques interiores: las juntas entre paneles de una misma tira, igual que en los muros;
      los extremos de la tira quedan con rebaje libre (se resuelven en obra).
    """
    for letra, lado in por_letra.items():
        ps = sorted((p for p in muros if p.lado == letra), key=lambda p: p.numero)
        if not ps:
            continue
        # A y B se numeran de izquierda a derecha en la vista interior; C y D al revés.
        hacia_sig = "der" if lado.dir in ("A", "B") else "izq"
        hacia_ant = "izq" if hacia_sig == "der" else "der"
        for a, b in zip(ps, ps[1:]):
            a.bordes[hacia_sig] = ("tirante", b.codigo)
            b.bordes[hacia_ant] = ("recibe", a.codigo)
        # En la vista interior la lectura de izquierda a derecha sigue el sentido horario:
        # a la izquierda está el lado anterior y a la derecha el siguiente.
        izq_esq, der_esq = lado.letra_prev, lado.letra_sig
        primero, ultimo = ps[0], ps[-1]
        borde_primero = hacia_ant      # el primer panel está en el extremo opuesto al "siguiente"
        borde_ultimo = hacia_sig
        primero.bordes[borde_primero] = ("tapa", izq_esq if borde_primero == "izq" else der_esq)
        ultimo.bordes[borde_ultimo] = ("tapa", izq_esq if borde_ultimo == "izq" else der_esq)

    ti = sorted((p for p in muros if p.lado == "I"), key=lambda p: p.numero)
    for p in ti:
        p.bordes["izq"] = ("libre", "")
        p.bordes["der"] = ("libre", "")
    for a, b in zip(ti, ti[1:]):
        if a.dir != b.dir:
            continue
        la, lb = _coord_a_lo_largo(a.dir, a.rect), _coord_a_lo_largo(b.dir, b.rect)
        mismo_eje = (abs(((a.rect.y0 + a.rect.y1) - (b.rect.y0 + b.rect.y1)) / 2) <= 0.02 if a.dir == "A"
                     else abs(((a.rect.x0 + a.rect.x1) - (b.rect.x0 + b.rect.x1)) / 2) <= 0.02)
        contiguos = abs(lb[0] - la[1]) <= C.TOL      # a termina donde empieza b (numeración creciente en +x / -y)
        if a.dir == "B":
            contiguos = abs(la[0] - lb[1]) <= C.TOL
        if mismo_eje and contiguos:
            a.bordes["der"] = ("tirante", b.codigo)
            b.bordes["izq"] = ("recibe", a.codigo)
