"""Modelo de datos: lo que se lee del plano y lo que se calcula."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Rect:
    """Rectángulo en planta (metros)."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def ancho_x(self) -> float:
        return self.x1 - self.x0

    @property
    def alto_y(self) -> float:
        return self.y1 - self.y0

    @property
    def centro(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def contiene(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def interseca(self, o: "Rect", tol: float = 0.0) -> bool:
        return (self.x0 < o.x1 - tol and o.x0 < self.x1 - tol
                and self.y0 < o.y1 - tol and o.y0 < self.y1 - tol)


@dataclass
class VanoLeido:
    """Vano dibujado en planta (rectángulo + atributos del bloque)."""
    id: str
    rect: Rect
    tipo: str = "V"              # V, PV, C, P
    alto: Optional[float] = None  # alto de la abertura (m)
    antepecho: float = 0.0       # altura del antepecho (m); 0 si llega al piso
    avisos: list[str] = field(default_factory=list)


@dataclass
class MarcaRevestimiento:
    x: float
    y: float
    cara: str = "EXT"            # EXT o INT
    sentido: str = "V"           # V (vertical) o H (horizontal)


@dataclass
class Plano:
    """Todo lo que se lee del DXF."""
    proyecto: str
    modulo: Rect
    caida_hacia: Optional[str]    # A, B, C o D
    paneles: list[Rect]
    techos: list[Rect]
    vanos: list[VanoLeido]
    marcas_rev: list[MarcaRevestimiento]
    avisos: list[str] = field(default_factory=list)


@dataclass
class VanoEnPanel:
    """Parte de un vano que cae dentro de un panel (coordenadas del panel)."""
    vano_id: str
    tipo: str
    # abertura "de proyecto" (sin huelgo) y vano de corte (con huelgo)
    u0: float                    # desde el borde izquierdo (vista interior)
    u1: float
    v0: float                    # desde el borde inferior del panel
    v1: float
    completo: bool               # el vano entero está dentro de este panel
    jamba_izq: bool              # el borde izquierdo del vano está en este panel
    jamba_der: bool
    tirante_dintel_taller: bool  # dintel con tirante colocado en taller
    tirante_antepecho_taller: bool
    tiene_antepecho: bool
    ancho_total: float           # ancho total del vano (con huelgo)
    alto_total: float


@dataclass
class PanelMuro:
    codigo: str                  # A-03
    lado: str                    # A, B, C, D
    numero: int
    rect: Rect                   # rectángulo en planta
    largo: float                 # ancho del panel (a lo largo del muro)
    espesor: float
    alto: float                  # 2,44 o 2,22
    es_ajuste: bool = False
    smart: bool = False
    cara_rev: str = ""
    sentido_rev: str = ""
    vanos: list[VanoEnPanel] = field(default_factory=list)
    # Bordes verticales en la vista interior: 'izq' / 'der' -> (clase, dato)
    #   ('tirante', 'A-02'): este panel trae el tirante clavado hacia A-02
    #   ('recibe', 'A-01'):  rebaje libre; recibe el tirante que trae A-01
    #   ('tapa', 'D'):       trae la tapa de 25x50 (esquina con el lado D)
    bordes: dict[str, tuple[str, str]] = field(default_factory=dict)
    alertas: list[str] = field(default_factory=list)


@dataclass
class PanelTecho:
    codigo: str                  # T-01
    numero: int
    rect: Rect
    ancho: float                 # a lo ancho (perpendicular a la caída)
    largo: float                 # en el sentido de la caída
    caida_hacia: str
    es_ajuste: bool = False
    en_caida: bool = False       # toca el borde del techo del lado de la caída
    uniones: dict[str, list[str]] = field(default_factory=dict)  # lado (en planta) -> paneles vecinos
    tirantes: dict[str, str] = field(default_factory=dict)       # lado -> 'lleva' | 'recibe' | 'mixto'
    alertas: list[str] = field(default_factory=list)


@dataclass
class Despiece:
    plano: Plano
    muros: list[PanelMuro]
    techos: list[PanelTecho]
    alertas: list[str]           # alertas generales (no de un panel)
