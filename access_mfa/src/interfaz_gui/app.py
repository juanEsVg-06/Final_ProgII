from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from datetime import date, datetime, time

from negocio.enums import EstadoCredencial, EstadoPermiso, TipoArea
from negocio.exceptions import DominioError
from negocio.modelos import AreaAcceso, CredencialRFID, Estudiante, PermisoAcceso, PinGestual, PatronGestual
from negocio.validadores import validar_cedula, validar_correo, validar_id_banner, validar_nombre

from interfaz_gui.bootstrap import AppBoot, crear_app


# --------------------- Utilidades UI ---------------------

def _set_readonly_text(widget: tk.Text, value: str) -> None:
    widget.config(state="normal")
    widget.delete("1.0", "end")
    widget.insert("end", value)
    widget.config(state="disabled")


def _parse_hhmm(s: str) -> time:
    s = (s or "").strip()
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError("Hora inválida. Use HH:MM (ej: 07:00).")
    hh = int(parts[0]); mm = int(parts[1])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("Hora inválida. Use HH:MM (00-23:00-59).")
    return time(hh, mm)


def _parse_yyyy_mm_dd(s: str) -> date:
    s = (s or "").strip()
    return datetime.strptime(s, "%Y-%m-%d").date()


# --------------------- Diálogo de configuración ---------------------

class ConfigDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.title("Configuración inicial")
        self.resizable(False, False)
        self.grab_set()

        self.var_camara = tk.IntVar(value=1)
        self.var_arduino = tk.IntVar(value=0)
        self.var_sim_arduino = tk.IntVar(value=1)
        self.var_port = tk.StringVar(value="COM5")

        self.var_camara_index = tk.StringVar(value="0")
        self.var_preview = tk.IntVar(value=1)
        self.var_baud = tk.StringVar(value="9600")

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Hardware", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))

        ttk.Checkbutton(frm, text="Usar cámara real (MediaPipe)", variable=self.var_camara).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(frm, text="Usar Arduino físico", variable=self.var_arduino).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(frm, text="Si falla Arduino, usar simulador", variable=self.var_sim_arduino).grid(row=3, column=0, sticky="w")

        rowp = ttk.Frame(frm)
        rowp.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(rowp, text="Puerto Arduino:").pack(side="left")
        ttk.Entry(rowp, textvariable=self.var_port, width=12).pack(side="left", padx=8)

        # Cámara
        rowc = ttk.Frame(frm)
        rowc.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(rowc, text="Índice de cámara:").pack(side="left")
        ttk.Entry(rowc, textvariable=self.var_camara_index, width=6).pack(side="left", padx=8)
        ttk.Checkbutton(rowc, text="Preview cámara", variable=self.var_preview).pack(side="left", padx=8)

        # Baud
        rowb = ttk.Frame(frm)
        rowb.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(rowb, text="Baudrate:").pack(side="left")
        ttk.Entry(rowb, textvariable=self.var_baud, width=10).pack(side="left", padx=8)


        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancelar", command=self._cancel).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="Iniciar", command=self._ok).pack(side="right")

        self.result = None

    def _ok(self) -> None:
        puerto = (self.var_port.get() or "").strip() or "COM5"

        usar_camara = bool(self.var_camara.get())
        usar_arduino = bool(self.var_arduino.get())
        fallback_sim = bool(self.var_sim_arduino.get())

        # camera_index (string -> int)
        try:
            camera_index = int((self.var_camara_index.get() or "").strip() or "0")
        except ValueError:
            camera_index = 0

        # baudrate (string -> int)
        try:
            baudrate = int((self.var_baud.get() or "").strip() or "9600")
        except ValueError:
            baudrate = 9600

        mostrar_preview = bool(self.var_preview.get()) if usar_camara else False

        self.result = {
            "usar_camara": usar_camara,
            "camera_index": camera_index,
            "mostrar_preview": mostrar_preview,

            "usar_arduino": usar_arduino,
            "fallback_sim_arduino": fallback_sim,
            "puerto_arduino": puerto,
            "baudrate": baudrate,

            # Opcionales (si no los pides en el diálogo, quedan por defecto en bootstrap)
            "stable_frames": 10,
            "debounce_s": 0.8,
            "no_hand_frames": 6,
            "debug": False,
        }
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


# --------------------- App principal ---------------------

class AccessMFAWindow(tk.Tk):
    def __init__(self, app: AppBoot):
        super().__init__()
        self.app = app
        self.title("Access MFA - Control de Acceso")
        self.geometry("1120x680")
        self.minsize(980, 620)

        self._build_style()
        self._build_layout()

        self._show_view("dashboard")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Sidebar.TFrame", background="#14161a")
        style.configure("Sidebar.TButton", padding=(14, 10), anchor="w", background="#14161a", foreground="white")
        style.map("Sidebar.TButton", background=[("active", "#1f232a")])
        style.configure("Topbar.TFrame", background="#0f1115")
        style.configure("Card.TFrame", background="#171a21")
        style.configure("Card.TLabel", background="#171a21", foreground="white")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("H2.TLabel", font=("Segoe UI", 11, "bold"))

    def _build_layout(self) -> None:
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = ttk.Frame(root, style="Sidebar.TFrame", width=240)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ttk.Label(self.sidebar, text="ACCESS MFA", foreground="white", background="#14161a",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 10))
        ttk.Label(self.sidebar, text="Control de acceso 2FA", foreground="#cbd5e1", background="#14161a",
                  font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 10))

        self._nav_btn("Dashboard", "dashboard")
        self._nav_btn("Gestión", "gestion")
        self._nav_btn("Acceso", "acceso")
        self._nav_btn("Auditoría", "auditoria")

        ttk.Separator(self.sidebar).pack(fill="x", padx=12, pady=10)

        ttk.Button(self.sidebar, text="Cargar SEED (Demo)", style="Sidebar.TButton", command=self._seed_demo).pack(fill="x", padx=12, pady=4)
        ttk.Button(self.sidebar, text="Salir", style="Sidebar.TButton", command=self._on_close).pack(fill="x", padx=12, pady=4)

        # Main
        self.main = ttk.Frame(root)
        self.main.pack(side="left", fill="both", expand=True)

        # Topbar
        self.topbar = ttk.Frame(self.main, style="Topbar.TFrame", padding=(16, 12))
        self.topbar.pack(fill="x")
        self.title_lbl = ttk.Label(self.topbar, text="", style="Title.TLabel", foreground="white", background="#0f1115")
        self.title_lbl.pack(side="left")

        # Container views
        self.container = ttk.Frame(self.main, padding=16)
        self.container.pack(fill="both", expand=True)

        self.views: dict[str, ttk.Frame] = {}
        self.views["dashboard"] = self._build_dashboard(self.container)
        self.views["gestion"] = self._build_gestion(self.container)
        self.views["acceso"] = self._build_acceso(self.container)
        self.views["auditoria"] = self._build_auditoria(self.container)

        for v in self.views.values():
            v.pack_forget()

    def _nav_btn(self, text: str, key: str) -> None:
        ttk.Button(self.sidebar, text=text, style="Sidebar.TButton", command=lambda: self._show_view(key)).pack(fill="x", padx=12, pady=4)

    def _show_view(self, key: str) -> None:
        titles = {
            "dashboard": "Dashboard",
            "gestion": "Gestión de datos",
            "acceso": "Acceso (2FA)",
            "auditoria": "Auditoría / Registros",
        }
        self.title_lbl.config(text=titles.get(key, ""))
        for k, v in self.views.items():
            v.pack_forget()
        self.views[key].pack(fill="both", expand=True)

        if key in ("dashboard", "auditoria"):
            self._refresh_counts()
            self._refresh_auditoria()

    # --------------------- Dashboard ---------------------

    def _build_dashboard(self, parent: ttk.Frame) -> ttk.Frame:

        frm = ttk.Frame(parent)
        card = ttk.Frame(frm, style="Card.TFrame", padding=16)
        card.pack(fill="x")

        ttk.Label(card, text="Resumen del sistema", style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.lbl_counts = ttk.Label(card, text="", style="Card.TLabel")
        self.lbl_counts.pack(anchor="w", pady=(8, 0))

        note = ttk.Frame(frm, style="Card.TFrame", padding=16)
        note.pack(fill="x", pady=12)
        ttk.Label(note, text="Nota sobre cámara", style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            note,
            text="Por ahora, al capturar PIN/Patrón se abrirá la ventana de OpenCV/MediaPipe.\n"
                 "Para embeber la cámara dentro de esta ventana, se hace un refactor del sensor para streaming de frames.",
            style="Card.TLabel",
        ).pack(anchor="w", pady=(6, 0))

        ttk.Button(card, text="Test OK (Verdes)",
                   command=lambda: threading.Thread(target=self.app.actuador.indicar_exito, daemon=True).start()).pack(
            anchor="w", pady=(10, 0))
        ttk.Button(card, text="Test FAIL (Rojos)",
                   command=lambda: threading.Thread(target=self.app.actuador.indicar_fallo, daemon=True).start()).pack(
            anchor="w", pady=(6, 0))

        self._refresh_counts()
        return frm

    def _refresh_counts(self) -> None:
        try:
            t = (
                f"Estudiantes: {len(self.app.repo_est.listar())}    |    "
                f"Áreas: {len(self.app.repo_areas.listar())}    |    "
                f"Permisos: {len(self.app.repo_permisos.listar())}    |    "
                f"RFID: {len(self.app.repo_rfid.listar())}\n"
                f"PINs: {len(self.app.repo_pins.listar())}    |    "
                f"Patrones: {len(self.app.repo_patrones.listar())}    |    "
                f"Registros: {len(self.app.repo_registros.listar())}    |    "
                f"Accesos: {len(self.app.repo_accesos.listar())}"
            )
            self.lbl_counts.config(text=t)
        except Exception:
            self.lbl_counts.config(text="No se pudo cargar el resumen.")

        sensor_name = type(self.app.sensor).__name__
        act_name = type(self.app.actuador).__name__
        preview_on = "SI" if getattr(self.app, "frame_sink", None) is not None else "NO"

        t += f"\nHardware: Sensor={sensor_name} | Actuador={act_name} | PreviewGUI={preview_on}"
        self.lbl_counts.config(text=t)

    # --------------------- Gestión ---------------------

    def _build_gestion(self, parent: ttk.Frame) -> ttk.Frame:
        frm = ttk.Frame(parent)

        nb = ttk.Notebook(frm)
        nb.pack(fill="both", expand=True)

        nb.add(self._tab_estudiante(nb), text="Estudiante")
        nb.add(self._tab_area(nb), text="Área")
        nb.add(self._tab_permiso(nb), text="Permiso")
        nb.add(self._tab_rfid(nb), text="RFID")
        nb.add(self._tab_pin(nb), text="PIN")
        nb.add(self._tab_patron(nb), text="Patrón")

        return frm

    def _tab_estudiante(self, parent) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)

        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        ttk.Label(left, text="Crear estudiante", style="H2.TLabel").pack(anchor="w", pady=(0, 10))

        vars_ = {
            "cedula": tk.StringVar(),
            "nombres": tk.StringVar(),
            "apellidos": tk.StringVar(),
            "correo": tk.StringVar(),
            "banner": tk.StringVar(),
            "carrera": tk.StringVar(),
        }

        def row(lbl, key):
            r = ttk.Frame(left)
            r.pack(fill="x", pady=4)
            ttk.Label(r, text=lbl, width=18).pack(side="left")
            ttk.Entry(r, textvariable=vars_[key]).pack(side="left", fill="x", expand=True)

        row("Cédula:", "cedula")
        row("Nombres:", "nombres")
        row("Apellidos:", "apellidos")
        row("Correo:", "correo")
        row("ID Banner:", "banner")
        row("Carrera:", "carrera")

        def on_create():
            try:
                ced = validar_cedula(vars_["cedula"].get())
                nom = validar_nombre(vars_["nombres"].get(), campo="Nombres")
                ape = validar_nombre(vars_["apellidos"].get(), campo="Apellidos")
                cor = validar_correo(vars_["correo"].get())
                ban = validar_id_banner(vars_["banner"].get())
                car = (vars_["carrera"].get() or "").strip()

                e = Estudiante(
                    cedula_propietario=ced,
                    nombres=nom,
                    apellidos=ape,
                    correo_institucional=cor,
                    id_banner=ban,
                    carrera=car,
                )
                self.app.repo_est.guardar(e)
                messagebox.showinfo("OK", "Estudiante creado correctamente.")
                self._refresh_counts()
            except DominioError as ex:
                messagebox.showerror("Validación", str(ex))
            except Exception as ex:
                messagebox.showerror("Error", f"{type(ex).__name__}: {ex}")

        ttk.Button(left, text="Guardar", command=on_create).pack(anchor="e", pady=10)

        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(right, text="Listado", style="H2.TLabel").pack(anchor="w", pady=(0, 10))
        txt = tk.Text(right, height=18, wrap="word")
        txt.pack(fill="both", expand=True)
        txt.config(state="disabled")

        def refresh():
            items = self.app.repo_est.listar()
            out = "\n".join([f"- {e.cedula_propietario} | {e.nombres} {e.apellidos} | {e.id_banner} | {e.carrera}" for e in items]) or "(vacío)"
            _set_readonly_text(txt, out)

        ttk.Button(right, text="Actualizar", command=refresh).pack(anchor="e", pady=10)
        refresh()
        return tab

    def _tab_area(self, parent) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)
        left = ttk.Frame(tab); left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ttk.Frame(tab); right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Crear área", style="H2.TLabel").pack(anchor="w", pady=(0, 10))

        v_id = tk.StringVar()
        v_nombre = tk.StringVar()
        v_tipo = tk.StringVar(value=TipoArea.LABORATORIO.name)
        v_ubic = tk.StringVar()
        v_ap = tk.StringVar(value="07:00")
        v_ci = tk.StringVar(value="20:00")

        def row(lbl, var, widget="entry", values=None):
            r = ttk.Frame(left); r.pack(fill="x", pady=4)
            ttk.Label(r, text=lbl, width=18).pack(side="left")
            if widget == "combo":
                cb = ttk.Combobox(r, textvariable=var, values=values, state="readonly")
                cb.pack(side="left", fill="x", expand=True)
            else:
                ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True)

        row("ID Área:", v_id)
        row("Nombre:", v_nombre)
        row("Tipo:", v_tipo, widget="combo", values=[t.name for t in TipoArea])
        row("Ubicación:", v_ubic)
        row("Apertura (HH:MM):", v_ap)
        row("Cierre (HH:MM):", v_ci)

        def on_create():
            try:
                a = AreaAcceso(
                    id_area=(v_id.get() or "").strip(),
                    nombre=(v_nombre.get() or "").strip(),
                    tipo=TipoArea[v_tipo.get()],
                    ubicacion=(v_ubic.get() or "").strip(),
                    hora_apertura=_parse_hhmm(v_ap.get()),
                    hora_cierre=_parse_hhmm(v_ci.get()),
                )
                self.app.repo_areas.guardar(a)
                messagebox.showinfo("OK", "Área creada correctamente.")
                self._refresh_counts()
            except DominioError as ex:
                messagebox.showerror("Validación", str(ex))
            except Exception as ex:
                messagebox.showerror("Error", f"{type(ex).__name__}: {ex}")

        ttk.Button(left, text="Guardar", command=on_create).pack(anchor="e", pady=10)

        ttk.Label(right, text="Listado", style="H2.TLabel").pack(anchor="w", pady=(0, 10))
        txt = tk.Text(right, height=18, wrap="word"); txt.pack(fill="both", expand=True); txt.config(state="disabled")

        def refresh():
            items = self.app.repo_areas.listar()
            out = "\n".join([f"- {a.id_area} | {a.nombre} | {a.tipo.name} | {a.ubicacion} | {a.hora_apertura}-{a.hora_cierre}" for a in items]) or "(vacío)"
            _set_readonly_text(txt, out)

        ttk.Button(right, text="Actualizar", command=refresh).pack(anchor="e", pady=10)
        refresh()
        return tab

    def _tab_permiso(self, parent) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)
        left = ttk.Frame(tab); left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ttk.Frame(tab); right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Asignar permiso", style="H2.TLabel").pack(anchor="w", pady=(0, 10))

        v_id = tk.StringVar(value="PERM-")
        v_ced = tk.StringVar()
        v_area = tk.StringVar()
        v_estado = tk.StringVar(value=EstadoPermiso.ACTIVO.name)
        v_desde = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        v_hasta = tk.StringVar(value=date.today().replace(year=date.today().year + 1).strftime("%Y-%m-%d"))

        def row(lbl, var, widget="entry", values=None):
            r = ttk.Frame(left); r.pack(fill="x", pady=4)
            ttk.Label(r, text=lbl, width=18).pack(side="left")
            if widget == "combo":
                ttk.Combobox(r, textvariable=var, values=values, state="readonly").pack(side="left", fill="x", expand=True)
            else:
                ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True)

        row("ID Permiso:", v_id)
        row("Cédula:", v_ced)
        row("ID Área:", v_area)
        row("Estado:", v_estado, widget="combo", values=[e.name for e in EstadoPermiso])
        row("Vigente desde:", v_desde)
        row("Vigente hasta:", v_hasta)

        def on_create():
            try:
                ced = validar_cedula(v_ced.get())
                p = PermisoAcceso(
                    id_permiso=(v_id.get() or "").strip(),
                    cedula_propietario=ced,
                    id_area=(v_area.get() or "").strip(),
                    estado=EstadoPermiso[v_estado.get()],
                    vigente_desde=_parse_yyyy_mm_dd(v_desde.get()),
                    vigente_hasta=_parse_yyyy_mm_dd(v_hasta.get()),
                )
                self.app.repo_permisos.guardar(p)
                messagebox.showinfo("OK", "Permiso asignado correctamente.")
                self._refresh_counts()
            except DominioError as ex:
                messagebox.showerror("Validación", str(ex))
            except Exception as ex:
                messagebox.showerror("Error", f"{type(ex).__name__}: {ex}")

        ttk.Button(left, text="Guardar", command=on_create).pack(anchor="e", pady=10)

        ttk.Label(right, text="Listado", style="H2.TLabel").pack(anchor="w", pady=(0, 10))
        txt = tk.Text(right, height=18, wrap="word"); txt.pack(fill="both", expand=True); txt.config(state="disabled")

        def refresh():
            items = self.app.repo_permisos.listar()
            out = "\n".join([f"- {p.id_permiso} | {p.cedula_propietario} | {p.id_area} | {p.estado.name} | {p.vigente_desde} -> {p.vigente_hasta}" for p in items]) or "(vacío)"
            _set_readonly_text(txt, out)

        ttk.Button(right, text="Actualizar", command=refresh).pack(anchor="e", pady=10)
        refresh()
        return tab

    def _tab_rfid(self, parent) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)
        left = ttk.Frame(tab); left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ttk.Frame(tab); right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Asignar RFID", style="H2.TLabel").pack(anchor="w", pady=(0, 10))

        v_serial = tk.StringVar(value="RFID-")
        v_ced = tk.StringVar()
        v_em = tk.StringVar(value=date.today().replace(year=date.today().year - 1).strftime("%Y-%m-%d"))
        v_ex = tk.StringVar(value=date.today().replace(year=date.today().year + 1).strftime("%Y-%m-%d"))
        v_estado = tk.StringVar(value=EstadoCredencial.ACTIVA.name)

        def row(lbl, var, widget="entry", values=None):
            r = ttk.Frame(left); r.pack(fill="x", pady=4)
            ttk.Label(r, text=lbl, width=18).pack(side="left")
            if widget == "combo":
                ttk.Combobox(r, textvariable=var, values=values, state="readonly").pack(side="left", fill="x", expand=True)
            else:
                ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True)

        row("Serial:", v_serial)
        row("Cédula:", v_ced)
        row("Emisión:", v_em)
        row("Expiración:", v_ex)
        row("Estado:", v_estado, widget="combo", values=[e.name for e in EstadoCredencial])

        def on_create():
            try:
                ced = validar_cedula(v_ced.get())
                c = CredencialRFID(
                    serial=(v_serial.get() or "").strip(),
                    cedula_propietario=ced,
                    fecha_emision=_parse_yyyy_mm_dd(v_em.get()),
                    fecha_expiracion=_parse_yyyy_mm_dd(v_ex.get()),
                    estado=EstadoCredencial[v_estado.get()],
                )
                self.app.repo_rfid.guardar(c)
                messagebox.showinfo("OK", "RFID asignada correctamente.")
                self._refresh_counts()
            except DominioError as ex:
                messagebox.showerror("Validación", str(ex))
            except Exception as ex:
                messagebox.showerror("Error", f"{type(ex).__name__}: {ex}")

        ttk.Button(left, text="Guardar", command=on_create).pack(anchor="e", pady=10)

        ttk.Label(right, text="Listado", style="H2.TLabel").pack(anchor="w", pady=(0, 10))
        txt = tk.Text(right, height=18, wrap="word"); txt.pack(fill="both", expand=True); txt.config(state="disabled")

        def refresh():
            items = self.app.repo_rfid.listar()
            out = "\n".join([f"- {r.serial} | {r.cedula_propietario} | {r.estado.name} | {r.fecha_emision} -> {r.fecha_expiracion}" for r in items]) or "(vacío)"
            _set_readonly_text(txt, out)

        ttk.Button(right, text="Actualizar", command=refresh).pack(anchor="e", pady=10)
        refresh()
        return tab

    def _tab_pin(self, parent) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)

        ttk.Label(tab, text="Configurar PIN gestual (por estudiante + área)", style="H2.TLabel").pack(anchor="w", pady=(0, 10))

        v_ced = tk.StringVar()
        v_banner = tk.StringVar()
        v_idpin = tk.StringVar(value="PIN-")
        v_area = tk.StringVar()

        form = ttk.Frame(tab)
        form.pack(fill="x")

        def row(lbl, var):
            r = ttk.Frame(form); r.pack(fill="x", pady=4)
            ttk.Label(r, text=lbl, width=18).pack(side="left")
            ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True)

        row("Cédula:", v_ced)
        row("ID Banner:", v_banner)
        row("ID PIN:", v_idpin)
        row("ID Área:", v_area)

        log = tk.Text(tab, height=12, wrap="word")
        log.pack(fill="both", expand=True, pady=(10, 0))
        log.config(state="disabled")

        def write(msg: str) -> None:
            log.config(state="normal")
            log.insert("end", msg + "\n")
            log.see("end")
            log.config(state="disabled")

        def do_capture_and_save():
            try:
                ced = validar_cedula(v_ced.get())
                ban = validar_id_banner(v_banner.get())
                id_pin = (v_idpin.get() or "").strip()
                id_area = (v_area.get() or "").strip()

                est = self.app.repo_est.buscar(ced)
                if not est:
                    raise DominioError("No existe un estudiante con esa cédula. Cree el estudiante primero.")
                if est.id_banner != ban:
                    raise DominioError("Identidad no verificada: el ID Banner no corresponde a la cédula ingresada.")

                if not self.app.repo_areas.buscar(id_area):
                    raise DominioError("No existe esa Área. Cree el Área primero.")

                write("Captura de PIN: se abrirá la ventana de la cámara/simulador. Registre 4 gestos.")

                sec, _tiempos = self.app.sensor.capturar_secuencia(4, gesto_cierre=19, timeout_s=60)

                if len(sec) != 4:
                    write("PIN incompleto/cancelado. No se guardó.")
                    return

                pin = PinGestual(
                    id_pin=id_pin,
                    cedula_propietario=ced,
                    id_area=id_area,
                    id_banner=ban,
                    secuencia_gestos=sec,
                )
                self.app.repo_pins.guardar(pin)
                write(f"OK: PIN guardado para {ced} en Área {id_area}.")
                self._refresh_counts()
            except DominioError as ex:
                messagebox.showerror("Validación", str(ex))
            except Exception as ex:
                messagebox.showerror("Error", f"{type(ex).__name__}: {ex}")

        def on_capture():
            # Hilo para no congelar UI
            threading.Thread(target=do_capture_and_save, daemon=True).start()

        ttk.Button(tab, text="Capturar y Guardar PIN", command=on_capture).pack(anchor="e", pady=10)
        return tab

    def _tab_patron(self, parent) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)

        ttk.Label(tab, text="Enrolar patrón (1 por estudiante)", style="H2.TLabel").pack(anchor="w", pady=(0, 10))

        v_ced = tk.StringVar()
        v_banner = tk.StringVar()
        v_idpat = tk.StringVar(value="PAT-")

        form = ttk.Frame(tab)
        form.pack(fill="x")

        def row(lbl, var):
            r = ttk.Frame(form); r.pack(fill="x", pady=4)
            ttk.Label(r, text=lbl, width=18).pack(side="left")
            ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True)

        row("Cédula:", v_ced)
        row("ID Banner:", v_banner)
        row("ID Patrón:", v_idpat)

        log = tk.Text(tab, height=12, wrap="word"); log.pack(fill="both", expand=True, pady=(10, 0)); log.config(state="disabled")

        def write(msg: str) -> None:
            log.config(state="normal")
            log.insert("end", msg + "\n")
            log.see("end")
            log.config(state="disabled")

        def do_capture_and_save():
            try:
                ced = validar_cedula(v_ced.get())
                ban = validar_id_banner(v_banner.get())
                id_pat = (v_idpat.get() or "").strip()

                est = self.app.repo_est.buscar(ced)
                if not est:
                    raise DominioError("No existe un estudiante con esa cédula. Cree el estudiante primero.")
                if est.id_banner != ban:
                    raise DominioError("Identidad no verificada: el ID Banner no corresponde a la cédula ingresada.")

                write("Captura de Patrón: se abrirá la ventana de la cámara/simulador. Registre 10 gestos.")

                sec, tiempos = self.app.sensor.capturar_secuencia(10, gesto_cierre=19, timeout_s=180)
                if len(sec) != 10:
                    write("Patrón incompleto/cancelado. No se guardó.")
                    return

                pat = PatronGestual(
                    id_patron=id_pat,
                    cedula_propietario=ced,
                    secuencia_gestos=sec,
                    fecha_captura=datetime.now(),
                    tiempos_entre_gestos=tiempos,
                )
                self.app.repo_patrones.guardar(pat)
                write(f"OK: Patrón guardado para {ced}.")
                self._refresh_counts()
            except DominioError as ex:
                messagebox.showerror("Validación", str(ex))
            except Exception as ex:
                messagebox.showerror("Error", f"{type(ex).__name__}: {ex}")

        ttk.Button(tab, text="Capturar y Guardar Patrón", command=lambda: threading.Thread(target=do_capture_and_save, daemon=True).start()).pack(anchor="e", pady=10)
        return tab

    # --------------------- Acceso (2FA) ---------------------

    def _build_acceso(self, parent: ttk.Frame) -> ttk.Frame:
        frm = ttk.Frame(parent)

        card = ttk.Frame(frm, style="Card.TFrame", padding=16)
        card.pack(fill="x")

        ttk.Label(card, text="Intentar acceso", style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")

        v_ced = tk.StringVar()
        v_area = tk.StringVar()
        v_serial = tk.StringVar(value="RFID-")

        def row(lbl, var):
            r = ttk.Frame(card); r.pack(fill="x", pady=4)
            ttk.Label(r, text=lbl, width=18, style="Card.TLabel").pack(side="left")
            e = ttk.Entry(r, textvariable=var)
            e.pack(side="left", fill="x", expand=True)

        row("Cédula:", v_ced)
        row("ID Área:", v_area)
        row("Serial RFID:", v_serial)

        out = tk.Text(frm, height=18, wrap="word")
        out.pack(fill="both", expand=True, pady=12)
        out.config(state="disabled")

        def write(msg: str) -> None:
            out.config(state="normal")
            out.insert("end", msg + "\n")
            out.see("end")
            out.config(state="disabled")

        def do_access():
            try:
                ced = validar_cedula(v_ced.get())
                id_area = (v_area.get() or "").strip()
                serial = (v_serial.get() or "").strip()

                write("Iniciando flujo 2FA: se abrirá la ventana de la cámara/simulador cuando corresponda.")
                acc = self.app.caso_uso.solicitar_acceso(
                    cedula_propietario=ced,
                    id_area=id_area,
                    serial_rfid=serial,
                    sensor=self.app.sensor,
                    actuador=self.app.actuador,
                    gesto_cierre=19,
                )
                write(f"RESULTADO: {acc.resultado.name} | motivo={acc.motivo}")
                self._refresh_counts()
                self._refresh_auditoria()
            except DominioError as ex:
                write(f"[DENEGADO] {ex}")
            except Exception as ex:
                write(f"[ERROR] {type(ex).__name__}: {ex}")

        ttk.Button(card, text="Solicitar Acceso", command=lambda: threading.Thread(target=do_access, daemon=True).start()).pack(anchor="e", pady=(10, 0))
        return frm

    # --------------------- Auditoría ---------------------

    def _build_auditoria(self, parent: ttk.Frame) -> ttk.Frame:
        frm = ttk.Frame(parent)

        top = ttk.Frame(frm)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="Registros de autenticación", style="H2.TLabel").pack(side="left")
        ttk.Button(top, text="Actualizar", command=self._refresh_auditoria).pack(side="right")

        cols = ("timestamp", "cedula", "area", "metodo", "resultado", "motivo")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=18)
        self.tree.pack(fill="both", expand=True)

        heads = {
            "timestamp": "Fecha/Hora",
            "cedula": "Cédula",
            "area": "Área",
            "metodo": "Método",
            "resultado": "Resultado",
            "motivo": "Motivo",
        }
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=160 if c == "motivo" else 120, anchor="w")

        self._refresh_auditoria()
        return frm

    def _refresh_auditoria(self) -> None:
        if not hasattr(self, "tree"):
            return
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            regs = self.app.repo_registros.listar()
            regs.sort(key=lambda r: r.timestamp, reverse=True)
            for r in regs[:200]:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        r.cedula_propietario,
                        r.id_area,
                        r.metodo.name,
                        r.resultado.name,
                        r.motivo,
                    ),
                )
        except Exception:
            pass

    # --------------------- Seed demo ---------------------

    def _seed_demo(self) -> None:
        try:
            e = Estudiante(
                cedula_propietario="1710034065",
                nombres="Juan Esteban",
                apellidos="Velastegui Gordillo",
                correo_institucional="juanes@udla.edu.ec",
                id_banner="A00126187",
                carrera="Ciberseguridad",
            )
            self.app.repo_est.guardar(e)

            a = AreaAcceso(
                id_area="LAB-101",
                nombre="Laboratorio Redes",
                tipo=TipoArea.LABORATORIO,
                ubicacion="Bloque A",
                hora_apertura=time(7, 0),
                hora_cierre=time(23, 59),
            )
            self.app.repo_areas.guardar(a)

            p = PermisoAcceso(
                id_permiso="PERM-001",
                cedula_propietario=e.cedula_propietario,
                id_area=a.id_area,
                estado=EstadoPermiso.ACTIVO,
                vigente_desde=date.today(),
                vigente_hasta=date.today().replace(year=date.today().year + 1),
            )
            self.app.repo_permisos.guardar(p)

            r = CredencialRFID(
                serial="RFID-12345",
                cedula_propietario=e.cedula_propietario,
                fecha_emision=date.today().replace(year=date.today().year - 1),
                fecha_expiracion=date.today().replace(year=date.today().year + 1),
                estado=EstadoCredencial.ACTIVA,
            )
            self.app.repo_rfid.guardar(r)

            pin = PinGestual(
                id_pin="PIN-001",
                cedula_propietario=e.cedula_propietario,
                id_area=a.id_area,
                id_banner=e.id_banner,
                secuencia_gestos=[3, 7, 6, 2],
            )
            self.app.repo_pins.guardar(pin)

            patron = PatronGestual(
                id_patron="PAT-001",
                cedula_propietario=e.cedula_propietario,
                secuencia_gestos=[17, 25, 25, 17, 6, 7, 7, 2, 30, 31],
                fecha_captura=datetime.now(),
                tiempos_entre_gestos=None,
            )
            self.app.repo_patrones.guardar(patron)

            messagebox.showinfo("SEED", "Seed cargada correctamente.")
            self._refresh_counts()
            self._refresh_auditoria()
        except Exception as ex:
            messagebox.showerror("SEED", f"{type(ex).__name__}: {ex}")

    def _on_close(self) -> None:
        try:
            self.app.close()
        finally:
            self.destroy()


def main() -> None:
    root = tk.Tk()
    root.withdraw()

    dlg = ConfigDialog(root)
    root.wait_window(dlg)

    if not dlg.result:
        return

    app = crear_app(**dlg.result)

    root.destroy()

    win = AccessMFAWindow(app)
    win.mainloop()


if __name__ == "__main__":
    main()
