# Generador de hojas de taller para paneles SIP

Lee un plano de AutoCAD (DXF) de **un módulo** con el despiece tentativo dibujado, verifica las reglas
y genera: una hoja de taller por panel (PDF A4, escala fija 1:20, en blanco y negro), el plano de nomenclatura, una planilla Excel y un
informe de validación.

## Cómo se usa (página web)

**Lo más simple: abrir `HABITEC_hojas_taller.html` con doble clic.** Es la página completa en un solo archivo (con el logo y el programa adentro): no hay que publicar nada.
Necesita internet solo la primera vez, para bajar Python. Mientras genera las hojas (unos 30 segundos) la pantalla se queda quieta: es normal.
Se regenera con `python crear_web.py`. La carpeta `web/` es la misma página en versión publicable.

La carpeta `web/` es una página que corre el programa dentro del navegador, sin instalar nada: se arrastra el DXF, se completa el nombre del
proyecto (los revestimientos de la carátula salen del propio plano) y se descargan las hojas (PDF, planilla y ZIP). El plano no se sube a ningún
servidor: se procesa en la computadora de quien la usa. La primera vez descarga Python y las librerías (unos 40 MB, 10 a 30 segundos);
después quedan guardadas en el navegador.

**Publicar la página en GitHub Pages:** subir el repositorio, ir a *Settings → Pages → Source: GitHub Actions* y ejecutar
*Actions → Publicar web → Run workflow*. La dirección aparece al terminar. (Con cuenta gratuita, GitHub Pages exige repositorio público;
alternativa: arrastrar la carpeta `web/` a netlify.com/drop.) Si se cambia el código, correr `python crear_web.py` o dejar que lo haga el workflow.

**Plantilla de AutoCAD:** el botón *Bajar plantilla de AutoCAD (con ejemplo)* entrega un único DXF con las capas y los bloques ya creados,
las instrucciones y un módulo de ejemplo dibujado. Para dibujar un módulo nuevo: abrirlo, **borrar todo el dibujo de ejemplo** (Ctrl+A y Supr;
las capas y los bloques quedan en el archivo), dibujar el módulo según la convención de más abajo y guardar como DXF (`SAVEAS` → *AutoCAD 2018 DXF* o anterior).
El módulo de ejemplo trae a propósito un vano a 10 cm de una junta; no genera alerta (la distancia mínima queda a criterio del proyectista).

Si el módulo tiene alertas, se muestran en pantalla y quedan en `informe_validacion.txt`: se corrige el dibujo y se repite.

Para uso técnico (opcional) sigue existiendo la línea de comandos: `python generar_hojas.py plano.dxf --proyecto "Nombre" [--unidades m|cm|mm|auto] [--salida carpeta] [--solo-validar]`
(requiere `pip install -r requirements.txt`). Sin unidades indicadas se leen las del DXF; si no las declara se asume metros.

## Carátula

La primera hoja del PDF es la carátula: marca HABITEC, proyecto, fecha de emisión y revisión, dos axonometrías esquemáticas (muros y techo),
resumen de paneles y los revestimientos. **El interior y el exterior salen del plano** (capas `REV_EXT_…` y `REV_INT_…`, cada material con los lados
donde va; sin líneas: smart panel afuera y OSB visto adentro). Cielorraso y observaciones los completa quien emite; lo vacío figura como «a definir». Es informativo: no cambia el despiece. En la web son campos; en la consola:
`--cielorraso "…" --obs "…" --rev 00` (y `--interior` / `--exterior` solo para pisar lo que sale del plano). El logo está embebido en `sip/logo_datos.py`.

**Cara exterior de los paneles** (selector de la web, o `--piel-exterior smart|osb` en consola): es el único campo que sí cambia las hojas.
Con *smart panel* (por defecto) todos los muros lo llevan; con *OSB* ningún muro lo lleva: las hojas muestran OSB en las dos caras y se omite el machimbrado
exterior. La barrera de agua y viento, las zonas de WPC o chapa y el revestimiento del techo se colocan en obra y no figuran en las hojas.

## Cómo leer las hojas (también en blanco y negro)

Cada elemento se distingue por su tipo de línea o trama, no por el color: contorno del panel, línea gruesa continua · rebaje perimetral de 30 mm, trazo largo ·
rebaje de 55 mm alrededor del vano, trazo y punto · vano de corte, contorno grueso (fino donde llega al borde del panel) · tirante de junta 50 × 70, relleno gris claro (25 mm adentro y 25 mm que sobresalen) ·
rebaje de 30 mm (sin EPS, recibe el tirante), rayado a 45° · tapa de esquina 25 × 70, trama cruzada · el machimbrado va como texto ("smart panel macho / hembra") sobre el borde.
En planta y en las axos: tono medio para el smart panel, tono más oscuro para las piezas de ajuste y blanco para la cara interior o el OSB.

## Salidas

| Archivo | Contenido |
| --- | --- |
| `hojas_taller.pdf` | Carátula + plano de nomenclatura + una página por panel (muros y techo) |
| `caratula.pdf` | La carátula sola |
| `hojas/A-01.pdf`, … | Las mismas hojas, un PDF por panel |
| `plano_nomenclatura.pdf/.png` | Planta del módulo con lados A–D y código de cada panel |
| `planilla_paneles.xlsx` | Un panel por fila: medidas, ajuste, revestimiento, vanos, alertas |
| `informe_validacion.txt` | Lista de alertas del dibujo |

## Convención del dibujo

Cada archivo es un único módulo. Todo en rectángulos cerrados, ejes alineados (sin girar).

| Capa | Qué se dibuja |
| --- | --- |
| `MODULO` | Polilínea cerrada del contorno exterior del módulo: rectángulo o cualquier contorno de lados horizontales y verticales (en L, con escalones…) |
| `CAIDA` | Flecha (LINE o polilínea) hacia donde baja el techo. Se toma el segmento más largo |
| `PANEL` | Un rectángulo por panel de muro (ancho × 90 mm), apoyado sobre el contorno. En las juntas las líneas se superponen. Los paneles que no apoyan sobre el contorno se toman como tabiques interiores |
| `TECHO` | Un rectángulo por panel de techo, en planta |
| `VANO` | Rectángulo con la medida de la abertura (**sin huelgo**), superpuesto a los paneles que atraviesa, y dentro de él un bloque `VANO_BLOQUE` |
| `REV_EXT_CHAPA`, `REV_EXT_WPC` | Lámina gráfica y carátula. Una línea sobre la cara exterior del muro, en el tramo que lleva ese revestimiento. Sin línea: smart panel |
| `REV_INT_PLACA`, `_OMEGA`, `_P35`, `_P70`, `_CERAMICO`, `_PVC` | Lámina gráfica y carátula. Una línea sobre la cara interior del muro (o de un tabique) en el tramo que lleva ese revestimiento. Sin línea: OSB visto |
| `TABIQUE_DURLOCK` | Solo lámina gráfica. Un rectángulo por tabique de durlock (con su espesor real). No entra al despiece; las puertas que caen en él no generan alertas |
| `SANITARIOS` | Solo lámina gráfica. Artefactos y equipamiento (líneas, polilíneas, círculos, elipses o bloques): se dibujan tal cual |
| `PISO` | Solo lámina gráfica. Sombreado o líneas del piso: se dibujan tal cual, con línea muy fina y tono claro |
| `ELECTRICIDAD` | Solo lámina gráfica. Bloques `ELEC_TOMA`, `ELEC_CENTRO`, `ELEC_LLAVE`, `ELEC_APLIQUE` (vienen en la plantilla) |
| `PUERTA_GIRO` | Hoja y arco de cada puerta. Queda en el DXF; no sale en la lámina gráfica |
| `PANEL_REV` | Opcional. Todos los muros llevan smart panel (cara exterior, sentido vertical), ajustes incluidos; un bloque `REV_BLOQUE` dentro de un panel cambia la cara o el sentido |

Para insertar un bloque, poner como capa actual `VANO` (o `PANEL_REV`) y usar `INSERT`. AutoCAD pregunta los atributos
(se leen en las mismas unidades que el dibujo):

* `VANO_BLOQUE`: `TIPO` (`V` ventana, `PV` puerta ventana, `C` corrediza hasta el piso, `P` puerta), `DINTEL` (cota del borde superior de la abertura, medida desde el piso: por ejemplo 2.05), `ANTEPECHO` (cota del borde inferior; se ignora en `PV`, `C` y `P`, que llegan al piso). La altura de la abertura es DINTEL − ANTEPECHO: una ventana de 1,00 × 1,00 con antepecho 1,05 lleva DINTEL 2.05. Los bloques viejos con el atributo `ALTO` se leen igual, tomándolo como cota del dintel.
* `REV_BLOQUE`: `CARA` (`EXT` o `INT`), `SENTIDO` (`V` o `H`).

## Reglas que aplica

* Lados del contorno: se nombran **A, B, C…** en sentido horario empezando por el lado horizontal más alto. En un rectángulo: **A** arriba, **B** derecha, **C** abajo, **D** izquierda. Con escalones hay más letras (A a F en un módulo en L).
* Tabiques interiores: los paneles de la capa `PANEL` que no apoyan sobre el contorno se numeran `I-01`, `I-02`… (los alineados y contiguos forman una tira; en sus juntas rige la misma regla del tirante). Alto 2,44 m, sin smart panel; sus extremos quedan con rebaje libre para resolverse en obra.
* Numeración: los muros que miran hacia arriba o abajo, de izquierda a derecha; los que miran a los costados, de arriba hacia abajo.
* Muro del lado de la caída: 2,22 m de alto; el resto, 2,44 m. Los laterales (perpendiculares a la caída) toman las esquinas: llegan hasta el vértice exterior y, en una esquina entrante, avanzan un espesor más; los demás muros se retraen un espesor en las esquinas salientes.
* Panel de muro estándar 1,22 × 0,09 m; se admite una pieza de ajuste por lado.
* Panel de techo: máximo 1,22 × 2,44 m, con el lado largo en el sentido corto del módulo y las juntas trabadas (las juntas de dos filas contiguas no coinciden). Numeración T-01, T-02… de izquierda a derecha y de arriba hacia abajo. El software verifica que cubran toda su zona, sin huecos ni superposiciones. La zona es el contorno menos el espesor de los muros en los lados sin caída; del lado de la caída puede sobresalir hasta 50 cm (se refila en obra).
* Vano de corte = abertura + 5 mm por lado (sin huelgo contra el piso en `PV`, `C` y `P`).
* Rebaje de 30 mm en el perímetro de cada panel: aloja la mitad (25 mm) del tirante de junta de 50 × 70 mm, con 5 mm de huelgo. En el techo, el lado de la caída no lleva rebaje.
* Tirante de junta de 50 × 70 mm (25 mm en cada panel) en cada junta entre dos paneles (muros y techo): lo trae clavado el panel de menor número, sobre el borde que da al vecino; el otro deja el rebaje libre para recibirlo.
* Tapa de 25 × 70 mm (medio tirante) en los muros de esquina: la traen los dos paneles que se encuentran en cada esquina, el que queda visible y el que queda tapado, sobre el borde que da a la esquina.
* Rebaje de 55 mm alrededor de cada vano: aloja el tirante de 50 × 70 mm con 5 mm de huelgo. Vano dentro de un panel: tirantes de los cuatro lados en taller. Vano que toma dos paneles: en taller solo las jambas; dintel y antepecho se completan in situ.
* No se controla la distancia de un vano al borde del panel (queda a criterio del proyectista). Si la abertura arranca justo en la junta entre dos paneles, el tirante de 50 × 70 de esa jamba lo trae el panel vecino, encastrado desde taller, y el panel del vano no lleva tirante de ese lado.
* El módulo (caja que envuelve al contorno) debería ser múltiplo de 61 cm; si no lo es, el informe lo muestra como aviso, sin contarlo como alerta.

## Pendientes para confirmar

* Medidas del machimbrado (se asumen unos 5 mm de profundidad × 20 mm de ancho, en los bordes verticales, cara exterior) y qué borde es macho y cuál hembra.
* Paneles de dintel acostados (revestimiento en el otro sentido): se agrega en una etapa posterior.
* Las hojas muestran el panel en **vista interior**. Si el taller prefiere vista exterior, es un cambio chico.

## Pruebas

`python pruebas.py` corre casos de control: ejemplo base, módulo girado 90° (caída hacia B), falta de flecha de caída,
panel faltante, módulo que no es múltiplo de 61 cm, y varios casos de techo (tamaño, cobertura, orientación, juntas trabadas).

## Notas

La página se probó en Chromium; la plantilla no se probó en AutoCAD (se generó desde otro entorno). Si algo falla al abrirla, avisar el mensaje de error y se corrige.


## Lámina gráfica (planta y vistas)

Sección 4 de la web. A3 vertical, sin escala, monocromática (tinta azul verdosa sobre fondo crema), con la tipografía Inter
incluida en el programa (`sip/fuentes`, licencia OFL). Planta y vistas van al mismo tamaño; las vistas se ordenan en columna, en
fila o de a dos por fila, lo que deje todo más grande.

* Planta: SIP lleno, revestimientos como líneas separadas según su espesor, tabiques, aberturas (símbolo + rectángulo de la capa
  VANO), sanitarios, piso y electricidad. Las puertas no muestran giro.
* Cotas, todas por fuera y en un tono más claro: dos totales del módulo (sin revestimiento) y una fila por lado de medidas interiores
  terminadas, sin repetir valores.
* Vistas de las caras con aberturas (o de todas): VISTA FRENTE (la cara con la puerta), LATERAL y POSTERIOR. Sin pendiente
  visible: los laterales van rectos al alto del lado alto y la cara de la caída al del lado bajo (panel + piso). Zinguería inferior
  completa, de esquina por encima y superior; dos espesores de línea (grueso: zinguerías, vanos y tierra; muy fino y claro: tramas).
* Rótulo: logo, MÓDULO + nombre, área del módulo y fecha de emisión.

En la web se editan el espesor y el dibujo de cada revestimiento (las claves coinciden con el nombre de la capa: `REV_EXT_WPC` → `wpc`),
el piso y las zinguerías. Para un revestimiento nuevo se crea la capa en AutoCAD y se lo agrega con el mismo nombre.

## Secuencia de carga del camión

La lámina 3 del PDF (y la solapa «Carga camión» del Excel) da el orden de carga. En obra el camión se descarga formando una pila invertida: lo primero que se carga queda arriba y se monta primero. Por eso el orden de carga es el orden de montaje:

1. Muros: primero los dos lados completos que forman la esquina de arranque (p. ej. todo el A y todo el F); después el resto de los lados, uno por uno, en sentido horario.
2. Tabiques interiores.
3. Techo, al final (se carga último, se descarga primero y se monta último), ordenado desde la esquina de arranque hacia el lado opuesto.

La esquina de arranque se nombra por las letras de sus dos lados (A-F, A-B, B-C…). En la web el selector se completa al cargar el DXF con todas las esquinas convexas del contorno; en la línea de comandos: `--esquina A-F`. También se aceptan NO|NE|SO|SE (esquina convexa más cercana).
