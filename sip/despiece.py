"""Despiece: asigna paneles a lados, numera, resuelve vanos y valida reglas."""
from __future__ import annotations

from . import config as C
from .modelo import (Despiece, PanelMuro, PanelTecho, Plano, Rect, VanoEnPanel,
                     VanoLeido)


def _cm(x: float) -> str:
    return f"{x * 100:.1f} cm"


def _fmt(x: float) -> str:
    return f"{x:.3f} m".replace(".", ",")


# ----------------------------------------------------------------------------------
# Geometría auxiliar por lado
# ----------------------------------------------------------------------------------
def _coord_a_lo_largo(lado: str, r: Rect) -> tuple[float, float]:
    """Intervalo (mín, máx) del rectángulo a lo largo del muro."""
    return (r.x0, r.x1) if lado in ("A", "C") else (r.y0, r.y1)


def _lado_de_panel(r: Rect, m: Rect) -> str:
    cx, cy = r.centro
    d = {"A": abs(cy - m.y1), "C": abs(cy - m.y0),
         "B": abs(cx - m.x1), "D": abs(cx - m.x0)}
    return min(d, key=d.get)


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
def calcular(plano: Plano) -> Despiece:
    alertas: list[str] = list(plano.avisos)
    m = plano.modulo
    W, H = m.ancho_x, m.alto_y

    # --- Módulo múltiplo de 61 cm -------------------------------------------------------
    for nombre, dim in (("ancho (X)", W), ("largo (Y)", H)):
        k = round(dim / C.MODULO_BASE)
        if k == 0 or abs(dim - k * C.MODULO_BASE) > C.TOL_MODULO:
            alertas.append(
                f"Módulo: {nombre} = {_fmt(dim)} no es múltiplo de 61 cm "
                f"(más cercano: {_fmt(max(k, 1) * C.MODULO_BASE)}).")

    caida = plano.caida_hacia
    laterales = _tiene_muro_lateral(caida)
    e = C.ESPESOR_PANEL

    # --- Paneles de muro por lado --------------------------------------------------------
    por_lado: dict[str, list[Rect]] = {l: [] for l in C.LADOS}
    for r in plano.paneles:
        por_lado[_lado_de_panel(r, m)].append(r)

    muros: list[PanelMuro] = []
    for lado in C.LADOS:
        rects = por_lado[lado]
        if not rects:
            alertas.append(f"Lado {lado}: no tiene paneles dibujados.")
            continue
        nx, ny = C.NUMERACION[lado]
        # A y C se numeran en +x; B y D en -y
        rects.sort(key=lambda r: r.centro[0] if nx else -r.centro[1])
        alto = C.ALTO_PANEL_BAJO if (caida == lado) else C.ALTO_PANEL
        n_ajustes = 0
        pos_prev = None
        for i, r in enumerate(rects, start=1):
            largo = r.ancho_x if lado in ("A", "C") else r.alto_y
            esp = r.alto_y if lado in ("A", "C") else r.ancho_x
            p = PanelMuro(codigo=f"{lado}-{i:02d}", lado=lado, numero=i, rect=r,
                          largo=largo, espesor=esp, alto=alto)
            if abs(esp - e) > C.TOL:
                p.alertas.append(f"Espesor en planta {_fmt(esp)}; debería ser {_fmt(e)}.")
            if largo > C.ANCHO_PANEL + C.TOL:
                p.alertas.append(f"Ancho {_fmt(largo)} supera el estándar de {_fmt(C.ANCHO_PANEL)}.")
            elif largo < C.ANCHO_PANEL - C.TOL:
                p.es_ajuste = True
                n_ajustes += 1
            # Apoya sobre el contorno del módulo
            cx, cy = r.centro
            borde = {"A": m.y1 - e / 2, "C": m.y0 + e / 2,
                     "B": m.x1 - e / 2, "D": m.x0 + e / 2}[lado]
            dist = abs((cy if lado in ("A", "C") else cx) - borde)
            if dist > 0.02:
                p.alertas.append("No apoya sobre el contorno del módulo "
                                 f"(desfasado {_cm(dist)}).")
            # Continuidad con el panel anterior
            lo, hi = _coord_a_lo_largo(lado, r)
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
            if lado in ("B", "D"):
                esperado = H if laterales[lado] else H - 2 * e
                a0 = m.y0 if laterales[lado] else m.y0 + e
                a1 = m.y1 if laterales[lado] else m.y1 - e
            else:
                esperado = W if laterales[lado] else W - 2 * e
                a0 = m.x0 if laterales[lado] else m.x0 + e
                a1 = m.x1 if laterales[lado] else m.x1 - e
            los = [_coord_a_lo_largo(lado, r) for r in rects]
            c0 = min(l[0] for l in los)
            c1 = max(l[1] for l in los)
            if abs(c0 - a0) > C.TOL or abs(c1 - a1) > C.TOL:
                tipo = "lateral (toma las esquinas)" if laterales[lado] else "entre laterales"
                alertas.append(
                    f"Lado {lado} ({tipo}): los paneles cubren {_fmt(c1 - c0)} y se esperan {_fmt(esperado)}.")

    _bordes_muros(muros)

    # --- Revestimiento ---------------------------------------------------------------------------
    # Todos los muros llevan smart panel (cara exterior, sentido vertical), ajustes incluidos.
    # Un bloque REV_BLOQUE dentro del panel cambia la cara o el sentido.
    for p in muros:
        p.smart, p.cara_rev, p.sentido_rev = True, "exterior", "vertical"
        for mk in plano.marcas_rev:
            if p.rect.contiene(mk.x, mk.y):
                p.smart = True
                p.cara_rev = "exterior" if mk.cara.startswith("E") else "interior"
                p.sentido_rev = "horizontal" if mk.sentido.startswith("H") else "vertical"
                break

    # --- Vanos --------------------------------------------------------------------------------------------
    for v in plano.vanos:
        _resolver_vano(v, muros, alertas)

    # --- Techo ------------------------------------------------------------------------------------------------
    techos = _despiece_techo(plano, caida, alertas)

    # Alertas por panel hacia la lista general
    for p in muros:
        for a in p.alertas:
            alertas.append(f"{p.codigo}: {a}")
    for t in techos:
        for a in t.alertas:
            alertas.append(f"{t.codigo}: {a}")
    return Despiece(plano=plano, muros=muros, techos=techos, alertas=alertas)


# ----------------------------------------------------------------------------------
def _resolver_vano(v: VanoLeido, muros: list[PanelMuro], alertas: list[str]) -> None:
    for a in v.avisos:
        alertas.append(f"{v.id}: {a}")
    tocados = [p for p in muros if p.rect.interseca(v.rect, tol=1e-4)]
    if not tocados:
        alertas.append(f"{v.id}: el rectángulo no toca ningún panel.")
        return
    lados = {p.lado for p in tocados}
    if len(lados) > 1:
        alertas.append(f"{v.id}: toca paneles de más de un lado ({', '.join(sorted(lados))}); revisar la posición.")
        return
    lado = next(iter(lados))
    if v.alto is None:
        return

    h = C.HUELGO_VANO
    s0, s1 = _coord_a_lo_largo(lado, v.rect)
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
        lo, hi = _coord_a_lo_largo(lado, p.rect)
        c0, c1 = max(s0, lo), min(s1, hi)
        if c1 - c0 < C.TOL:
            continue
        u_a, u_b = _a_vista(lado, p.rect, s0), _a_vista(lado, p.rect, s1)
        u_ini, u_fin = min(u_a, u_b), max(u_a, u_b)
        jamba_izq = u_ini >= -C.TOL
        jamba_der = u_fin <= p.largo + C.TOL
        # Parte contenida en este panel
        cu0, cu1 = max(u_ini, 0.0), min(u_fin, p.largo)
        # Tirantes: verticales (jambas) siempre en taller. Dintel y antepecho en
        # taller solo si el vano entero está dentro de un panel.
        vp = VanoEnPanel(
            vano_id=v.id, tipo=v.tipo, u0=cu0, u1=cu1, v0=v0, v1=v1,
            completo=completo, jamba_izq=jamba_izq, jamba_der=jamba_der,
            tirante_dintel_taller=completo,
            tirante_antepecho_taller=completo and not hasta_piso,
            tiene_antepecho=not hasta_piso,
            ancho_total=ancho_total, alto_total=alto_total)
        p.vanos.append(vp)

        # Distancia mínima a los bordes del panel (solo en los lados que son jambas)
        # Se mide desde la abertura, sin huelgo.
        if jamba_izq:
            d = (u_ini + h) - 0.0
            if d < C.DIST_MIN_BORDE - C.TOL:
                p.alertas.append(f"{v.id} a {_cm(d)} del borde izquierdo (mínimo {_cm(C.DIST_MIN_BORDE)}).")
        if jamba_der:
            d = p.largo - (u_fin - h)
            if d < C.DIST_MIN_BORDE - C.TOL:
                p.alertas.append(f"{v.id} a {_cm(d)} del borde derecho (mínimo {_cm(C.DIST_MIN_BORDE)}).")
        # Altura
        if p.alto - v1 < C.REBAJE_VANO - C.TOL:
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

    # --- Numeración: de izquierda a derecha y de arriba hacia abajo (filas) ---------------
    def fila(r):
        return round(-r.centro[1] / 0.05)       # agrupa por filas con 5 cm de tolerancia
    rects.sort(key=lambda r: (fila(r), r.centro[0]))

    # Borde del techo del lado de la caída
    bx0 = min(r.x0 for r in rects)
    bx1 = max(r.x1 for r in rects)
    by0 = min(r.y0 for r in rects)
    by1 = max(r.y1 for r in rects)

    def toca_caida(r):
        return {"A": abs(r.y1 - by1) < C.TOL, "C": abs(r.y0 - by0) < C.TOL,
                "B": abs(r.x1 - bx1) < C.TOL, "D": abs(r.x0 - bx0) < C.TOL}[caida]

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
        W, H = m.ancho_x, m.alto_y
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

    # --- Cobertura: el techo debe cubrir todo el módulo y no tener huecos -------------------
    falta = []
    for lado, d in (("D (izquierda)", m.x0 - bx0), ("B (derecha)", bx1 - m.x1),
                    ("C (abajo)", m.y0 - by0), ("A (arriba)", by1 - m.y1)):
        if d < -C.TOL:
            falta.append(f"lado {lado}: {_cm(-d)}")
    if falta:
        alertas.append("Techo: los paneles no llegan a cubrir el módulo (" + "; ".join(falta) + ").")
    area_paneles = sum(r.ancho_x * r.alto_y for r in rects)
    area_envolvente = (bx1 - bx0) * (by1 - by0)
    if area_envolvente - area_paneles > 0.01:
        alertas.append(f"Techo: hay huecos sin cubrir ({area_envolvente - area_paneles:.2f} m² entre "
                       f"los paneles dibujados y el rectángulo que los envuelve).")
    elif area_paneles - area_envolvente > 0.01:
        alertas.append(f"Techo: los paneles se superponen ({area_paneles - area_envolvente:.2f} m² de más).")
    return out


def _bordes_muros(muros: list[PanelMuro]) -> None:
    """Define, para cada panel de muro, qué trae en sus bordes verticales:

    * En cada junta entre dos paneles de un lado, el de menor número trae el tirante
      de 25 x 50 mm clavado; el otro deja el rebaje libre para recibirlo.
    * Los paneles de esquina (primero y último de cada lado) traen la tapa de 25 x 50 mm
      en el borde que da a la esquina. Lo hacen los dos paneles que se encuentran en ella.
    """
    # (lado) -> (esquina que da el borde izquierdo, esquina del borde derecho) en la vista interior
    esquinas = {"A": ("D", "B"), "B": ("A", "C"), "C": ("B", "D"), "D": ("C", "A")}
    for lado in C.LADOS:
        ps = sorted((p for p in muros if p.lado == lado), key=lambda p: p.numero)
        if not ps:
            continue
        # A y B se numeran de izquierda a derecha en la vista interior; C y D al revés.
        hacia_sig = "der" if lado in ("A", "B") else "izq"
        hacia_ant = "izq" if hacia_sig == "der" else "der"
        for a, b in zip(ps, ps[1:]):
            a.bordes[hacia_sig] = ("tirante", b.codigo)
            b.bordes[hacia_ant] = ("recibe", a.codigo)
        izq_esq, der_esq = esquinas[lado]
        primero, ultimo = ps[0], ps[-1]
        borde_primero = hacia_ant      # el primer panel está en el extremo opuesto al "siguiente"
        borde_ultimo = hacia_sig
        primero.bordes[borde_primero] = ("tapa", izq_esq if borde_primero == "izq" else der_esq)
        ultimo.bordes[borde_ultimo] = ("tapa", izq_esq if borde_ultimo == "izq" else der_esq)
