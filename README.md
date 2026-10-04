# Generador de hojas de taller para paneles SIP

Lee un plano de AutoCAD (DXF) de **un módulo** con el despiece tentativo dibujado, verifica las reglas
y genera: una hoja de taller por panel (PDF A3), el plano de nomenclatura, una planilla Excel y un
informe de validación.

## Opción A: programa con ventana (.exe, sin instalar Python)

`app_sip.py` es una ventana: se elige el DXF, se escribe el nombre del proyecto y se hace clic en *Generar hojas*
(también tiene *Solo validar*, abrir la carpeta o el PDF de resultados, y guardar la plantilla de AutoCAD y un DXF de ejemplo).

Para obtener el `.exe` hay que compilarlo una vez en Windows (no se puede compilar desde otro sistema):

* **Con Python en la PC:** instalar Python, doble clic en `crear_exe.bat`. Queda `dist\SIP_Paneles.exe`: un único archivo que se copia a cualquier PC y no necesita Python.
* **Sin instalar nada:** subir esta carpeta a un repositorio de GitHub; la acción `.github/workflows/compilar-windows.yml` compila el `.exe` y lo deja descargable en *Actions → Artifacts*.
* **Instalador opcional:** con el `.exe` ya generado, abrir `instalador.iss` en Inno Setup (gratuito) y compilar; crea `SIP_Paneles_Instalador.exe` con acceso directo en el menú Inicio.

Diagnóstico: `SIP_Paneles.exe --autotest` (comprueba que todo quedó empaquetado) y `SIP_Paneles.exe --cli plano.dxf --proyecto "Nombre"` (modo consola).

## Opción B: con Python

**Una sola vez**

1. Instalar Python desde https://www.python.org/downloads/ (en el instalador, tildar *Add python.exe to PATH*).
2. Descomprimir esta carpeta donde quieras (por ejemplo `C:\sip_paneles`).
3. Hacer doble clic en `instalar_requisitos.bat`. Instala las tres librerías que usa el programa.

**Cada vez que se quiere generar las hojas de un módulo**

1. Abrir `plantilla\plantilla_modulo.dxf` en AutoCAD y guardarlo como DWG: es la plantilla con las capas y los bloques ya creados. Dibujar el módulo siguiendo la convención de más abajo.
2. Guardar el dibujo como DXF: `SAVEAS` → tipo *AutoCAD 2018 DXF* (o anterior).
3. Arrastrar el archivo `.dxf` sobre `generar_hojas.bat`, escribir el nombre del proyecto y Enter.
4. Se crea una carpeta junto al DXF, con el nombre del archivo más `_hojas`, con todas las salidas.

Si el módulo tiene alertas, se muestran en pantalla y quedan en `informe_validacion.txt`: se corrige el dibujo y se repite.

Desde la línea de comandos es equivalente:

```
python generar_hojas.py plano.dxf --proyecto "Nombre del proyecto" [--unidades m|cm|mm|auto] [--salida carpeta] [--solo-validar]
```

Si no se indican unidades, el programa lee las del DXF; si el archivo no las declara asume metros.
Para ver cómo funciona sin dibujar nada: `python generar_ejemplo.py ejemplo.dxf` y arrastrar ese archivo.
El ejemplo trae a propósito un vano a 10 cm de una junta para mostrar una alerta.

## Salidas

| Archivo | Contenido |
| --- | --- |
| `hojas_taller.pdf` | Plano de nomenclatura + una página por panel (muros y techo) |
| `hojas/A-01.pdf`, … | Las mismas hojas, un PDF por panel |
| `plano_nomenclatura.pdf/.png` | Planta del módulo con lados A–D y código de cada panel |
| `planilla_paneles.xlsx` | Un panel por fila: medidas, ajuste, revestimiento, vanos, alertas |
| `informe_validacion.txt` | Lista de alertas del dibujo |

## Convención del dibujo

Cada archivo es un único módulo. Todo en rectángulos cerrados, ejes alineados (sin girar).

| Capa | Qué se dibuja |
| --- | --- |
| `MODULO` | Rectángulo del contorno exterior del módulo |
| `CAIDA` | Flecha (LINE o polilínea) hacia donde baja el techo. Se toma el segmento más largo |
| `PANEL` | Un rectángulo por panel de muro (ancho × 90 mm), apoyado sobre el contorno. En las juntas las líneas se superponen |
| `TECHO` | Un rectángulo por panel de techo, en planta |
| `VANO` | Rectángulo con la medida de la abertura (**sin huelgo**), superpuesto a los paneles que atraviesa, y dentro de él un bloque `VANO_BLOQUE` |
| `PANEL_REV` | Opcional. Todos los muros llevan smart panel (cara exterior, sentido vertical), ajustes incluidos; un bloque `REV_BLOQUE` dentro de un panel cambia la cara o el sentido |

Para insertar un bloque, poner como capa actual `VANO` (o `PANEL_REV`) y usar `INSERT`. AutoCAD pregunta los atributos
(se leen en las mismas unidades que el dibujo):

* `VANO_BLOQUE`: `TIPO` (`V` ventana, `PV` puerta ventana, `C` corrediza hasta el piso, `P` puerta), `ALTO` (alto de la abertura), `ANTEPECHO` (se ignora en `PV`, `C` y `P`).
* `REV_BLOQUE`: `CARA` (`EXT` o `INT`), `SENTIDO` (`V` o `H`).

## Reglas que aplica

* Lados en planta: **A** arriba, **B** derecha, **C** abajo, **D** izquierda.
* Numeración: A y C de izquierda a derecha; B y D de arriba hacia abajo.
* Muro del lado de la caída: 2,22 m de alto; los otros tres, 2,44 m. Los dos laterales (perpendiculares a la caída) toman las cuatro esquinas.
* Panel de muro estándar 1,22 × 0,09 m; se admite una pieza de ajuste por lado.
* Panel de techo: máximo 1,22 × 2,44 m, con el lado largo en el sentido corto del módulo y las juntas trabadas (las juntas de dos filas contiguas no coinciden). Numeración T-01, T-02… de izquierda a derecha y de arriba hacia abajo. El software verifica que cubran todo el módulo, sin huecos ni superposiciones.
* Vano de corte = abertura + 5 mm por lado (sin huelgo contra el piso en `PV`, `C` y `P`).
* Rebaje de 30 mm en el perímetro de cada panel: aloja el tirante chico de 25 × 50 mm con 5 mm de huelgo. En el techo, el lado de la caída no lleva rebaje.
* Tirante chico de 25 × 50 mm en cada junta entre dos paneles (muros y techo): lo trae clavado el panel de menor número, sobre el borde que da al vecino; el otro deja el rebaje libre para recibirlo.
* Tapa de 25 × 50 mm en los muros de esquina: la traen los dos paneles que se encuentran en cada esquina, el que queda visible y el que queda tapado, sobre el borde que da a la esquina.
* Rebaje de 55 mm alrededor de cada vano: aloja el tirante de 50 × 70 mm con 5 mm de huelgo. Vano dentro de un panel: tirantes de los cuatro lados en taller. Vano que toma dos paneles: en taller solo las jambas; dintel y antepecho se completan in situ.
* Distancia mínima de un vano al borde del panel: 20 cm.
* El módulo debe ser múltiplo de 61 cm.

## Pendientes para confirmar

* Medidas del machimbrado (se asumen unos 5 mm de profundidad × 20 mm de ancho, en los bordes verticales, cara exterior) y qué borde es macho y cuál hembra.
* Paneles de dintel acostados (revestimiento en el otro sentido): se agrega en una etapa posterior.
* Las hojas muestran el panel en **vista interior**. Si el taller prefiere vista exterior, es un cambio chico.

## Pruebas

`python pruebas.py` corre casos de control: ejemplo base, módulo girado 90° (caída hacia B), falta de flecha de caída,
panel faltante, módulo que no es múltiplo de 61 cm, y varios casos de techo (tamaño, cobertura, orientación, juntas trabadas).

## Notas

Los `.bat` y la plantilla no se probaron en una PC con Windows ni en AutoCAD (se generaron desde otro entorno);
si algo falla al abrirlos, avisar el mensaje de error y se corrige.
