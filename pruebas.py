"""Pruebas de humo del lector y del despiece. Correr con:  python pruebas.py"""
import math
import tempfile
from pathlib import Path

import ezdxf
from ezdxf.math import Matrix44

import generar_ejemplo
from sip.despiece import calcular
from sip.lector_dxf import leer_plano

tmp = Path(tempfile.mkdtemp())


def base() -> Path:
    ruta = tmp / "base.dxf"
    generar_ejemplo.crear(str(ruta), "m")
    return ruta


def modificar(origen: Path, nombre: str, fn) -> Path:
    doc = ezdxf.readfile(str(origen))
    fn(doc, doc.modelspace())
    destino = tmp / nombre
    doc.saveas(str(destino))
    return destino


def correr(ruta):
    return calcular(leer_plano(ruta, "Prueba"))


def test_ejemplo():
    d = correr(base())
    assert len(d.muros) == 14 and len(d.techos) == 8
    assert d.plano.caida_hacia == "A"
    alturas = {m.lado: m.alto for m in d.muros}
    assert alturas == {"A": 2.22, "B": 2.44, "C": 2.44, "D": 2.44}
    assert not d.alertas, d.alertas      # el vano a 10 cm de una junta ya no alerta (criterio del proyectista)
    # Techo por dentro del espesor de los muros (lados sin caída): 2,44 en X más ajuste de 0,43; fila inferior de 1,13
    ancho_x = sorted({(round(t.rect.ancho_x, 2), round(t.rect.alto_y, 2)) for t in d.techos})
    assert ancho_x == [(0.43, 1.13), (0.43, 1.22), (2.44, 1.13), (2.44, 1.22)], ancho_x
    assert sum(t.es_ajuste for t in d.techos) == 5
    t01 = d.techos[0]
    assert t01.en_caida and set(t01.uniones) == {"B", "C"}, t01.uniones   # vecino a la derecha y abajo
    assert not d.techos[-1].en_caida
    # Huelgo: ventana 1,00 x 1,00 -> 1,010 x 1,010 ; puerta ventana alto 2,05 -> 2,055
    a02 = next(m for m in d.muros if m.codigo == "A-02")
    vp = a02.vanos[0]
    assert abs(vp.ancho_total - 0.81) < 1e-6 and abs(vp.alto_total - 1.01) < 1e-6
    c01 = next(m for m in d.muros if m.codigo == "C-01")
    assert c01.vanos[0].completo and c01.vanos[0].jamba_der and c01.vanos[0].junta_izq == "C-02"
    assert abs(c01.vanos[0].alto_total - 2.055) < 1e-6      # sin huelgo contra el piso
    assert c01.vanos[0].tirante_dintel_taller               # vano completo en C-01: dintel en taller
    d03 = next(m for m in d.muros if m.codigo == "D-03")
    assert not d03.vanos[0].completo and not d03.vanos[0].tirante_dintel_taller   # corrediza compartida
    assert a02.vanos[0].tirante_dintel_taller               # vano completo: todo en taller


def test_caida_hacia_b():
    """Se gira el módulo 90° (A pasa a B): los laterales pasan a ser A y C."""
    def girar(doc, msp):
        rot = Matrix44.z_rotate(-math.pi / 2)
        for e in list(msp):
            e.transform(rot)
    d = correr(modificar(base(), "giro.dxf", girar))
    assert d.plano.caida_hacia == "B"
    bajos = {m.lado for m in d.muros if m.alto < 2.3}
    assert bajos == {"B"}
    assert not d.alertas, d.alertas


def test_sin_flecha():
    d = correr(modificar(base(), "sin_flecha.dxf",
                         lambda doc, msp: [msp.delete_entity(e) for e in list(msp.query('LINE[layer=="CAIDA"]'))]))
    assert any("flecha de caída" in a for a in d.alertas)


def test_panel_faltante_y_ancho_excedido():
    def quitar(doc, msp):
        for e in msp.query('LWPOLYLINE[layer=="PANEL"]'):
            pts = list(e.get_points("xy"))
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if abs(min(xs) - 1.31) < 1e-6 and max(ys) > 4.8:      # A-02
                msp.delete_entity(e)
                break
    d = correr(modificar(base(), "falta.dxf", quitar))
    assert any("hueco" in a for a in d.alertas), d.alertas


def test_modulo_no_multiplo():
    def agrandar(doc, msp):
        for e in msp.query('LWPOLYLINE[layer=="MODULO"]'):
            e.set_points([(0, 0), (3.10, 0), (3.10, 4.88), (0, 4.88)])
    d = correr(modificar(base(), "modulo.dxf", agrandar))
    assert any("no es múltiplo de 61 cm" in a for a in d.avisos) and not any("múltiplo" in a for a in d.alertas)


def test_techo_demasiado_largo_y_sin_cubrir():
    """Tiras de 5 m de largo (como en una versión anterior del ejemplo) deben dar alerta."""
    def tiras(doc, msp):
        for e in list(msp.query('LWPOLYLINE[layer=="TECHO"]')):
            msp.delete_entity(e)
        for x0, x1 in ((0, 1.22), (1.22, 2.44), (2.44, 3.05)):
            msp.add_lwpolyline([(x0, 0), (x1, 0), (x1, 5.0), (x0, 5.0)], close=True, dxfattribs={"layer": "TECHO"})
    d = correr(modificar(base(), "tiras.dxf", tiras))
    assert sum("el máximo es" in a for a in d.alertas) == 3, d.alertas


def test_techo_incompleto():
    def quitar_uno(doc, msp):
        e = list(msp.query('LWPOLYLINE[layer=="TECHO"]'))[0]
        msp.delete_entity(e)
    d = correr(modificar(base(), "techo_falta.dxf", quitar_uno))
    assert any("hay huecos" in a for a in d.alertas), d.alertas


def test_techo_orientacion():
    """Paneles de 1,22 x 2,44 con el lado largo en el sentido largo del módulo: alerta."""
    def girados(doc, msp):
        for e in list(msp.query('LWPOLYLINE[layer=="TECHO"]')):
            msp.delete_entity(e)
        for x0, x1 in ((0, 1.22), (1.22, 2.44), (2.44, 3.05)):
            for y0, y1 in ((0, 2.44), (2.44, 4.88)):
                msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                                   dxfattribs={"layer": "TECHO"})
    d = correr(modificar(base(), "techo_girado.dxf", girados))
    assert sum("sentido largo del módulo" in a for a in d.alertas) == 6, d.alertas


def test_techo_trabado():
    """El ejemplo está trabado (sin alerta); una grilla alineada da una alerta por cada par de filas."""
    d = correr(base())
    assert not any("trabarse" in a for a in d.alertas)
    def alineado(doc, msp):
        for e in list(msp.query('LWPOLYLINE[layer=="TECHO"]')):
            msp.delete_entity(e)
        for x0, x1 in ((0, 2.44), (2.44, 3.05)):
            for y0 in (0, 1.22, 2.44, 3.66):
                msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y0 + 1.22), (x0, y0 + 1.22)], close=True,
                                   dxfattribs={"layer": "TECHO"})
    d = correr(modificar(base(), "techo_alineado.dxf", alineado))
    assert sum("trabarse" in a for a in d.alertas) == 3, d.alertas


def test_tirantes_y_tapas():
    d = correr(base())
    m = {p.codigo: p for p in d.muros}
    # A: numeración = lectura de izquierda a derecha en la vista interior
    assert m["A-01"].bordes == {"izq": ("tapa", "D"), "der": ("tirante", "A-02")}
    assert m["A-02"].bordes == {"izq": ("recibe", "A-01"), "der": ("tirante", "A-03")}
    assert m["A-03"].bordes == {"izq": ("recibe", "A-02"), "der": ("tapa", "B")}
    # C: la numeración corre al revés de la lectura (vista interior mirando al sur)
    assert m["C-01"].bordes == {"der": ("tapa", "D"), "izq": ("tirante", "C-02")}
    assert m["C-03"].bordes["izq"] == ("tapa", "B")
    # Techo: el de menor número trae el tirante
    t = {x.codigo: x for x in d.techos}
    assert set(t["T-01"].tirantes.values()) == {"lleva"}
    assert set(t["T-08"].tirantes.values()) == {"recibe"}
    assert t["T-04"].tirantes == {"A": "recibe", "D": "recibe", "C": "lleva"}


def test_smart_y_corrediza_compartida():
    d = correr(base())
    for m in d.muros:
        assert m.smart, m.codigo
    a01 = next(m for m in d.muros if m.codigo == "A-01")
    assert a01.sentido_rev == "horizontal"
    assert all(m.cara_rev == "exterior" for m in d.muros if m.smart)
    cor = [m for m in d.muros if any(v.tipo == "C" for v in m.vanos)]
    assert sorted(m.codigo for m in cor) == ["D-02", "D-03"]
    for m in cor:
        v = m.vanos[0]
        assert not v.completo and abs((v.u1 - v.u0) - 0.605) < 1e-6
        assert v.v0 == 0 and abs(v.v1 - 2.005) < 1e-6
    assert [m for m in cor if m.vanos[0].jamba_izq] and [m for m in cor if m.vanos[0].jamba_der]


def test_jamba_sobre_la_junta():
    """Un vano cuya abertura arranca justo en la junta es válido: el tirante lo trae el vecino."""
    def mover(doc, msp):
        for e in list(msp):
            if e.dxf.layer != "VANO":
                continue
            if e.dxftype() == "LWPOLYLINE":
                pts = [(x, y) for x, y, *_ in e.get_points()]
                if max(y for _, y in pts) < 0.2:                    # vano del lado C
                    e.set_points([(0.61, 0), (1.31, 0), (1.31, 0.09), (0.61, 0.09)])
            elif e.dxftype() == "INSERT" and e.dxf.insert.y < 0.2:
                e.dxf.insert = (0.96, 0.045, 0)
    d = correr(modificar(base(), "junta.dxf", mover))
    assert not [a for a in d.alertas if "V4" in a], d.alertas
    c01 = next(m for m in d.muros if m.codigo == "C-01")
    c02 = next(m for m in d.muros if m.codigo == "C-02")
    vp = c01.vanos[0]
    assert vp.completo and vp.junta_izq == "C-02" and not vp.jamba_izq and vp.jamba_der
    assert len(c02.jambas_junta) == 1 and c02.jambas_junta[0].borde == "der"
    assert c02.jambas_junta[0].con_panel == "C-01" and not c01.jambas_junta


def test_caratula_y_marca():
    from sip.proceso import generar
    out = tmp / "salida_car"
    res = generar(base(), "Casa X", "auto", out, caratula={"interior": "Durlock sobre omega"}, log=lambda t: None)
    assert (out / "caratula.pdf").stat().st_size > 5000
    assert res.n_muros == 14
    assert "HABITEC" in (out / "informe_validacion.txt").read_text(encoding="utf-8")


def test_cara_exterior_osb():
    from sip.proceso import generar
    out = tmp / "salida_osb"
    generar(base(), "Casa OSB", "auto", out, caratula={"piel_exterior": "osb"}, log=lambda t: None)
    d = calcular(leer_plano(base(), "Prueba"), "osb")
    assert not any(m.smart for m in d.muros) and all(m.cara_rev == "" for m in d.muros)
    d2 = calcular(leer_plano(base(), "Prueba"))
    assert all(m.smart for m in d2.muros)
    assert (out / "hojas_taller.pdf").exists()


def test_modulo_con_escalon():
    """Contorno de 6 lados (rectángulo con un escalón) y tabiques interiores."""
    from pathlib import Path
    ruta = Path(__file__).parent / "pruebas_datos" / "modulo_con_escalon.dxf"
    d = calcular(leer_plano(ruta, "Escalón"))
    assert [l.letra for l in d.plano.lados] == list("ABCDEF")
    assert [l.dir for l in d.plano.lados] == list("ABCDCD")
    assert len(d.muros) == 19 and len(d.techos) == 8
    assert sorted({m.lado for m in d.muros}) == list("ABCDEFI")
    assert not [a for a in d.alertas if "no tiene paneles" in a or "hueco" in a or "se esperan" in a], d.alertas
    # Los dos tramos del escalón: D (vertical, lateral: toma las esquinas) y E (horizontal)
    m = {p.codigo: p for p in d.muros}
    assert m["D-01"].bordes == {"izq": ("tapa", "C"), "der": ("tapa", "E")}
    assert abs(m["D-01"].largo - 0.65) < 1e-6 and abs(m["E-01"].rect.x0 - 0.09) < 1e-6
    assert m["E-02"].bordes["izq"] == ("tapa", "D") and m["F-01"].bordes["der"] == ("tapa", "A")
    # Tabiques: I-01 e I-02 forman una tira; el resto de los extremos queda libre
    assert m["I-01"].bordes["der"] == ("tirante", "I-02") and m["I-02"].bordes["izq"] == ("recibe", "I-01")
    assert m["I-03"].bordes == {"izq": ("libre", ""), "der": ("libre", "")}
    assert not any(p.smart for p in d.muros if p.lado == "I") and all(p.smart for p in d.muros if p.lado != "I")
    # El techo que entra 5 cm en el espesor del muro C se detecta; el múltiplo de 61 es solo un aviso
    assert not d.alertas, d.alertas
    assert sum("múltiplo" in a for a in d.avisos) == 2 and any("ALTO" in a for a in d.avisos)
    assert not any("múltiplo" in a for a in d.alertas)
    # ALTO (legado) se lee como cota del dintel: ventana de 1,00 x 1,00 con antepecho 1,05
    v = {x.id: x for x in d.plano.vanos}
    assert abs(v["V3"].alto - 1.0) < 1e-6 and abs(v["V3"].dintel - 2.05) < 1e-6 and abs(v["V1"].alto - 2.05) < 1e-6
    assert not any("revisar DINTEL" in a for a in d.alertas)
    # Cada bloque queda asociado a su vano aunque el punto de inserción caiga al costado
    assert all(v.alto is not None for v in d.plano.vanos)
    from sip.proceso import generar
    out = tmp / "salida_escalon"
    generar(ruta, "Escalón", "auto", out, log=lambda t: None)
    assert (out / "hojas_taller.pdf").stat().st_size > 20000


def test_secuencia_de_carga():
    from sip.carga import secuencia, esquinas_disponibles
    d = calcular(leer_plano(Path(__file__).parent / "pruebas_datos" / "modulo_con_escalon.dxf", "Prueba"))
    assert "A-F" in esquinas_disponibles(d)
    items, v0 = secuencia(d, "A-F", True)
    g = [i.grupo for i in items]
    codigos = [i.codigo for i in items]
    assert g[0] == "PARRILLAS DE PISO"
    assert sorted(codigos[1:]) == sorted([p.codigo for p in d.muros] + [t.codigo for t in d.techos])
    assert g[-len(d.techos):] == ["TECHO"] * len(d.techos)            # el techo va último
    assert g.index("TABIQUES INTERIORES") > max(i for i, x in enumerate(g) if x.startswith("PANELES"))
    assert g.index("PANELES F") > max(i for i, x in enumerate(g) if x == "PANELES A")
    assert g.index("PANELES B") > max(i for i, x in enumerate(g) if x == "PANELES F")
    assert [c for c in codigos if c.startswith("A-")][0] == "A-01" and g[1] == "PANELES A"
    otro, _ = secuencia(d, "SE", False)
    assert otro[0].grupo.startswith("PANELES")



def test_lamina_grafica():
    """Lámina gráfica: revestimientos desde capas, tabique de durlock, sanitarios y piso."""
    from sip.lamina import Modelo, CONFIG_BASE, cadenas, hoja_lamina
    d0 = correr(base())
    m = d0.plano.modulo

    def agregar(doc, msp):
        x = m.x0 + m.ancho_x * 0.6
        msp.add_lwpolyline([(x, m.y0 + 0.09), (x + 0.1, m.y0 + 0.09), (x + 0.1, m.y1 - 0.09), (x, m.y1 - 0.09)],
                           close=True, dxfattribs={"layer": "TABIQUE_DURLOCK"})
        msp.add_lwpolyline([(x, m.y0 + 0.5), (x + 0.1, m.y0 + 0.5), (x + 0.1, m.y0 + 1.3), (x, m.y0 + 1.3)],
                           close=True, dxfattribs={"layer": "VANO"})
        bl = msp.add_blockref("VANO_BLOQUE", (x + 0.05, m.y0 + 0.9), dxfattribs={"layer": "VANO"})
        bl.add_auto_attribs({"TIPO": "P", "DINTEL": "2.05", "ANTEPECHO": "0"})
        msp.add_circle((m.x0 + 0.5, m.y0 + 0.5), 0.2, dxfattribs={"layer": "SANITARIOS"})
        msp.add_line((x + 0.1, m.y0 + 2.0), (x + 0.1, m.y0 + 3.0), dxfattribs={"layer": "REV_INT_CERAMICO"})
        msp.add_line((m.x0 + 0.3, m.y0 + 0.3), (m.x0 + 0.3, m.y0 + 1.3), dxfattribs={"layer": "PISO"})
    d = correr(modificar(base(), "lamina.dxf", agregar))
    assert len(d.plano.tabiques_durlock) == 1 and len(d.plano.sanitarios) == 1 and len(d.plano.piso) == 1
    assert not any("no toca ningún panel" in a for a in d.alertas), d.alertas
    assert len(d.muros) == len(d0.muros)                     # el durlock no entra al despiece
    mo = Modelo(d.plano, dict(CONFIG_BASE))
    por_letra = {mu.letra: mu for mu in mo.muros}
    assert any(mat == "wpc" for mat, _, _ in por_letra["C"].ext)          # de la plantilla
    assert por_letra["A"].int_ == [("omega", 0.0, por_letra["A"].largo)] or por_letra["A"].int_[0][0] == "omega"
    assert por_letra["D"].int_ == [("sip", 0.0, por_letra["D"].largo)]  # sin línea: OSB visto
    assert len(mo.bandas_tab) == 1                                       # cerámico sobre el tabique
    assert len(mo.locales) == 2
    cad = cadenas(mo)
    assert sum(c["total"] for c in cad.values()) == 2                    # solo dos totales
    fig, avisos = hoja_lamina(d.plano, {}, "01/01/2026")
    assert not avisos, avisos
    fig.savefig(tmp / "lamina.pdf")



def test_obra_in_situ():
    """Láminas de obra: bocas con altura, cañerías, ejes sanitarios, tabiques (en tiras) y vistas interiores."""
    from sip.lamina import CONFIG_BASE
    from sip.obra import Obra, hojas_obra
    d0 = correr(base())
    p0 = d0.plano
    assert len(p0.bocas) == 8 and len(p0.canerias) == 8 and len(p0.ejes_sanitarios) == 1
    tg = next(b for b in p0.bocas if b.tipo == "TABLERO")
    assert abs(tg.altura - 1.50) < 1e-9 and not tg.por_defecto
    assert next(b for b in p0.bocas if b.tipo == "CENTRO").altura is None
    assert sum(v for _, v in p0.canerias) == 1                        # una cañería vista

    def agregar(doc, msp):
        def rect(x0, y0, x1, y1, capa):
            msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": capa})
        rect(1.60, 1.60, 2.96, 1.70, "TABIQUE_DURLOCK")                 # baño en L: dos tiras
        rect(1.60, 0.09, 1.70, 1.60, "TABIQUE_DURLOCK")
        msp.add_line((1.70, 1.60), (2.96, 1.60), dxfattribs={"layer": "REV_INT_CERAMICO"})
        msp.add_line((2.96, 0.09), (2.96, 1.60), dxfattribs={"layer": "REV_INT_CERAMICO"})   # muro B en el baño
        msp.add_line((1.70, 0.09), (1.70, 1.60), dxfattribs={"layer": "REV_INT_CERAMICO"})   # tabique, lado baño
        msp.add_blockref("ELEC_LLAVE", (1.70, 1.50), dxfattribs={"layer": "ELECTRICIDAD"})   # sin ALTURA
        i = msp.add_blockref("SAN_EJE", (2.20, 0.35), dxfattribs={"layer": "SAN_EJE"})
        i.add_auto_attribs({"ARTEFACTO": "Inodoro"})
    pl = correr(modificar(base(), "obra.dxf", agregar)).plano
    ob = Obra(pl, dict(CONFIG_BASE))
    assert [t["tipo"] for t in ob.tabs] == ["DURLOCK", "DURLOCK"]
    assert sorted(round(t["largo"], 2) for t in ob.tabs) == [1.36, 1.51]
    llave = next(it for it in ob.bocas if it["b"].x == 1.70 and it["b"].tipo == "LLAVE")
    assert llave["b"].por_defecto and abs(llave["b"].altura - 1.10) < 1e-9
    assert llave["cara"]["tab"] is not None and llave["cara"]["nf"] == (1, 0)    # cara del tabique hacia B
    ino = next(it for it in ob.ejes if it["e"].artefacto == "Inodoro")
    # cotas al terminado: el muro C arranca en el cerámico del muro B (1,2 cm)
    assert ino["cara"]["nombre"] == "MURO C" and abs(ino["u"] - (2.96 - 0.012 - 2.20)) < 1e-6
    tb = next(t for t in ino["cara"]["tabs"])
    assert abs((tb["b"] - tb["a"]) - 0.112) < 1e-6                    # tabique de 10 cm + cerámico
    # pendiente: 2,31 junto al muro alto (C) y 2,22 junto al de la caída (A)
    muro_b = next(c for c in ob.caras if c["nombre"] == "MURO B")
    assert {round(muro_b["z0"], 3), round(muro_b["z1"], 3)} == {2.22, 2.31}
    muro_c = next(c for c in ob.caras if c["nombre"] == "MURO C")
    assert [round(t["a"], 3) for t in muro_c["tabs"]] == [1.236]   # cara terminada del tabique (cerámico en B y en el tabique)
    cer = next(c for c in ob.caras if c["corto"].startswith("TB") and c["nf"] == (0, -1))
    assert any(ob.cod_rev(m) == "R2" for m, _, _ in cer["revs"]), cer["revs"]   # cerámico sobre el tabique
    figs, avisos = hojas_obra(pl, {}, "01/01/2026")
    assert len(figs) >= 3 and not avisos, avisos
    figs[0].savefig(tmp / "obra.pdf")


if __name__ == "__main__":
    for nombre, f in list(globals().items()):
        if nombre.startswith("test_"):
            f()
            print("OK ", nombre)
