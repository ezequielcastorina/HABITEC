"""Arma web/sip_python.zip: el código Python que la página web ejecuta en el navegador.

Correr después de cambiar cualquier archivo del programa:  python crear_web.py
La carpeta web/ completa es el sitio: se puede publicar en GitHub Pages, Netlify, etc.
"""
import zipfile
from pathlib import Path

RAIZ = Path(__file__).parent
SALIDA = RAIZ / "web" / "sip_python.zip"


def main():
    SALIDA.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((RAIZ / "sip").glob("*.py")):
            z.write(p, f"sip/{p.name}")
        for p in sorted((RAIZ / "sip" / "fuentes").glob("*")):     # Inter (OFL) para la lámina gráfica
            z.write(p, f"sip/fuentes/{p.name}")
        for nombre in ("puente_web.py", "generar_ejemplo.py"):
            z.write(RAIZ / nombre, nombre)
    print(f"Escrito {SALIDA} ({SALIDA.stat().st_size // 1024} KB)")
    autonoma()


def autonoma():
    """Arma HABITEC_hojas_taller.html: la misma página en UN solo archivo, que anda con doble clic
    (sin publicar nada). Necesita internet solo para bajar Python la primera vez."""
    import base64
    web = RAIZ / "web"
    html = (web / "index.html").read_text(encoding="utf8")
    worker = (web / "worker.js").read_text(encoding="utf8")
    assert "</script" not in worker
    logo = base64.b64encode((web / "logo.jpg").read_bytes()).decode()
    zipb64 = base64.b64encode(SALIDA.read_bytes()).decode()
    html = html.replace('src="logo.jpg"', f'src="data:image/jpeg;base64,{logo}"')
    html = html.replace('<link rel="icon" href="logo.jpg">', f'<link rel="icon" href="data:image/jpeg;base64,{logo}">')
    extra = (f'<script type="text/plain" id="workerSrc">{worker}</script>\n'
             f'<script type="text/plain" id="zipB64">{zipb64}</script>\n')
    html = html.replace("<script>", extra + "<script>", 1)
    destino = RAIZ / "HABITEC_hojas_taller.html"
    destino.write_text(html, encoding="utf8")
    print(f"Escrito {destino} ({destino.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
