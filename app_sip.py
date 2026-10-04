"""Hojas de taller de paneles SIP: ventana de escritorio.

Doble clic (o `python app_sip.py`) abre la ventana. También acepta un archivo .dxf como
argumento (por ejemplo arrastrándolo sobre el programa) y lo deja cargado.

Modo consola, útil para pruebas:  app_sip.py --cli plano.dxf --proyecto "Nombre"
"""
from __future__ import annotations

import io
import json
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

# Con --windowed (sin consola) en Windows, stdout/stderr valen None: se reemplazan para
# que cualquier print() o aviso de una librería no rompa el programa.
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

UNIDADES = {"Automático (las del DXF)": "auto", "Metros": "m", "Centímetros": "cm", "Milímetros": "mm"}
CONFIG = Path.home() / ".sip_paneles.json"


def _leer_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _guardar_config(datos: dict) -> None:
    try:
        CONFIG.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def abrir_ruta(ruta: Path) -> None:
    """Abre un archivo o carpeta con el programa predeterminado del sistema."""
    if sys.platform.startswith("win"):
        os.startfile(str(ruta))               # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
    else:
        subprocess.Popen(["xdg-open", str(ruta)])


def abrir_ventana(dxf_inicial: str | None = None) -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    from sip.proceso import carpeta_por_defecto, generar

    cfg = _leer_config()
    root = tk.Tk()
    root.title("Hojas de taller · Paneles SIP")
    root.geometry("760x600")
    root.minsize(640, 520)

    v_dxf = tk.StringVar(value=dxf_inicial or "")
    v_proy = tk.StringVar(value=cfg.get("proyecto", ""))
    v_unid = tk.StringVar(value="Automático (las del DXF)")
    estado = {"resultado": None, "ocupado": False}
    cola: "queue.Queue[tuple[str, object]]" = queue.Queue()

    marco = ttk.Frame(root, padding=12)
    marco.pack(fill="both", expand=True)
    marco.columnconfigure(1, weight=1)
    marco.rowconfigure(5, weight=1)

    # --- Entradas -------------------------------------------------------------------
    ttk.Label(marco, text="Plano (DXF):").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Entry(marco, textvariable=v_dxf).grid(row=0, column=1, sticky="ew", padx=6)

    def elegir_dxf():
        ruta = filedialog.askopenfilename(
            title="Elegir el plano en DXF", initialdir=cfg.get("carpeta") or None,
            filetypes=[("Plano DXF", "*.dxf"), ("Todos los archivos", "*.*")])
        if ruta:
            v_dxf.set(ruta)
            cfg["carpeta"] = str(Path(ruta).parent)

    ttk.Button(marco, text="Elegir…", command=elegir_dxf).grid(row=0, column=2)

    ttk.Label(marco, text="Nombre del proyecto:").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Entry(marco, textvariable=v_proy).grid(row=1, column=1, columnspan=2, sticky="ew", padx=6)

    ttk.Label(marco, text="Unidades del dibujo:").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Combobox(marco, textvariable=v_unid, values=list(UNIDADES), state="readonly",
                 width=28).grid(row=2, column=1, sticky="w", padx=6)

    # --- Botones ----------------------------------------------------------------------
    botones = ttk.Frame(marco)
    botones.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 4))
    b_generar = ttk.Button(botones, text="Generar hojas")
    b_validar = ttk.Button(botones, text="Solo validar el dibujo")
    b_carpeta = ttk.Button(botones, text="Abrir carpeta de resultados", state="disabled")
    b_pdf = ttk.Button(botones, text="Abrir hojas_taller.pdf", state="disabled")
    for b in (b_generar, b_validar, b_carpeta, b_pdf):
        b.pack(side="left", padx=(0, 8))

    ttk.Label(marco, text="Resultado:").grid(row=4, column=0, sticky="w", pady=(8, 2))
    log_w = ScrolledText(marco, height=16, font=("Consolas", 9), state="disabled", wrap="word")
    log_w.grid(row=5, column=0, columnspan=3, sticky="nsew")

    def log(txt: str) -> None:
        log_w.configure(state="normal")
        log_w.insert("end", txt + "\n")
        log_w.see("end")
        log_w.configure(state="disabled")

    def limpiar_log() -> None:
        log_w.configure(state="normal")
        log_w.delete("1.0", "end")
        log_w.configure(state="disabled")

    # --- Ejecución en segundo plano ---------------------------------------------------------
    def correr(solo_validar: bool):
        if estado["ocupado"]:
            return
        dxf = v_dxf.get().strip().strip('"')
        proyecto = v_proy.get().strip()
        if not dxf or not Path(dxf).is_file():
            messagebox.showwarning("Falta el plano", "Elegí un archivo DXF existente.")
            return
        if dxf.lower().endswith(".dwg"):
            messagebox.showwarning(
                "El archivo es DWG",
                "El programa lee DXF. En AutoCAD usá SAVEAS y guardalo como «AutoCAD 2018 DXF».")
            return
        if not proyecto:
            messagebox.showwarning("Falta el nombre", "Escribí el nombre del proyecto.")
            return
        cfg["proyecto"] = proyecto
        _guardar_config(cfg)
        limpiar_log()
        estado["ocupado"] = True
        estado["resultado"] = None
        for b in (b_generar, b_validar):
            b.configure(state="disabled")
        b_carpeta.configure(state="disabled")
        b_pdf.configure(state="disabled")
        unidades = UNIDADES.get(v_unid.get(), "auto")

        def tarea():
            try:
                res = generar(dxf, proyecto, unidades, None, solo_validar, lambda t: cola.put(("log", t)))
                cola.put(("fin", res))
            except Exception as e:                       # noqa: BLE001
                cola.put(("log", "\nNo se pudo procesar el plano:\n" + "".join(
                    traceback.format_exception_only(type(e), e)).strip()))
                cola.put(("error", str(e)))

        threading.Thread(target=tarea, daemon=True).start()
        root.after(100, revisar_cola)

    def revisar_cola():
        seguir = True
        try:
            while True:
                tipo, dato = cola.get_nowait()
                if tipo == "log":
                    log(str(dato))
                elif tipo == "fin":
                    estado["resultado"] = dato
                    terminar(True)
                    seguir = False
                elif tipo == "error":
                    terminar(False)
                    seguir = False
        except queue.Empty:
            pass
        if seguir:
            root.after(100, revisar_cola)

    def terminar(ok: bool):
        estado["ocupado"] = False
        for b in (b_generar, b_validar):
            b.configure(state="normal")
        res = estado["resultado"]
        if ok and res is not None:
            b_carpeta.configure(state="normal")
            if (res.carpeta / "hojas_taller.pdf").exists():
                b_pdf.configure(state="normal")
            if res.alertas:
                log(f"\nRevisá el dibujo: hay {len(res.alertas)} alerta(s).")

    def abrir_carpeta():
        res = estado["resultado"]
        if res is not None:
            abrir_ruta(res.carpeta)

    def abrir_pdf():
        res = estado["resultado"]
        if res is not None and (res.carpeta / "hojas_taller.pdf").exists():
            abrir_ruta(res.carpeta / "hojas_taller.pdf")

    b_generar.configure(command=lambda: correr(False))
    b_validar.configure(command=lambda: correr(True))
    b_carpeta.configure(command=abrir_carpeta)
    b_pdf.configure(command=abrir_pdf)

    # --- Plantilla y ejemplo ------------------------------------------------------------------
    pie = ttk.Frame(marco)
    pie.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def guardar_plantilla():
        ruta = filedialog.asksaveasfilename(
            title="Guardar la plantilla de AutoCAD", defaultextension=".dxf",
            initialfile="plantilla_modulo.dxf", filetypes=[("DXF", "*.dxf")])
        if ruta:
            from crear_plantilla import crear
            crear(Path(ruta))
            messagebox.showinfo(
                "Plantilla guardada",
                "Abrila en AutoCAD, guardala como DWG y dibujá el módulo con esas capas y bloques.")

    def guardar_ejemplo():
        ruta = filedialog.asksaveasfilename(
            title="Guardar un DXF de ejemplo", defaultextension=".dxf",
            initialfile="ejemplo_modulo.dxf", filetypes=[("DXF", "*.dxf")])
        if ruta:
            from generar_ejemplo import crear
            crear(ruta, "m")
            v_dxf.set(ruta)
            messagebox.showinfo("Ejemplo guardado", "Quedó cargado en la ventana. Ingresá un nombre y generá las hojas.")

    ttk.Button(pie, text="Guardar plantilla de AutoCAD…", command=guardar_plantilla).pack(side="left", padx=(0, 8))
    ttk.Button(pie, text="Guardar DXF de ejemplo…", command=guardar_ejemplo).pack(side="left")

    log("1) Elegí el plano en DXF   2) Escribí el nombre del proyecto   3) Generar hojas.\n"
        "Si el plano está en DWG, en AutoCAD usá SAVEAS y guardalo como «AutoCAD 2018 DXF».")
    root.mainloop()


def autotest() -> None:
    """Comprueba que todo lo necesario está empaquetado: crea la plantilla y el ejemplo,
    y genera las hojas en una carpeta temporal. Útil para diagnosticar el .exe."""
    import tempfile

    from crear_plantilla import crear as crear_plantilla
    from generar_ejemplo import crear as crear_ejemplo
    from sip.proceso import generar

    tmp = Path(tempfile.mkdtemp())
    crear_plantilla(tmp / "plantilla.dxf")
    crear_ejemplo(str(tmp / "ejemplo.dxf"), "m")
    res = generar(tmp / "ejemplo.dxf", "Autotest", "auto", tmp / "salida")
    assert (tmp / "salida" / "hojas_taller.pdf").stat().st_size > 10000
    assert (tmp / "salida" / "planilla_paneles.xlsx").exists()
    print(f"AUTOTEST OK ({res.n_muros} muros, {res.n_techos} techos, {len(res.alertas)} alertas)")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--cli":
        import generar_hojas
        generar_hojas.main(args[1:])
        return
    if args and args[0] == "--autotest":
        autotest()
        return
    dxf = next((a for a in args if a.lower().endswith(".dxf")), None)
    abrir_ventana(dxf)


if __name__ == "__main__":
    main()
