"""Reglas y constantes del sistema de paneles SIP.

Todas las medidas internas están en METROS. Si el DXF está en cm o mm,
se indica con --unidades al correr el programa.
"""

# --- Paneles ---------------------------------------------------------------
ANCHO_PANEL = 1.22          # ancho estándar de panel
ESPESOR_PANEL = 0.09        # 9 mm OSB + 70 mm EPS + 9 mm OSB (se toma 90 mm)
LARGO_MAX_PANEL = 2.44      # largo máximo de panel (placa de 1,22 x 2,44)
ALTO_PANEL = 2.44           # alto de los paneles de muro (3 lados)
ALTO_PANEL_BAJO = 2.22      # alto del muro del lado de la caída
MODULO_BASE = 0.61          # el módulo crece de a 61 cm

# --- Rebajes y vanos ---------------------------------------------------------
REBAJE_PERIMETRAL = 0.030   # rebaje de EPS en el perímetro del panel
REBAJE_VANO = 0.055         # rebaje alrededor de cada vano (aloja tirante 5x7)
TIRANTE_VANO = (0.05, 0.07)  # sección del tirante de vano (ancho x espesor)
TIRANTE_CHICO = (0.025, 0.05)  # tirante de unión / tapa (25 x 50 mm); el rebaje de 30 mm le deja 5 mm de huelgo
HUELGO_VANO = 0.005         # huelgo por lado que se suma a la abertura
DIST_MIN_BORDE = 0.20       # distancia mínima vano - junta/borde de panel
MACHIMBRE_PROF = 0.005      # profundidad aprox. del rebaje de machimbrado
MACHIMBRE_ANCHO = 0.02      # ancho aprox. del machimbrado

# --- Tolerancias ---------------------------------------------------------------
TOL = 0.005                 # tolerancia geométrica general (5 mm)
TOL_MODULO = 0.01           # tolerancia para múltiplo de 61 cm

# --- Capas del DXF -------------------------------------------------------------
CAPA_MODULO = "MODULO"
CAPA_CAIDA = "CAIDA"
CAPA_PANEL = "PANEL"
CAPA_VANO = "VANO"
CAPA_PANEL_REV = "PANEL_REV"
CAPA_TECHO = "TECHO"

# --- Lados -----------------------------------------------------------------------
# A arriba, B derecha, C abajo, D izquierda (en planta)
LADOS = ("A", "B", "C", "D")
# Dirección de numeración dentro de cada lado: A y C de izquierda a derecha,
# B y D de arriba hacia abajo.
# Dirección de lectura de izquierda a derecha en la vista interior:
#   A: +x   B: -y   C: -x   D: +y
VISTA_INTERIOR = {"A": (1, 0), "B": (0, -1), "C": (-1, 0), "D": (0, 1)}
# A y C se numeran en +x; B y D en -y.
NUMERACION = {"A": (1, 0), "B": (0, -1), "C": (1, 0), "D": (0, -1)}

# Tipos de vano
TIPOS_VANO = {
    "V": "Ventana",
    "PV": "Puerta ventana",
    "C": "Corrediza hasta el piso",
    "P": "Puerta",
}
TIPOS_HASTA_PISO = {"PV", "C", "P"}   # sin antepecho, sin huelgo contra el piso
