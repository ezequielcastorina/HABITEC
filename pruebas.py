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
    assert [a for a in d.alertas if "V2" in a], "debe alertar el vano a 10 cm de la junta"
    assert len(d.alertas) == 1, d.alertas
    # Techo: 2,44 en el sentido corto del módulo (X): una columna de 2,44 y otra de ajuste de 0,61
    ancho_x = sorted({(round(t.rect.ancho_x, 2), round(t.rect.alto_y, 2)) for t in d.techos})
    assert ancho_x == [(0.61, 1.22), (2.44, 1.22)], ancho_x
    assert sum(t.es_ajuste for t in d.techos) == 4
    t01 = d.techos[0]
    assert t01.en_caida and set(t01.uniones) == {"B", "C"}, t01.uniones   # vecino a la derecha y abajo
    assert not d.techos[-1].en_caida
    # Huelgo: ventana 1,00 x 1,00 -> 1,010 x 1,010 ; puerta ventana alto 2,05 -> 2,055
    a02 = next(m for m in d.muros if m.codigo == "A-02")
    vp = a02.vanos[0]
    assert abs(vp.ancho_total - 0.81) < 1e-6 and abs(vp.alto_total - 1.01) < 1e-6
    c01 = next(m for m in d.muros if m.codigo == "C-01")
    assert not c01.vanos[0].completo and c01.vanos[0].jamba_der and not c01.vanos[0].jamba_izq
    assert abs(c01.vanos[0].alto_total - 2.055) < 1e-6      # sin huelgo contra el piso
    assert not c01.vanos[0].tirante_dintel_taller           # vano compartido: dintel in situ
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
    # los vanos se renumeran al girar; la alerta debe seguir siendo una sola, a 10 cm de la junta
    assert len(d.alertas) == 1 and "10.0 cm" in d.alertas[0], d.alertas


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
    assert any("no es múltiplo de 61 cm" in a for a in d.alertas)


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


if __name__ == "__main__":
    for nombre, f in list(globals().items()):
        if nombre.startswith("test_"):
            f()
            print("OK ", nombre)
