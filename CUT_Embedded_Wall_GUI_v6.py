# -*- coding: utf-8 -*-

"""
CUT Embedded Wall GUI v7.4

Modular desktop interface for CUT embedded-wall solvers.

Expected files in the same folder:
CUT_Embedded_Wall_ENGINE_v1_0.py
CUT_Embedded_Wall_SOLVER_DISPATCHER_v6.py
CUT_Embedded_Wall_GUI_v6.py
"""
from __future__ import annotations

import math
import os
import sys
import importlib.util
import json
import webbrowser
import threading
import queue
import time
import textwrap
from io import BytesIO
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any
import copy

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_pdf import PdfPages

# ============================================================
# Resource path helper for PyInstaller EXE
# ============================================================

def resource_path(relative_path):
    """
    Return absolute path to resource for both:
    - normal Python execution
    - PyInstaller EXE execution
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

PROGRAM_VERSION = "CUT Embedded Wall v7.4"


class ToolTip:
    """Small Tk/ttk tooltip used for inline help markers."""
    def __init__(self, widget, text, delay=450, wraplength=360):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        lbl = ttk.Label(self._tip, text=self.text, justify="left", wraplength=self.wraplength,
                        relief="solid", borderwidth=1, padding=(8, 5), background="#fffbe6")
        lbl.pack()

    def _hide(self, _event=None):
        self._cancel()
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def add_help(parent, row, column, text, sticky="w", padx=(4, 0), pady=3):
    marker = ttk.Label(parent, text="?", width=2, anchor="center", cursor="question_arrow")
    marker.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady)
    ToolTip(marker, text)
    return marker


DESKTOP_HELP_TEXTS = {
    "H (m)": "Wall/ground height measured downward from the retained-side ground surface. Left is excavation side; right is retained side.",
    "z_ex=H_R-H_L (m)": "Final excavation depth below the retained-side ground surface. It is computed from H_R − H_L.",
    "β (deg)": "Ground-surface inclination angle on each side, in degrees.",
    "q (kPa)": "Uniform surface surcharge applied on the corresponding side.",
    "z_w (m)": "Water-table elevation/depth below the retained-side ground surface on the corresponding side.",
    "k_h (-)": "Horizontal seismic coefficient used in the pseudo-static analysis.",
    "k_v (-)": "Vertical seismic coefficient. The sign controls upward/downward inertial effect.",
    "γ_w (kN/m³)": "Unit weight of water used for hydrostatic pressure calculations.",
    "Stiffness type": "Choose whether wall bending stiffness is entered directly as EI or calculated from E with I/thickness.",
    "EI (kPa·m⁴)": "Flexural rigidity per metre width of wall.",
    "E (kPa)": "Young's modulus of the wall material.",
    "I (m⁴) or t (m)": "Second moment of area per metre width, or wall thickness when the program computes I automatically.",
    "Type": "Select the support/reinforcement family. Anchors and MSE reinforcement act on the retained side; props act on the excavation side.",
    "Number of main excavation stages n": "Number of principal excavation levels after Stage 0. Stage 0 is no excavation/no supports; the final stage is locked to z_ex = H_R − H_L.",
    "Intermediate excavation drops between main stages": "Optional lowering steps inserted before each main stage. Example: 4 creates four drops before Stage i, with only supports 1..i−1 active until Stage i is reached.",
    "Apply q_L": "Defines at which construction stage the left/excavation-side surcharge becomes active.",
    "Apply q_R from": "Defines from which construction stage the right/retained-side surcharge is active.",
    "Solver": "Select the analysis model. Reinforced systems are automatically restricted to compatible differential-equation solvers.",
    "Integration": "Numerical integration method used for resultant forces and moments.",
    "Rigid-wall movement mode": "Controls how a rigid wall translation/rotation mechanism is selected.",
    "Rigid optimization solver": "Fast equilibrium solves only the balance equations; energy-aware mode also checks work/compatibility criteria.",
    "θ min/max": "Search interval for wall rotation angle in rigid/general-case calculations.",
    "z_p min/max": "Search interval for the pivot/depth parameter in rigid/general-case calculations.",
    "x_min": "Manual left plotting limit. Leave the automatic value unless extra horizontal space is needed.",
    "x_max": "Manual right plotting limit. Increase it when long reinforcement elements must be visible.",
    "Diagram": "Select which result quantity is displayed in the animation/plot.",
    "Frame duration (ms)": "Delay between animation frames. Larger values make the animation slower.",
    "Stage frame": "Select the construction-stage frame shown in the animation preview.",
    "Fixed-base solver": "Solver used to locate the point of virtual fixity/zero deflection for the PVF interpretation.",
    "Zero-deflection tolerance (mm)": "Numerical tolerance used when identifying zero-deflection locations.",
}

def attach_context_help(root):
    """Attach '?' hover help to common desktop labels without using long inline notes."""
    def walk(w):
        try:
            children = w.winfo_children()
        except Exception:
            children = []
        for child in children:
            try:
                txt = child.cget("text")
            except Exception:
                txt = ""
            if isinstance(txt, str) and txt:
                base = txt.replace("  ?", "")
                help_txt = DESKTOP_HELP_TEXTS.get(base)
                if help_txt:
                    try:
                        child.configure(text=base + "  ?", cursor="question_arrow")
                    except Exception:
                        pass
                    try:
                        ToolTip(child, help_txt)
                    except Exception:
                        pass
            walk(child)
    walk(root)

_SOLVER_MODULE = None


# Conservative professional palette: designed to remain readable with the
# native ttk theme on Windows, while giving the application a more polished
# engineering-software appearance.
UI_BG = "#f3f6f9"
PANEL_BG = "#ffffff"
HEADER_BG = "#e8eef6"
SUBTLE_BG = "#f8fafc"
ACCENT = "#1f5f99"
ACCENT_DARK = "#173f6b"
SELECT_BG = "#d7e9fb"
TEXT_DARK = "#172033"
TEXT_MUTED = "#56657a"
BORDER = "#c8d2df"


def _is_finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except Exception:
        return False


def load_solver_module():
    global _SOLVER_MODULE
    if _SOLVER_MODULE is not None:
        return _SOLVER_MODULE

    here = resource_path(".")
    path = os.path.join(here, "CUT_Embedded_Wall_SOLVER_DISPATCHER_v6.py")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing external solver module:\n{path}")

    spec = importlib.util.spec_from_file_location("cut_wall_solver_dispatcher", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load external solver module: {path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _SOLVER_MODULE = mod
    return mod


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).strip() or default)
    except Exception:
        return float(default)


def fmt(value: Any) -> str:
    try:
        x = float(value)
        if not math.isfinite(x):
            return "—"
        if abs(x) >= 1.0e5 or (0.0 < abs(x) < 1.0e-4):
            return f"{x:.4e}"
        return f"{x:.5g}"
    except Exception:
        return "—"


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, width=760, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, width=width, highlightthickness=0)
        self.vscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.inner = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class EditableLayerTable(ttk.Frame):
    columns = ("code", "h", "c", "phi", "gamma", "gamma_sat", "E", "nu")
    headings = {
        "code": "code",
        "h": "h (m)",
        "c": "c′ (kPa)",
        "phi": "φ′ (°)",
        "gamma": "γ (kN/m³)",
        "gamma_sat": "γsat (kN/m³)",
        "E": "E (kPa)",
        "nu": "ν (-)",
    }

    def __init__(self, parent, prefix: str, default_height: float, on_change=None):
        super().__init__(parent)
        self.prefix = prefix
        self.on_change = on_change
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", height=5)
        widths = {"code": 52, "h": 64, "c": 82, "phi": 70, "gamma": 92, "gamma_sat": 108, "E": 78, "nu": 58}
        for col in self.columns:
            self.tree.heading(col, text=self.headings[col])
            self.tree.column(col, width=widths[col], anchor="center", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        x = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        ttk.Button(buttons, text="+ Add layer", command=self.add_layer).pack(side="left", padx=3)
        ttk.Button(buttons, text="− Remove selected", command=self.remove_selected).pack(side="left", padx=3)
        ttk.Label(buttons, text="Double-click a cell to edit.", foreground="#555").pack(side="left", padx=10)
        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.insert("", "end", values=(f"{self.prefix}1", f"{default_height:g}", "0.001", "30.0", "20.0", "20.0", "20000", "0.30"))

    def add_layer(self):
        n = len(self.tree.get_children()) + 1
        self.tree.insert("", "end", values=(f"{self.prefix}{n}", "1.0", "0.001", "30.0", "20.0", "20.0", "20000", "0.30"))
        self._notify()

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            children = self.tree.get_children()
            sel = children[-1:] if children else []
        for item in sel:
            self.tree.delete(item)
        self._renumber_codes()
        self._notify()

    def _renumber_codes(self):
        for i, item in enumerate(self.tree.get_children(), start=1):
            vals = list(self.tree.item(item, "values"))
            vals[0] = f"{self.prefix}{i}"
            self.tree.item(item, values=vals)

    def _begin_edit(self, event):
        item = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not item or not col_id:
            return
        col_index = int(col_id[1:]) - 1
        if col_index < 0:
            return
        bbox = self.tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        vals = list(self.tree.item(item, "values"))
        old = vals[col_index]
        editor = ttk.Entry(self.tree)
        editor.insert(0, old)
        editor.select_range(0, "end")
        editor.focus_set()
        editor.place(x=x, y=y, width=w, height=h)

        def finish(event=None):
            vals[col_index] = editor.get()
            self.tree.item(item, values=vals)
            editor.destroy()
            self._notify()

        editor.bind("<Return>", finish)
        editor.bind("<FocusOut>", finish)
        editor.bind("<Escape>", lambda e: editor.destroy())

    def _notify(self):
        if self.on_change:
            self.on_change()

    def height(self) -> float:
        total = 0.0
        for layer in self.as_dicts():
            total += max(0.0, parse_float(layer["thickness"], 0.0))
        return total

    def as_dicts(self) -> list[dict[str, Any]]:
        out = []
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, "values"))
            while len(vals) < 8:
                vals.append("")
            out.append({
                "code": str(vals[0]),
                "thickness": parse_float(vals[1], 1.0),
                "c_prime": max(0.001, parse_float(vals[2], 0.0)),
                "phi_prime_deg": parse_float(vals[3], 30.0),
                "gamma": parse_float(vals[4], 18.0),
                "gamma_sat": parse_float(vals[5], 20.0),
                "E_s": parse_float(vals[6], 20000.0),
                "nu": parse_float(vals[7], 0.30),
            })
        return out


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(PROGRAM_VERSION)
        try:
            self.state("zoomed")
        except Exception:
            self.geometry("1500x900")
        self.project_file_path = None
        self._pause_requested = False
        self._stop_requested = False
        self._solver_thread = None
        self._solver_queue = queue.Queue()
        self._run_started_at = None
        self._paused_elapsed = 0.0
        self._pause_started_at = None
        self._progress_has_fraction = False
        self._build_style()
        self._build_vars()
        self._build_menu()
        self._build_ui()
        self.bind_all("<Shift-Return>", lambda event: self.run_solver())
        self.bind_all("<Shift-KP_Enter>", lambda event: self.run_solver())
        self._draw_geometry()
        self._empty_results()
        self.refresh_validation()
        self.after(250, self._enable_cursor_readout_for_all_plots)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _enable_cursor_readout_for_all_plots(self):
        """Attach live x/z readout with 3 decimals to every matplotlib canvas.

        The readout is deliberately figure-level, so it works for all normal
        plots and both animation panels without requiring a toolbar.
        """
        for name, obj in list(self.__dict__.items()):
            if not name.startswith("canvas_"):
                continue
            try:
                fig = obj.figure
            except Exception:
                continue
            if getattr(fig, "_cut_cursor_enabled", False):
                continue
            fig._cut_cursor_enabled = True
            fig._cut_cursor_text = None

            def _motion(event, canvas=obj, fig=fig):
                try:
                    old = getattr(fig, "_cut_cursor_text", None)
                    if old is not None:
                        old.remove()
                        fig._cut_cursor_text = None
                    if event.inaxes is not None and event.xdata is not None and event.ydata is not None:
                        fig._cut_cursor_text = fig.text(
                            0.995, 0.006,
                            f"x = {event.xdata:.3f}, z = {event.ydata:.3f}",
                            ha="right", va="bottom", fontsize=8, color="#111827",
                            bbox=dict(boxstyle="round,pad=0.20", facecolor="white", edgecolor="#94a3b8", alpha=0.85),
                        )
                    canvas.draw_idle()
                except Exception:
                    pass

            def _leave(event, canvas=obj, fig=fig):
                try:
                    old = getattr(fig, "_cut_cursor_text", None)
                    if old is not None:
                        old.remove()
                        fig._cut_cursor_text = None
                        canvas.draw_idle()
                except Exception:
                    pass

            try:
                obj.mpl_connect("motion_notify_event", _motion)
                obj.mpl_connect("figure_leave_event", _leave)
            except Exception:
                pass

    def _register_plot_canvas(self, canvas):
        """Register a newly-created canvas for the live coordinate readout."""
        try:
            self.after(10, self._enable_cursor_readout_for_all_plots)
        except Exception:
            pass
        return canvas

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=("Segoe UI", 10), background="#eef1f5", foreground="#1f2937")
        style.configure("TFrame", background="#eef1f5")
        style.configure("TLabelframe", background="#eef1f5", relief="solid")
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), background="#eef1f5")
        style.configure("TNotebook.Tab", padding=(14, 7))
        style.configure("Treeview", rowheight=26, background="#ffffff", fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Run.TButton", padding=(14, 7), font=("Segoe UI", 10, "bold"))
        style.configure("Start.TButton", padding=(14, 7), font=("Segoe UI", 10, "bold"), background="#d9f2df")
        style.map("Start.TButton", background=[("active", "#c6ebcf")])
        style.configure("Pause.TButton", padding=(14, 7), font=("Segoe UI", 10, "bold"), background="#ffe3b3")
        style.map("Pause.TButton", background=[("active", "#ffd28a")])
        style.configure("Stop.TButton", padding=(14, 7), font=("Segoe UI", 10, "bold"), background="#ffd6d6")
        style.map("Stop.TButton", background=[("active", "#ffb8b8")])
        style.configure("WaterRun.TButton", padding=(14, 7), font=("Segoe UI", 10, "bold"), background="#fecaca", foreground="#7f1d1d")
        style.map("WaterRun.TButton", background=[("active", "#fca5a5")])
        style.configure("WaterPlay.TButton", padding=(14, 7), font=("Segoe UI", 10, "bold"), background="#bbf7d0", foreground="#14532d")
        style.map("WaterPlay.TButton", background=[("active", "#86efac")])

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Home", command=lambda: webbrowser.open("https://cut-apps.streamlit.app/"))
        file_menu.add_command(label="Open", command=self.file_open)
        file_menu.add_command(label="Save", command=self.file_save)
        file_menu.add_command(label="Save as", command=self.file_save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Report (PDF)", command=self.export_report_pdf)
        file_menu.add_command(label="Manual", command=self.open_manual_pdf)
        file_menu.add_command(label="Description", command=self.open_description_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Run solver    Shift+Enter", command=self.run_solver)
        file_menu.add_command(label="Load defaults", command=self.load_defaults)
        file_menu.add_command(label="Copy results table", command=self.copy_results_table)
        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_command(label="Home", command=self._open_home)
        menubar.add_command(label="About", command=self.show_about)
        self.config(menu=menubar)


    def open_manual_pdf(self):
        """Open manual.pdf from the program folder or PyInstaller bundle, if available."""
        candidates = [
            resource_path("manual.pdf"),
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "manual.pdf"),
            os.path.join(os.getcwd(), "manual.pdf"),
        ]
        manual_path = next((p for p in candidates if p and os.path.exists(p)), None)
        if not manual_path:
            messagebox.showinfo("Manual", "manual.pdf was not found in the program folder.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(manual_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", manual_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", manual_path])
        except Exception as exc:
            messagebox.showerror("Manual", f"Could not open manual.pdf:\n{exc}")


    def open_description_pdf(self):
        """Open CUT_Embedded_Wall_Description.pdf from the program folder or PyInstaller bundle, if available."""
        candidates = [
            resource_path("CUT_Embedded_Wall_Description.pdf"),
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "CUT_Embedded_Wall_Description.pdf"),
            os.path.join(os.getcwd(), "CUT_Embedded_Wall_Description.pdf"),
        ]
        description_path = next((p for p in candidates if p and os.path.exists(p)), None)
        if not description_path:
            messagebox.showinfo("Description", "CUT_Embedded_Wall_Description.pdf was not found in the program folder.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(description_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", description_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", description_path])
        except Exception as exc:
            messagebox.showerror("Description", f"Could not open CUT_Embedded_Wall_Description.pdf:\n{exc}")
            
    def _layer_table_rows(self, table):
        return [list(table.tree.item(item, "values")) for item in table.tree.get_children()]

    def _set_layer_table_rows(self, table, rows):
        for item in table.tree.get_children():
            table.tree.delete(item)
        for row in rows or []:
            vals = list(row)
            while len(vals) < 8:
                vals.append("")
            table.tree.insert("", "end", values=vals[:8])
        if not table.tree.get_children():
            table.add_layer()
        table._renumber_codes()
        table._notify()

    def _collect_project_data(self):
        return {
            "version": PROGRAM_VERSION,
            "inputs": {
                "beta_L": self.var_beta_L.get(),
                "beta_R": self.var_beta_R.get(),
                "q_L": self.var_q_L.get(),
                "q_R": self.var_q_R.get(),
                "z_w_L": self.var_z_w_L.get(),
                "z_w_R": self.var_z_w_R.get(),
                "gamma_w": self.var_gamma_w.get(),
                "k_h": self.var_k_h.get(),
                "k_v": self.var_k_v.get(),
                "dx_trans": self.var_dx_trans.get(),
                "theta_rot": self.var_theta_rot.get(),
                "z_pivot": self.var_z_pivot.get(),
                "stiffness_type": self.var_stiffness_type.get(),
                "EI": self.var_EI.get(),
                "E": self.var_E.get(),
                "I_or_t": self.var_I_or_t.get(),
                "dz": self.var_dz.get(),
                "n_points": self.var_n_points.get(),
                "N": self.var_N.get(),
                "tol": self.var_tol.get(),
                "equilibrium_force_tol": self.var_equilibrium_force_tol.get(),
                "equilibrium_moment_tol": self.var_equilibrium_moment_tol.get(),
                "work_band_tol": self.var_work_band_tol.get(),
                "general_case_bending_schemes": self.var_general_case_bending_schemes.get(),
                "general_case_theta_refine_passes": self.var_general_case_theta_refine_passes.get(),
                "general_case_theta_points": self.var_general_case_theta_points.get(),
                "general_case_zp_points": self.var_general_case_zp_points.get(),
                "general_case_pivot_margin_frac": self.var_general_case_pivot_margin_frac.get(),
                "general_case_parallel": bool(self.var_general_case_parallel.get()),
                "general_case_max_workers": self.var_general_case_max_workers.get(),
                "solver_display": self.var_solver_display.get(),
                "integration_method": self.var_integration_method.get(),
                "no_bending_mode": self.var_no_bending_mode.get(),
                "rigid_optimization_solver": self.var_rigid_optimization_solver.get(),
                "work_theta_min": self.var_work_theta_min.get(),
                "work_theta_max": self.var_work_theta_max.get(),
                "work_theta_count": self.var_work_theta_count.get(),
                "work_dx_count": self.var_work_dx_count.get(),
                "work_zp_count": self.var_work_zp_count.get(),
            },
            "left_layers": self._layer_table_rows(self.left_table),
            "right_layers": self._layer_table_rows(self.right_table),
            "reinforcement_type": self.var_reinf_type.get() if hasattr(self, "var_reinf_type") else "No reinforcement",
            "reinforcement_rows_by_type": getattr(self, "reinf_rows_by_type", {}),
            "excavation_stage_count": int(self.var_stage_count.get()) if hasattr(self, "var_stage_count") else 1,
            "excavation_intermediate_count": int(self.var_stage_intermediate_count.get()) if hasattr(self, "var_stage_intermediate_count") else 0,
            "stage_q_L_apply": self.var_stage_q_L_apply.get() if hasattr(self, "var_stage_q_L_apply") else "Stage N+1 (after final)",
            "stage_q_R_apply": self.var_stage_q_R_apply.get() if hasattr(self, "var_stage_q_R_apply") else "Stage 0",
            "excavation_stages": self._stage_rows_for_save() if hasattr(self, "stage_tree") else [],
        }

    def _apply_project_data(self, data):
        inp = data.get("inputs", {}) if isinstance(data, dict) else {}
        setters = {
            "beta_L": self.var_beta_L, "beta_R": self.var_beta_R,
            "q_L": self.var_q_L, "q_R": self.var_q_R,
            "z_w_L": self.var_z_w_L, "z_w_R": self.var_z_w_R,
            "gamma_w": self.var_gamma_w, "k_h": self.var_k_h, "k_v": self.var_k_v,
            "dx_trans": self.var_dx_trans, "theta_rot": self.var_theta_rot, "z_pivot": self.var_z_pivot,
            "stiffness_type": self.var_stiffness_type, "EI": self.var_EI, "E": self.var_E, "I_or_t": self.var_I_or_t,
            "dz": self.var_dz, "n_points": self.var_n_points, "N": self.var_N, "tol": self.var_tol,
            "equilibrium_force_tol": self.var_equilibrium_force_tol, "equilibrium_moment_tol": self.var_equilibrium_moment_tol, "work_band_tol": self.var_work_band_tol,
            "general_case_bending_schemes": self.var_general_case_bending_schemes, "general_case_theta_refine_passes": self.var_general_case_theta_refine_passes,
            "general_case_theta_points": self.var_general_case_theta_points, "general_case_zp_points": self.var_general_case_zp_points,
            "general_case_pivot_margin_frac": self.var_general_case_pivot_margin_frac,
            "general_case_parallel": self.var_general_case_parallel, "general_case_max_workers": self.var_general_case_max_workers,
            "solver_display": self.var_solver_display, "integration_method": self.var_integration_method,
            "no_bending_mode": self.var_no_bending_mode,
            "rigid_optimization_solver": self.var_rigid_optimization_solver,
            "work_theta_min": self.var_work_theta_min, "work_theta_max": self.var_work_theta_max,
            "work_theta_count": self.var_work_theta_count, "work_dx_count": self.var_work_dx_count,
            "work_zp_count": self.var_work_zp_count,
        }
        for key, var in setters.items():
            if key in inp:
                try:
                    var.set(inp[key])
                except Exception:
                    pass
        if "left_layers" in data:
            self._set_layer_table_rows(self.left_table, data.get("left_layers"))
        if "right_layers" in data:
            self._set_layer_table_rows(self.right_table, data.get("right_layers"))
        if hasattr(self, "var_reinf_type"):
            self.reinf_rows_by_type = data.get("reinforcement_rows_by_type", getattr(self, "reinf_rows_by_type", {}))
            self.var_reinf_type.set(data.get("reinforcement_type", self.var_reinf_type.get()))
            if "excavation_stage_count" in data and hasattr(self, "var_stage_count"):
                try:
                    self.var_stage_count.set(max(1, int(data.get("excavation_stage_count", 1))))
                except Exception:
                    self.var_stage_count.set(1)
            if "excavation_intermediate_count" in data and hasattr(self, "var_stage_intermediate_count"):
                try:
                    self.var_stage_intermediate_count.set(max(0, int(data.get("excavation_intermediate_count", 0))))
                except Exception:
                    self.var_stage_intermediate_count.set(0)
            if hasattr(self, "var_stage_q_L_apply"):
                self.var_stage_q_L_apply.set(str(data.get("stage_q_L_apply", "Stage N+1 (after final)")))
            if hasattr(self, "var_stage_q_R_apply"):
                self.var_stage_q_R_apply.set(str(data.get("stage_q_R_apply", "Stage 0")))
            if hasattr(self, "_refresh_stage_load_options"):
                self._refresh_stage_load_options()
            if hasattr(self, "_set_stage_rows"):
                self._set_stage_rows(data.get("excavation_stages", []), preserve_count=True)
            self._reinforcement_type_changed()
        self._update_wall_stiffness_visibility()
        self._update_solver_visibility()
        self._update_heights()
        self._draw_geometry_safe()

    def file_open(self):
        path = filedialog.askopenfilename(
            title="Open CUT embedded wall project",
            filetypes=[("CUT project", "*.cutwall.json"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_project_data(data)
            self.project_file_path = path
            self.run_status.set(f"Opened project: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Open", f"Could not open project file:\n{exc}")

    def file_save(self):
        if not self.project_file_path:
            return self.file_save_as()
        try:
            with open(self.project_file_path, "w", encoding="utf-8") as f:
                json.dump(self._collect_project_data(), f, indent=2, ensure_ascii=False)
            self.run_status.set(f"Saved project: {os.path.basename(self.project_file_path)}")
        except Exception as exc:
            messagebox.showerror("Save", f"Could not save project file:\n{exc}")

    def file_save_as(self):
        path = filedialog.asksaveasfilename(
            title="Save CUT embedded wall project as",
            defaultextension=".cutwall.json",
            filetypes=[("CUT project", "*.cutwall.json"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        self.project_file_path = path
        self.file_save()

    def _report_value(self, value):
        try:
            if isinstance(value, float):
                if abs(value) >= 1.0e4 or (0.0 < abs(value) < 1.0e-3):
                    return f"{value:.4e}"
                return f"{value:.6g}"
            return str(value)
        except Exception:
            return str(value)

    def _safe_legend(self, ax, *args, **kwargs):
        """Draw a legend only when labelled artists exist."""
        try:
            handles, labels = ax.get_legend_handles_labels()
            pairs = [(h, l) for h, l in zip(handles, labels) if l and not str(l).startswith('_')]
            if not pairs:
                return None
            seen = {}
            for h, l in pairs:
                if l not in seen:
                    seen[l] = h
            return ax.legend(list(seen.values()), list(seen.keys()), *args, **kwargs)
        except Exception:
            return None

    def _report_short_text(self, value, limit=92):
        txt = self._report_value(value)
        txt = " ".join(str(txt).replace("\n", " ").split())
        if len(txt) > limit:
            return txt[:max(0, limit - 1)] + "…"
        return txt

    def _report_table_page(self, pdf, title, columns, rows, note=None, max_rows=28, landscape=False, col_widths=None, fontsize=None):
        """Compact, non-overflowing PDF table page.

        This is intentionally conservative: long values are truncated in normal report
        pages and diagnostics are shown as compact samples rather than raw dumps.
        """
        rows = list(rows or [])
        if not rows:
            return
        ncols = max(1, len(columns))
        if landscape is None:
            landscape = ncols > 7
        fig_size = (11.69, 8.27) if landscape else (8.27, 11.69)
        page_w, page_h = fig_size
        if fontsize is None:
            fontsize = 7.0 if ncols <= 4 else (6.0 if ncols <= 8 else 4.8)
        max_rows = min(max_rows, 34 if landscape else 30)
        for start in range(0, len(rows), max_rows):
            chunk = rows[start:start + max_rows]
            fig = Figure(figsize=fig_size, dpi=120)
            ax = fig.add_subplot(111)
            ax.axis("off")
            page_title = title if len(rows) <= max_rows else f"{title} ({start + 1}-{start + len(chunk)} of {len(rows)})"
            ax.text(0.04, 0.965, page_title, ha="left", va="top", fontsize=12, weight="bold", color="#111827")
            y_top = 0.925
            if note:
                wrapped = "\n".join(textwrap.wrap(str(note), width=118 if landscape else 88))
                ax.text(0.04, 0.925, wrapped, ha="left", va="top", fontsize=7.2, color="#475569")
                y_top = 0.875 - 0.018 * max(0, wrapped.count("\n"))
            cell_text = []
            for row in chunk:
                cell_text.append([self._report_short_text(v, 80 if ncols <= 6 else 42) for v in row])
            if col_widths is None:
                if ncols == 2:
                    col_widths = [0.34, 0.66]
                else:
                    col_widths = [1.0 / ncols] * ncols
            table_h = min(0.72, max(0.07, 0.026 * (len(chunk) + 1) + 0.008))
            table_y = max(0.055, y_top - table_h)
            tbl = ax.table(
                cellText=cell_text,
                colLabels=[self._report_short_text(c, 42) for c in columns],
                loc="upper left",
                cellLoc="left",
                colWidths=col_widths,
                bbox=[0.04, table_y, 0.92, table_h],
            )
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(fontsize)
            for (rr, cc), cell in tbl.get_celld().items():
                cell.set_linewidth(0.20)
                cell.set_edgecolor("#cbd5e1")
                cell.PAD = 0.025
                if rr == 0:
                    cell.set_facecolor("#1f2937")
                    cell.set_text_props(weight="bold", color="white")
                elif rr % 2 == 0:
                    cell.set_facecolor("#f8fafc")
                else:
                    cell.set_facecolor("#ffffff")
            ax.text(0.04, 0.025, "CUT Embedded Wall - educational/research software - no warranty", ha="left", va="bottom", fontsize=6.2, color="#64748b")
            ax.text(0.96, 0.025, PROGRAM_VERSION, ha="right", va="bottom", fontsize=6.2, color="#64748b")
            pdf.savefig(fig)
            plt.close(fig)

    def _report_multi_table_page(self, pdf, title, blocks, landscape=False):
        """Place several compact small tables on one A4 page.

        blocks: list of (subtitle, columns, rows, col_widths)
        Designed for short input/result tables so they do not consume whole pages.
        """
        blocks = [(st, cols, list(rows or []), cw) for st, cols, rows, cw in (blocks or []) if rows]
        if not blocks:
            return
        fig_size = (11.69, 8.27) if landscape else (8.27, 11.69)
        fig = Figure(figsize=fig_size, dpi=120)
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.04, 0.965, title, ha="left", va="top", fontsize=12.5, weight="bold", color="#111827")
        y = 0.915
        for subtitle, columns, rows, col_widths in blocks:
            ncols = max(1, len(columns))
            nrows = len(rows) + 1
            # Compact height: enough for rows, never page-filling for small tables.
            row_h = 0.038 if (landscape and ncols > 6) else (0.030 if landscape else 0.026)
            table_h = min(0.40 if (landscape and ncols > 6) else 0.33, max(0.095, row_h * nrows + 0.012))
            if y - table_h < 0.075:
                ax.text(0.04, 0.025, "CUT Embedded Wall - educational/research software - no warranty", ha="left", va="bottom", fontsize=6.2, color="#64748b")
                ax.text(0.96, 0.025, PROGRAM_VERSION, ha="right", va="bottom", fontsize=6.2, color="#64748b")
                pdf.savefig(fig)
                plt.close(fig)
                fig = Figure(figsize=fig_size, dpi=120)
                ax = fig.add_subplot(111)
                ax.axis("off")
                ax.text(0.04, 0.965, title + " (continued)", ha="left", va="top", fontsize=12.5, weight="bold", color="#111827")
                y = 0.915
            ax.text(0.04, y, subtitle, ha="left", va="top", fontsize=9.4, weight="bold", color="#334155")
            y -= 0.024
            cell_text = [[self._report_short_text(v, 70 if ncols <= 5 else 34) for v in row] for row in rows]
            if col_widths is None:
                col_widths = [1.0 / ncols] * ncols
            tbl = ax.table(
                cellText=cell_text,
                colLabels=[self._report_short_text(c, 44) for c in columns],
                loc="upper left",
                cellLoc="left",
                colWidths=col_widths,
                bbox=[0.04, y - table_h, 0.92, table_h],
            )
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(6.2 if ncols > 6 else 7.4)
            for (rr, cc), cell in tbl.get_celld().items():
                cell.set_linewidth(0.18)
                cell.set_edgecolor("#cbd5e1")
                cell.PAD = 0.025
                if rr == 0:
                    cell.set_facecolor("#1f2937")
                    cell.set_text_props(weight="bold", color="white")
                elif rr % 2 == 0:
                    cell.set_facecolor("#f8fafc")
                else:
                    cell.set_facecolor("#ffffff")
            y -= table_h + 0.035
        ax.text(0.04, 0.025, "CUT Embedded Wall - educational/research software - no warranty", ha="left", va="bottom", fontsize=6.2, color="#64748b")
        ax.text(0.96, 0.025, PROGRAM_VERSION, ha="right", va="bottom", fontsize=6.2, color="#64748b")
        pdf.savefig(fig)
        plt.close(fig)

    def _report_fig_to_array(self, fig_obj):
        if fig_obj is None:
            return None
        buf = BytesIO()
        try:
            fig_obj.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
            buf.seek(0)
            return mpimg.imread(buf)
        except Exception:
            return None
        finally:
            try:
                buf.close()
            except Exception:
                pass

    def _report_plot_grid_page(self, pdf, title, items):
        """Place existing GUI figures in the report, two per A4 page.

        The plots are exported from the GUI figures directly so the report matches
        the on-screen chart styling, axes, legends and user x-limits as closely as possible.
        """
        items = [(name, fig) for name, fig in items if fig is not None]
        for start in range(0, len(items), 2):
            pair = items[start:start + 2]
            if str(title).startswith("Problem definition"):
                fig = Figure(figsize=(11.69, 8.27), dpi=150)
                page_ax = fig.add_axes([0, 0, 1, 1])
                page_ax.axis("off")
                page_ax.text(0.045, 0.955, title if start == 0 else f"{title} (continued)", ha="left", va="top", fontsize=13, weight="bold", color="#111827")
                boxes = [(0.055, 0.12, 0.43, 0.76), (0.525, 0.12, 0.43, 0.76)]
            else:
                fig = Figure(figsize=(8.27, 11.69), dpi=120)
                page_ax = fig.add_axes([0, 0, 1, 1])
                page_ax.axis("off")
                page_ax.text(0.055, 0.965, title if start == 0 else f"{title} (continued)", ha="left", va="top", fontsize=13, weight="bold", color="#111827")
                boxes = [(0.07, 0.52, 0.86, 0.39), (0.07, 0.075, 0.86, 0.39)]
            for (name, fig_obj), box in zip(pair, boxes):
                arr = self._report_fig_to_array(fig_obj)
                ax = fig.add_axes(box)
                ax.axis("off")
                ax.text(0.0, 1.03, name, transform=ax.transAxes, ha="left", va="bottom", fontsize=9.5, weight="bold", color="#334155")
                if arr is not None:
                    ax.imshow(arr, aspect="equal")
                    ax.set_anchor("C")
                else:
                    ax.text(0.5, 0.5, "Plot unavailable", ha="center", va="center", fontsize=9)
            page_ax.text(0.055, 0.025, "CUT Embedded Wall - educational/research software - no warranty", ha="left", va="bottom", fontsize=6.2, color="#64748b")
            page_ax.text(0.945, 0.025, PROGRAM_VERSION, ha="right", va="bottom", fontsize=6.2, color="#64748b")
            pdf.savefig(fig)
            plt.close(fig)

    def export_report_pdf(self):
        """Export a compact A4 engineering report of the current run."""
        if self.last_result is None or self.last_model is None:
            messagebox.showwarning("Report", "Run a solver first; no results are available for export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export CUT embedded wall report",
            defaultextension=".pdf",
            filetypes=[("PDF report", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with PdfPages(path) as pdf:
                r = self.last_result
                m = self.last_model
                s = dict(getattr(r, 'summary', {}) or {})

                # Cover / executive summary.
                fig = Figure(figsize=(8.27, 11.69), dpi=120)
                ax = fig.add_subplot(111)
                ax.axis("off")
                ax.text(0.055, 0.955, "Cyprus University of Technology", ha="left", va="top", fontsize=15, weight="bold", color="#0f172a")
                ax.text(0.055, 0.925, "Department of Civil Engineering and Geoinformatics", ha="left", va="top", fontsize=10.5, color="#334155")
                ax.text(0.055, 0.875, "CUT Embedded Wall", ha="left", va="top", fontsize=24, weight="bold", color="#0f172a")
                ax.text(0.055, 0.840, "Engineering calculation report", ha="left", va="top", fontsize=13, color="#334155")
                ax.text(0.055, 0.805, f"Program: {PROGRAM_VERSION}", ha="left", va="top", fontsize=9.0)
                ax.text(0.055, 0.785, f"Solver: {self.var_solver_display.get()}", ha="left", va="top", fontsize=9.0)
                ax.text(0.055, 0.765, f"Status: {getattr(r, 'status', '')}", ha="left", va="top", fontsize=9.0)

                notice = (
                    "Educational / research software - no warranty. This program is intended for teaching, research, "
                    "method development and independent engineering checking. It is not a certified commercial design "
                    "package. No warranty, expressed or implied, is provided regarding correctness, completeness, fitness "
                    "for design or code compliance. Results must be reviewed and independently verified by a qualified "
                    "engineer before practical use."
                )
                notice_wrapped = "\n".join(textwrap.wrap(notice, width=78))
                ax.add_patch(plt.Rectangle((0.055, 0.615), 0.89, 0.125, facecolor="#fff7ed", edgecolor="#fb923c", linewidth=0.8))
                ax.text(0.072, 0.720, "Educational / research software - no warranty", fontsize=10.0, weight="bold", color="#9a3412", va="top")
                ax.text(0.072, 0.688, notice_wrapped, fontsize=6.2, color="#7c2d12", va="top", linespacing=1.00)

                def mm_val(key):
                    try:
                        return f"{1000.0 * float(s.get(key, 0.0)):.2f}"
                    except Exception:
                        return "-"
                key_rows = []
                key_rows.append(["Converged", "Yes" if bool(s.get("converged", False)) else "No"])
                key_rows.append(["Iterations", self._report_value(s.get("iterations", ""))])
                if "max_deflection_abs_m" in s:
                    key_rows.append(["Max |Δx| (mm)", mm_val("max_deflection_abs_m")])
                if "max_iteration_change_m" in s:
                    key_rows.append(["Final Δchange (mm)", mm_val("max_iteration_change_m")])
                if "max_net_pressure_change_kPa" in s:
                    key_rows.append(["Final pressure change (kPa)", self._report_value(s.get("max_net_pressure_change_kPa"))])
                if "max_support_force_abs_kN_per_m" in s:
                    key_rows.append(["Max support force (kN/m)", self._report_value(s.get("max_support_force_abs_kN_per_m"))])
                tbl = ax.table(cellText=key_rows, colLabels=["Quantity", "Value"], cellLoc="left", colWidths=[0.48, 0.52], loc="upper left", bbox=[0.055, 0.420, 0.89, 0.18])
                tbl.auto_set_font_size(False); tbl.set_fontsize(8.2)
                for (rr, cc), cell in tbl.get_celld().items():
                    cell.set_linewidth(0.25); cell.set_edgecolor("#cbd5e1"); cell.PAD = 0.05
                    if rr == 0:
                        cell.set_facecolor("#1f2937"); cell.set_text_props(color="white", weight="bold")
                    elif rr % 2 == 0:
                        cell.set_facecolor("#f8fafc")

                notes = []
                for key in ("solver", "fixed-base boundary conditions", "pressure update formulation", "reinforcement formulation"):
                    if key in s:
                        notes.append(f"- {key}: {self._report_short_text(s.get(key), 140)}")
                notes.append("- x(z) is the horizontal displacement at depth z; the report plots use the same plotted figures as the GUI.")
                ax.text(0.055, 0.365, "Formulation notes", ha="left", va="top", fontsize=11.5, weight="bold", color="#111827")
                wrapped_notes = []
                for nt in notes:
                    wrapped_notes.extend(textwrap.wrap(nt, width=86, subsequent_indent="  "))
                ax.text(0.055, 0.335, "\n".join(wrapped_notes[:12]), ha="left", va="top", fontsize=6.6, color="#111827", linespacing=1.08)
                ax.text(0.055, 0.025, "CUT Embedded Wall - educational/research software - no warranty", ha="left", va="bottom", fontsize=6.2, color="#64748b")
                ax.text(0.945, 0.025, PROGRAM_VERSION, ha="right", va="bottom", fontsize=6.2, color="#64748b")
                pdf.savefig(fig)
                plt.close(fig)

                # Problem definition: export the same schematic figures used in the GUI.
                # This makes the report self-contained: geometry, wall, excavation and
                # reinforcement layout are shown before the numerical results.
                self._report_plot_grid_page(pdf, "Problem definition - geometry and reinforcement", [
                    ("Geometry / soil configuration", getattr(self, 'fig_geom', None)),
                    ("Reinforcement layout", getattr(self, 'fig_reinf', None)),
                ])

                # Compact input and results tables.
                geometry_rows = [
                    ["H_L excavation side (m)", m.geometry.H_L], ["H_R total depth (m)", m.geometry.H_R],
                    ["left ground β_L (deg)", m.left.beta_deg], ["right ground β_R (deg)", m.right.beta_deg],
                    ["left surcharge q_L (kPa)", m.left.q], ["right surcharge q_R (kPa)", m.right.q],
                    ["left water depth z_w,L (m)", m.left.z_w], ["right water depth z_w,R (m)", m.right.z_w],
                    ["γ_w (kN/m³)", m.gamma_w], ["k_h", m.seismic.k_h], ["k_v", m.seismic.k_v],
                    ["wall stiffness type", m.wall.stiffness_type], ["EI used (kPa·m⁴)", m.wall.effective_EI()],
                ]
                numerical_rows = [
                    ["n profile points", m.controls.n_points], ["max iterations", m.controls.max_iterations],
                    ["tolerance", m.controls.tolerance], ["integration method", m.controls.integration_method],
                ]
                layer_rows = []
                for side, layers in (("Left / excavation", m.left_layers), ("Right / retained", m.right_layers)):
                    for lay in layers:
                        layer_rows.append([side, lay.code, getattr(lay, "thickness", getattr(lay, "h", "")), lay.c_prime, lay.phi_prime_deg, lay.gamma, lay.gamma_sat, lay.E_s, lay.nu])
                reinf_rows = []
                for rr in list(getattr(m, 'reinforcement_supports', []) or []):
                    reinf_rows.append([rr.get('code',''), rr.get('type',''), rr.get('z',''), rr.get('theta_deg',''), rr.get('k',''), rr.get('prestress',''), rr.get('cap',''), rr.get('spacing','')])
                self._report_multi_table_page(pdf, "Input data", [
                    ("Geometry, loading, water and stiffness", ["Quantity", "Value"], geometry_rows, [0.38, 0.62]),
                    ("Numerical controls", ["Quantity", "Value"], numerical_rows, [0.38, 0.62]),
                ], landscape=False)
                self._report_multi_table_page(pdf, "Soil and reinforcement input", [
                    ("Soil layers", ["side", "code", "h (m)", "c′ (kPa)", "φ′ (°)", "γ (kN/m³)", "γsat (kN/m³)", "E (kPa)", "ν (-)"], layer_rows, None),
                    ("Reinforcement/supports", ["code", "type", "z (m)", "θ (°)", "k (kN/m/m)", "prestress (kN)", "cap (kN)", "spacing (m)"], reinf_rows or [["none", "", "", "", "", "", "", ""]], None),
                ], landscape=True)

                scalar_keys = ["solver", "iterations", "converged", "max_deflection_abs_m", "max_iteration_change_m", "max_net_pressure_change_kPa", "max_support_force_abs_kN_per_m", "fixed-base boundary conditions"]
                scalar_rows = [[k, s.get(k, "")] for k in scalar_keys if k in s]
                self._report_multi_table_page(pdf, "Solver results", [
                    ("Governing values", ["Quantity", "Value"], scalar_rows, [0.38, 0.62]),
                ], landscape=False)
                support_rows = self._support_result_rows(r, m)
                if support_rows:
                    report_support_rows = [[
                        row.get("code", ""), row.get("type", ""),
                        self._report_value(row.get("z", "")),
                        self._report_value(row.get("theta_deg", "")),
                        self._report_value(1000.0 * float(row.get("w", 0.0))),
                        self._report_value(row.get("Fh", "")),
                        self._report_value(row.get("axial", "")),
                        self._report_value(row.get("cap", "")),
                        self._report_value(row.get("util", "")),
                        row.get("status", ""),
                    ] for row in support_rows]
                    self._report_table_page(
                        pdf,
                        "Reinforcement / support results",
                        ["ID", "Type", "z (m)", "Angle (deg)", "Δx (mm)", "Fh (kN/m)", "Axial (kN/m)", "Capacity", "Utilization", "Status"],
                        report_support_rows,
                        note="Support forces are final converged nodal reactions. Fh is the horizontal component acting on the wall per metre run; axial force is recovered along the support axis using the support angle.",
                        landscape=True,
                        max_rows=16,
                    )

                # GUI plots, two per page.
                self._report_plot_grid_page(pdf, "Engineering plots - as displayed in the GUI", [
                    ("Total pressure", getattr(self, 'fig_pressure', None)),
                    ("Deflection", getattr(self, 'fig_deflection', None)),
                    ("Net pressure", getattr(self, 'fig_net', None)),
                    ("Rotation", getattr(self, 'fig_rotation', None)),
                    ("Shear", getattr(self, 'fig_shear', None)),
                    ("Moment", getattr(self, 'fig_moment', None)),
                    ("K diagram", getattr(self, 'fig_k', None)),
                    ("Δx / Δxmax", getattr(self, 'fig_mobilization', None)),
                    ("Convergence - change", getattr(self, 'fig_conv_change', None)),
                    ("Convergence - |Δx|", getattr(self, 'fig_conv_defl', None)),
                ])

                # Compact appendix samples only; full raw debug dump remains in GUI/results tables.
                pressure_rows = list(s.get("final_pressure_table", []) or [])
                if pressure_rows:
                    sample = pressure_rows[:12] + ([{"z_m":"...", "w_mm":"...", "p_left":"...", "p_right":"...", "q_net":"...", "K_left":"...", "K_right":"...", "state_hint":"..."}] if len(pressure_rows) > 24 else []) + pressure_rows[-12:]
                    cols = ["z_m", "w_mm", "p_left", "p_right", "q_net", "K_left", "K_right", "state_hint"]
                    self._report_table_page(pdf, "Appendix - CUT engine audit sample", cols, [[row.get(c, '') for c in cols] for row in sample], note="Compact sample only. Full diagnostic data remain available in the GUI results tables.", landscape=True, max_rows=28)
                conv_rows = []
                for rec in list(getattr(r, 'convergence_history', []) or []):
                    conv_rows.append([rec.get('iteration',''), rec.get('max_change_m',''), rec.get('max_abs_deflection_m',''), rec.get('max_net_pressure_change_kPa',''), rec.get('max_support_force_change_kN_per_m',''), rec.get('max_support_force_abs_kN_per_m','')])
                if conv_rows:
                    self._report_table_page(pdf, "Appendix - convergence history", ["iter", "max Δw (m)", "max |w| (m)", "max Δq (kPa)", "max ΔFsup", "max |Fsup|"], conv_rows, landscape=True, max_rows=28)
            self.run_status.set(f"Report exported: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Report", f"Could not export report:\n{exc}")

    def _file_report_placeholder(self):
        self.export_report_pdf()

    def _build_vars(self):
        self.var_beta_L = tk.DoubleVar(value=0.0)
        self.var_beta_R = tk.DoubleVar(value=0.0)
        self.var_q_L = tk.DoubleVar(value=0.0)
        self.var_q_R = tk.DoubleVar(value=0.0)
        self.var_z_w_L = tk.DoubleVar(value=20.0)
        self.var_z_w_R = tk.DoubleVar(value=20.0)
        self.var_gamma_w = tk.DoubleVar(value=9.81)
        self.var_k_h = tk.DoubleVar(value=0.0)
        self.var_k_v = tk.DoubleVar(value=0.0)
        self.var_k_v_arrow = tk.StringVar(value="↑  k_v")
        self.var_dx_trans = tk.DoubleVar(value=0.0)
        self.var_theta_rot = tk.DoubleVar(value=0.0)
        self.var_z_pivot = tk.DoubleVar(value=4.0)
        self.var_stiffness_type = tk.StringVar(value="EI")
        self.var_EI = tk.StringVar(value="1500000")
        self.var_E = tk.StringVar(value="1000000")
        self.var_I_or_t = tk.StringVar(value="1.5")
        self.var_H_L_display = tk.StringVar(value="")
        self.var_H_R_display = tk.StringVar(value="")
        self.var_z_ex_display = tk.StringVar(value="")
        self.var_stage_count = tk.IntVar(value=1)
        self.var_stage_intermediate_count = tk.IntVar(value=0)
        self.var_stage_anim_frame = tk.IntVar(value=1)
        self.var_stage_anim_speed_ms = tk.IntVar(value=650)
        self.var_stage_anim_quantity = tk.StringVar(value="Total horizontal pressure")
        self.var_stage_anim_x_min = tk.DoubleVar(value=-1.0)
        self.var_stage_anim_x_max = tk.DoubleVar(value=1.0)
        self.var_stage_q_L_apply = tk.StringVar(value="Stage N+1 (after final)")
        self.var_stage_q_R_apply = tk.StringVar(value="Stage 0")
        self.var_pvf_solver = tk.StringVar(value="Fixed base differential")
        self.var_pvf_tol_mm = tk.DoubleVar(value=5.0)
        self.var_pvf_result = tk.StringVar(value="z_PVF: —")
        self.var_pvf_status = tk.StringVar(value="Define below-fixed-point layers, then run PVF search.")
        self.var_dz = tk.DoubleVar(value=0.05)
        self.var_n_points = tk.IntVar(value=401)
        self.var_N = tk.IntVar(value=100)
        self.var_tol = tk.DoubleVar(value=1.0e-8)
        self.var_equilibrium_force_tol = tk.DoubleVar(value=0.05)
        self.var_equilibrium_moment_tol = tk.DoubleVar(value=0.05)
        self.var_work_band_tol = tk.DoubleVar(value=0.05)
        self.var_general_case_bending_schemes = tk.IntVar(value=10)
        self.var_general_case_theta_refine_passes = tk.IntVar(value=5)
        self.var_general_case_theta_points = tk.IntVar(value=41)
        self.var_general_case_zp_points = tk.IntVar(value=17)
        self.var_general_case_pivot_margin_frac = tk.DoubleVar(value=0.02)
        self.var_general_case_parallel = tk.BooleanVar(value=True)
        self.var_general_case_max_workers = tk.IntVar(value=0)
        self.var_solver_display = tk.StringVar(value="Flexible wall - Fixed base (closed-form bending)")
        self.var_integration_method = tk.StringVar(value="Gauss")
        self.var_no_bending_mode = tk.StringVar(value="Auto (ΣF=0 & ΣM=0)")
        self.var_rigid_optimization_solver = tk.StringVar(value="Fast equilibrium only")
        self.var_work_theta_min = tk.DoubleVar(value=0.0)
        self.var_work_theta_max = tk.DoubleVar(value=5.0)
        self.var_work_theta_count = tk.IntVar(value=6)
        self.var_work_dx_count = tk.IntVar(value=25)
        self.var_work_zp_count = tk.IntVar(value=25)
        self.var_work_status = tk.StringVar(value="Run diagnostic heatmaps after setting inputs.")
        self._last_work_best_equilibrium = None
        self._last_work_min_work = None
        self.var_query_z = tk.DoubleVar(value=2.0)
        self.var_height_status = tk.StringVar(value="")
        self.run_status = tk.StringVar(value="Ready. Select a solver and run.")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.timer_var = tk.StringVar(value="Elapsed: 00:00:00")
        self.eta_var = tk.StringVar(value="")
        self.progress_text_var = tk.StringVar(value="Progress: idle")
        self.last_result = None
        self.last_model = None
        self.water_animation_items = []
        self.var_water_anim_quantity = tk.StringVar(value="Total horizontal pressure")
        self.var_water_anim_mode = tk.StringVar(value="Uniform rise")
        self.var_water_anim_steps = tk.IntVar(value=15)
        self.var_water_anim_z_final_left = tk.DoubleVar(value=0.0)
        self.var_water_anim_z_final_right = tk.DoubleVar(value=0.0)
        self.var_water_anim_speed_ms = tk.IntVar(value=650)
        self.var_water_anim_x_min = tk.DoubleVar(value=-1.0)
        self.var_water_anim_x_max = tk.DoubleVar(value=1.0)
        self.var_water_anim_frame = tk.IntVar(value=1)
        self.water_anim_support_selected = {}
        self._water_anim_after_id = None
        for var in (self.var_beta_L, self.var_beta_R, self.var_z_w_L, self.var_z_w_R, self.var_z_pivot, self.var_q_L, self.var_q_R):
            var.trace_add("write", lambda *_: self._draw_geometry_safe())
        self._kh_clamping = False
        self.var_k_h.trace_add("write", lambda *_: self._clamp_k_h_nonnegative())
        self.var_k_v.trace_add("write", lambda *_: self._update_k_v_arrow())
        self.var_solver_display.trace_add("write", lambda *_: self._on_solver_display_changed())

    def _configure_professional_style(self):
        """Apply a consistent, publication-grade visual language to the GUI.

        Tk themes vary substantially between systems.  The settings below are
        intentionally conservative: they improve spacing, headings and table
        readability without depending on a third-party theme package.
        """
        try:
            self.configure(bg=UI_BG)
            style = ttk.Style(self)
            try:
                style.theme_use("clam")
            except Exception:
                pass
            default_font = ("Segoe UI", 9)
            heading_font = ("Segoe UI Semibold", 9)
            title_font = ("Segoe UI Semibold", 10)
            style.configure(".", font=default_font, background=UI_BG, foreground=TEXT_DARK)
            style.configure("App.TFrame", background=UI_BG)
            style.configure("TFrame", background=UI_BG)
            style.configure("TLabelframe", background=UI_BG, bordercolor=BORDER, relief="solid")
            style.configure("TLabelframe.Label", font=title_font, foreground=ACCENT_DARK, background=UI_BG)
            style.configure("TLabel", background=UI_BG, foreground=TEXT_DARK)
            style.configure("Muted.TLabel", background=UI_BG, foreground=TEXT_MUTED)
            style.configure("Status.TLabel", background=UI_BG, foreground=ACCENT_DARK, font=("Segoe UI Semibold", 9))
            style.configure("TNotebook", background=UI_BG, borderwidth=0)
            style.configure(
                "TNotebook.Tab",
                padding=(10, 7),
                font=heading_font,
                background="#d7dee8",
                foreground="#4b5563",
                borderwidth=1,
                relief="flat",
            )
            style.map(
                "TNotebook.Tab",
                background=[
                    ("selected", "#ffffff"),
                    ("active", "#edf4ff"),
                ],
                foreground=[
                    ("selected", "#0f172a"),
                    ("active", ACCENT_DARK),
                ],
                bordercolor=[
                    ("selected", "#0ea5e9"),
                    ("active", "#93c5fd"),
                ],
                lightcolor=[("selected", "#0ea5e9")],
                darkcolor=[("selected", "#0284c7")],
                expand=[("selected", (5, 5, 5, 0))],
            )
            style.configure("TButton", padding=(10, 5), font=heading_font)
            style.configure("Run.TButton", background="#d8f3dc", foreground="#0f5132")
            style.configure("Pause.TButton", background="#fff3cd", foreground="#664d03")
            style.configure("Stop.TButton", background="#f8d7da", foreground="#842029")
            style.configure("Treeview", rowheight=25, background=PANEL_BG, fieldbackground=PANEL_BG, foreground=TEXT_DARK, bordercolor=BORDER)
            style.configure("Treeview.Heading", font=heading_font, background=HEADER_BG, foreground=TEXT_DARK, relief="flat")
            style.map("Treeview", background=[("selected", SELECT_BG)], foreground=[("selected", TEXT_DARK)])
            style.configure("Candidate.Treeview", rowheight=26, background=PANEL_BG, fieldbackground=PANEL_BG)
            style.configure("Candidate.Treeview.Heading", font=heading_font, background=HEADER_BG)
            style.configure("Horizontal.TProgressbar", troughcolor="#e5e7eb", background=ACCENT)
        except Exception:
            pass

    def _make_tab_image(self, filename: str):
        """Load a full-colour tab header image."""
        try:
            path = resource_path(os.path.join("assets", "tabs", filename))
            return tk.PhotoImage(file=path)
        except Exception:
            img = tk.PhotoImage(width=20, height=20)
            img.put("#2563eb", to=(0, 0, 20, 20))
            return img


    def _load_engineering_icons(self):
        """Load custom engineering schematic icons for solver and reinforcement cards."""
        self._eng_icons = {}
        icons_dir = resource_path(os.path.join("assets", "icons"))
        for key in (
            "fixed_closed", "fixed_diff", "base_spring", "rigid", "general",
            "none", "anchor", "prop", "geogrid", "strip", "metalgrid",
        ):
            path = os.path.join(icons_dir, f"{key}.png")
            try:
                self._eng_icons[key] = tk.PhotoImage(file=path)
            except Exception:
                self._eng_icons[key] = None

    def _make_icon_button(self, parent, icon_key, title, subtitle, command, bg="#ffffff", fg="#172033", width=None, height=None):
        """Image-sized clickable engineering button with raised/active/selected states."""
        img = getattr(self, "_eng_icons", {}).get(icon_key)
        if img is None:
            img = tk.PhotoImage(width=96, height=96)
            img.put("#ffffff", to=(0, 0, 96, 96))
            img.put("#111827", to=(12, 12, 84, 84))
        btn = tk.Button(
            parent,
            image=img,
            command=command,
            cursor="hand2",
            relief="raised",
            bd=2,
            highlightthickness=2,
            highlightbackground="#c8d2df",
            highlightcolor="#c8d2df",
            activebackground="#eef6ff",
            bg="#ffffff",
            padx=0,
            pady=0,
            takefocus=True,
        )
        btn.image = img
        btn._normal_bg = "#ffffff"
        btn._hover_bg = bg or "#eef6ff"
        btn._selected_bg = bg or "#d7e9fb"
        btn._normal_border = "#c8d2df"
        btn._hover_border = fg or "#1f5f99"
        btn._selected_border = fg or "#1f5f99"
        btn._selected = False
        # Keep the clickable surface equal to the schematic image itself.
        try:
            btn.configure(width=img.width(), height=img.height())
        except Exception:
            pass
        def _enter(event=None):
            if not getattr(btn, "_selected", False):
                btn.configure(relief="raised", bd=3, bg=btn._hover_bg, activebackground=btn._hover_bg,
                              highlightbackground=btn._hover_border, highlightcolor=btn._hover_border)
        def _leave(event=None):
            if not getattr(btn, "_selected", False):
                btn.configure(relief="raised", bd=2, bg=btn._normal_bg, activebackground="#eef6ff",
                              highlightbackground=btn._normal_border, highlightcolor=btn._normal_border)
        def _press(event=None):
            btn.configure(relief="sunken")
        def _release(event=None):
            btn.configure(relief="sunken" if getattr(btn, "_selected", False) else "raised")
        btn.bind("<Enter>", _enter)
        btn.bind("<Leave>", _leave)
        btn.bind("<ButtonPress-1>", _press)
        btn.bind("<ButtonRelease-1>", _release)
        return btn

    def _set_icon_button_selected(self, btn, selected: bool):
        """Apply a persistent selected colour to a schematic button."""
        try:
            btn._selected = bool(selected)
            if selected:
                btn.configure(
                    relief="sunken",
                    bd=7,
                    bg=btn._selected_bg,
                    activebackground=btn._selected_bg,
                    highlightthickness=6,
                    highlightbackground=btn._selected_border,
                    highlightcolor=btn._selected_border,
                )
            else:
                btn.configure(
                    relief="raised",
                    bd=2,
                    bg=btn._normal_bg,
                    activebackground="#eef6ff",
                    highlightthickness=2,
                    highlightbackground=btn._normal_border,
                    highlightcolor=btn._normal_border,
                )
        except Exception:
            pass

    _REINFORCEMENT_REQUIRED_SOLVER = "Flexible wall - Fixed base (differential equation)"
    _REINFORCEMENT_ALLOWED_SOLVERS = {
        "Flexible wall - Fixed base (differential equation)",
        "Flexible wall - Base spring (differential equation)",
    }

    def _reinforcement_is_active(self) -> bool:
        """True when the selected reinforcement system requires the nonlinear nodal support solver."""
        try:
            return self.var_reinf_type.get().strip() != "No reinforcement"
        except Exception:
            return False

    def _reinforcement_solver_lock_message(self) -> str:
        return "Reinforcement active → differential fixed-base or base-spring solver required."

    def _on_solver_display_changed(self):
        self._enforce_reinforcement_solver_requirement(show_status=False)
        self._update_solver_visibility()
        self._refresh_solver_button_selection()

    def _enforce_reinforcement_solver_requirement(self, show_status=True):
        """Keep reinforcement on differential solvers that support nonlinear nodal supports."""
        if not self._reinforcement_is_active():
            self._refresh_solver_button_selection()
            return False
        required = self._REINFORCEMENT_REQUIRED_SOLVER
        allowed = getattr(self, "_REINFORCEMENT_ALLOWED_SOLVERS", {required})
        try:
            if self.var_solver_display.get() not in allowed:
                self.var_solver_display.set(required)
                if show_status and hasattr(self, "run_status"):
                    self.run_status.set(self._reinforcement_solver_lock_message())
                return True
        except Exception:
            pass
        if show_status and hasattr(self, "run_status"):
            self.run_status.set(self._reinforcement_solver_lock_message())
        self._refresh_solver_button_selection()
        return False

    def _set_icon_button_disabled(self, btn, disabled: bool):
        """Grey-out an incompatible solver card while keeping the selected card vivid."""
        try:
            btn._disabled_by_reinforcement = bool(disabled)
            if disabled:
                btn.configure(
                    state="disabled",
                    cursor="arrow",
                    relief="flat",
                    bd=1,
                    bg="#e5e7eb",
                    activebackground="#e5e7eb",
                    highlightthickness=2,
                    highlightbackground="#cbd5e1",
                    highlightcolor="#cbd5e1",
                )
            else:
                btn.configure(state="normal", cursor="hand2")
        except Exception:
            pass

    def _refresh_reinforcement_button_selection(self):
        selected = getattr(self, "var_reinf_type", tk.StringVar(value="")).get()
        for value, btn in getattr(self, "reinf_icon_buttons", {}).items():
            self._set_icon_button_selected(btn, value == selected)

    def _refresh_solver_button_selection(self):
        selected = getattr(self, "var_solver_display", tk.StringVar(value="")).get()
        required = getattr(self, "_REINFORCEMENT_REQUIRED_SOLVER", "Flexible wall - Fixed base (differential equation)")
        allowed = getattr(self, "_REINFORCEMENT_ALLOWED_SOLVERS", {required})
        locked = self._reinforcement_is_active() if hasattr(self, "var_reinf_type") else False
        for value, btn in getattr(self, "solver_icon_buttons", {}).items():
            incompatible = bool(locked and value not in allowed)
            self._set_icon_button_disabled(btn, incompatible)
            if not incompatible:
                self._set_icon_button_selected(btn, value == selected)
        try:
            if hasattr(self, "solver_lock_note_var"):
                self.solver_lock_note_var.set(self._reinforcement_solver_lock_message() if locked else "")
        except Exception:
            pass

    def _open_home(self):
        webbrowser.open("https://cut-apps.streamlit.app/")

    def _section_label(self, parent, text: str, row: int, column: int = 0, columnspan: int = 1):
        lbl = ttk.Label(parent, text=text, style="Status.TLabel")
        lbl.grid(row=row, column=column, columnspan=columnspan, sticky="w", padx=4, pady=(8, 3))
        return lbl

    def _build_ui(self):
        self._configure_professional_style()
        self._load_engineering_icons()
        root = ttk.Frame(self, padding=8, style="App.TFrame")
        root.pack(fill="both", expand=True)
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        self.nb = ttk.Notebook(root)
        self.nb.grid(row=0, column=0, sticky="nsew")
        self._tab_icons = {
            "model": self._make_tab_image("tab_model_inputs.png"),
            "reinforcement": self._make_tab_image("tab_stages_reinforcement.png"),
            "run": self._make_tab_image("tab_run.png"),
            "results": self._make_tab_image("tab_results.png"),
            "plots": self._make_tab_image("tab_plots.png"),
            "query": self._make_tab_image("tab_query.png"),
            "advanced": self._make_tab_image("tab_advanced.png"),
            # animation tabs have their own purple category
            "water": self._make_tab_image("tab_water_animation.png"),
            "stages_anim": self._make_tab_image("tab_stages_animation.png"),
            "pvf": self._make_tab_image("tab_pvf.png"),
        }
        self.tab_input = ttk.Frame(self.nb)
        self.tab_reinforcement = ttk.Frame(self.nb)
        self.tab_run = ttk.Frame(self.nb)
        self.tab_validation = ttk.Frame(self.nb)  # internal only; not added as a top-level tab
        self.tab_summary = ttk.Frame(self.nb)
        self.tab_charts = ttk.Frame(self.nb)
        self.tab_query = ttk.Frame(self.nb)
        self.tab_work = ttk.Frame(self.nb)
        self.tab_pvf = ttk.Frame(self.nb)
        self.tab_water_animation = ttk.Frame(self.nb)
        self.tab_stages_animation = ttk.Frame(self.nb)
        self.nb.add(self.tab_input, text="", image=self._tab_icons["model"], compound="center")
        self.nb.add(self.tab_reinforcement, text="", image=self._tab_icons["reinforcement"], compound="center")
        self.nb.add(self.tab_run, text="", image=self._tab_icons["run"], compound="center")
        self.nb.add(self.tab_summary, text="", image=self._tab_icons["results"], compound="center")
        self.nb.add(self.tab_charts, text="", image=self._tab_icons["plots"], compound="center")
        self.nb.add(self.tab_query, text="", image=self._tab_icons["query"], compound="center")
        self.nb.add(self.tab_work, text="", image=self._tab_icons["advanced"], compound="center")
        # PVF tab is intentionally hidden temporarily in v7.4.
        # self.nb.add(self.tab_pvf, text="", image=self._tab_icons["pvf"], compound="center")
        # Animation tabs are grouped at the end.
        self.nb.add(self.tab_water_animation, text="", image=self._tab_icons["water"], compound="center")
        self.nb.add(self.tab_stages_animation, text="", image=self._tab_icons["stages_anim"], compound="center")
        self._build_input_tab()
        self._build_reinforcement_tab()
        self._build_run_tab()
        self._build_main_results_tab()
        self._build_query_tab()
        self._build_work_heatmaps_tab()
        self._build_pvf_tab()
        self._build_water_animation_tab()
        self._build_stages_animation_tab()
        attach_context_help(self)

    def _entry(self, parent, row, col, label, var, width=12):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=4, pady=3)
        ent = ttk.Entry(parent, textvariable=var, width=width)
        ent.grid(row=row, column=col + 1, sticky="ew", padx=4, pady=3)
        return ent

    def _readonly(self, parent, row, col, label, textvariable, width=12):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=4, pady=3)
        lab = ttk.Label(parent, textvariable=textvariable, relief="sunken", anchor="e", width=width)
        lab.grid(row=row, column=col + 1, sticky="ew", padx=4, pady=3)
        return lab

    def _clamp_k_h_nonnegative(self):
        if getattr(self, "_kh_clamping", False):
            return
        try:
            if float(self.var_k_h.get()) < 0.0:
                self._kh_clamping = True
                self.var_k_h.set(0.0)
        except Exception:
            pass
        finally:
            self._kh_clamping = False

    def _update_k_v_arrow(self):
        try:
            kv = float(self.var_k_v.get())
        except Exception:
            kv = 0.0
        if kv < 0.0:
            self.var_k_v_arrow.set("↓  k_v")
        elif kv > 0.0:
            self.var_k_v_arrow.set("↑  k_v")
        else:
            self.var_k_v_arrow.set("↕  k_v")

    def _build_input_tab(self):
        self.tab_input.columnconfigure(1, weight=1)
        self.tab_input.rowconfigure(0, weight=1)
        left = ScrollableFrame(self.tab_input, width=560)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        panel = left.inner

        home_bar = ttk.Frame(panel)
        home_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        home_bar.columnconfigure(1, weight=1)
        try:
            home_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "home.png")
            self.home_img = tk.PhotoImage(file=home_path).subsample(10, 10)
            ttk.Button(home_bar, image=self.home_img, command=self._open_home).grid(row=0, column=0, sticky="w", padx=2, pady=2)
        except Exception:
            ttk.Button(home_bar, text="CUT Apps Home", command=self._open_home).grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Label(home_bar, text="https://cut-apps.streamlit.app/", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=8)

        data = ttk.LabelFrame(panel, text="Input data")
        data.grid(row=1, column=0, sticky="ew", pady=4)
        data.columnconfigure(0, weight=0)
        data.columnconfigure(1, weight=1)
        data.columnconfigure(2, weight=1)
        ttk.Label(data, text="Magnitude", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=3)
        ttk.Label(data, text="Left side", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w", padx=5, pady=3)
        ttk.Label(data, text="Right side", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="w", padx=5, pady=3)

        ttk.Label(data, text="H (m)").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        ttk.Label(data, textvariable=self.var_H_L_display, relief="sunken", anchor="w", width=12).grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        ttk.Label(data, textvariable=self.var_H_R_display, relief="sunken", anchor="w", width=12).grid(row=1, column=2, sticky="ew", padx=5, pady=3)
        ttk.Label(data, text="z_ex=H_R-H_L (m)").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        ttk.Label(data, textvariable=self.var_z_ex_display, relief="sunken", anchor="w", width=12).grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=3)

        ttk.Label(data, text="β (deg)").grid(row=3, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(data, textvariable=self.var_beta_L, width=12).grid(row=3, column=1, sticky="ew", padx=5, pady=3)
        ttk.Entry(data, textvariable=self.var_beta_R, width=12).grid(row=3, column=2, sticky="ew", padx=5, pady=3)

        ttk.Label(data, text="q (kPa)").grid(row=4, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(data, textvariable=self.var_q_L, width=12).grid(row=4, column=1, sticky="ew", padx=5, pady=3)
        ttk.Entry(data, textvariable=self.var_q_R, width=12).grid(row=4, column=2, sticky="ew", padx=5, pady=3)

        ttk.Label(data, text="z_w (m)").grid(row=5, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(data, textvariable=self.var_z_w_L, width=12).grid(row=5, column=1, sticky="ew", padx=5, pady=3)
        ttk.Entry(data, textvariable=self.var_z_w_R, width=12).grid(row=5, column=2, sticky="ew", padx=5, pady=3)
        
        seis = ttk.LabelFrame(panel, text="Seismic and water")
        seis.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Label(seis, text="k_h (-)").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(seis, textvariable=self.var_k_h, width=10).grid(row=0, column=1, sticky="ew", padx=(4, 2), pady=3)
        ttk.Label(seis, text="←  k_h", foreground="blue", font=("Segoe UI", 11, "bold")).grid(row=0, column=2, sticky="w", padx=(6, 14), pady=3)
        ttk.Label(seis, text="k_v (-)").grid(row=0, column=3, sticky="w", padx=4, pady=3)
        ttk.Entry(seis, textvariable=self.var_k_v, width=10).grid(row=0, column=4, sticky="ew", padx=(4, 2), pady=3)
        ttk.Label(seis, textvariable=self.var_k_v_arrow, foreground="red", font=("Segoe UI", 11, "bold")).grid(row=0, column=5, sticky="w", padx=(6, 14), pady=3)
        ttk.Label(seis, text="γ_w (kN/m³)").grid(row=0, column=6, sticky="w", padx=4, pady=3)
        ttk.Entry(seis, textvariable=self.var_gamma_w, width=10).grid(row=0, column=7, sticky="ew", padx=4, pady=3)

        wall = ttk.LabelFrame(panel, text="Wall stiffness")
        wall.grid(row=3, column=0, sticky="ew", pady=4)
        ttk.Label(wall, text="Stiffness type").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.OptionMenu(
            wall,
            self.var_stiffness_type,
            self.var_stiffness_type.get(),
            "EI", "E & I", "E & t",
            command=lambda *_: self._update_wall_stiffness_fields(),
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        self.wall_EI_label = ttk.Label(wall, text="EI (kPa·m⁴)")
        self.wall_EI_entry = ttk.Entry(wall, textvariable=self.var_EI, width=12)
        self.wall_E_label = ttk.Label(wall, text="E (kPa)")
        self.wall_E_entry = ttk.Entry(wall, textvariable=self.var_E, width=12)
        self.wall_I_label = ttk.Label(wall, text="I (m⁴) or t (m)")
        self.wall_I_entry = ttk.Entry(wall, textvariable=self.var_I_or_t, width=12)
        self._update_wall_stiffness_fields()

        soils = ttk.LabelFrame(panel, text="Soil layers")
        soils.grid(row=5, column=0, sticky="nsew", pady=4)
        soils.columnconfigure(0, weight=1)
        ttk.Label(soils, text="Left / excavation side", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        self.left_layers_table = EditableLayerTable(soils, "SL", 6.0, on_change=self._layers_changed)
        self.left_layers_table.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))
        ttk.Label(soils, text="Right / retained side", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", padx=4, pady=(4, 2))
        self.right_layers_table = EditableLayerTable(soils, "SR", 10.0, on_change=self._layers_changed)
        self.right_layers_table.grid(row=3, column=0, sticky="nsew", padx=4, pady=(0, 4))

        right = ttk.Frame(self.tab_input)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.fig_geom = Figure(figsize=(8, 7), dpi=100)
        self.ax_geom = self.fig_geom.add_subplot(111)
        self.canvas_geom = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_geom, master=right))
        self.canvas_geom.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._layers_changed()


    def _update_wall_stiffness_fields(self):
        widgets = (
            self.wall_EI_label, self.wall_EI_entry,
            self.wall_E_label, self.wall_E_entry,
            self.wall_I_label, self.wall_I_entry,
        )
        for w in widgets:
            try:
                w.grid_remove()
            except Exception:
                pass
        st = self.var_stiffness_type.get()
        if st == "EI":
            self.wall_EI_label.grid(row=0, column=2, sticky="w", padx=4, pady=3)
            self.wall_EI_entry.grid(row=0, column=3, sticky="ew", padx=4, pady=3)
        elif st == "E & I":
            self.wall_E_label.grid(row=0, column=2, sticky="w", padx=4, pady=3)
            self.wall_E_entry.grid(row=0, column=3, sticky="ew", padx=4, pady=3)
            self.wall_I_label.configure(text="I (m⁴)")
            self.wall_I_label.grid(row=0, column=4, sticky="w", padx=4, pady=3)
            self.wall_I_entry.grid(row=0, column=5, sticky="ew", padx=4, pady=3)
        elif st == "E & t":
            self.wall_E_label.grid(row=0, column=2, sticky="w", padx=4, pady=3)
            self.wall_E_entry.grid(row=0, column=3, sticky="ew", padx=4, pady=3)
            self.wall_I_label.configure(text="t (m)")
            self.wall_I_label.grid(row=0, column=4, sticky="w", padx=4, pady=3)
            self.wall_I_entry.grid(row=0, column=5, sticky="ew", padx=4, pady=3)

    def _build_reinforcement_tab(self):
        tab = self.tab_reinforcement
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        outer = ttk.Frame(tab, padding=8)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        top = ttk.Frame(outer)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(3, weight=1)
        ttk.Label(top, text="Stages and reinforcement", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="Type").grid(row=0, column=1, padx=(18, 4), sticky="e")
        self.reinforcement_options = [
            "No reinforcement",
            "Anchored embedded wall",
            "Propped embedded wall",
            "MSE walls, geogrid reinforced",
            "MSE walls, metal strip reinforced",
            "MSE walls, metal grid reinforced",
        ]
        self.var_reinf_type = tk.StringVar(value="No reinforcement")
        combo = ttk.Combobox(top, textvariable=self.var_reinf_type, values=self.reinforcement_options, state="readonly", width=38)
        combo.grid(row=0, column=2, sticky="w")
        combo.bind("<<ComboboxSelected>>", lambda *_: self._reinforcement_type_changed())
        ttk.Label(
            top,
            text="Anchors and MSE reinforcement are placed on the Right/retained side; props are placed on the Left/excavation side.",
            wraplength=1150,
            justify="left",
            foreground="#555",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew")

        # The left pane is scrollable so the enlarged icon panel and tables stay usable
        # on smaller displays.  The preview pane occupies the full remaining height.
        left_scroll = ScrollableFrame(body, width=560)
        left = left_scroll.inner
        right = ttk.LabelFrame(body, text="Reinforcement preview", padding=6)
        body.add(left_scroll, weight=3)
        body.add(right, weight=4)
        left.columnconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        stages_box = ttk.LabelFrame(left, text="Excavation stages", padding=6)
        stages_box.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        stages_box.columnconfigure(0, weight=1)
        stages_box.columnconfigure(3, weight=0)
        ttk.Label(
            stages_box,
            text="Define excavation stage elevations z below the retained-side ground surface.",
            wraplength=560, justify="left", foreground="#555",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        add_help(stages_box, 0, 3, "Stage 0 is the initial ground-surface/no-excavation state. Stage 1 is the first excavation line; Stage n is fixed at z_ex = H_R - H_L.")
        ttk.Label(stages_box, text="Number of main excavation stages n").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=3)
        self.stage_count_spin = ttk.Spinbox(stages_box, from_=1, to=50, textvariable=self.var_stage_count, width=8, command=self._stage_count_changed)
        self.stage_count_spin.grid(row=1, column=1, sticky="w", pady=3)
        ttk.Button(stages_box, text="Apply / regenerate", command=self._stage_count_changed).grid(row=1, column=2, sticky="w", padx=(6, 0), pady=3)
        add_help(stages_box, 1, 3, "Changes the number of main excavation stages and regenerates the stage table. The final row remains locked to z_ex.")
        ttk.Label(stages_box, text="Intermediate excavation drops between main stages").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=3)
        self.stage_intermediate_spin = ttk.Spinbox(stages_box, from_=0, to=50, textvariable=self.var_stage_intermediate_count, width=8, command=self._stage_intermediate_count_changed)
        self.stage_intermediate_spin.grid(row=2, column=1, sticky="w", pady=3)
        add_help(stages_box, 2, 2, "Example: 4 creates four lowering steps before Stage i with only supports 1..i-1 active until Stage i is reached.", padx=(6, 0), pady=3)

        load_box = ttk.LabelFrame(stages_box, text="Surcharge staging", padding=6)
        load_box.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(6, 4))
        for c in range(4):
            load_box.columnconfigure(c, weight=1)
        ql_label_frame = ttk.Frame(load_box)
        ql_label_frame.grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(ql_label_frame, text="Apply q_L from").pack(side="left")
        ql_help = ttk.Label(ql_label_frame, text="?", width=2, anchor="center", cursor="question_arrow")
        ql_help.pack(side="left", padx=(4, 0))
        ToolTip(ql_help, "Select the excavation stage from which the left-side surcharge q_L is active. Use Stage N+1 (after final) when q_L must not affect the staged excavation analysis.")
        self.stage_q_L_combo = ttk.Combobox(load_box, textvariable=self.var_stage_q_L_apply, values=["Stage N (final)", "Stage N+1 (after final)"], state="readonly", width=24)
        self.stage_q_L_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Label(load_box, text="Apply q_R from").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.stage_q_R_combo = ttk.Combobox(load_box, textvariable=self.var_stage_q_R_apply, values=["Stage 0", "Stage 1", "Stage N+1"], state="readonly", width=20)
        self.stage_q_R_combo.grid(row=0, column=3, sticky="ew", padx=4, pady=2)
        self.stage_q_L_combo.bind("<<ComboboxSelected>>", lambda *_: self._stage_inputs_changed())
        self.stage_q_R_combo.bind("<<ComboboxSelected>>", lambda *_: self._stage_inputs_changed())

        stage_cols = ("stage", "z", "note")
        self.stage_tree = ttk.Treeview(stages_box, columns=stage_cols, show="headings", height=5, selectmode="browse")
        for col, txt, wid in (("stage", "Stage", 80), ("z", "z (m)", 100), ("note", "Description", 300)):
            self.stage_tree.heading(col, text=txt)
            self.stage_tree.column(col, width=wid, anchor="center" if col != "note" else "w")
        self.stage_tree.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        add_help(stages_box, 5, 0, "All cells are editable except the final Stage n row, which is fixed at z_ex. Intermediate drops are generated automatically for the animation/analysis path.", sticky="w", padx=(0, 0), pady=(4, 0))
        self.stage_tree.bind("<Double-1>", self._stage_begin_edit_cell)
        self._set_stage_rows([])
        self._refresh_stage_load_options()

        # Icon-only reinforcement selector, in the same order as the reinforcement drop-down.
        reinf_cards = ttk.Frame(left)
        reinf_cards.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        for c in range(3):
            reinf_cards.columnconfigure(c, weight=1)
        reinf_specs = [
            ("none", "#f8fafc", "#475569", "No reinforcement"),
            ("anchor", "#eaf3ff", "#1d4ed8", "Anchored embedded wall"),
            ("prop", "#fff1f2", "#b91c1c", "Propped embedded wall"),
            ("geogrid", "#ecfdf3", "#15803d", "MSE walls, geogrid reinforced"),
            ("strip", "#fff7ed", "#a16207", "MSE walls, metal strip reinforced"),
            ("metalgrid", "#f1f5f9", "#334155", "MSE walls, metal grid reinforced"),
        ]
        self.reinf_icon_buttons = {}
        for i, spec in enumerate(reinf_specs):
            r, c = divmod(i, 3)
            key, bg, fg, value = spec
            btn = self._make_icon_button(
                reinf_cards,
                key,
                "",
                "",
                lambda v=value: (self.var_reinf_type.set(v), self._reinforcement_type_changed()),
                bg=bg,
                fg=fg,
                width=172,
                height=172,
            )
            btn.grid(row=r, column=c, sticky="n", padx=8, pady=8)
            self.reinf_icon_buttons[value] = btn

        self.reinf_table_frame = ttk.Frame(left)
        self.reinf_table_frame.grid(row=2, column=0, sticky="nsew", pady=(4, 0))
        self.reinf_table_frame.columnconfigure(0, weight=1)
        self.reinf_status = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.reinf_status, wraplength=760, justify="left").grid(row=3, column=0, sticky="w", pady=(8, 0))

        notation_box = ttk.LabelFrame(left, text="Notation for selected reinforcement", padding=6)
        notation_box.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        notation_box.columnconfigure(0, weight=1)
        self.reinf_notation_var = tk.StringVar(value="")
        ttk.Label(notation_box, textvariable=self.reinf_notation_var, wraplength=760, justify="left", foreground="#334155").grid(row=0, column=0, sticky="w")

        ttk.Label(right, text="", wraplength=720, justify="left", foreground="#555").grid(row=0, column=0, sticky="w")
        self.fig_reinf = Figure(figsize=(7.2, 7.2), dpi=100)
        self.ax_reinf = self.fig_reinf.add_subplot(111)
        self.canvas_reinf = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_reinf, master=right))
        self.canvas_reinf.get_tk_widget().grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.reinf_rows_by_type = {}
        self.reinf_tree = None
        self._support_elements = []
        self._reinforcement_type_changed()
        self._refresh_reinforcement_button_selection()

    def _final_excavation_z(self) -> float:
        try:
            return max(0.0, float(self._height_right()) - float(self._height_left()))
        except Exception:
            return 0.0


    def _refresh_stage_load_options(self):
        """Refresh surcharge-stage selectors for current number of stages."""
        try:
            n = max(1, int(self.var_stage_count.get()))
        except Exception:
            n = 1
        qR_values = [f"Stage {i}" for i in range(0, n + 1)] + [f"Stage {n+1} (after final)"]
        try:
            cur = str(self.var_stage_q_R_apply.get())
            self.stage_q_R_combo.configure(values=qR_values)
            if cur not in qR_values:
                # Preserve old generic N+1 wording if used in earlier files.
                if "N+1" in cur:
                    self.var_stage_q_R_apply.set(qR_values[-1])
                else:
                    self.var_stage_q_R_apply.set("Stage 0")
        except Exception:
            pass
        try:
            if self.var_stage_q_L_apply.get() not in ("Stage N (final)", "Stage N+1 (after final)"):
                self.var_stage_q_L_apply.set("Stage N+1 (after final)")
        except Exception:
            pass

    def _stage_load_index_from_text(self, text, n, default=0):
        """Map strings like Stage 0, Stage 3, Stage N+1 to a load-stage index."""
        import re
        txt = str(text or "").strip()
        if "N+1" in txt or "after final" in txt:
            return int(n) + 1
        if "N" in txt and "final" in txt:
            return int(n)
        m = re.search(r"(-?\d+)", txt)
        if m:
            return max(0, min(int(n) + 1, int(m.group(1))))
        return int(default)

    def _stage_surcharge_indices(self, n):
        qL_stage = n if str(self.var_stage_q_L_apply.get()).startswith("Stage N (final)") else n + 1
        qR_stage = self._stage_load_index_from_text(self.var_stage_q_R_apply.get(), n, default=0)
        return int(qL_stage), int(qR_stage)

    def _default_stage_rows(self):
        z_ex = self._final_excavation_z()
        try:
            n = max(1, int(self.var_stage_count.get()))
        except Exception:
            n = 1
            try:
                self.var_stage_count.set(1)
            except Exception:
                pass
        if n <= 1:
            return [("Stage 1", f"{z_ex:.6g}", "Final excavation")]
        return [(f"Stage {i}", f"{(z_ex * i / n):.6g}", "Final excavation" if i == n else "") for i in range(1, n + 1)]

    def _stage_rows_for_save(self):
        if not hasattr(self, "stage_tree") or self.stage_tree is None:
            return []
        return [list(self.stage_tree.item(item, "values")) for item in self.stage_tree.get_children()]

    def _stage_rows(self):
        rows = []
        if not hasattr(self, "stage_tree") or self.stage_tree is None:
            return rows
        for item in self.stage_tree.get_children():
            vals = list(self.stage_tree.item(item, "values"))
            while len(vals) < 3:
                vals.append("")
            try:
                z = float(vals[1])
            except Exception:
                continue
            rows.append({"stage": str(vals[0]), "z": z, "note": str(vals[2])})
        rows.sort(key=lambda r: r["z"])
        return rows

    def _set_stage_rows(self, rows, preserve_count=False):
        if not hasattr(self, "stage_tree") or self.stage_tree is None:
            return
        for item in self.stage_tree.get_children():
            self.stage_tree.delete(item)
        z_ex = self._final_excavation_z()
        clean = []
        for idx, row in enumerate(rows or []):
            vals = list(row) if not isinstance(row, dict) else [row.get("stage", f"Stage {idx+1}"), row.get("z", row.get("H_L", "")), row.get("note", "")]
            while len(vals) < 3:
                vals.append("")
            try:
                z = float(vals[1])
            except Exception:
                continue
            clean.append((z, str(vals[2])))
        if not clean:
            clean = [(float(r[1]), r[2]) for r in self._default_stage_rows()]
        clean.sort(key=lambda t: t[0])
        if preserve_count:
            try:
                n = max(1, int(self.var_stage_count.get()))
            except Exception:
                n = max(1, len(clean))
                self.var_stage_count.set(n)
        else:
            n = max(1, len(clean))
            try:
                self.var_stage_count.set(n)
            except Exception:
                pass
        if len(clean) != n:
            clean = [(float(r[1]), r[2]) for r in self._default_stage_rows()]
        # Stage n is always the final excavation z_ex. Intermediate stages must be above it.
        normalised = []
        for i in range(1, n + 1):
            if i == n:
                z = z_ex
                note = "Final excavation"
            elif i - 1 < len(clean):
                z = min(max(0.0, clean[i-1][0]), max(0.0, z_ex - 1.0e-9))
                note = clean[i-1][1]
            else:
                z = z_ex * i / n
                note = ""
            normalised.append((z, note))
        normalised.sort(key=lambda t: t[0])
        for i, (z, note) in enumerate(normalised, start=1):
            if i == n:
                z, note = z_ex, "Final excavation"
            self.stage_tree.insert("", "end", values=(f"Stage {i}", f"{z:.6g}", note))
        self._stage_inputs_changed()

    def _sync_stages_to_final_excavation(self):
        if not hasattr(self, "stage_tree") or self.stage_tree is None:
            return
        rows = self._stage_rows_for_save()
        self._set_stage_rows(rows, preserve_count=True)

    def _stage_count_changed(self):
        try:
            n = max(1, int(self.var_stage_count.get()))
        except Exception:
            n = 1
        self.var_stage_count.set(n)
        self._refresh_stage_load_options()
        self._set_stage_rows(self._default_stage_rows(), preserve_count=True)

    def _stage_intermediate_count_changed(self):
        try:
            m = max(0, int(self.var_stage_intermediate_count.get()))
        except Exception:
            m = 0
        self.var_stage_intermediate_count.set(m)
        self._stage_inputs_changed()
        if hasattr(self, "stage_animation_items"):
            self._refresh_stages_animation_items()
            self._draw_stages_animation_frame(max(0, int(self.var_stage_anim_frame.get()) - 1))

    def _stage_begin_edit_cell(self, event):
        tree = self.stage_tree
        if tree is None:
            return
        item = tree.identify_row(event.y)
        col_id = tree.identify_column(event.x)
        if not item or not col_id:
            return
        items = list(tree.get_children())
        if item == items[-1]:
            return  # Stage n is fixed at z_ex.
        col_index = int(col_id.replace("#", "")) - 1
        cols = ("stage", "z", "note")
        if col_index < 0 or col_index >= len(cols):
            return
        bbox = tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        vals = list(tree.item(item, "values"))
        while len(vals) < 3:
            vals.append("")
        old = vals[col_index]
        entry = ttk.Entry(tree)
        entry.insert(0, old)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        def commit(_event=None):
            new = entry.get().strip()
            if cols[col_index] == "z":
                try:
                    v = float(new)
                    z_ex = self._final_excavation_z()
                    if v < 0.0 or v >= z_ex:
                        raise ValueError
                    new = f"{v:.6g}"
                except Exception:
                    new = old
            vals[col_index] = new
            tree.item(item, values=vals)
            try:
                entry.destroy()
            except Exception:
                pass
            self._set_stage_rows(self._stage_rows_for_save(), preserve_count=True)
            self._stage_inputs_changed()
        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)

    def _stage_inputs_changed(self):
        self._draw_reinforcement_preview_safe()

    def _reinforcement_specs(self, rtype: str):
        if rtype == "No reinforcement":
            return []
        if rtype == "Anchored embedded wall":
            return [
                ("code", "code", 80), ("z", "z (m)", 75), ("angle", "θ (°)", 90),
                ("Lfree", "Lf (m)", 90), ("Lbond", "Lb (m)", 90), ("EA", "EA (kN)", 100),
                ("spacing", "s (m)", 85), ("prestress", "T0 (kN)", 110),
                ("Tpull", "Tpo (kN)", 110), ("Tsteel", "Ts (kN)", 105),
            ]
        if rtype == "Propped embedded wall":
            return [("code", "code", 80), ("z", "z (m)", 80), ("L", "L (m)", 90), ("EA", "EA (kN)", 115), ("spacing", "s (m)", 95), ("Rult", "Rult (kN)", 115)]
        if rtype == "MSE walls, geogrid reinforced":
            return [("code", "code", 80), ("z", "z (m)", 80), ("L", "L (m)", 90), ("EA", "J/EA (kN/m)", 125), ("Tult", "Tult (kN/m)", 125)]
        if rtype == "MSE walls, metal strip reinforced":
            return [("code", "code", 80), ("z", "z (m)", 80), ("L", "L (m)", 90), ("spacing", "s_h (m)", 95), ("EA", "EA strip (kN)", 125), ("Tult", "Tult strip (kN)", 130)]
        if rtype == "MSE walls, metal grid reinforced":
            return [("code", "code", 80), ("z", "z (m)", 80), ("L", "L (m)", 90), ("spacing", "s_h (m)", 95), ("EA", "EA grid (kN)", 125), ("Tult", "Tult grid (kN)", 130)]
        return []

    def _reinforcement_default_row(self, rtype: str, idx: int):
        # Default support/reinforcement levels: first at z=1.0 m, then every 0.5 m.
        z_default = 1.0 + 0.5 * max(0, int(idx) - 1)
        z_txt = f"{z_default:.1f}"
        if rtype == "Anchored embedded wall":
            return (f"A{idx}", z_txt, "-15.0", "6.0", "4.0", "200000", "2.0", "0.0", "500.0", "500.0")
        if rtype == "Propped embedded wall":
            return (f"P{idx}", z_txt, "4.0", "200000", "2.0", "500.0")
        if rtype == "MSE walls, geogrid reinforced":
            return (f"R{idx}", z_txt, "5.0", "1000.0", "50.0")
        if rtype in ("MSE walls, metal strip reinforced", "MSE walls, metal grid reinforced"):
            return (f"R{idx}", z_txt, "5.0", "1.0", "1000.0", "50.0")
        return ()

    def _reinforcement_notation_text(self, rtype: str) -> str:
        """Readable notation list shown in the lower part of the Reinforcement pane."""
        if rtype == "Anchored embedded wall":
            return (
                "• z: level below right ground surface (m)\n"
                "• θ: anchor angle; negative is downward into retained soil\n"
                "• Lf: free/deformable length (m)\n"
                "• Lb: bonded/fixed length (m)\n"
                "• EA: axial stiffness of one anchor (kN)\n"
                "• s: horizontal anchor spacing, required for conversion per metre wall\n"
                "• T0: prestress/lock-off load (kN)\n"
                "• Tpo, Ts: pull-out and steel capacities (kN)"
            )
        if rtype == "Propped embedded wall":
            return (
                "• z: prop level (m)\n"
                "• L: unsupported/deformable prop length (m), required; L=0 is not allowed\n"
                "• EA: axial stiffness of one prop/level (kN)\n"
                "• s: prop spacing, required for conversion per metre wall\n"
                "• equivalent stiffness per metre wall: k = EA/(L·s)\n"
                "• Rult: compression capacity (kN)\n"
                "• props are compression-only and act from the excavation side"
            )
        if rtype == "MSE walls, geogrid reinforced":
            return (
                "• z: geogrid layer level (m)\n"
                "• L: geogrid length behind the wall, drawn to scale\n"
                "• Sv: computed automatically from the z-levels; not entered manually\n"
                "• J/EA: tensile stiffness per metre wall width (kN/m); no horizontal spacing is required\n"
                "• Tult: tensile capacity per metre wall width (kN/m)"
            )
        if rtype == "MSE walls, metal strip reinforced":
            return (
                "• z: strip layer level (m)\n"
                "• L: strip length behind the wall, drawn to scale\n"
                "• Sv: computed automatically from the z-levels; not entered manually\n"
                "• s_h: horizontal strip spacing, required because strips are discrete\n"
                "• EA and Tult: stiffness/capacity of one strip; converted internally per metre wall"
            )
        if rtype == "MSE walls, metal grid reinforced":
            return (
                "• z: grid layer level (m)\n"
                "• L: grid length behind the wall, drawn to scale\n"
                "• Sv: computed automatically from the z-levels; not entered manually\n"
                "• s_h: transverse grid spacing; default 1.0 m if not changed\n"
                "• EA and Tult: stiffness/capacity per grid line; converted internally per metre wall"
            )
        return "• No reinforcement: no support parameters are active."

    def _migrate_reinforcement_row_for_type(self, rtype: str, vals):
        """Convert older saved MSE rows that contained manual Sv to the new Auto-Sv table layout."""
        vals = tuple(vals)
        try:
            if rtype == "Propped embedded wall" and len(vals) == 5:
                # old: code,z,EA,spacing,Rult -> new: code,z,L,EA,spacing,Rult
                return (vals[0], vals[1], "4.0", vals[2], vals[3], vals[4])
            if rtype == "MSE walls, geogrid reinforced" and len(vals) >= 6:
                # old: code,z,L,Sv,EA,Tult -> new: code,z,L,EA,Tult
                return (vals[0], vals[1], vals[2], vals[4], vals[5])
            if rtype in ("MSE walls, metal strip reinforced", "MSE walls, metal grid reinforced") and len(vals) >= 7:
                # old: code,z,L,Sv,s_h,EA,Tult -> new: code,z,L,s_h,EA,Tult
                return (vals[0], vals[1], vals[2], vals[4], vals[5], vals[6])
        except Exception:
            pass
        return vals

    def _auto_mse_vertical_spacings(self, rows):
        """Return Auto Sv values from reinforcement z-levels using tributary spacing."""
        indexed = []
        for idx, r in enumerate(rows):
            try:
                indexed.append((float(r.get("z", "0") or 0.0), idx))
            except Exception:
                indexed.append((0.0, idx))
        if not indexed:
            return {}
        indexed.sort(key=lambda t: t[0])
        out = {}
        if len(indexed) == 1:
            out[indexed[0][1]] = 1.0
            return out
        for pos, (z, idx) in enumerate(indexed):
            if pos == 0:
                sv = abs(indexed[1][0] - z)
            elif pos == len(indexed) - 1:
                sv = abs(z - indexed[pos-1][0])
            else:
                sv = 0.5 * abs(indexed[pos+1][0] - indexed[pos-1][0])
            out[idx] = max(float(sv), 1.0e-12)
        return out

    def _reinforcement_type_changed(self):
        rtype = self.var_reinf_type.get()
        if hasattr(self, "reinf_notation_var"):
            self.reinf_notation_var.set(self._reinforcement_notation_text(rtype))
        self._refresh_reinforcement_button_selection()
        for w in self.reinf_table_frame.winfo_children():
            w.destroy()
        specs = self._reinforcement_specs(rtype)
        if rtype == "No reinforcement":
            self.reinf_table_frame.columnconfigure(0, weight=1)
            ttk.Label(self.reinf_table_frame, text="No reinforcement is applied.", wraplength=760, justify="left", foreground="#555").grid(row=0, column=0, sticky="nw", pady=20)
            self.reinf_tree = None
            self._support_elements = []
            self.reinf_status.set("No reinforcement selected. Solver support list is empty.")
            self._draw_reinforcement_preview_safe()
            self._refresh_solver_button_selection()
            return
        cols = tuple(s[0] for s in specs)
        self.reinf_table_frame.columnconfigure(0, weight=1)
        self.reinf_table_frame.rowconfigure(1, weight=1)
        self.reinf_tree = ttk.Treeview(self.reinf_table_frame, columns=cols, show="headings", height=8, selectmode="browse")
        # Use the full left-pane width.  Wider tables are narrowed by column type.
        compact_width = {
            "code": 64, "z": 70, "angle": 70, "Lfree": 78, "Lbond": 78,
            "EA": 92, "spacing": 72, "prestress": 86, "Tpull": 86, "Tsteel": 82,
            "L": 78, "Sv": 78, "Tult": 105, "Rult": 96,
        }
        for key, heading, width in specs:
            self.reinf_tree.heading(key, text=heading, anchor="center")
            self.reinf_tree.column(key, width=compact_width.get(key, width), minwidth=48, anchor="center", stretch=True)
        rows = self.reinf_rows_by_type.get(rtype) or [self._reinforcement_default_row(rtype, 1)]
        migrated_rows = [self._migrate_reinforcement_row_for_type(rtype, vals) for vals in rows]
        for i, vals in enumerate(migrated_rows):
            self.reinf_tree.insert("", "end", values=vals, tags=("even" if i % 2 == 0 else "odd",))
        self.reinf_tree.grid(row=1, column=0, sticky="nsew")
        y = ttk.Scrollbar(self.reinf_table_frame, orient="vertical", command=self.reinf_tree.yview)
        x = ttk.Scrollbar(self.reinf_table_frame, orient="horizontal", command=self.reinf_tree.xview)
        y.grid(row=1, column=1, sticky="ns")
        x.grid(row=2, column=0, sticky="ew")
        self.reinf_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        btns = ttk.Frame(self.reinf_table_frame)
        btns.grid(row=3, column=0, sticky="w", pady=6)
        ttk.Button(btns, text="+ Add layer", command=self._reinforcement_add_row).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(btns, text="– Remove selected", command=self._reinforcement_remove_selected).grid(row=0, column=1, padx=4)
        ttk.Label(btns, text="Double-click a cell to edit.", foreground="#555").grid(row=0, column=2, padx=(12, 0))
        self.reinf_tree.bind("<Double-1>", self._reinforcement_begin_edit_cell)
        self._reinforcement_inputs_changed()
        self._enforce_reinforcement_solver_requirement(show_status=True)

    def _reinforcement_rows(self):
        if self.reinf_tree is None:
            return []
        cols = self.reinf_tree["columns"]
        rows = []
        for item in self.reinf_tree.get_children():
            vals = self.reinf_tree.item(item, "values")
            rows.append({str(c): str(vals[i]) if i < len(vals) else "" for i, c in enumerate(cols)})
        return rows

    def _save_current_reinf_rows(self):
        if self.reinf_tree is not None:
            self.reinf_rows_by_type[self.var_reinf_type.get()] = [tuple(self.reinf_tree.item(i, "values")) for i in self.reinf_tree.get_children()]

    def _reinforcement_add_row(self):
        if self.reinf_tree is None:
            return
        rtype = self.var_reinf_type.get()
        n = len(self.reinf_tree.get_children()) + 1
        self.reinf_tree.insert("", "end", values=self._reinforcement_default_row(rtype, n))
        self._reinforcement_inputs_changed()

    def _reinforcement_remove_selected(self):
        if self.reinf_tree is None:
            return
        sel = self.reinf_tree.selection() or self.reinf_tree.get_children()[-1:]
        for item in sel:
            self.reinf_tree.delete(item)
        self._renumber_reinforcement_codes()
        self._reinforcement_inputs_changed()

    def _renumber_reinforcement_codes(self):
        if self.reinf_tree is None:
            return
        prefix = "A" if self.var_reinf_type.get() == "Anchored embedded wall" else ("P" if self.var_reinf_type.get() == "Propped embedded wall" else "R")
        for i, item in enumerate(self.reinf_tree.get_children(), start=1):
            vals = list(self.reinf_tree.item(item, "values"))
            if vals:
                vals[0] = f"{prefix}{i}"
                self.reinf_tree.item(item, values=vals)

    def _reinforcement_begin_edit_cell(self, event):
        tree = self.reinf_tree
        if tree is None or tree.identify("region", event.x, event.y) != "cell":
            return
        rowid = tree.identify_row(event.y)
        colid = tree.identify_column(event.x)
        if not rowid or not colid:
            return
        col_index = int(colid.replace("#", "")) - 1
        if col_index == 0:
            return
        bbox = tree.bbox(rowid, colid)
        if not bbox:
            return
        x, y, w, h = bbox
        vals = list(tree.item(rowid, "values"))
        editor = ttk.Entry(tree)
        editor.insert(0, vals[col_index])
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_set()
        def commit(_event=None):
            txt = editor.get().strip()
            try:
                val = float(txt)
                if not (self.var_reinf_type.get() == "Anchored embedded wall" and col_index == 2) and val < 0.0:
                    raise ValueError
                vals[col_index] = txt
                tree.item(rowid, values=vals)
                editor.destroy()
                self._reinforcement_inputs_changed()
            except Exception:
                editor.destroy()
                self.reinf_status.set("Invalid reinforcement value rejected. Values must be non-negative, except anchor angle may be signed.")
        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", lambda _=None: editor.destroy())

    def _reinforcement_inputs_changed(self):
        self._save_current_reinf_rows()
        self._sync_reinforcement_to_solver_silent()
        self._draw_reinforcement_preview_safe()
        self._enforce_reinforcement_solver_requirement(show_status=False)

    def _sync_reinforcement_to_solver_silent(self):
        rtype = self.var_reinf_type.get() if hasattr(self, "var_reinf_type") else "No reinforcement"
        self._support_elements = []
        if rtype == "No reinforcement":
            self.reinf_status.set("No reinforcement selected. Solver support list is empty.")
            return True
        try:
            converted = []
            for r in self._reinforcement_rows():
                z_val = float(r.get("z", "0") or 0.0)
                if z_val < 0.0:
                    raise ValueError("Support elevation z must be non-negative.")
                if rtype == "Propped embedded wall":
                    spacing = float(r.get("spacing", "1") or 1.0)
                    Lprop = float(r.get("L", "0") or 0.0)
                    EA = float(r.get("EA", "0") or 0.0)
                    Rult = float(r.get("Rult", "0") or 0.0)
                    if spacing <= 0.0:
                        raise ValueError("Prop spacing s must be greater than zero.")
                    if Lprop <= 0.0:
                        raise ValueError("Prop length L must be greater than zero; L=0 is not allowed.")
                    converted.append({"type": "prop", "code": r.get("code", "P"), "z": z_val, "theta_deg": 0.0, "L": Lprop, "EA": EA, "spacing": spacing, "k": EA / (Lprop * spacing), "cap": Rult / spacing})
                elif rtype.startswith("MSE walls"):
                    # Auto Sv is computed from the z-levels, not entered by the user.
                    # It is kept in the support dictionary for reporting/future formulations.
                    EA = float(r.get("EA", "0") or 0.0)
                    Tult = float(r.get("Tult", "0") or 0.0)
                    L_val = float(r.get("L", "0") or 0.0)
                    if rtype == "MSE walls, geogrid reinforced":
                        # Geogrids are treated as continuous sheets per metre wall.
                        # The user gives J/EA and Tult per metre width; no horizontal spacing is required.
                        sh = 1.0
                    else:
                        # Metal strips/grids are discrete reinforcement lines, so horizontal spacing is needed
                        # to convert one element to an equivalent force/stiffness per metre wall.
                        sh = max(float(r.get("spacing", "1") or 1.0), 1e-12)
                    # Placeholder; replaced below with the Auto-Sv value after all rows are known.
                    converted.append({"type": "mse", "code": r.get("code", "R"), "z": z_val, "theta_deg": 0.0, "L": L_val, "Sv": 1.0, "spacing": sh, "k": EA / sh, "cap": Tult / sh})
                else:
                    spacing = max(float(r.get("spacing", "1") or 1.0), 1e-12)
                    EA = float(r.get("EA", "0") or 0.0)
                    Lfree = float(r.get("Lfree", "0") or 0.0)
                    if Lfree <= 0.0:
                        raise ValueError("Anchor free length Lf must be greater than zero; Lf=0 is not allowed.")
                    Tpull = float(r.get("Tpull", "0") or 0.0)
                    Tsteel = float(r.get("Tsteel", "0") or 0.0)
                    cap = min(Tpull, Tsteel) / spacing
                    converted.append({"type": "anchor", "code": r.get("code", "A"), "z": z_val, "theta_deg": float(r.get("angle", "0") or 0.0), "k": EA / Lfree / spacing, "cap": cap, "prestress": float(r.get("prestress", "0") or 0.0) / spacing})
            if rtype.startswith("MSE walls"):
                mse_rows = self._reinforcement_rows()
                auto_sv = self._auto_mse_vertical_spacings(mse_rows)
                mse_i = 0
                for elem in converted:
                    if elem.get("type") == "mse":
                        elem["Sv"] = auto_sv.get(mse_i, 1.0)
                        mse_i += 1
                sv_txt = ", ".join([f"{elem.get('code','R')}: Sv={float(elem.get('Sv',1.0)):.3g} m" for elem in converted if elem.get("type") == "mse"])
                self.reinf_status.set(f"{rtype}: {len(converted)} support element(s) prepared. Auto Sv from z-levels: {sv_txt}")
            else:
                self.reinf_status.set(f"{rtype}: {len(converted)} support element(s) prepared for the external solver.")
            self._support_elements = converted
            return True
        except Exception as exc:
            self._support_elements = []
            self.reinf_status.set(f"Reinforcement input error: {exc}")
            return False

    def _read_reinforcement_supports(self):
        self._sync_reinforcement_to_solver_silent()
        return [dict(s) for s in getattr(self, "_support_elements", [])]

    def _draw_reinforcement_preview_safe(self):
        try:
            self._draw_reinforcement_preview()
        except Exception:
            pass

    def _draw_reinforcement_preview(self):
        ax = self.ax_reinf
        ax.clear()
        H_R = self._height_right() if hasattr(self, "right_layers_table") else 10.0
        H_L = self._height_left() if hasattr(self, "left_layers_table") else 6.0
        z_left_surface = H_R - H_L
        rtype = self.var_reinf_type.get() if hasattr(self, "var_reinf_type") else "No reinforcement"
        rows = self._reinforcement_rows()
        force_by_code = self._support_force_by_code() if getattr(self, "last_result", None) is not None else {}

        # Reinforcement preview horizontal domain:
        # base limits are exactly xmin=-0.6*H_R and xmax=+0.6*H_R.
        # The right/left limits are enlarged only when reinforcement geometry
        # (anchors/MSE to the retained side, props to the excavation side)
        # actually needs more space. The axes remain in true 1:1 scale.
        base_extent = max(1.0, 0.60 * H_R)
        x_left_extent = base_extent
        x_right_extent = base_extent
        y_extra = []
        try:
            if rtype == "Anchored embedded wall":
                for r in rows:
                    theta = math.radians(float(r.get("angle", "0") or 0.0))
                    Lf = max(0.0, float(r.get("Lfree", "0") or 0.0))
                    Lb = max(0.0, float(r.get("Lbond", "0") or 0.0))
                    x_right_extent = max(x_right_extent, 1.08 * abs((Lf + Lb) * math.cos(theta)) + 0.4)
                    z0 = float(r.get("z", "0") or 0.0)
                    # z is positive downward. Negative θ therefore gives a downward anchor.
                    y_extra.extend([z0, z0 - Lf * math.sin(theta), z0 - (Lf + Lb) * math.sin(theta)])
            elif rtype == "Propped embedded wall":
                for r in rows:
                    x_left_extent = max(x_left_extent, 1.08 * max(0.0, float(r.get("L", "0") or 0.0)) + 0.4)
            elif rtype.startswith("MSE walls"):
                for r in rows:
                    x_right_extent = max(x_right_extent, 1.08 * max(0.0, float(r.get("L", "0") or 0.0)) + 0.4)
        except Exception:
            pass
        x_extent = max(x_left_extent, x_right_extent)

        ax.fill_betweenx([0, H_R], 0, x_right_extent, color="#dbeafe", alpha=0.22)
        ax.fill_betweenx([z_left_surface, H_R], -x_left_extent, 0, color="#fecdd3", alpha=0.20)
        ax.plot([0, 0], [0, H_R], color="black", linewidth=3)
        ax.plot([0, x_right_extent], [0, 0], color="saddlebrown", linewidth=2)
        ax.plot([0, -x_left_extent], [z_left_surface, z_left_surface], color="saddlebrown", linewidth=2)

        # Excavation stages: z1 < z2 < ... < zn, with Stage n fixed at z_ex = H_R - H_L.
        try:
            stage_rows = self._stage_rows()
        except Exception:
            stage_rows = []
        for sr in stage_rows:
            try:
                z_stage = float(sr.get("z", 0.0))
            except Exception:
                continue
            if z_stage < -1.0e-9 or z_stage > H_R + 1.0e-9:
                continue
            is_final = abs(z_stage - z_left_surface) <= 1.0e-6
            if not is_final:
                ax.plot([-x_left_extent, 0], [z_stage, z_stage], color="#a16207", linewidth=1.8, linestyle="--", alpha=0.9)
                ax.text(-0.98 * x_left_extent, z_stage, str(sr.get("stage", "Stage")), ha="left", va="bottom", color="#92400e", fontsize=9)
            else:
                ax.text(-0.98 * x_left_extent, z_stage, f"{sr.get('stage','Stage')} / final excavation", ha="left", va="bottom", color="#92400e", fontsize=9)

        if rtype == "No reinforcement":
            ax.text(0.50 * x_right_extent, 0.50 * H_R, "No reinforcement", ha="center", va="center", fontsize=12, color="#475569")

        for r in rows:
            try:
                z = float(r.get("z", "0") or 0.0)
            except Exception:
                continue
            code = str(r.get("code", "R"))
            if rtype == "Propped embedded wall":
                try:
                    Lprop = max(0.0, float(r.get("L", "0") or 0.0))
                except Exception:
                    Lprop = 0.0
                x_left = -max(Lprop, 0.12 * x_extent)
                ax.plot([x_left, 0], [z, z], color="darkorange", linewidth=2.8, solid_capstyle="round")
                ax.plot(0, z, marker="s", color="darkorange", markersize=5)
                label = f"{code}  L={Lprop:g} m"
                if code in force_by_code:
                    label += f"  Fh={float(force_by_code[code].get('Fh',0.0)):.1f} kN/m"
                ax.text(x_left - 0.04 * max(x_extent, 1.0), z, label, va="center", ha="right", color="darkorange", fontsize=8)
            elif rtype.startswith("MSE walls"):
                try:
                    L = max(0.0, float(r.get("L", "0") or 0.0))
                except Exception:
                    L = 0.0
                ax.plot([0, L], [z, z], color="purple", linewidth=2.3, solid_capstyle="round")
                ax.plot(L, z, marker="|", color="purple", markersize=9)
                label = f"{code}  L={L:g} m"
                if code in force_by_code:
                    label += f"  Fh={float(force_by_code[code].get('Fh',0.0)):.1f} kN/m"
                ax.text(max(0.15, 0.5 * L), z, label, va="bottom", ha="center", color="purple", fontsize=9)
            elif rtype == "Anchored embedded wall":
                try:
                    theta = math.radians(float(r.get("angle", "0") or 0.0))
                    Lf = max(0.0, float(r.get("Lfree", "0") or 0.0))
                    Lb = max(0.0, float(r.get("Lbond", "0") or 0.0))
                    T0 = max(0.0, float(r.get("prestress", "0") or 0.0))
                except Exception:
                    theta, Lf, Lb, T0 = 0.0, 0.0, 0.0, 0.0
                x1 = Lf * math.cos(theta)
                y1 = z - Lf * math.sin(theta)
                x2 = (Lf + Lb) * math.cos(theta)
                y2 = z - (Lf + Lb) * math.sin(theta)
                ax.plot([0, x1], [z, y1], color="#2563eb", linewidth=2.4, solid_capstyle="round", label="Lf free length" if code == "A1" else None)
                ax.plot([x1, x2], [y1, y2], color="#f97316", linewidth=4.2, solid_capstyle="round", label="Lb bond length" if code == "A1" else None)
                ax.plot(0, z, marker="o", color="#1d4ed8", markersize=5)
                ax.plot(x1, y1, marker="o", color="#f97316", markersize=4)
                ax.plot(x2, y2, marker="o", color="#111827", markersize=4)
                label = f"{code}  Lf={Lf:g}, Lb={Lb:g}"
                if code in force_by_code:
                    fr = force_by_code[code]
                    label += f"  Fh={float(fr.get('Fh',0.0)):.1f} kN/m"
                ax.text(x2 + 0.05, y2, label, va="center", ha="left", color="#1d4ed8", fontsize=8)
                if T0 > 0.0:
                    # Prestress is shown as a short arrow along the anchor direction.
                    arr_len = min(max(0.30, 0.06 * x_extent), max(0.65, 0.18 * max(Lf + Lb, 1.0)))
                    ax.annotate(
                        "T0",
                        xy=(arr_len * math.cos(theta), z - arr_len * math.sin(theta)),
                        xytext=(0.04 * x_extent, z),
                        arrowprops=dict(arrowstyle="->", lw=1.8, color="#dc2626"),
                        color="#dc2626",
                        fontsize=9,
                        ha="left",
                        va="bottom",
                    )

        y_min = min([-0.5, z_left_surface - 0.5] + y_extra)
        y_max = max([H_R + 0.5] + y_extra)
        # Exact requested base preview limits with reinforcement-aware extension.
        ax.set_xlim(-x_left_extent, x_right_extent)
        ax.set_ylim(y_max, y_min)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x (m, true scale)")
        ax.set_ylabel("z (m)")
        ax.set_title(rtype)
        ax.grid(True, linestyle="--", alpha=0.3)
        try:
            self._safe_legend(ax, loc="best", fontsize=8)
        except Exception:
            pass
        self.fig_reinf.tight_layout()
        self.canvas_reinf.draw_idle()

    def _build_run_tab(self):
        self.tab_run.columnconfigure(0, weight=0, minsize=560)
        self.tab_run.columnconfigure(1, weight=1)
        self.tab_run.rowconfigure(0, weight=1)
        panel_scroll = ScrollableFrame(self.tab_run, width=560)
        panel_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
        panel = ttk.Frame(panel_scroll.inner, padding=8)
        panel.grid(row=0, column=0, sticky="new")
        panel.columnconfigure(0, weight=1)
        run = ttk.LabelFrame(panel, text="Run")
        run.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        ttk.Button(run, text="Start", style="Start.TButton", command=self.run_solver).grid(row=0, column=0, sticky="ew", padx=4, pady=5)
        ttk.Button(run, text="Pause", style="Pause.TButton", command=self.pause_solver).grid(row=0, column=1, sticky="ew", padx=4, pady=5)
        ttk.Button(run, text="Stop", style="Stop.TButton", command=self.stop_solver).grid(row=0, column=2, sticky="ew", padx=4, pady=5)
        for c in range(3):
            run.columnconfigure(c, weight=1)
        ttk.Label(run, textvariable=self.run_status, wraplength=470).grid(row=1, column=0, columnspan=3, sticky="w", padx=4, pady=5)
        self.progress_bar = ttk.Progressbar(run, variable=self.progress_var, maximum=100.0, mode="indeterminate")
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=(4, 2))
        ttk.Label(run, textvariable=self.progress_text_var).grid(row=3, column=0, columnspan=3, sticky="w", padx=4, pady=2)
        ttk.Label(run, textvariable=self.timer_var, font=("Segoe UI", 13, "bold")).grid(row=4, column=0, columnspan=3, sticky="w", padx=4, pady=2)
        refine = ttk.LabelFrame(run, text="Post-run refinement suggestion")
        refine.grid(row=5, column=0, columnspan=3, sticky="ew", padx=4, pady=(8, 4))
        for c in range(4):
            refine.columnconfigure(c, weight=1)
        solver_box = ttk.LabelFrame(panel, text="Solver selection")
        solver_box.grid(row=1, column=0, sticky="ew", pady=5)
        ttk.Label(solver_box, text="Solver").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.solver_option_menu = ttk.OptionMenu(
            solver_box,
            self.var_solver_display,
            self.var_solver_display.get(),
            "Flexible wall - Fixed base (closed-form bending)",
            "Flexible wall - Fixed base (differential equation)",
            "Flexible wall - Base spring (differential equation)",
            "Rigid wall (no bending)",
            "Any wall (general case)",
        )
        self.solver_option_menu.grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        self.solver_lock_note_var = tk.StringVar(value="")
        ttk.Label(solver_box, textvariable=self.solver_lock_note_var, foreground="#0f766e", wraplength=500, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
        ttk.Label(solver_box, text="Integration").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.OptionMenu(solver_box, self.var_integration_method, self.var_integration_method.get(), "Gauss", "Lumped").grid(row=2, column=1, sticky="ew", padx=4, pady=3)
        self.no_bending_label = ttk.Label(solver_box, text="Rigid-wall movement mode")
        self.no_bending_label.grid(row=3, column=0, sticky="w", padx=4, pady=3)
        self.no_bending_menu = ttk.OptionMenu(solver_box, self.var_no_bending_mode, self.var_no_bending_mode.get(), "Auto (ΣF=0 & ΣM=0)", "Manual")
        self.no_bending_menu.grid(row=3, column=1, sticky="ew", padx=4, pady=3)
        self.rigid_opt_label = ttk.Label(solver_box, text="Rigid optimization solver")
        self.rigid_opt_label.grid(row=4, column=0, sticky="w", padx=4, pady=3)
        self.rigid_opt_menu = ttk.OptionMenu(
            solver_box,
            self.var_rigid_optimization_solver,
            self.var_rigid_optimization_solver.get(),
            "Fast equilibrium only",
            "Energy-aware variational",
        )
        self.rigid_opt_menu.grid(row=4, column=1, sticky="ew", padx=4, pady=3)

        # Icon-only solver selector. Layout: CS / differential on top, rigid / general case below.
        cards = ttk.LabelFrame(solver_box, text="Quick solver selection")
        cards.grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 4))
        card_specs = [
            ("fixed_closed", "#eaf3ff", "#173f6b", "Flexible wall - Fixed base (closed-form bending)"),
            ("fixed_diff", "#e7f8f5", "#0f766e", "Flexible wall - Fixed base (differential equation)"),
            ("base_spring", "#ecfeff", "#0e7490", "Flexible wall - Base spring (differential equation)"),
            ("rigid", "#f0ebff", "#5b21b6", "Rigid wall (no bending)"),
            ("general", "#fff1df", "#92400e", "Any wall (general case)"),
        ]
        self.solver_icon_buttons = {}
        for i, spec in enumerate(card_specs):
            r, c = divmod(i, 2)
            cards.columnconfigure(c, weight=0)
            key, bg, fg, display = spec
            btn = self._make_icon_button(cards, key, "", "",
                                         lambda d=display: self._select_solver_display(d),
                                         bg=bg, fg=fg, width=172, height=172)
            btn.grid(row=r, column=c, sticky="nsew", padx=8, pady=8)
            self.solver_icon_buttons[display] = btn
        self._refresh_solver_button_selection()

        self.rigid_move_box = ttk.LabelFrame(panel, text="Rigid movement")
        self.rigid_move_box.grid(row=2, column=0, sticky="ew", pady=5)
        self._entry(self.rigid_move_box, 0, 0, "Δx_trans (m)", self.var_dx_trans)
        self._entry(self.rigid_move_box, 0, 2, "θ_rot (deg)", self.var_theta_rot)
        self._entry(self.rigid_move_box, 0, 4, "z_pivot (m)", self.var_z_pivot)

        disc = ttk.LabelFrame(panel, text="Discretization")
        disc.grid(row=3, column=0, sticky="ew", pady=5)
        self._entry(disc, 0, 0, "Δz / plotting dz (m)", self.var_dz)
        self._entry(disc, 1, 0, "n profile points", self.var_n_points)
        self._entry(disc, 2, 0, "N iterations", self.var_N)
        self._entry(disc, 3, 0, "tol", self.var_tol)

        opttol = ttk.LabelFrame(panel, text="Optimization tolerances")
        opttol.grid(row=4, column=0, sticky="ew", pady=5)
        self._entry(opttol, 0, 0, "tol_F = |ΣF|/scale", self.var_equilibrium_force_tol)
        self._entry(opttol, 1, 0, "tol_M = |ΣM|/scale", self.var_equilibrium_moment_tol)
        self._entry(opttol, 2, 0, "tol_W work band", self.var_work_band_tol)
        self._entry(opttol, 3, 0, "general n bending schemes", self.var_general_case_bending_schemes)
        self._entry(opttol, 4, 0, "general θ refine passes", self.var_general_case_theta_refine_passes)
        self._entry(opttol, 5, 0, "general θ grid points", self.var_general_case_theta_points)
        self._entry(opttol, 6, 0, "general z_pivot grid points", self.var_general_case_zp_points)
        self._entry(opttol, 7, 0, "general pivot margin frac", self.var_general_case_pivot_margin_frac)
        ttk.Checkbutton(opttol, text="general: run schemes in parallel", variable=self.var_general_case_parallel).grid(row=8, column=0, columnspan=2, sticky="w", padx=4, pady=3)
        self._entry(opttol, 9, 0, "general max workers (0=auto)", self.var_general_case_max_workers)

        self.refine_msg_var = tk.StringVar(value="Run the general solver to get a suggested local refinement window.")
        ttk.Label(refine, textvariable=self.refine_msg_var, style="Muted.TLabel", wraplength=430).grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=2)
        self.refine_theta_min = tk.StringVar(value="")
        self.refine_theta_max = tk.StringVar(value="")
        self.refine_zp_min = tk.StringVar(value="")
        self.refine_zp_max = tk.StringVar(value="")
        ttk.Label(refine, text="θ min/max").grid(row=1, column=0, sticky="w", padx=4)
        ttk.Entry(refine, textvariable=self.refine_theta_min, width=8).grid(row=1, column=1, sticky="w", padx=2)
        ttk.Entry(refine, textvariable=self.refine_theta_max, width=8).grid(row=1, column=2, sticky="w", padx=2)
        ttk.Label(refine, text="z_p min/max").grid(row=2, column=0, sticky="w", padx=4)
        ttk.Entry(refine, textvariable=self.refine_zp_min, width=8).grid(row=2, column=1, sticky="w", padx=2)
        ttk.Entry(refine, textvariable=self.refine_zp_max, width=8).grid(row=2, column=2, sticky="w", padx=2)
        ttk.Button(refine, text="Apply high-accuracy settings", command=self.apply_refinement_suggestion).grid(row=1, column=3, rowspan=2, sticky="ew", padx=4, pady=2)

        monitor = ttk.LabelFrame(self.tab_run, text="Solver monitor")
        monitor.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        monitor.rowconfigure(0, weight=2)
        monitor.rowconfigure(1, weight=1)
        monitor.columnconfigure(0, weight=1)

        summary_frame = ttk.LabelFrame(monitor, text="Selected solution, governing equations and checks")
        summary_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 6))
        summary_frame.rowconfigure(0, weight=1)
        summary_frame.columnconfigure(0, weight=1)
        self.monitor_tree = ttk.Treeview(summary_frame, columns=("quantity", "value"), show="headings", height=15)
        self.monitor_tree.heading("quantity", text="Quantity")
        self.monitor_tree.heading("value", text="Value")
        self.monitor_tree.column("quantity", width=270, anchor="w", stretch=False)
        self.monitor_tree.column("value", width=960, anchor="w", stretch=True)
        self.monitor_tree.tag_configure("section", background="#e5e7eb", font=("Segoe UI", 10, "bold"))
        self.monitor_tree.tag_configure("movement", background="#dbeafe")
        self.monitor_tree.tag_configure("formula", background="#f8fafc")
        self.monitor_tree.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(summary_frame, orient="vertical", command=self.monitor_tree.yview)
        y.grid(row=0, column=1, sticky="ns")
        x = ttk.Scrollbar(summary_frame, orient="horizontal", command=self.monitor_tree.xview)
        x.grid(row=1, column=0, sticky="ew")
        self.monitor_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)

        # Ranked general-case candidates: a professional wide table.  It is intentionally
        # non-stretching and horizontally scrollable because the candidate energy budget
        # contains more information than can fit in a normal laptop-width pane.
        cand_frame = ttk.LabelFrame(monitor, text="Ranked candidate solutions")
        cand_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        cand_frame.rowconfigure(1, weight=1)
        cand_frame.columnconfigure(0, weight=1)
        self.candidate_note_var = tk.StringVar(value="General-case candidates only. Fixed-base runs use the summary and results tables above.")
        ttk.Label(cand_frame, textvariable=self.candidate_note_var, foreground="#475569", wraplength=1100).grid(row=0, column=0, sticky="w", padx=6, pady=(4, 2))
        self.candidate_tree = ttk.Treeview(
            cand_frame,
            columns=("rank", "factor", "bend", "dx", "zp", "theta", "F", "M", "WL", "WR", "Wtot", "Wbend", "Wrigid", "U", "E", "Action", "status"),
            show="headings",
            height=9,
            style="Candidate.Treeview",
        )
        cand_cols = (
            ("rank", "Rank", 54), ("factor", "γ factor", 78), ("bend", "max bend dx", 104),
            ("dx", "dx_trans", 92), ("zp", "z_pivot", 86), ("theta", "θ", 78),
            ("F", "|ΣF|/scale", 96), ("M", "|ΣM|/scale", 96),
            ("WL", "W_L,total", 94), ("WR", "W_R,total", 94), ("Wtot", "W_total", 90),
            ("Wbend", "W_bend,net", 108), ("Wrigid", "W_rigid,net", 108),
            ("U", "U_bend", 86), ("E", "E_bend res", 96),
            ("Action", "|WL|+|WR|", 98), ("status", "status", 124),
        )
        for col, label, width in cand_cols:
            self.candidate_tree.heading(col, text=label)
            self.candidate_tree.column(col, width=width, minwidth=width, anchor="center", stretch=False)
        self.candidate_tree.tag_configure("selected", background="#dbeafe", font=("Segoe UI", 9, "bold"))
        self.candidate_tree.tag_configure("candidate_even", background="#ffffff")
        self.candidate_tree.tag_configure("candidate_odd", background="#f8fafc")
        self.candidate_tree.tag_configure("diagnostic", foreground="#777777", background="#f3f4f6")
        self.candidate_tree.grid(row=1, column=0, sticky="nsew", padx=(4, 0), pady=(2, 0))
        y2 = ttk.Scrollbar(cand_frame, orient="vertical", command=self.candidate_tree.yview)
        y2.grid(row=1, column=1, sticky="ns", pady=(2, 0))
        x2 = ttk.Scrollbar(cand_frame, orient="horizontal", command=self.candidate_tree.xview)
        x2.grid(row=2, column=0, sticky="ew", padx=(4, 0))
        self.candidate_tree.configure(yscrollcommand=y2.set, xscrollcommand=x2.set)

        self._monitor_clear()
        self._update_solver_visibility()

    def _build_validation_tab(self):
        parent = getattr(self, "validation_container", self.tab_validation)
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        top = ttk.Frame(parent, padding=4)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Button(top, text="Check inputs", command=self.refresh_validation).pack(side="left", padx=4)
        ttk.Label(top, text="Warnings here are diagnostic. Red errors should be corrected before design use.", foreground="#555").pack(side="left", padx=10)
        self.validation_summary_var = tk.StringVar(value="Validation has not been run yet.")
        ttk.Label(top, textvariable=self.validation_summary_var, foreground="#374151").pack(side="right", padx=6)

        self.validation_tree = ttk.Treeview(
            parent,
            columns=("severity", "item", "message"),
            show="headings",
            height=24,
        )
        for col, txt, width in (("severity", "Severity", 80), ("item", "Item", 150), ("message", "Message", 420)):
            self.validation_tree.heading(col, text=txt)
            self.validation_tree.column(col, width=width, anchor="w", stretch=(col == "message"))
        self.validation_tree.tag_configure("ERROR", background="#fee2e2")
        self.validation_tree.tag_configure("WARNING", background="#fef3c7")
        self.validation_tree.tag_configure("INFO", background="#e0f2fe")
        self.validation_tree.tag_configure("OK", background="#dcfce7")
        self.validation_tree.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        y = ttk.Scrollbar(parent, orient="vertical", command=self.validation_tree.yview)
        y.grid(row=1, column=1, sticky="ns")
        self.validation_tree.configure(yscrollcommand=y.set)

    def _raw_layer_rows_for_validation(self, table):
        rows = []
        if table is None:
            return rows
        for i, item in enumerate(table.tree.get_children(), start=1):
            vals = list(table.tree.item(item, "values"))
            while len(vals) < 8:
                vals.append("")
            rows.append((i, vals))
        return rows

    def _add_validation(self, checks, severity, item, message):
        checks.append({"severity": severity, "item": item, "message": message})

    def validate_current_model(self, result=None):
        checks = []
        add = lambda sev, item, msg: self._add_validation(checks, sev, item, msg)
        try:
            H_L = self._height_left()
            H_R = self._height_right()
            if H_L <= 0.0:
                add("ERROR", "H_L", "Left-side total layer height must be positive.")
            if H_R <= 0.0:
                add("ERROR", "H_R", "Right-side total layer height must be positive.")
            if H_L > H_R + 1.0e-12:
                add("WARNING", "Geometry", "H_L is greater than H_R. This is allowed only if intended; check the excavation geometry.")
            z_exc = H_R - H_L
            zwL_raw = float(self.var_z_w_L.get())
            if zwL_raw < z_exc - 1.0e-12:
                add("WARNING", "z_w,L", f"Left water level was above the excavation surface. It will be clipped from {zwL_raw:g} m to {z_exc:g} m.")
            zwR = float(self.var_z_w_R.get())
            if zwR < 0.0:
                add("WARNING", "z_w,R", "Right water level is above the right ground surface. Check whether this is intended.")
            zp = float(self.var_z_pivot.get())
            if zp < 0.0 or zp > H_R:
                add("ERROR", "z_pivot", f"z_pivot should lie within the modeled wall height: 0 ≤ z_pivot ≤ H_R = {H_R:g} m.")
        except Exception as exc:
            add("ERROR", "Geometry", f"Could not validate geometry: {exc}")

        try:
            kh = float(self.var_k_h.get())
            kv = float(self.var_k_v.get())
            if kh < 0.0:
                add("WARNING", "k_h", "Negative k_h is not allowed; the GUI clamps it to zero.")
            if abs(kv) >= 1.0:
                add("ERROR", "k_v", "|k_v| must be smaller than 1.0 because the effective vertical inertial factor becomes singular.")
            elif abs(kv) > 0.5:
                add("WARNING", "k_v", "Large |k_v| value. Check seismic input.")
            if float(self.var_gamma_w.get()) <= 0.0:
                add("ERROR", "γ_w", "Water unit weight γ_w must be positive.")
        except Exception as exc:
            add("ERROR", "Seismic and water", f"Could not validate seismic/water inputs: {exc}")

        for side_name, table in (("Left", getattr(self, "left_layers_table", None)), ("Right", getattr(self, "right_layers_table", None))):
            for idx, vals in self._raw_layer_rows_for_validation(table):
                code = vals[0] or f"layer {idx}"
                label = f"{side_name} {code}"
                try:
                    h = float(vals[1]); c = float(vals[2]); phi = float(vals[3]); gam = float(vals[4]); gamsat = float(vals[5]); E = float(vals[6]); nu = float(vals[7])
                    if h <= 0.0:
                        add("ERROR", label, "Layer thickness h must be positive.")
                    if c <= 0.0:
                        add("INFO", label, "c′ = 0 is silently regularized to 0.001 kPa before calling the CUT engine.")
                    elif c < 0.001:
                        add("INFO", label, "c′ < 0.001 is regularized to 0.001 kPa before calling the CUT engine.")
                    if phi <= 0.0:
                        add("INFO", label, "φ′ ≤ 0 is regularized inside the CUT engine to avoid singular trigonometric terms.")
                    if phi > 60.0:
                        add("WARNING", label, "φ′ is unusually high. Check units and input.")
                    if E <= 0.0:
                        add("ERROR", label, "Soil E must be positive.")
                    if not (0.0 <= nu < 0.5):
                        add("ERROR", label, "ν must satisfy 0 ≤ ν < 0.5.")
                    if gam <= 0.0 or gamsat <= 0.0:
                        add("WARNING", label, "Unit weights should normally be positive.")
                    if gamsat + 1.0e-12 < gam:
                        add("WARNING", label, "γsat is smaller than γ. Check whether this is intended.")
                except Exception:
                    add("ERROR", label, "Layer row contains non-numeric or incomplete values.")

        try:
            qL = float(self.var_q_L.get()); qR = float(self.var_q_R.get())
            if qL < 0.0:
                add("WARNING", "q_L", "Negative uniform surcharge is unusual. Check input.")
            if qR < 0.0:
                add("WARNING", "q_R", "Negative uniform surcharge is unusual. Check input.")
        except Exception:
            add("ERROR", "q", "Could not read surcharge inputs.")

        try:
            dz = float(self.var_dz.get()); n = int(self.var_n_points.get()); N = int(self.var_N.get()); tol = float(self.var_tol.get())
            if dz <= 0.0:
                add("ERROR", "Δz", "Δz must be positive.")
            if n < 3:
                add("ERROR", "n profile points", "At least 3 profile points are required.")
            elif n < 80:
                add("WARNING", "n profile points", "Low point count may produce visibly coarse diagrams and less stable equilibrium diagnostics.")
            if N <= 0:
                add("ERROR", "N iterations", "N must be positive.")
            if tol <= 0.0:
                add("ERROR", "tol", "Convergence tolerance must be positive.")
            tolF = float(self.var_equilibrium_force_tol.get())
            tolM = float(self.var_equilibrium_moment_tol.get())
            tolW = float(self.var_work_band_tol.get())
            if tolF < 0.0 or tolM < 0.0 or tolW < 0.0:
                add("ERROR", "Optimization tolerances", "tol_F, tol_M and tol_W must be non-negative.")
            ng = int(self.var_general_case_bending_schemes.get())
            if ng < 2:
                add("ERROR", "General case", "At least 2 bending schemes are required; default is 10.")
            if int(self.var_general_case_theta_refine_passes.get()) < 0:
                add("ERROR", "General case", "θ refine passes must be non-negative.")
            if int(self.var_general_case_max_workers.get()) < 0:
                add("ERROR", "General case", "parallel max workers must be 0 (auto) or positive.")
            if tolF > 0.20 or tolM > 0.20:
                add("WARNING", "Optimization tolerances", "Equilibrium tolerances above 0.20 are very relaxed.")
            if tolW > 0.50:
                add("WARNING", "Optimization tolerances", "Work-band tolerance above 0.50 is very broad.")
        except Exception:
            add("ERROR", "Discretization", "Could not read discretization controls.")

        if result is not None:
            s = dict(getattr(result, "summary", {}) or {})
            if str(getattr(result, "status", "")).lower() not in ("ok", "done", "success", "completed", "engineering_converged"):
                add("WARNING", "Solver status", f"Solver returned status: {getattr(result, 'status', 'unknown')}.")
            converged = s.get("converged", None)
            engineering_converged = bool(s.get("engineering_converged", False))
            if (converged is False or str(converged).lower() == "false") and not engineering_converged:
                add("WARNING", "Convergence", "Solver did not report convergence. Inspect convergence charts and residuals.")
            elif engineering_converged:
                add("INFO", "Engineering convergence", str(s.get("engineering_convergence_reason", "accepted")))
            diag_warning = str(s.get("diagnostic_warning", "") or "").strip()
            if diag_warning:
                add("WARNING", "Base-spring diagnostic", diag_warning)
            try:
                max_change = float(s.get("max_iteration_change_m", 0.0))
                tol = float(self.var_tol.get())
                if max_change > max(10.0 * tol, 1.0e-12):
                    add("WARNING", "Convergence", f"Final max iteration change {max_change:.3e} m is larger than 10×tol.")
            except Exception:
                pass
            for key in ("ΣF kN/m", "force_residual", "F", "ΣF"):
                if key in s:
                    try:
                        if abs(float(s[key])) > 50.0:
                            add("WARNING", "ΣF", f"Large force residual reported: {float(s[key]):.4g} kN/m.")
                    except Exception:
                        pass
                    break
            for key in ("ΣM kNm/m", "moment_residual", "M", "ΣM"):
                if key in s:
                    try:
                        if abs(float(s[key])) > 250.0:
                            add("WARNING", "ΣM", f"Large moment residual reported: {float(s[key]):.4g} kNm/m.")
                    except Exception:
                        pass
                    break
            try:
                clipped = 0
                for attr in ("p_left", "p_right"):
                    for v in getattr(result, attr, []) or []:
                        if _is_finite(v) and float(v) == 0.0:
                            clipped += 1
                if clipped > 0:
                    add("INFO", "Tension cut-off", "Zero pressure zones may include points where cohesive tensile horizontal stress was clipped to zero.")
            except Exception:
                pass

        if not checks:
            add("OK", "Validation", "No issues detected by the current checks.")
        return checks

    def refresh_validation(self, result=None):
        checks = self.validate_current_model(result=result)
        if not hasattr(self, "validation_tree"):
            return checks
        for item in self.validation_tree.get_children():
            self.validation_tree.delete(item)
        counts = {"ERROR": 0, "WARNING": 0, "INFO": 0, "OK": 0}
        for rec in checks:
            sev = rec.get("severity", "INFO")
            counts[sev] = counts.get(sev, 0) + 1
            self.validation_tree.insert("", "end", values=(sev, rec.get("item", ""), rec.get("message", "")), tags=(sev,))
        if counts.get("ERROR", 0):
            summary = f"{counts['ERROR']} error(s), {counts.get('WARNING', 0)} warning(s), {counts.get('INFO', 0)} info item(s)."
        elif counts.get("WARNING", 0):
            summary = f"No errors. {counts['WARNING']} warning(s), {counts.get('INFO', 0)} info item(s)."
        else:
            summary = "No validation errors."
        self.validation_summary_var.set(summary)
        return checks


    def _sort_treeview(self, tree, col, reverse=False):
        try:
            data = []
            for iid in tree.get_children(""):
                val = tree.set(iid, col)
                try:
                    key = float(str(val).replace(",", "").split()[0])
                except Exception:
                    key = str(val).lower()
                data.append((key, iid))
            data.sort(reverse=reverse)
            for index, (_, iid) in enumerate(data):
                tree.move(iid, "", index)
            tree.heading(col, command=lambda: self._sort_treeview(tree, col, not reverse))
        except Exception:
            pass

    def _support_result_rows(self, result=None, model=None):
        """Return compact reinforcement/support result rows for GUI and report.

        The solver stores final support reactions in the result summary.  Older
        branches use either ``support reactions`` or ``support_reactions_table``;
        this normalises both and enriches them with the input support capacity,
        stiffness, angle and prestress so the user can see the engineering
        meaning of each anchor/prop force directly in the GUI and the PDF.
        """
        result = result or getattr(self, "last_result", None)
        model = model or getattr(self, "last_model", None)
        if result is None:
            return []
        summary = dict(getattr(result, "summary", {}) or {})
        reactions = list(summary.get("support reactions", []) or summary.get("support_reactions_table", []) or [])
        supports = list(getattr(model, "reinforcement_supports", []) or []) if model is not None else []
        by_code = {str(s.get("code", f"S{i+1}")): dict(s) for i, s in enumerate(supports)}
        rows = []
        if not reactions and supports:
            # Show inactive supports explicitly after a run.
            for i, sup in enumerate(supports, start=1):
                code = str(sup.get("code", f"S{i}"))
                rows.append({
                    "code": code, "type": str(sup.get("type", "support")),
                    "z": float(sup.get("z", 0.0) or 0.0),
                    "theta_deg": float(sup.get("theta_deg", 0.0) or 0.0),
                    "w": 0.0, "k": float(sup.get("k", 0.0) or 0.0),
                    "prestress": float(sup.get("prestress", 0.0) or 0.0),
                    "cap": float(sup.get("cap", 0.0) or 0.0),
                    "Fh": 0.0, "axial": 0.0, "util": 0.0,
                    "status": "inactive",
                })
            return rows
        for j, r in enumerate(reactions, start=1):
            rr = dict(r)
            code = str(rr.get("code", f"S{j}"))
            sup = by_code.get(code, {})
            typ = str(rr.get("type", sup.get("type", "support")))
            z = float(rr.get("z", sup.get("z", 0.0)) or 0.0)
            theta = float(rr.get("theta_deg", sup.get("theta_deg", 0.0)) or 0.0)
            k = float(rr.get("k", sup.get("k", 0.0)) or 0.0)
            prestress = float(rr.get("prestress", sup.get("prestress", 0.0)) or 0.0)
            cap = float(rr.get("cap", sup.get("cap", 0.0)) or 0.0)
            Fh = float(rr.get("Fh", rr.get("horizontal", 0.0)) or 0.0)
            # If an older solver/report branch did not return final support force
            # but the support is active in the solved displacement field, recover
            # the reaction from the same unified one-way law used in the solver.
            # This is essential for props/struts, which otherwise may appear with
            # Fh=0 even though their stiffness participated in the beam solve.
            recovered_from_law = False
            # Horizontal and axial force are not identical for inclined anchors.
            # Fh is the horizontal component acting on the wall; axial is along
            # the support axis.  Use the solver-provided axial value when
            # available, otherwise recover it by projection.
            cth = max(1.0e-12, abs(math.cos(math.radians(theta))))
            if "axial" in rr and rr.get("axial") not in (None, ""):
                axial = float(rr.get("axial") or 0.0)
            else:
                axial = abs(Fh) / cth
            if "w" in rr and rr.get("w") not in (None, ""):
                w = float(rr.get("w") or 0.0)
            elif "w_reference" in rr and rr.get("w_reference") not in (None, ""):
                w = float(rr.get("w_reference") or 0.0)
            else:
                # Interpolate the final displacement profile at the support level.
                w = 0.0
                try:
                    zprof = list(getattr(result, "z", []) or [])
                    wprof = list(getattr(result, "deflection", []) or [])
                    if zprof and wprof:
                        if z <= zprof[0]:
                            w = float(wprof[0])
                        elif z >= zprof[-1]:
                            w = float(wprof[-1])
                        else:
                            for ii in range(1, min(len(zprof), len(wprof))):
                                if float(zprof[ii]) >= z:
                                    z1, z2 = float(zprof[ii-1]), float(zprof[ii])
                                    w1, w2 = float(wprof[ii-1]), float(wprof[ii])
                                    t = 0.0 if abs(z2-z1) <= 1e-15 else (z-z1)/(z2-z1)
                                    w = w1 + t*(w2-w1)
                                    break
                except Exception:
                    w = 0.0
            # Recover missing/stale zero forces from the final displacement and support law.
            if abs(Fh) <= 1e-12 and k > 0.0:
                sign = -1.0 if typ.strip().lower() == "prop" else 1.0
                signed_disp = sign * float(w) * cth
                if signed_disp > 0.0 or prestress > 0.0:
                    axial_law = prestress + k * max(0.0, signed_disp)
                    if cap > 0.0:
                        axial_law = min(axial_law, cap)
                    Fh = -sign * axial_law * cth
                    axial = abs(Fh) / cth
                    recovered_from_law = True
            util = float(rr.get("util", rr.get("utilization", (abs(axial) / cap if cap > 0 else 0.0))) or 0.0)
            if recovered_from_law and (cap > 0.0):
                util = abs(axial) / cap
            if abs(Fh) <= 1e-12 and abs(axial) <= 1e-12:
                status = "inactive"
            else:
                status = str(rr.get("status", "elastic" if (cap <= 0 or abs(axial) < cap) else "capacity"))
            rows.append({
                "code": code, "type": typ, "z": z, "theta_deg": theta,
                "w": w, "k": k, "prestress": prestress, "cap": cap,
                "Fh": Fh, "axial": axial, "util": util, "status": status,
            })
        return rows

    def _populate_support_results_table(self, result=None):
        if not hasattr(self, "support_results_tree"):
            return
        for item in self.support_results_tree.get_children():
            self.support_results_tree.delete(item)
        rows = self._support_result_rows(result=result)
        if not rows:
            self.support_results_tree.insert("", "end", values=("—", "none", "", "", "", "", "", "", "No active reinforcement/support result"), tags=("inactive",))
            return
        for row in rows:
            tag = "inactive" if str(row.get("status", "")).lower() == "inactive" else ("capacity" if float(row.get("util", 0.0)) >= 0.95 else "ok")
            self.support_results_tree.insert("", "end", values=(
                row.get("code", ""),
                row.get("type", ""),
                self._report_value(row.get("z", "")),
                self._report_value(row.get("theta_deg", "")),
                self._report_value(1000.0 * float(row.get("w", 0.0))),
                self._report_value(row.get("Fh", "")),
                self._report_value(row.get("axial", "")),
                self._report_value(row.get("util", "")),
                row.get("status", ""),
            ), tags=(tag,))

    def _support_force_by_code(self):
        """Map support code to final reaction row for annotation in schematic plots."""
        return {str(r.get("code", "")): r for r in self._support_result_rows()}

    def _build_main_results_tab(self):
        # Summary table is now a first-level tab.
        self.tab_summary.columnconfigure(0, weight=1)
        self.tab_summary.rowconfigure(3, weight=1)
        top = ttk.Frame(self.tab_summary, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Button(top, text="Copy table", command=self.copy_results_table).pack(side="left", padx=4)
        ttk.Label(top, textvariable=self.run_status, foreground="#555").pack(side="left", padx=10)

        support_frame = ttk.LabelFrame(self.tab_summary, text="Reinforcement / support results", padding=6)
        support_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        support_frame.columnconfigure(0, weight=1)
        support_cols = ("code", "type", "z", "angle", "w", "Fh", "axial", "util", "status")
        self.support_results_tree = ttk.Treeview(support_frame, columns=support_cols, show="headings", height=4)
        support_heads = {
            "code": "ID", "type": "Type", "z": "z (m)", "angle": "Angle (deg)",
            "w": "Δx at support (mm)", "Fh": "Horizontal force Fh (kN/m)",
            "axial": "Axial force (kN/m)", "util": "Utilization", "status": "Status",
        }
        support_widths = {"code": 70, "type": 90, "z": 70, "angle": 90, "w": 135, "Fh": 150, "axial": 135, "util": 90, "status": 95}
        for col in support_cols:
            self.support_results_tree.heading(col, text=support_heads[col], command=lambda c=col: self._sort_treeview(self.support_results_tree, c, False))
            self.support_results_tree.column(col, width=support_widths.get(col, 100), anchor="center", stretch=False)
        self.support_results_tree.tag_configure("ok", background="#ecfdf5")
        self.support_results_tree.tag_configure("capacity", background="#fee2e2")
        self.support_results_tree.tag_configure("inactive", foreground="#64748b", background="#f8fafc")
        self.support_results_tree.grid(row=0, column=0, sticky="ew")
        sy = ttk.Scrollbar(support_frame, orient="vertical", command=self.support_results_tree.yview)
        sy.grid(row=0, column=1, sticky="ns")
        sx = ttk.Scrollbar(support_frame, orient="horizontal", command=self.support_results_tree.xview)
        sx.grid(row=1, column=0, sticky="ew")
        self.support_results_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

        ttk.Label(self.tab_summary, text="Detailed depth-by-depth results", style="Status.TLabel").grid(row=2, column=0, sticky="w", padx=10, pady=(0, 0))

        self.results_table = ttk.Treeview(
            self.tab_summary,
            columns=(
                "z", "p_left", "p_right", "net",
                "eff_left", "eff_right", "u_left", "u_right",
                "K_left", "K_right", "m_left", "m_right",
                "dxmax_A", "dxmax_P", "V", "M", "w", "theta"
            ),
            show="headings",
        )
        heads = {
            "z": "z (m)", "p_left": "p_L total (kPa)", "p_right": "p_R total (kPa)", "net": "p_net (kPa)",
            "eff_left": "σ'_h,L (kPa)", "eff_right": "σ'_h,R (kPa)", "u_left": "u_L (kPa)", "u_right": "u_R (kPa)",
            "K_left": "K_L (-)", "K_right": "K_R (-)", "m_left": "m_L (-)", "m_right": "m_R (-)",
            "dxmax_A": "Δxmax,A (mm)", "dxmax_P": "Δxmax,P (mm)",
            "V": "V (kN/m)", "M": "M (kNm/m)", "w": "Δx (mm)", "theta": "θ (deg)",
        }
        widths = {"z":80, "p_left":115, "p_right":115, "net":100, "eff_left":110, "eff_right":110, "u_left":95, "u_right":95,
                  "K_left":80, "K_right":80, "m_left":80, "m_right":80, "dxmax_A":105, "dxmax_P":105,
                  "V":95, "M":100, "w":90, "theta":85}
        for col in self.results_table["columns"]:
            self.results_table.heading(col, text=heads[col])
            self.results_table.column(col, width=widths.get(col, 100), anchor="center", stretch=False)
        self.results_table.grid(row=3, column=0, sticky="nsew", padx=8, pady=8)
        y = ttk.Scrollbar(self.tab_summary, orient="vertical", command=self.results_table.yview)
        x = ttk.Scrollbar(self.tab_summary, orient="horizontal", command=self.results_table.xview)
        y.grid(row=3, column=1, sticky="ns")
        x.grid(row=4, column=0, sticky="ew", padx=8)
        self.results_table.configure(yscrollcommand=y.set, xscrollcommand=x.set)

        # Charts is also a first-level tab: scrollable two-column dashboard.
        self.tab_charts.columnconfigure(0, weight=1)
        self.tab_charts.rowconfigure(0, weight=1)
        self.charts_scroll = ScrollableFrame(self.tab_charts, width=1180)
        self.charts_scroll.grid(row=0, column=0, sticky="nsew")
        charts = self.charts_scroll.inner
        charts.columnconfigure(0, weight=1)
        charts.columnconfigure(1, weight=1)
        self.chart_limits = {}

        self.fig_pressure, self.ax_pressure, self.canvas_pressure = self._make_chart(charts, 0, 0, "Total pressure")
        self.fig_deflection, self.ax_deflection, self.canvas_deflection = self._make_chart(charts, 0, 1, "Deflection")
        self.fig_effective, self.ax_effective, self.canvas_effective = self._make_chart(charts, 1, 0, "Effective stresses")
        self.fig_water, self.ax_water, self.canvas_water = self._make_chart(charts, 1, 1, "Water stresses")
        self.fig_k, self.ax_k, self.canvas_k = self._make_chart(charts, 2, 0, "K diagram")
        self.fig_mobilization, self.ax_mobilization, self.canvas_mobilization = self._make_chart(charts, 2, 1, "Δx/Δxmax")
        self.fig_net, self.ax_net, self.canvas_net = self._make_chart(charts, 3, 0, "Net pressure")
        self.fig_rotation, self.ax_rotation, self.canvas_rotation = self._make_chart(charts, 3, 1, "Rotation")
        self.fig_shear, self.ax_shear, self.canvas_shear = self._make_chart(charts, 4, 0, "Shear")
        self.fig_moment, self.ax_moment, self.canvas_moment = self._make_chart(charts, 4, 1, "Moment")
        self.fig_conv_change, self.ax_conv_change, self.canvas_conv_change = self._make_chart(charts, 5, 0, "Energy compatibility")
        self.fig_conv_defl, self.ax_conv_defl, self.canvas_conv_defl = self._make_chart(charts, 5, 1, "Mechanism kinematics")

        # Backward aliases retained only for internal plotting calls.
        self.ax_p = self.ax_pressure
        self.canvas_p = self.canvas_pressure

    def _make_chart(self, parent, row: int, col: int, title: str):
        """Create a chart panel with embedded Matplotlib figure and local x-limits.

        The external frame title was intentionally removed; the only title shown
        is the Matplotlib axis title inside the chart. Each chart has its own
        x_min / x_max fields; blank/auto means autoscale from the calculated
        curve only.
        """
        frame = ttk.LabelFrame(parent, text=title, padding=(8, 8, 8, 10))
        frame.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        fig, ax = plt.subplots(figsize=(5.8, 4.2), dpi=100)
        fig.patch.set_facecolor(PANEL_BG)
        ax.set_facecolor(SUBTLE_BG)
        canvas = self._register_plot_canvas(FigureCanvasTkAgg(fig, master=frame))
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        controls = ttk.Frame(frame)
        controls.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)
        xmin_var = tk.StringVar(value="auto")
        xmax_var = tk.StringVar(value="auto")
        ttk.Label(controls, text="x_min").grid(row=0, column=0, sticky="w", padx=(0, 3))
        ttk.Entry(controls, textvariable=xmin_var, width=9).grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(controls, text="x_max").grid(row=0, column=2, sticky="w", padx=(0, 3))
        ttk.Entry(controls, textvariable=xmax_var, width=9).grid(row=0, column=3, sticky="w", padx=(0, 8))
        ttk.Button(controls, text="Redraw", command=self._redraw_charts_from_last).grid(row=0, column=4, sticky="e")
        coord_var = tk.StringVar(value="x: —    z: —")
        ttk.Label(controls, textvariable=coord_var, style="Muted.TLabel").grid(row=0, column=5, sticky="e", padx=(10, 0))
        controls.columnconfigure(5, weight=1)

        self.chart_limits[title] = {"xmin": xmin_var, "xmax": xmax_var, "coord": coord_var}
        self._attach_coordinate_readout(canvas, ax, coord_var)
        return fig, ax, canvas

    def _attach_coordinate_readout(self, canvas, ax, coord_var):
        def on_move(event):
            if event.inaxes is ax and event.xdata is not None and event.ydata is not None:
                try:
                    coord_var.set(f"x: {event.xdata:.3f}    z: {event.ydata:.3f} m")
                except Exception:
                    coord_var.set("x: —    z: —")
            else:
                coord_var.set("x: —    z: —")
        try:
            canvas.mpl_connect("motion_notify_event", on_move)
        except Exception:
            pass

    def _build_work_heatmaps_tab(self):
        self.tab_work.columnconfigure(0, weight=1)
        self.tab_work.rowconfigure(1, weight=1)
        top = ttk.LabelFrame(self.tab_work, text="Advanced diagnostics controls (optional / legacy heatmaps)")
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        for c in range(12):
            top.columnconfigure(c, weight=0)
        self._entry(top, 0, 0, "θ min (deg)", self.var_work_theta_min, width=8)
        self._entry(top, 0, 2, "θ max (deg)", self.var_work_theta_max, width=8)
        self._entry(top, 0, 4, "θ charts", self.var_work_theta_count, width=8)
        self._entry(top, 0, 6, "dx points", self.var_work_dx_count, width=8)
        self._entry(top, 0, 8, "z_pivot points", self.var_work_zp_count, width=8)
        ttk.Button(top, text="Generate heatmaps", command=self.generate_work_heatmaps).grid(row=0, column=10, sticky="ew", padx=8, pady=3)

        status_frame = ttk.Frame(top)
        status_frame.grid(row=1, column=0, columnspan=11, sticky="ew", padx=4, pady=3)
        status_frame.columnconfigure(0, weight=1)
        ttk.Label(status_frame, textvariable=self.var_work_status, foreground="#555", wraplength=760).grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.btn_use_best_equilibrium = ttk.Button(
            status_frame,
            text="Use best equilibrium for manual search",
            command=lambda: self._use_heatmap_candidate("equilibrium"),
            state="disabled",
        )
        self.btn_use_best_equilibrium.grid(row=0, column=1, sticky="e", padx=3)
        self.btn_use_min_work = ttk.Button(
            status_frame,
            text="Use min work for manual search",
            command=lambda: self._use_heatmap_candidate("work"),
            state="disabled",
        )
        self.btn_use_min_work.grid(row=0, column=2, sticky="e", padx=3)

        self.work_nb = ttk.Notebook(self.tab_work)
        self.work_nb.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.work_heatmap_tab = ttk.Frame(self.work_nb)
        self.work_points_tab = ttk.Frame(self.work_nb)
        self.work_nb.add(self.work_points_tab, text="Candidate diagnostics")
        self.work_nb.add(self.work_heatmap_tab, text="Legacy heatmaps")
        self.work_heatmap_tab.columnconfigure(0, weight=1)
        self.work_heatmap_tab.rowconfigure(0, weight=1)
        self.work_points_tab.columnconfigure(0, weight=1)
        self.work_points_tab.rowconfigure(1, weight=1)
        self.work_points_tab.rowconfigure(3, weight=1)

        points_top = ttk.Frame(self.work_points_tab, padding=6)
        points_top.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.accepted_points_status = tk.StringVar(value="After a general-case run, this tab shows the candidate family, selected mechanism and residual quality without recomputing heatmaps.")
        ttk.Label(points_top, textvariable=self.accepted_points_status, foreground="#555").pack(side="left", fill="x", expand=True)
        ttk.Button(points_top, text="Use selected point for manual run", command=self._use_selected_accepted_point).pack(side="right", padx=4)

        self.accepted_points_tree = ttk.Treeview(
            self.work_points_tab,
            columns=("rank", "dx", "theta", "zp", "F", "M", "W", "Fnorm", "Mnorm", "score", "Wnorm"),
            show="headings",
            height=13,
        )
        for col, label, width in (
            ("rank", "Rank", 60),
            ("dx", "dx (m)", 95),
            ("theta", "θ (deg)", 95),
            ("zp", "z_pivot (m)", 105),
            ("F", "ΣF", 110),
            ("M", "ΣM", 110),
            ("W", "Work", 110),
            ("Fnorm", "|ΣF|/scale", 115),
            ("Mnorm", "|ΣM|/scale", 115),
            ("score", "Score", 90),
            ("Wnorm", "W/Wmin", 95),
        ):
            self.accepted_points_tree.heading(col, text=label, command=lambda c=col: self._sort_accepted_points_tree(c))
            self.accepted_points_tree.column(col, width=width, anchor="center", stretch=False)
        self.accepted_points_tree.grid(row=1, column=0, sticky="nsew")
        ypts = ttk.Scrollbar(self.work_points_tab, orient="vertical", command=self.accepted_points_tree.yview)
        ypts.grid(row=1, column=1, sticky="ns")
        xpts = ttk.Scrollbar(self.work_points_tab, orient="horizontal", command=self.accepted_points_tree.xview)
        xpts.grid(row=2, column=0, sticky="ew")
        self.accepted_points_tree.configure(yscrollcommand=ypts.set, xscrollcommand=xpts.set)

        self.accepted_points_scatter_frame = ttk.Frame(self.work_points_tab, padding=(6, 4))
        self.accepted_points_scatter_frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.accepted_points_scatter_frame.columnconfigure(0, weight=1)
        self.accepted_points_scatter_frame.rowconfigure(0, weight=1)
        self.fig_accepted_points = None
        self.canvas_accepted_points = None

        self.work_scroll = ScrollableFrame(self.work_heatmap_tab, width=1180)
        self.work_scroll.grid(row=0, column=0, sticky="nsew")
        self.work_frame = self.work_scroll.inner
        self.work_frame.columnconfigure(0, weight=1)
        self.fig_work = None
        self.canvas_work = None
        self._accepted_points_records = []

    def generate_work_heatmaps(self):
        try:
            solvers = load_solver_module()
            model = self.build_model_input()
            # Work/equilibrium heatmaps follow the selected rigid-family solver.
            # For No bending they map the pure rigid wall; for General case each
            # heatmap point also performs a short bending iteration.
            selected_display = self.var_solver_display.get()
            if selected_display == "Any wall (general case)":
                model.solver_mode = "general_case"
                heatmap_func = solvers.compute_general_work_heatmap
                self._last_work_solver_display = "Any wall (general case)"
            else:
                model.solver_mode = "no_bending"
                heatmap_func = solvers.compute_no_bending_work_heatmap
                self._last_work_solver_display = "Rigid wall (no bending)"
            ndx = max(3, int(self.var_work_dx_count.get()))
            nzp = max(3, int(self.var_work_zp_count.get()))
            if selected_display == "Any wall (general case)":
                theta_values = None
                dx_values = None
                zp_values = None
                ntheta_label = 6
                self.var_work_status.set(
                    f"Computing general-case heatmaps from extreme-state admissible bounds: 6 θ values × internal dx/z_pivot grids × 3 diagnostics "
                    f"(tol_F={float(self.var_equilibrium_force_tol.get()):.4g}, tol_M={float(self.var_equilibrium_moment_tol.get()):.4g}, tol_W={float(self.var_work_band_tol.get()):.4g}) ..."
                )
            else:
                th_min = float(self.var_work_theta_min.get())
                th_max = float(self.var_work_theta_max.get())
                ntheta = max(1, int(self.var_work_theta_count.get()))
                if th_min > th_max:
                    th_min, th_max = th_max, th_min
                if ntheta == 1:
                    theta_values = [0.5 * (th_min + th_max)]
                else:
                    theta_values = [th_min + (th_max - th_min) * i / (ntheta - 1) for i in range(ntheta)]
                H = max(float(model.geometry.H_R), 1.0e-9)
                dx0 = max(0.0, float(model.movement.dx_trans))
                dx_max = max(dx0 * 3.0, 0.02 * H, 0.05)
                dx_max = min(dx_max, 0.20 * H)
                dx_values = [dx_max * i / (ndx - 1) for i in range(ndx)]
                zp_values = [H * i / (nzp - 1) for i in range(nzp)]
                ntheta_label = len(theta_values)
                self.var_work_status.set(
                    f"Computing heatmaps: {ntheta_label} θ values × {ndx} dx × {nzp} z_pivot × 3 diagnostics "
                    f"(tol_F={float(self.var_equilibrium_force_tol.get()):.4g}, tol_M={float(self.var_equilibrium_moment_tol.get()):.4g}, tol_W={float(self.var_work_band_tol.get()):.4g}) ..."
                )
            self._last_work_best_equilibrium = None
            self._last_work_min_work = None
            try:
                self.btn_use_best_equilibrium.configure(state="disabled")
                self.btn_use_min_work.configure(state="disabled")
            except Exception:
                pass
            self.update_idletasks()
            data = heatmap_func(model, theta_values=theta_values, dx_values=dx_values, z_pivot_values=zp_values, n_z=min(max(25, int(model.controls.n_points // 6)), 61))
            self._plot_work_heatmaps(data)
            self._populate_accepted_points(data)
            best_eq = data.get("best_equilibrium", {})
            best_w = data.get("best_work", {})
            self._last_work_best_equilibrium = dict(best_eq) if best_eq else None
            self._last_work_min_work = dict(best_w) if best_w else None
            try:
                self.btn_use_best_equilibrium.configure(state=("normal" if self._last_work_best_equilibrium else "disabled"))
                self.btn_use_min_work.configure(state=("normal" if self._last_work_min_work else "disabled"))
            except Exception:
                pass
            self.var_work_status.set(
                f"Heatmaps complete ({data.get('solver_family', self._last_work_solver_display)}). Shared normalized scale. Evaluations: {data.get('n_eval', 0)}. "
                f"Tolerances: tol_F={float(self.var_equilibrium_force_tol.get()):.4g}, tol_M={float(self.var_equilibrium_moment_tol.get()):.4g}, tol_W={float(self.var_work_band_tol.get()):.4g}. "
                f"Best equilibrium: dx={best_eq.get('dx', 0):.5g} m, θ={best_eq.get('theta_deg', 0):.5g}°, "
                f"z_pivot={best_eq.get('z_pivot', 0):.5g} m, |ΣF|/scale={best_eq.get('F_norm', 0):.4g}, "
                f"|ΣM|/scale={best_eq.get('M_norm', 0):.4g}. "
                f"Min work: dx={best_w.get('dx', 0):.5g} m, θ={best_w.get('theta_deg', 0):.5g}°, "
                f"z_pivot={best_w.get('z_pivot', 0):.5g} m."
            )
        except Exception as exc:
            self._last_work_best_equilibrium = None
            self._last_work_min_work = None
            try:
                self.btn_use_best_equilibrium.configure(state="disabled")
                self.btn_use_min_work.configure(state="disabled")
            except Exception:
                pass
            self.var_work_status.set(f"Work heatmap error: {exc}")
            messagebox.showerror("Work heatmap error", str(exc))

    def _populate_accepted_points(self, data: dict):
        """Populate the Accepted points tab from heatmap matrices.

        A point is accepted when both normalized residuals satisfy the user
        tolerances: |ΣF|/scale <= tol_F and |ΣM|/scale <= tol_M.
        Ranking is transparent: lowest work band first, then min |theta|, then min |dx|.
        """
        if not hasattr(self, "accepted_points_tree"):
            return
        for item in self.accepted_points_tree.get_children():
            self.accepted_points_tree.delete(item)
        self._accepted_points_records = []
        theta_values = list(data.get("theta_values", []))
        dx_values = list(data.get("dx_values", []))
        zp_values = list(data.get("z_pivot_values", []))
        work_raw = data.get("work_raw_matrices", [])
        f_norm = data.get("force_norm_matrices", [])
        m_norm = data.get("moment_norm_matrices", [])
        force_raw = data.get("force_raw_matrices", [])
        moment_raw = data.get("moment_raw_matrices", [])
        try:
            tol_f = float(self.var_equilibrium_force_tol.get())
            tol_m = float(self.var_equilibrium_moment_tol.get())
        except Exception:
            tol_f, tol_m = 0.01, 0.01
        records = []
        for it, theta in enumerate(theta_values):
            if it >= len(work_raw) or it >= len(f_norm) or it >= len(m_norm):
                continue
            for iz, zp in enumerate(zp_values):
                if iz >= len(work_raw[it]):
                    continue
                for ix, dx in enumerate(dx_values):
                    try:
                        W = float(work_raw[it][iz][ix])
                        Fn = float(f_norm[it][iz][ix])
                        Mn = float(m_norm[it][iz][ix])
                        F = float(force_raw[it][iz][ix]) if it < len(force_raw) and iz < len(force_raw[it]) and ix < len(force_raw[it][iz]) else float("nan")
                        M = float(moment_raw[it][iz][ix]) if it < len(moment_raw) and iz < len(moment_raw[it]) and ix < len(moment_raw[it][iz]) else float("nan")
                    except Exception:
                        continue
                    if not (_is_finite(W) and _is_finite(Fn) and _is_finite(Mn)):
                        continue
                    if Fn <= tol_f and Mn <= tol_m:
                        records.append({
                            "dx": float(dx),
                            "theta_deg": float(theta),
                            "z_pivot": float(zp),
                            "work_index": W,
                            "F": F,
                            "M": M,
                            "F_norm": Fn,
                            "M_norm": Mn,
                            "score": math.sqrt(Fn * Fn + Mn * Mn),
                        })
        if not records:
            self._plot_accepted_points_scatter([])
            self.accepted_points_status.set(
                f"No accepted points for tol_F={tol_f:.4g}, tol_M={tol_m:.4g}. Try relaxed tolerances or finer heatmap grids."
            )
            return
        wmin = min(max(float(r["work_index"]), 0.0) for r in records)
        if wmin <= 1.0e-30:
            wmin = 1.0
        for r in records:
            r["W_norm"] = float(r["work_index"]) / wmin
        records.sort(key=lambda r: (r["W_norm"], abs(r["theta_deg"]), abs(r["dx"]), r["z_pivot"]))
        self._accepted_points_records = records
        for rank, r in enumerate(records, start=1):
            self.accepted_points_tree.insert(
                "",
                "end",
                iid=str(rank - 1),
                values=(
                    rank,
                    f"{r['dx']:.6g}",
                    f"{r['theta_deg']:.6g}",
                    f"{r['z_pivot']:.6g}",
                    f"{r.get('F', float('nan')):.6g}",
                    f"{r.get('M', float('nan')):.6g}",
                    f"{r['work_index']:.6g}",
                    f"{r['F_norm']:.6g}",
                    f"{r['M_norm']:.6g}",
                    f"{r.get('score', math.sqrt(r['F_norm']*r['F_norm'] + r['M_norm']*r['M_norm'])):.6g}",
                    f"{r['W_norm']:.6g}",
                ),
            )
        self._plot_accepted_points_scatter(records)
        self.accepted_points_status.set(
            f"Accepted points: {len(records)} for tol_F={tol_f:.4g}, tol_M={tol_m:.4g}. "
            f"Score = sqrt((|ΣF|/scale)^2 + (|ΣM|/scale)^2). Ranked by W/Wmin, then min |θ| and min |dx|."
        )

    def _plot_accepted_points_scatter(self, records: list[dict[str, float]]):
        if not hasattr(self, "accepted_points_scatter_frame"):
            return
        for widget in self.accepted_points_scatter_frame.winfo_children():
            widget.destroy()
        fig = Figure(figsize=(7.8, 3.8), dpi=100)
        ax = fig.add_subplot(111)
        if not records:
            ax.text(0.5, 0.5, "No accepted points", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
        else:
            dx = [float(r.get("dx", 0.0)) for r in records]
            zp = [float(r.get("z_pivot", 0.0)) for r in records]
            th = [float(r.get("theta_deg", 0.0)) for r in records]
            sc = ax.scatter(dx, zp, c=th, s=36, cmap="viridis", edgecolors="black", linewidths=0.25)
            # Mark the first-ranked accepted point.
            ax.scatter([dx[0]], [zp[0]], s=90, facecolors="none", edgecolors="red", linewidths=1.6, label="selected rank 1")
            ax.set_xlabel("Δx (m)")
            ax.set_ylabel("z_pivot (m)")
            ax.invert_yaxis()
            ax.set_title("Accepted equilibrium points: Δx vs z_pivot, colored by θ")
            ax.grid(True, alpha=0.30)
            self._safe_legend(ax, loc="best", fontsize=8)
            cbar = fig.colorbar(sc, ax=ax, fraction=0.035, pad=0.02)
            cbar.set_label("θ (deg)")
        fig.tight_layout()
        canvas = self._register_plot_canvas(FigureCanvasTkAgg(fig, master=self.accepted_points_scatter_frame))
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.fig_accepted_points = fig
        self.canvas_accepted_points = canvas

    def _sort_accepted_points_tree(self, col: str):
        """Sort accepted-points table by clicked heading, toggling ascending/descending."""
        if not hasattr(self, "accepted_points_tree"):
            return
        numeric_cols = {"rank", "dx", "theta", "zp", "F", "M", "W", "Fnorm", "Mnorm", "score", "Wnorm"}
        reverse = bool(getattr(self, "_accepted_sort_reverse", {}).get(col, False))
        def key(item):
            val = self.accepted_points_tree.set(item, col)
            if col in numeric_cols:
                try:
                    return float(val)
                except Exception:
                    return float("inf")
            return str(val)
        items = list(self.accepted_points_tree.get_children(""))
        items.sort(key=key, reverse=reverse)
        for idx, item in enumerate(items):
            self.accepted_points_tree.move(item, "", idx)
        if not hasattr(self, "_accepted_sort_reverse"):
            self._accepted_sort_reverse = {}
        self._accepted_sort_reverse[col] = not reverse

    def _use_selected_accepted_point(self):
        if not getattr(self, "_accepted_points_records", None):
            messagebox.showerror("Accepted points", "No accepted point is available. Generate heatmaps first.")
            return
        sel = self.accepted_points_tree.selection()
        if not sel:
            messagebox.showerror("Accepted points", "Select an accepted point first.")
            return
        try:
            rec = self._accepted_points_records[int(sel[0])]
            self.var_dx_trans.set(float(rec.get("dx", 0.0)))
            self.var_theta_rot.set(float(rec.get("theta_deg", 0.0)))
            self.var_z_pivot.set(float(rec.get("z_pivot", 0.0)))
            self.var_solver_display.set(getattr(self, "_last_work_solver_display", "Rigid wall (no bending)"))
            self.var_no_bending_mode.set("Manual")
            self.var_work_status.set(
                f"Using accepted point as manual movement: dx={float(rec.get('dx', 0.0)):.6g} m, "
                f"θ={float(rec.get('theta_deg', 0.0)):.6g}°, z_pivot={float(rec.get('z_pivot', 0.0)):.6g} m. Running solver ..."
            )
            self.update_idletasks()
            self.run_solver()
        except Exception as exc:
            messagebox.showerror("Accepted points", str(exc))

    def _use_heatmap_candidate(self, candidate_kind: str):
        """Use a heatmap candidate as prescribed manual movement and run it.

        candidate_kind:
            "equilibrium" -> best ΣF=0 & ΣM=0 residual from the heatmaps
            "work"        -> minimum work candidate from the heatmaps
        """
        if candidate_kind == "work":
            rec = self._last_work_min_work
            label = "minimum-work"
        else:
            rec = self._last_work_best_equilibrium
            label = "best-equilibrium"
        if not rec:
            messagebox.showerror("Heatmap candidate", "No heatmap candidate is available. Generate heatmaps first.")
            return
        try:
            dx = float(rec.get("dx", 0.0))
            theta = float(rec.get("theta_deg", 0.0))
            zp = float(rec.get("z_pivot", 0.0))
            self.var_dx_trans.set(dx)
            self.var_theta_rot.set(theta)
            self.var_z_pivot.set(zp)
            self.var_solver_display.set(getattr(self, "_last_work_solver_display", "Rigid wall (no bending)"))
            self.var_no_bending_mode.set("Manual")
            self.var_work_status.set(
                f"Using {label} heatmap candidate as manual movement: "
                f"dx={dx:.6g} m, θ={theta:.6g}°, z_pivot={zp:.6g} m. Running solver ..."
            )
            self.update_idletasks()
            self.run_solver()
        except Exception as exc:
            messagebox.showerror("Heatmap candidate", str(exc))

    def _plot_work_heatmaps(self, data: dict):
        import numpy as np
        for widget in self.work_frame.winfo_children():
            widget.destroy()

        theta_values = list(data.get("theta_values", []))
        dx_values = list(data.get("dx_values", []))
        zp_values = list(data.get("z_pivot_values", []))
        work_mats = data.get("work_matrices", [])
        force_mats = data.get("force_norm_matrices", [])
        moment_mats = data.get("moment_norm_matrices", [])
        ntheta = len(theta_values)
        if ntheta == 0 or not work_mats or not force_mats or not moment_mats:
            return

        # One row per θ. Three columns per row: normalized Work, |ΣF|, |ΣM|.
        ncols = 3
        nrows = ntheta
        all_vals = []
        for mats in (work_mats, force_mats, moment_mats):
            for mat in mats:
                arr = np.array(mat, dtype=float)
                all_vals.extend(arr[np.isfinite(arr)].ravel().tolist())
        if not all_vals:
            vmin, vmax = 0.0, 1.0
        else:
            vmin = 0.0
            vmax = max(all_vals)
            if vmax <= 1.0e-15:
                vmax = 1.0
            # Avoid one extreme residual making every other chart blank.
            vmax_p = float(np.percentile(np.array(all_vals, dtype=float), 98.0))
            vmax = max(min(vmax, vmax_p if vmax_p > 0 else vmax), 1.0)

        fig_h = max(2.65 * nrows, 3.4)
        self.fig_work = Figure(figsize=(12.2, fig_h), dpi=100)
        extent = [min(dx_values), max(dx_values), max(zp_values), min(zp_values)]
        titles = ("Work / max(Work)", "|ΣF| / ∫|p|dz", "|ΣM| / ∫|p·arm|dz")
        mat_groups = (work_mats, force_mats, moment_mats)
        mappable = None

        best_eq = data.get("best_equilibrium", {}) or {}
        best_w = data.get("best_work", {}) or {}
        theta_tol = max(1.0e-9, 0.5 * abs(theta_values[1] - theta_values[0]) if len(theta_values) > 1 else 1.0e-9)

        for r, theta in enumerate(theta_values):
            for c in range(ncols):
                ax = self.fig_work.add_subplot(nrows, ncols, r * ncols + c + 1)
                arr = np.array(mat_groups[c][r], dtype=float)
                mappable = ax.imshow(arr, aspect="auto", origin="upper", extent=extent, vmin=vmin, vmax=vmax)
                if r == 0:
                    ax.set_title(titles[c], fontsize=10)
                if c == 0:
                    ax.set_ylabel(f"θ={theta:.3g}°\nz_pivot (m)")
                else:
                    ax.set_ylabel("z_pivot (m)")
                if r == nrows - 1:
                    ax.set_xlabel("dx (m)")
                else:
                    ax.set_xlabel("")
                ax.grid(False)

                # User-visible equilibrium tolerance contours.
                # Force map: white contour at tol_F; Moment map: white contour at tol_M.
                try:
                    if c in (1, 2):
                        tol_level = float(self.var_equilibrium_force_tol.get()) if c == 1 else float(self.var_equilibrium_moment_tol.get())
                        if np.isfinite(tol_level) and float(np.nanmin(arr)) <= tol_level <= float(np.nanmax(arr)):
                            xx = np.array(dx_values, dtype=float)
                            yy = np.array(zp_values, dtype=float)
                            X, Y = np.meshgrid(xx, yy)
                            ax.contour(X, Y, arr, levels=[tol_level], colors="white", linewidths=1.1)
                except Exception:
                    pass

                # Mark best equilibrium on all three panels of the corresponding θ row.
                try:
                    if abs(float(best_eq.get("theta_deg", 1e99)) - float(theta)) <= theta_tol:
                        ax.plot(float(best_eq.get("dx", 0.0)), float(best_eq.get("z_pivot", 0.0)),
                                marker="o", markersize=6, markerfacecolor="none", markeredgecolor="white", linewidth=1.4)
                except Exception:
                    pass
                # Mark minimum-work candidate with a small x on the Work map only.
                try:
                    if c == 0 and abs(float(best_w.get("theta_deg", 1e99)) - float(theta)) <= theta_tol:
                        ax.plot(float(best_w.get("dx", 0.0)), float(best_w.get("z_pivot", 0.0)),
                                marker="x", markersize=6, color="white", linewidth=1.2)
                except Exception:
                    pass

        if mappable is not None:
            self.fig_work.subplots_adjust(right=0.90, hspace=0.42, wspace=0.32)
            cax = self.fig_work.add_axes([0.925, 0.16, 0.018, 0.70])
            cb = self.fig_work.colorbar(mappable, cax=cax)
            cb.set_label("Normalized diagnostic value")
        else:
            self.fig_work.tight_layout()

        note = ttk.Label(
            self.work_frame,
            text=("Rows correspond to fixed θ values. Columns show normalized work, normalized force residual, "
                  "and normalized moment residual. White circle = best equilibrium; white × = minimum work; "
                  "white contours = tol_F/tol_M."),
            foreground="#555",
            wraplength=1100,
        )
        note.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 4))
        self.canvas_work = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_work, master=self.work_frame))
        self.canvas_work.draw()
        self.canvas_work.get_tk_widget().grid(row=1, column=0, sticky="nsew")


    # ============================================================
    # STAGES ANIMATION (excavation sequence preview)
    # ============================================================
    STAGE_ANIM_OPTIONS = {
        "Total horizontal pressure": "pressure",
        "Deflection": "deflection",
        "Moment": "moment",
        "Shear": "shear",
        "Rotation": "rotation",
        "Water stresses": "water",
        "Effective stresses": "effective",
        "Net pressure": "net",
    }

    def _build_stages_animation_tab(self):
        tab = self.tab_stages_animation
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        controls = ttk.LabelFrame(tab, text="Stages animation controls", padding=8)
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        for c in range(13):
            controls.columnconfigure(c, weight=1)
        ttk.Label(controls, text="Diagram").grid(row=0, column=0, sticky="w", padx=4)
        self._stage_quantity_combo = ttk.Combobox(
            controls,
            textvariable=self.var_stage_anim_quantity,
            values=list(self.STAGE_ANIM_OPTIONS.keys()),
            state="readonly",
            width=25,
        )
        self._stage_quantity_combo.grid(row=1, column=0, sticky="ew", padx=4)
        self._stage_quantity_combo.bind("<<ComboboxSelected>>", lambda *_: self._on_stage_anim_quantity_changed())
        ttk.Label(controls, text="Frame duration (ms)").grid(row=0, column=1, sticky="w", padx=4)
        ttk.Entry(controls, textvariable=self.var_stage_anim_speed_ms, width=10).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(controls, text="x_min").grid(row=0, column=2, sticky="w", padx=4)
        ttk.Entry(controls, textvariable=self.var_stage_anim_x_min, width=10).grid(row=1, column=2, sticky="ew", padx=4)
        ttk.Label(controls, text="x_max").grid(row=0, column=3, sticky="w", padx=4)
        ttk.Entry(controls, textvariable=self.var_stage_anim_x_max, width=10).grid(row=1, column=3, sticky="ew", padx=4)
        ttk.Button(controls, text="Smart x", command=self._smart_stage_anim_x_limits).grid(row=1, column=4, sticky="ew", padx=4)
        self.stage_anim_build_button = ttk.Button(controls, text="Build stages animation", style="WaterRun.TButton", command=self.run_stages_animation)
        self.stage_anim_build_button.grid(row=1, column=5, sticky="ew", padx=6)
        ttk.Button(controls, text="Play", style="WaterPlay.TButton", command=self.play_stages_animation).grid(row=1, column=6, sticky="ew", padx=4)
        ttk.Button(controls, text="Pause", style="Pause.TButton", command=self.pause_stages_animation).grid(row=1, column=7, sticky="ew", padx=4)
        ttk.Label(
            controls,
            text="One common slider drives both the geometry animation and the selected result diagram. Smart x uses all solved stage/substage frames.",
            foreground="#555", wraplength=430,
        ).grid(row=1, column=8, columnspan=5, sticky="w", padx=8)

        self.stage_anim_status = tk.StringVar(value="Define excavation stages, then build the stages animation.")
        status_box = ttk.Frame(tab)
        status_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))
        status_box.columnconfigure(0, weight=1)
        ttk.Label(status_box, textvariable=self.stage_anim_status, foreground="#555").grid(row=0, column=0, sticky="ew")
        self.stage_anim_progress = ttk.Progressbar(status_box, mode="determinate", maximum=1, value=0)
        self.stage_anim_progress.grid(row=1, column=0, sticky="ew", pady=(3, 0))

        body = ttk.Panedwindow(tab, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew", padx=8, pady=6)
        geom_frame = ttk.LabelFrame(body, text="Geometry animation (stages)", padding=6)
        chart_frame = ttk.LabelFrame(body, text="Chart animation", padding=6)
        body.add(geom_frame, weight=3)
        body.add(chart_frame, weight=3)

        for fr in (geom_frame, chart_frame):
            fr.columnconfigure(0, weight=1)
            fr.rowconfigure(0, weight=1)
        self.fig_stage_anim = Figure(figsize=(7.2, 5.8), dpi=100)
        self.ax_stage_anim = self.fig_stage_anim.add_subplot(111)
        self.canvas_stage_anim = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_stage_anim, master=geom_frame))
        self.canvas_stage_anim.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        self.fig_stage_chart_anim = Figure(figsize=(7.2, 5.8), dpi=100)
        self.ax_stage_chart_anim = self.fig_stage_chart_anim.add_subplot(111)
        self.canvas_stage_chart_anim = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_stage_chart_anim, master=chart_frame))
        self.canvas_stage_chart_anim.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Common slider: one frame selector synchronizes geometry and chart panels.
        slider_box = ttk.Frame(tab)
        slider_box.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 8))
        slider_box.columnconfigure(1, weight=1)
        ttk.Label(slider_box, text="Stage frame").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.stage_anim_slider = ttk.Scale(slider_box, from_=1, to=1, orient="horizontal", variable=self.var_stage_anim_frame, command=self._on_stage_anim_slider)
        self.stage_anim_slider.grid(row=0, column=1, sticky="ew")
        self.stage_anim_frame_label = ttk.Label(slider_box, text="1 / 1", width=12, anchor="e")
        self.stage_anim_frame_label.grid(row=0, column=2, sticky="e", padx=(8, 0))

        self._refresh_stages_animation_items()
        self._draw_stages_animation_frame(0)

    def _refresh_stages_animation_items(self):
        """Build the staged excavation animation path.

        The sequence now starts from Stage 0 (no excavation, no support active).
        For each main excavation stage i, the optional intermediate-drop count
        first lowers the excavation level with only the already-installed
        supports 1..i-1 active.  The new support i is activated only at the
        corresponding main stage line.  Therefore, for m=4 and Stage 1:

            Stage 0 -> Stage 0.1 -> ... -> Stage 0.4 -> Stage 1 + support 1

        Then the same logic repeats before Stage 2, where support 2 is activated
        only when Stage 2 is reached.
        """
        rows = self._stage_rows() if hasattr(self, "stage_tree") else []
        if not rows:
            rows = [{"stage":"Stage 1", "z": self._height_right() - self._height_left(), "note":"Final excavation"}]
        try:
            m = max(0, int(self.var_stage_intermediate_count.get()))
        except Exception:
            m = 0
            try:
                self.var_stage_intermediate_count.set(0)
            except Exception:
                pass

        items = []
        # Stage 0 is the construction-start state: original ground, no excavation,
        # no anchors/props activated.  This must be the first animation frame.
        items.append({
            "stage": "Stage 0",
            "z": 0.0,
            "comment": "Initial condition: no excavation; no supports active",
            "main_stage": 0,
            "substep": 0,
            "is_main_stage": True,
            "active_support_count": 0,
        })

        prev_z = 0.0
        n = len(rows)
        qL_apply_stage, qR_apply_stage = self._stage_surcharge_indices(n)
        items[0]["load_index"] = 0
        items[0]["qL_active"] = 0 >= qL_apply_stage
        items[0]["qR_active"] = 0 >= qR_apply_stage
        for i, r in enumerate(rows, start=1):
            z_main = float(r.get("z", 0.0))
            main_label = str(r.get("stage", f"Stage {i}"))
            if i == n:
                main_label = f"Stage {i} (final)"

            # Intermediate excavation drops BEFORE main Stage i.  The support
            # associated with Stage i is not yet installed, so only supports
            # 1..i-1 are active.  For i=1 this correctly means no active support.
            for k in range(1, m + 1):
                z_sub = prev_z + (z_main - prev_z) * k / (m + 1)
                prefix = i - 1
                items.append({
                    "stage": f"Stage {prefix}.{k}",
                    "z": z_sub,
                    "comment": f"Intermediate drop {k}/{m} before Stage {i}; supports 1..{max(0, i-1)} active",
                    "main_stage": i - 1,
                    "substep": k,
                    "is_main_stage": False,
                    "active_support_count": max(0, i - 1),
                    "load_index": i - 1,
                    "qL_active": (i - 1) >= qL_apply_stage,
                    "qR_active": (i - 1) >= qR_apply_stage,
                })

            # At the main stage line, support i is activated.  Stage 1 therefore
            # shows support 1, Stage 2 shows supports 1+2, etc.
            items.append({
                "stage": main_label,
                "z": z_main,
                "comment": str(r.get("note", "")),
                "main_stage": i,
                "substep": 0,
                "is_main_stage": True,
                "active_support_count": i,
                "load_index": i,
                "qL_active": i >= qL_apply_stage,
                "qR_active": i >= qR_apply_stage,
            })
            prev_z = z_main

        # Optional post-excavation load stage N+1. This is a real visible
        # construction frame when either surcharge is requested after the final
        # excavation. No geometry changes occur; only the load state changes.
        if qL_apply_stage == n + 1 or qR_apply_stage == n + 1:
            items.append({
                "stage": f"Stage {n+1} (post-excavation loading)",
                "z": prev_z,
                "comment": "Post-excavation loading stage: excavation already at final level",
                "main_stage": n + 1,
                "substep": 0,
                "is_main_stage": True,
                "is_post_loading_stage": True,
                "active_support_count": n,
                "load_index": n + 1,
                "qL_active": (n + 1) >= qL_apply_stage,
                "qR_active": (n + 1) >= qR_apply_stage,
            })

        self.stage_animation_items = items
        if hasattr(self, "stage_anim_slider"):
            try:
                self.stage_anim_slider.configure(to=max(1, len(items)))
                self.var_stage_anim_frame.set(min(max(1, int(self.var_stage_anim_frame.get())), max(1, len(items))))
            except Exception:
                pass
        if hasattr(self, "stage_anim_frame_label"):
            try:
                self.stage_anim_frame_label.configure(text=f"{int(self.var_stage_anim_frame.get())} / {max(1, len(items))}")
            except Exception:
                pass
        return items

    def _stage_support_rows_for_animation(self, result=None, model=None):
        """Return supports sorted top-to-bottom and enriched with force results when available.

        The stage-animation chart must use the stage-specific model/result, not
        the final global result.  Otherwise the geometry may advance while the
        plotted forces remain frozen at the last full analysis.
        """
        if model is None:
            model = getattr(self, "last_model", None)
        if result is None:
            result = getattr(self, "last_result", None)
        supports = []
        try:
            if model is not None:
                supports = [dict(s) for s in list(getattr(model, "reinforcement_supports", []) or [])]
        except Exception:
            supports = []
        if not supports and hasattr(self, "_sync_reinforcement_to_solver_silent"):
            try:
                self._sync_reinforcement_to_solver_silent()
                supports = [dict(s) for s in list(getattr(self, "_support_elements", []) or [])]
            except Exception:
                supports = []
        by_code = {str(s.get("code", f"S{i+1}")): s for i, s in enumerate(supports)}
        try:
            for rr in self._support_result_rows(result=result, model=model):
                code = str(rr.get("code", ""))
                if code in by_code:
                    by_code[code].update({
                        "Fh": float(rr.get("Fh", 0.0) or 0.0),
                        "axial": float(rr.get("axial", 0.0) or 0.0),
                        "status": str(rr.get("status", "")),
                    })
        except Exception:
            pass
        rows = list(by_code.values()) if by_code else supports
        rows.sort(key=lambda s: float(s.get("z", 0.0) or 0.0))
        return rows

    def _interp_stage_deflection(self, result, z0):
        """Interpolate stage deflection at support installation depth."""
        try:
            zz = [float(v) for v in list(getattr(result, "z", []) or [])]
            ww = [float(v) for v in list(getattr(result, "deflection", []) or [])]
            if not zz or not ww:
                return 0.0
            z0 = float(z0)
            if z0 <= zz[0]:
                return float(ww[0])
            if z0 >= zz[-1]:
                return float(ww[-1])
            for ii in range(1, min(len(zz), len(ww))):
                if zz[ii] >= z0:
                    z1, z2 = zz[ii-1], zz[ii]
                    w1, w2 = ww[ii-1], ww[ii]
                    if abs(z2 - z1) <= 1.0e-15:
                        return float(w2)
                    t = (z0 - z1) / (z2 - z1)
                    return float(w1 + t * (w2 - w1))
            return float(ww[-1])
        except Exception:
            return 0.0

    def _stage_model_for_animation_item(self, base_model, item, all_supports):
        """Create a real analysis model for one stage/substage animation frame."""
        model = copy.deepcopy(base_model)
        z_current = max(0.0, float(item.get("z", 0.0) or 0.0))
        H_R = float(model.geometry.H_R)
        model.geometry.H_L = max(1.0e-6, H_R - z_current)

        # Stage-dependent surcharge application.  q_L/q_R in Model inputs are
        # the final magnitudes; here they are either active or zero depending
        # on the staged load selectors.
        try:
            model.left.q = float(model.left.q) if bool(item.get("qL_active", True)) else 0.0
        except Exception:
            pass
        try:
            model.right.q = float(model.right.q) if bool(item.get("qR_active", True)) else 0.0
        except Exception:
            pass

        # Do not allow the left-side water level to lie above the current
        # excavation surface in a staged frame.  This mirrors the main model
        # validation but uses the temporary stage excavation level.
        try:
            model.left.z_w = max(float(model.left.z_w), z_current)
        except Exception:
            pass

        active_count = max(0, min(int(item.get("active_support_count", 0) or 0), len(all_supports)))
        model.reinforcement_supports = [copy.deepcopy(s) for s in all_supports[:active_count]]
        return model

    def run_stages_animation(self):
        """Build stage-animation frames without blocking the Tk event loop.

        The previous implementation solved all frames in the button callback.
        For difficult nonlinear/contact cases this made Windows mark the
        application as "Not Responding" until the full sequence completed.
        Here the heavy solve loop runs in a worker thread and the GUI is
        updated through a queue and an after() polling callback.  Tk widgets
        and Matplotlib canvases are touched only from the main thread.
        """
        if getattr(self, "_stage_anim_worker_running", False):
            self.stage_anim_status.set("Stages animation is already building...")
            return
        items = self._refresh_stages_animation_items()
        if not items:
            return
        try:
            solvers = load_solver_module()
            base_model = self.build_model_input()
        except Exception as exc:
            messagebox.showerror("Stages animation", f"Could not build the staged analysis model:\n{exc}")
            return

        try:
            all_supports = [copy.deepcopy(s) for s in list(getattr(base_model, "reinforcement_supports", []) or [])]
            all_supports.sort(key=lambda s: float(s.get("z", 0.0) or 0.0))
        except Exception:
            all_supports = []

        self._stage_anim_worker_running = True
        self._stage_anim_queue = queue.Queue()
        self._stage_anim_total_frames = len(items)
        self._stage_anim_partial_items = []
        try:
            self.stage_anim_progress.configure(maximum=max(1, len(items)), value=0)
        except Exception:
            pass
        try:
            self.stage_anim_build_button.state(["disabled"])
        except Exception:
            pass
        self.stage_anim_status.set(f"Stages animation: solving frames 0/{len(items)}...")
        self.update_idletasks()

        def worker():
            previous_result = None
            installed_support_offsets = {}
            solved_items = []
            for i, item in enumerate(items, start=1):
                stage_item = dict(item)
                try:
                    active_n = max(0, min(int(stage_item.get("active_support_count", 0) or 0), len(all_supports)))
                    for si in range(active_n):
                        code = str(all_supports[si].get("code", f"S{si+1}"))
                        if code not in installed_support_offsets:
                            installed_support_offsets[code] = self._interp_stage_deflection(previous_result, all_supports[si].get("z", 0.0)) if previous_result is not None else 0.0
                    stage_supports = [copy.deepcopy(sup) for sup in all_supports]
                    for sup in stage_supports:
                        code = str(sup.get("code", ""))
                        if code in installed_support_offsets:
                            sup["install_w"] = float(installed_support_offsets[code])
                    model = self._stage_model_for_animation_item(base_model, stage_item, stage_supports)
                    if previous_result is not None:
                        try:
                            model.initial_deflection = list(getattr(previous_result, "deflection", []) or [])
                        except Exception:
                            pass
                    result = solvers.solve(model)
                    previous_result = result
                    stage_item["model"] = model
                    stage_item["result"] = result
                    try:
                        stage_item["status"] = str(result.summary.get("status", ""))
                    except Exception:
                        stage_item["status"] = ""
                except Exception as exc:
                    stage_item["model"] = None
                    stage_item["result"] = None
                    stage_item["status"] = "error"
                    stage_item["error"] = str(exc)
                solved_items.append(stage_item)
                self._stage_anim_queue.put(("progress", i, len(items), stage_item, list(solved_items)))
            self._stage_anim_queue.put(("done", list(solved_items)))

        threading.Thread(target=worker, daemon=True).start()
        self.after(75, self._poll_stage_animation_build)

    def _poll_stage_animation_build(self):
        """Poll background staged-animation solve progress and update the GUI."""
        qobj = getattr(self, "_stage_anim_queue", None)
        if qobj is None:
            return
        try:
            while True:
                msg = qobj.get_nowait()
                if not msg:
                    continue
                kind = msg[0]
                if kind == "progress":
                    _, i, total, stage_item, partial_items = msg
                    self._stage_anim_partial_items = partial_items
                    self.stage_animation_items = partial_items
                    try:
                        self.stage_anim_progress.configure(maximum=max(1, total), value=i)
                    except Exception:
                        pass
                    self.stage_anim_status.set(f"Stages animation: solved frame {i}/{total} — {stage_item.get('stage','')}")
                    # Keep the UI alive and show the most recently completed frame.
                    try:
                        self.stage_anim_slider.configure(to=max(1, len(partial_items)))
                        self.var_stage_anim_frame.set(len(partial_items))
                        self._draw_stages_animation_frame(len(partial_items) - 1)
                    except Exception:
                        pass
                elif kind == "done":
                    solved_items = msg[1]
                    self.stage_animation_items = solved_items
                    qkey = self.STAGE_ANIM_OPTIONS.get(self.var_stage_anim_quantity.get(), "pressure")
                    vals = [it for it in solved_items if it.get("result") is not None]
                    try:
                        xmin, xmax = self._smart_water_x_range([{"result": it.get("result")} for it in vals], qkey, self.last_result)
                        self.var_stage_anim_x_min.set(xmin)
                        self.var_stage_anim_x_max.set(xmax)
                    except Exception:
                        pass
                    try:
                        self.stage_anim_slider.configure(to=max(1, len(solved_items)))
                        self.var_stage_anim_frame.set(1)
                        self.stage_anim_progress.configure(maximum=max(1, len(solved_items)), value=len(solved_items))
                    except Exception:
                        pass
                    self._draw_stages_animation_frame(0)
                    n_ok = sum(1 for it in solved_items if it.get("result") is not None)
                    self.stage_anim_status.set(f"Stages animation ready: {n_ok}/{len(solved_items)} frames solved; common slider controls geometry and chart.")
                    self._stage_anim_worker_running = False
                    try:
                        self.stage_anim_build_button.state(["!disabled"])
                    except Exception:
                        pass
                    return
        except queue.Empty:
            pass
        if getattr(self, "_stage_anim_worker_running", False):
            self.after(75, self._poll_stage_animation_build)

    def _smart_stage_anim_x_limits(self):
        """Select x limits from all solved stage/substage frames for the active diagram."""
        q = self.STAGE_ANIM_OPTIONS.get(self.var_stage_anim_quantity.get(), "pressure")
        items = getattr(self, "stage_animation_items", []) or []
        xmin, xmax = self._smart_water_x_range(items, q, self.last_result)
        try:
            self.var_stage_anim_x_min.set(xmin)
            self.var_stage_anim_x_max.set(xmax)
        except Exception:
            pass
        try:
            self._draw_stage_chart_frame(max(0, int(self.var_stage_anim_frame.get()) - 1))
        except Exception:
            pass

    def _on_stage_anim_quantity_changed(self):
        q=self.STAGE_ANIM_OPTIONS.get(self.var_stage_anim_quantity.get(),"pressure")
        items = getattr(self, "stage_animation_items", []) or []
        xmin,xmax=self._smart_water_x_range(items,q,self.last_result)
        try:
            self.var_stage_anim_x_min.set(xmin); self.var_stage_anim_x_max.set(xmax)
        except Exception:
            pass
        self._draw_stages_animation_frame(max(0, int(self.var_stage_anim_frame.get())-1))

    def _on_stage_anim_slider(self, value=None):
        try:
            idx = int(round(float(value if value is not None else self.var_stage_anim_frame.get()))) - 1
        except Exception:
            idx = 0
        self._draw_stages_animation_frame(idx)

    def play_stages_animation(self):
        self._stage_anim_playing = True
        self._play_stages_animation_step()

    def pause_stages_animation(self):
        self._stage_anim_playing = False

    def _play_stages_animation_step(self):
        if not getattr(self, "_stage_anim_playing", False):
            return
        items = getattr(self, "stage_animation_items", None) or self._refresh_stages_animation_items()
        n = max(1, len(items))
        try:
            cur = int(self.var_stage_anim_frame.get())
        except Exception:
            cur = 1
        nxt = cur + 1 if cur < n else 1
        self.var_stage_anim_frame.set(nxt)
        self._draw_stages_animation_frame(nxt - 1)
        try:
            delay = max(100, int(self.var_stage_anim_speed_ms.get()))
        except Exception:
            delay = 650
        self.after(delay, self._play_stages_animation_step)

    def _draw_stages_animation_frame(self, idx=0):
        if not hasattr(self, "ax_stage_anim"):
            return
        items = getattr(self, "stage_animation_items", None) or self._refresh_stages_animation_items()
        if not items:
            return
        idx = max(0, min(int(idx), len(items)-1))
        H_R = self._height_right(); H_L = self._height_left(); z_ex = H_R - H_L
        z_current = float(items[idx]["z"])
        x_ext = max(6.0, 0.6*float(H_R))
        stage_result = items[idx].get("result") if isinstance(items[idx], dict) else None
        stage_model = items[idx].get("model") if isinstance(items[idx], dict) else None
        supports = self._stage_support_rows_for_animation(result=stage_result, model=stage_model)
        active_count = min(int(items[idx].get("active_support_count", idx + 1)), len(supports))
        ax = self.ax_stage_anim
        ax.clear()
        ax.axvspan(-x_ext, 0, ymin=0, ymax=1, color="#fff1f2", alpha=0.40)
        ax.axvspan(0, x_ext, ymin=0, ymax=1, color="#f0f9ff", alpha=0.45)
        ax.fill_between([-x_ext, 0], [0, 0], [z_current, z_current], color="#ffffff", alpha=0.94, zorder=1)
        ax.plot([0, 0], [0, H_R], color="black", linewidth=3, zorder=3)
        ax.hlines(0, 0, x_ext, colors="#7c2d12", linewidth=2.2)
        ax.hlines(z_current, -x_ext, 0, colors="#7c2d12", linewidth=2.2)
        ax.text(-0.96*x_ext, z_current, f"{items[idx]['stage']}  z={z_current:.3g} m", color="#7c2d12", fontsize=11, va="bottom")
        main_stage_rows = self._stage_rows() if hasattr(self, "stage_tree") else []
        if not main_stage_rows:
            main_stage_rows = [{"stage": "Stage 1", "z": z_ex}]
        current_main = int(items[idx].get("main_stage", idx + 1))
        for j, it in enumerate(main_stage_rows, start=1):
            z = float(it.get("z", 0.0))
            ls = "-" if j == current_main and items[idx].get("is_main_stage", False) else "--"
            lw = 2.0 if j == current_main else 1.2
            alpha = 0.95 if j == current_main else 0.55
            ax.hlines(z, -x_ext, 0, colors="#a16207", linestyles=ls, linewidth=lw, alpha=alpha)
            ax.text(-0.98*x_ext, z, str(it.get("stage", f"Stage {j}")), color="#92400e", fontsize=8, va="bottom", alpha=alpha)
        if not items[idx].get("is_main_stage", True):
            ax.hlines(z_current, -x_ext, 0, colors="#dc2626", linestyles=":", linewidth=2.0, alpha=0.95)
            ax.text(-0.96*x_ext, z_current, items[idx]["stage"], color="#dc2626", fontsize=8, va="top")
        ax.hlines(z_ex, -x_ext, 0, colors="#7c2d12", linewidth=1.4, alpha=0.55)
        ax.text(-0.4*x_ext, z_ex, "Final excavation", color="#7c2d12", fontsize=9, va="bottom", alpha=0.75)

        # Stage-dependent surcharge visualization. These arrows are drawn only
        # after the selected construction stage has activated the corresponding
        # surcharge. q_R acts on the retained ground surface; q_L acts on the
        # current excavation-side ground surface.
        try:
            qL_val = float(self.var_q_L.get())
        except Exception:
            qL_val = 0.0
        try:
            qR_val = float(self.var_q_R.get())
        except Exception:
            qR_val = 0.0
        def _draw_stage_surcharge(side, zsurf, qval, active, color):
            if not active or abs(float(qval or 0.0)) <= 1.0e-12:
                return
            if side == "L":
                xs = [-0.88*x_ext, -0.70*x_ext, -0.52*x_ext, -0.34*x_ext, -0.16*x_ext]
                label_x = -0.82*x_ext
                ha = "left"
                txt = f"q_L = {qval:.3g} kPa"
            else:
                xs = [0.16*x_ext, 0.34*x_ext, 0.52*x_ext, 0.70*x_ext, 0.88*x_ext]
                label_x = 0.16*x_ext
                ha = "left"
                txt = f"q_R = {qval:.3g} kPa"
            arrow_len = max(0.18, 0.025*H_R)
            for xx in xs:
                ax.annotate("", xy=(xx, zsurf + arrow_len), xytext=(xx, zsurf - 0.06),
                            arrowprops=dict(arrowstyle="-|>", color=color, lw=1.25, alpha=0.90), zorder=7)
            ax.text(label_x, zsurf - 0.12, txt, color=color, fontsize=9, ha=ha, va="top", zorder=8,
                    bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor=color, alpha=0.78))
        _draw_stage_surcharge("L", z_current, qL_val, bool(items[idx].get("qL_active", False)), "#dc2626")
        _draw_stage_surcharge("R", 0.0, qR_val, bool(items[idx].get("qR_active", False)), "#9333ea")
        if items[idx].get("is_post_loading_stage"):
            ax.text(0.02*x_ext, max(0.25, min(H_R*0.08, 0.8)), "Stage N+1: post-excavation loading",
                    color="#9333ea", fontsize=10, ha="left", va="bottom", zorder=8,
                    bbox=dict(boxstyle="round,pad=0.20", facecolor="white", edgecolor="#9333ea", alpha=0.75))

        # Staged reinforcement activation: Stage 1 shows support 1, Stage 2 support 1+2, etc.
        for k, sup in enumerate(supports):
            z = float(sup.get("z", 0.0) or 0.0)
            code = str(sup.get("code", f"S{k+1}"))
            typ = str(sup.get("type", "support")).lower()
            theta = math.radians(float(sup.get("theta_deg", 0.0) or 0.0))
            is_active = k < active_count
            color = "#2563eb" if is_active else "#9ca3af"
            lw = 2.0 if is_active else 1.2
            ls = "-" if is_active else "--"
            alpha = 0.95 if is_active else 0.45
            if typ == "prop":
                x2 = -min(x_ext*0.75, float(sup.get("L", 3.0) or 3.0))
                ax.plot([0, x2], [z, z], color=color, linewidth=lw, linestyle=ls, alpha=alpha, zorder=4)
                label_x = x2 - 0.15
                ha = "right"
            else:
                L = float(sup.get("L", sup.get("Lfree", 0.0)) or 0.0)
                if L <= 0.0:
                    L = float(sup.get("Lfree", 0.0) or 0.0) + float(sup.get("Lbond", 0.0) or 0.0)
                if L <= 0.0:
                    L = x_ext*0.45
                x2 = min(x_ext*0.95, L*math.cos(theta))
                z2 = z - L*math.sin(theta)
                z2 = max(-0.1, min(H_R+0.1, z2))
                ax.plot([0, x2], [z, z2], color=color, linewidth=lw, linestyle=ls, alpha=alpha, zorder=4)
                ax.plot([0], [z], marker="o", color=color, markersize=4 if is_active else 3, alpha=alpha, zorder=5)
                label_x = min(x_ext*0.95, x2 + 0.15)
                ha = "left"
            F = float(sup.get("axial", sup.get("Fh", 0.0)) or 0.0)
            if is_active:
                ax.text(label_x, z, f"{code}\nF={F:.1f} kN/m", color=color, fontsize=8, va="center", ha=ha, zorder=6)
            else:
                ax.text(label_x, z, code, color=color, fontsize=8, va="center", ha=ha, alpha=alpha, zorder=6)

        if not supports:
            rtype = self.var_reinf_type.get() if hasattr(self, "var_reinf_type") else "No reinforcement"
            ax.text(0.30*x_ext, 0.55*H_R, rtype, ha="center", va="center", fontsize=13, color="#334155", alpha=0.75)
        ax.set_xlim(-x_ext, x_ext); ax.set_ylim(H_R+0.25, -0.25)
        ax.set_xlabel("x (m, true scale)"); ax.set_ylabel("z (m)")
        ax.set_title(f"{items[idx]['stage']} — frame {idx+1}/{len(items)} — "f"active supports: {active_count}/{len(supports)}")
        ax.grid(True, linestyle="--", alpha=0.30)
        self.fig_stage_anim.tight_layout()
        self.canvas_stage_anim.draw_idle()

        self._draw_stage_chart_frame(idx)
        try:
            self.var_stage_anim_frame.set(idx+1)
            self.stage_anim_frame_label.configure(text=f"{idx+1} / {len(items)}")
        except Exception:
            pass
        if hasattr(self, "stage_anim_status"):
            qtxt = f"q_L={'on' if items[idx].get('qL_active') else 'off'}, q_R={'on' if items[idx].get('qR_active') else 'off'}"
            self.stage_anim_status.set(f"{items[idx]['stage']}: z={z_current:.3g} m; "f"active supports {active_count}/{len(supports)}; {qtxt}.")

    def _draw_stage_chart_frame(self, idx=0):
        if not hasattr(self, "ax_stage_chart_anim"):
            return
        ax = self.ax_stage_chart_anim
        ax.clear()
        items = getattr(self, "stage_animation_items", []) or []
        idx = max(0, min(int(idx), len(items)-1)) if items else 0
        item = items[idx] if items else {}
        result = item.get("result") or getattr(self, "last_result", None)
        model = item.get("model") or getattr(self, "last_model", None)
        if result is None or model is None:
            msg = "Build stages animation first to solve every stage/substage frame."
            if item.get("error"):
                msg = f"Stage frame failed:\n{item.get('error')}"
            ax.text(0.5, 0.5, msg, transform=ax.transAxes, ha="center", va="center", color="#64748b", wrap=True)
            ax.set_axis_off()
            self.canvas_stage_chart_anim.draw_idle()
            return
        q=self.STAGE_ANIM_OPTIONS.get(self.var_stage_anim_quantity.get(),"pressure")
        try:
            xmin=float(self.var_stage_anim_x_min.get()); xmax=float(self.var_stage_anim_x_max.get())
        except Exception:
            xmin,xmax=self._smart_water_x_range([], q, result)
        zL = float(items[idx].get("z", self._height_right()-self._height_left())) if items else self._height_right()-self._height_left()
        zR = 0.0
        self._plot_quantity_on_axis(ax, result, model, q, zL, zR, xmin, xmax)
        try:
            ax.set_title(f"{self.var_stage_anim_quantity.get()} — {item.get('stage', f'Frame {idx+1}')} — frame {idx+1}/{max(1,len(items))}")
        except Exception:
            pass
        self.fig_stage_chart_anim.tight_layout()
        self.canvas_stage_chart_anim.draw_idle()


    # ============================================================
    # WATER LEVEL ANIMATION (desktop mirror of Streamlit workflow)
    # ============================================================
    WATER_ANIM_OPTIONS = {
        "Total horizontal pressure": "pressure",
        "Deflection": "deflection",
        "Moment": "moment",
        "Shear": "shear",
        "Rotation": "rotation",
        "Water stresses": "water",
        "Effective stresses": "effective",
        "Net pressure": "net",
    }


    def _make_readonly_layer_tree(self, parent, title):
        box = ttk.LabelFrame(parent, text=title, padding=4)
        tree = ttk.Treeview(box, columns=EditableLayerTable.columns, show="headings", height=4)
        widths = {"code": 50, "h": 58, "c": 70, "phi": 62, "gamma": 78, "gamma_sat": 88, "E": 78, "nu": 50}
        for col in EditableLayerTable.columns:
            tree.heading(col, text=EditableLayerTable.headings[col])
            tree.column(col, width=widths.get(col, 70), anchor="center", stretch=False)
        tree.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(box, orient="horizontal", command=tree.xview)
        y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        box.rowconfigure(0, weight=1); box.columnconfigure(0, weight=1)
        return box, tree

    def _build_pvf_tab(self):
        self.tab_pvf.columnconfigure(1, weight=1)
        self.tab_pvf.rowconfigure(0, weight=1)
        left = ScrollableFrame(self.tab_pvf, width=640)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        panel = left.inner
        panel.columnconfigure(0, weight=1)

        info = ttk.LabelFrame(panel, text="Point of virtual fixity (PVF)", padding=8)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(info, text=(
            "PVF is treated as a near-zero-deflection point in a fixed-base solution. "
            "The search is intentionally tolerance-based, not an exact zero search."
        ), wraplength=600).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(info, text="Fixed-base solver").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.OptionMenu(info, self.var_pvf_solver, self.var_pvf_solver.get(),
                       "Fixed base differential", "Fixed base closed-form").grid(row=1, column=1, sticky="ew", padx=4, pady=3)
        ttk.Label(info, text="Zero-deflection tolerance (mm)").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(info, textvariable=self.var_pvf_tol_mm, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
        ttk.Button(info, text="Sync defaults from Model inputs", command=self._pvf_sync_from_main_layers).grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=5)
        ttk.Button(info, text="Run PVF search", command=self._run_pvf_search).grid(row=3, column=2, sticky="ew", padx=4, pady=5)
        ttk.Label(info, textvariable=self.var_pvf_result, font=("Segoe UI", 11, "bold"), foreground="#075985").grid(row=4, column=0, columnspan=4, sticky="w", padx=4, pady=(8,2))
        ttk.Label(info, textvariable=self.var_pvf_status, wraplength=600).grid(row=5, column=0, columnspan=4, sticky="w", padx=4, pady=2)
        info.columnconfigure(1, weight=1)

        base = ttk.LabelFrame(panel, text="Soil layers above the current fixed point (read-only copy from Model inputs)", padding=6)
        base.grid(row=1, column=0, sticky="ew", pady=6)
        base.columnconfigure(0, weight=1)
        boxL, self.pvf_left_readonly_tree = self._make_readonly_layer_tree(base, "Left / excavation side — read only")
        boxL.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        boxR, self.pvf_right_readonly_tree = self._make_readonly_layer_tree(base, "Right / retained side — read only")
        boxR.grid(row=1, column=0, sticky="ew")

        below = ttk.LabelFrame(panel, text="Additional soil below the fixed point used in Model inputs", padding=6)
        below.grid(row=2, column=0, sticky="ew", pady=6)
        below.columnconfigure(0, weight=1)
        ttk.Label(below, text="Left / excavation-side continuation below fixed point", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.pvf_left_below_table = EditableLayerTable(below, "PVFL", 2.0, on_change=lambda: None)
        self.pvf_left_below_table.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(below, text="Right / retained-side continuation below fixed point", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w")
        self.pvf_right_below_table = EditableLayerTable(below, "PVFR", 2.0, on_change=lambda: None)
        self.pvf_right_below_table.grid(row=3, column=0, sticky="ew")

        right = ttk.Frame(self.tab_pvf)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1); right.columnconfigure(0, weight=1)
        self.fig_pvf = Figure(figsize=(8, 7), dpi=100)
        self.ax_pvf = self.fig_pvf.add_subplot(111)
        self.canvas_pvf = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_pvf, master=right))
        self.canvas_pvf.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._pvf_sync_from_main_layers()
        self._draw_pvf_placeholder()

    def _tree_set_rows(self, tree, rows):
        try:
            for item in tree.get_children():
                tree.delete(item)
            for row in rows or []:
                vals = list(row)
                while len(vals) < 8: vals.append("")
                tree.insert("", "end", values=vals[:8])
        except Exception:
            pass

    def _pvf_main_table_rows(self, table):
        return [list(table.tree.item(item, "values")) for item in table.tree.get_children()]

    def _pvf_sync_from_main_layers(self):
        if not hasattr(self, "pvf_left_readonly_tree"):
            return
        left_rows = self._pvf_main_table_rows(self.left_layers_table)
        right_rows = self._pvf_main_table_rows(self.right_layers_table)
        self._tree_set_rows(self.pvf_left_readonly_tree, left_rows)
        self._tree_set_rows(self.pvf_right_readonly_tree, right_rows)
        def last_to_below(rows, prefix):
            vals = list(rows[-1]) if rows else [f"{prefix}1", "2.0", "0.001", "30.0", "20.0", "20.0", "20000", "0.30"]
            vals[0] = f"{prefix}1"
            vals[1] = "2.0"
            return [vals]
        self._set_layer_table_rows(self.pvf_left_below_table, last_to_below(left_rows, "PVFL"))
        self._set_layer_table_rows(self.pvf_right_below_table, last_to_below(right_rows, "PVFR"))

    def _pvf_table_to_solver_layers(self, solvers_mod, table):
        out=[]
        for layer in table.as_dicts():
            out.append(solvers_mod.SoilLayer(
                code=layer["code"], thickness=layer["thickness"], c_prime=layer["c_prime"],
                phi_prime_deg=layer["phi_prime_deg"], gamma=layer["gamma"], gamma_sat=layer["gamma_sat"],
                E_s=layer["E_s"], nu=layer["nu"]
            ))
        return out

    def _draw_pvf_placeholder(self):
        try:
            ax = self.ax_pvf; ax.clear()
            ax.text(0.5, 0.5, "Run PVF search to obtain z_PVF", ha="center", va="center", transform=ax.transAxes, fontsize=13)
            ax.set_axis_off(); self.canvas_pvf.draw_idle()
        except Exception:
            pass

    def _run_pvf_search(self):
        """Search the point of virtual fixity by candidate fixed-base depths.

        The previous PVF prototype extended the wall to the full additional depth and
        then searched the resulting profile for a zero-deflection point. That is too
        severe for long/flexible walls because it asks the ordinary wall solver to
        carry the full artificial extension in one step. Here the PVF depth itself is
        the continuation parameter: a sequence of candidate fixed-base depths is
        tried, and each candidate is judged by engineering PVF indicators:

        - the candidate fixed point is a zero-deflection boundary by construction;
        - the point immediately above the candidate fixed point must have small
          displacement (user tolerance, with a practical engineering fallback);
        - the maximum bending moment should occur close to the candidate fixed point;
        - left/right effective stresses should be reasonably balanced in magnitude;
        - runaway/mechanism-like candidates are rejected.
        """
        try:
            solvers = load_solver_module()
            base_model = self.build_model_input()
            left_extra = self._pvf_table_to_solver_layers(solvers, self.pvf_left_below_table)
            right_extra = self._pvf_table_to_solver_layers(solvers, self.pvf_right_below_table)
            H_R0 = float(base_model.geometry.H_R)
            H_L0 = float(base_model.geometry.H_L)
            dL = sum(max(0.0, float(x.thickness)) for x in left_extra)
            dR = sum(max(0.0, float(x.thickness)) for x in right_extra)
            dmax = max(0.0, min(dL, dR))
            if dmax <= 0.0:
                raise ValueError("Add at least one positive-thickness below-fixed-point layer on both sides.")

            mode = "fixed_base_differential_equation" if "differential" in self.var_pvf_solver.get().lower() else "fixed_base_only_bending"
            tol_mm = max(0.0, float(self.var_pvf_tol_mm.get()))
            tol_m = tol_mm / 1000.0

            # Candidate fixed-point depths.  Include small, intermediate and full
            # extensions, but avoid excessively many expensive solves.
            n_try = int(max(8, min(28, round(dmax / 0.25) + 1)))
            adds = []
            for i in range(1, n_try + 1):
                # Quadratic spacing gives better resolution near the current fixed point.
                r = i / n_try
                adds.append(dmax * (0.15 * r + 0.85 * r * r))
            adds.append(dmax)
            adds = sorted(set(round(max(0.05, min(dmax, a)), 6) for a in adds if a > 1.0e-9))

            history = []
            best = None
            selected = None

            def finite_list(values):
                out = []
                for v in values or []:
                    try:
                        fv = float(v)
                        if math.isfinite(fv):
                            out.append(fv)
                        else:
                            out.append(float('nan'))
                    except Exception:
                        out.append(float('nan'))
                return out

            for add in adds:
                geom = copy.copy(base_model.geometry)
                geom.H_R = H_R0 + add
                geom.H_L = H_L0 + add   # preserve excavation depth z_ex = H_R - H_L
                pvf_model = copy.copy(base_model)
                pvf_model.geometry = geom
                pvf_model.left_layers = list(base_model.left_layers) + left_extra
                pvf_model.right_layers = list(base_model.right_layers) + right_extra
                pvf_model.solver_mode = mode
                if mode == "fixed_base_only_bending":
                    pvf_model.reinforcement_supports = []

                try:
                    result = solvers.solve(pvf_model)
                except Exception as exc:
                    history.append({"add": add, "z": H_R0 + add, "ok": False, "reason": f"solver error: {exc}"})
                    continue

                z = finite_list(getattr(result, "z", []) or [])
                w = finite_list(getattr(result, "deflection", []) or [])
                M = finite_list(getattr(result, "moment", []) or [])
                if not z or not w:
                    history.append({"add": add, "z": H_R0 + add, "ok": False, "reason": "empty profile"})
                    continue
                zc = H_R0 + add
                # Index at/near candidate fixed point and index just above it.
                idx_base = min(range(len(z)), key=lambda k: abs(z[k] - zc))
                above = [k for k, zk in enumerate(z) if zk < zc - 1.0e-8]
                idx_above = above[-1] if above else idx_base
                w_above_mm = abs(w[idx_above]) * 1000.0 if idx_above < len(w) and math.isfinite(w[idx_above]) else float('inf')
                max_w_mm = max([abs(v) * 1000.0 for v in w if math.isfinite(v)] or [float('inf')])

                # Reject obvious runaway candidates.  A PVF search should not accept a
                # mechanism-like full-wall response just because the fixed boundary is zero.
                Htot = max(1.0, float(geom.H_R))
                runaway_limit_mm = max(5000.0, 0.25 * Htot * 1000.0)
                status = str(getattr(result, "status", "")).lower()
                runaway = (not math.isfinite(max_w_mm)) or (max_w_mm > runaway_limit_mm and w_above_mm > max(10.0 * tol_mm, 50.0))

                # Location of maximum moment.
                moment_dist = float('inf')
                if M and any(math.isfinite(v) for v in M):
                    imax = max(range(min(len(M), len(z))), key=lambda k: abs(M[k]) if math.isfinite(M[k]) else -1.0)
                    moment_dist = abs(z[imax] - zc)
                moment_tol = max(0.50, 0.25 * add)

                # At-rest balance indicator at/near candidate fixed point.
                stress_mismatch = 100.0
                try:
                    sl = finite_list(getattr(result, "sigma_left_eff", []) or [])
                    sr = finite_list(getattr(result, "sigma_right_eff", []) or [])
                    if idx_base < len(sl) and idx_base < len(sr):
                        denom = max(1.0e-9, abs(sl[idx_base]) + abs(sr[idx_base]))
                        stress_mismatch = abs(abs(sl[idx_base]) - abs(sr[idx_base])) / denom * 100.0
                except Exception:
                    pass

                # Score: small above-base displacement, moment peak near candidate, balanced stresses.
                disp_score = w_above_mm / max(tol_mm, 1.0e-6)
                moment_score = moment_dist / max(moment_tol, 1.0e-9)
                stress_score = stress_mismatch / 10.0
                status_penalty = 0.0 if ("ok" in status or "conver" in status) else 5.0
                score = disp_score + moment_score + stress_score + status_penalty
                ok_candidate = (not runaway) and (w_above_mm <= max(tol_mm, 0.25)) and (moment_dist <= moment_tol)
                rec = {"add": add, "z": zc, "ok": ok_candidate, "runaway": runaway,
                       "w_above_mm": w_above_mm, "max_w_mm": max_w_mm,
                       "moment_dist": moment_dist, "stress_mismatch": stress_mismatch,
                       "score": score, "status": getattr(result, "status", "?"),
                       "result": result, "idx": idx_base}
                history.append(rec)
                if (best is None) or (score < best["score"]):
                    best = rec
                if ok_candidate:
                    selected = rec
                    break

            if selected is None:
                if best is None:
                    raise ValueError("No usable PVF candidate solution was generated.")
                selected = best
                method = ("best engineering candidate; strict PVF criteria were not fully met "
                          "within the available below-fixed-point layers")
            else:
                method = (f"candidate-depth search; near-zero displacement above fixed point "
                          f"within ±{tol_mm:.3g} mm")

            result = selected["result"]
            idx = int(selected.get("idx", 0))
            z_pvf = float(selected["z"])
            add = z_pvf - H_R0
            self.var_pvf_result.set(f"z_PVF = {z_pvf:.3f} m  (below current fixed point: {add:.3f} m)")
            tried_txt = f"; candidates tried: {len(history)}"
            bal_txt = f"; stress mismatch ≈ {selected.get('stress_mismatch', float('nan')):.2f}%"
            disp_txt = f"; Δx above PVF ≈ {selected.get('w_above_mm', float('nan')):.3f} mm"
            moment_txt = f"; |M|max distance from PVF ≈ {selected.get('moment_dist', float('nan')):.3f} m"
            self.var_pvf_status.set(
                f"PVF selected by {method}{tried_txt}{disp_txt}{moment_txt}{bal_txt}; "
                f"solver status: {getattr(result,'status','?')}."
            )
            self._plot_pvf_result(result, H_R0, z_pvf, idx, history=history)
        except Exception as exc:
            self.var_pvf_status.set(f"PVF search failed: {exc}")
            messagebox.showerror("PVF search", str(exc))

    def _plot_pvf_result(self, result, H_R0, z_pvf, idx, history=None):
        ax = self.ax_pvf; ax.clear()
        z = [float(x) for x in list(getattr(result, "z", []) or [])]
        wmm = [1000.0*float(x) for x in list(getattr(result, "deflection", []) or [])]
        M = [float(x) for x in list(getattr(result, "moment", []) or [])]
        if z and wmm:
            ax.plot(wmm, z, label="deflection Δx (mm)", linewidth=2)
        if z and M:
            scale = max([abs(x) for x in M] or [1.0]) or 1.0
            maxw = max([abs(x) for x in wmm] or [1.0]) or 1.0
            M_scaled = [x/scale*maxw for x in M]
            ax.plot(M_scaled, z, linestyle="--", label="M scaled", linewidth=1.8)
        ax.axvline(0.0, color="black", linewidth=1.0)
        ax.axhline(float(H_R0), color="#64748b", linestyle=":", linewidth=1.5, label="current fixed point")
        ax.axhline(float(z_pvf), color="#dc2626", linestyle="-.", linewidth=2.0, label=f"PVF z={z_pvf:.3f} m")
        ax.set_ylim(max(z or [H_R0])+0.25, -0.25)
        ax.set_xlabel("deflection (mm); moment plotted scaled")
        ax.set_ylabel("z (m)")
        # Show candidate-depth search summary in the corner so the user can see
        # that PVF was not obtained by one blind full-depth solve.
        try:
            if history:
                accepted = [h for h in history if h.get("ok")]
                best = min(history, key=lambda h: h.get("score", 1.0e99))
                txt = f"candidates tried: {len(history)}\n"
                txt += f"selected z: {float(z_pvf):.3f} m\n"
                txt += f"best Δx above PVF: {best.get('w_above_mm', float('nan')):.3f} mm\n"
                txt += f"stress mismatch: {best.get('stress_mismatch', float('nan')):.2f}%"
                if not accepted:
                    txt += "\n(strict criteria not fully met)"
                ax.text(0.02, 0.02, txt, transform=ax.transAxes, va="bottom", ha="left",
                        fontsize=8, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#94a3b8", alpha=0.85))
        except Exception:
            pass
        ax.set_title("Point of virtual fixity candidate-depth search")
        ax.grid(True, linestyle="--", alpha=0.30)
        self._safe_legend(ax, loc="best", fontsize=8)
        self.fig_pvf.tight_layout(); self.canvas_pvf.draw_idle()

    def _build_water_animation_tab(self):
        tab = self.tab_water_animation
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        controls = ttk.LabelFrame(tab, text="Animation controls", padding=8)
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        for c in range(12):
            controls.columnconfigure(c, weight=1)

        self._water_quantity_combo = ttk.Combobox(controls, textvariable=self.var_water_anim_quantity, values=list(self.WATER_ANIM_OPTIONS.keys()), state="readonly", width=25)
        labels = [("Diagram",0),("Water rise mode",1),("Number of steps",2),("z_final_left (m)",3),("z_final_right (m)",4),("Frame duration (ms)",5),("x_min",6),("x_max",7)]
        for text, col in labels:
            ttk.Label(controls, text=text).grid(row=0, column=col, sticky="w", padx=4)
        self._water_quantity_combo.grid(row=1, column=0, sticky="ew", padx=4)
        self._water_quantity_combo.bind("<<ComboboxSelected>>", lambda *_: self._on_water_anim_quantity_changed())
        ttk.Combobox(controls, textvariable=self.var_water_anim_mode, values=["Uniform rise", "Simultaneous proportional rise"], state="readonly", width=27).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Entry(controls, textvariable=self.var_water_anim_steps, width=10).grid(row=1, column=2, sticky="ew", padx=4)
        ttk.Entry(controls, textvariable=self.var_water_anim_z_final_left, width=12).grid(row=1, column=3, sticky="ew", padx=4)
        ttk.Entry(controls, textvariable=self.var_water_anim_z_final_right, width=12).grid(row=1, column=4, sticky="ew", padx=4)
        ttk.Entry(controls, textvariable=self.var_water_anim_speed_ms, width=12).grid(row=1, column=5, sticky="ew", padx=4)
        ttk.Entry(controls, textvariable=self.var_water_anim_x_min, width=10).grid(row=1, column=6, sticky="ew", padx=4)
        ttk.Entry(controls, textvariable=self.var_water_anim_x_max, width=10).grid(row=1, column=7, sticky="ew", padx=4)
        ttk.Button(controls, text="Run water level animation", style="WaterRun.TButton", command=self.run_water_level_animation).grid(row=1, column=8, sticky="ew", padx=6)
        ttk.Button(controls, text="Play", style="WaterPlay.TButton", command=self.play_water_animation).grid(row=1, column=9, sticky="ew", padx=4)
        ttk.Button(controls, text="Pause", style="Pause.TButton", command=self.pause_water_animation).grid(row=1, column=10, sticky="ew", padx=4)
        add_help(controls, 1, 11, "x_min/x_max are selected intelligently when the diagram changes; they can still be adjusted manually. Increase x_max when long reinforcement elements need to be visible.", padx=8)

        self.water_anim_status = tk.StringVar(value="Run a solver first, then run the water-level sequence.")
        ttk.Label(tab, textvariable=self.water_anim_status, foreground="#555").grid(row=1, column=0, sticky="ew", padx=12, pady=(0,4))

        body = ttk.Panedwindow(tab, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew", padx=8, pady=6)
        plot_frame = ttk.LabelFrame(body, text="Animation", padding=6)
        right_frame = ttk.Frame(body)
        body.add(plot_frame, weight=3)
        body.add(right_frame, weight=2)

        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        plot_frame.rowconfigure(1, weight=0)
        self.fig_water_anim = Figure(figsize=(7.8, 5.5), dpi=100)
        self.ax_water_anim = self.fig_water_anim.add_subplot(111)
        self.canvas_water_anim = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_water_anim, master=plot_frame))
        self.canvas_water_anim.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.water_anim_slider = ttk.Scale(plot_frame, from_=1, to=1, orient="horizontal", variable=self.var_water_anim_frame, command=self._on_water_anim_slider)
        self.water_anim_slider.grid(row=1, column=0, sticky="ew", padx=8, pady=(6, 0))

        right_frame.columnconfigure(0, weight=1)
        for r in range(5):
            right_frame.rowconfigure(r, weight=1 if r in (0,2,4) else 0)
        table_frame = ttk.LabelFrame(right_frame, text="Water-level sequence table", padding=6)
        table_frame.grid(row=0, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1); table_frame.rowconfigure(0, weight=1)
        cols=("Step","z_w_L","z_w_R","Max","Status","Comment")
        self.water_anim_tree=ttk.Treeview(table_frame, columns=cols, show="headings", height=7)
        heads={"Step":"Step","z_w_L":"z_w_L (m)","z_w_R":"z_w_R (m)","Max":"Max value","Status":"Status","Comment":"Comment"}
        widths={"Step":55,"z_w_L":80,"z_w_R":80,"Max":115,"Status":85,"Comment":260}
        for c in cols:
            self.water_anim_tree.heading(c,text=heads[c]); self.water_anim_tree.column(c,width=widths[c],anchor="center" if c!="Comment" else "w")
        self.water_anim_tree.grid(row=0,column=0,sticky="nsew")
        y=ttk.Scrollbar(table_frame,orient="vertical",command=self.water_anim_tree.yview); y.grid(row=0,column=1,sticky="ns"); self.water_anim_tree.configure(yscrollcommand=y.set)

        evol_frame = ttk.LabelFrame(right_frame, text="Evolution of maximum value", padding=6)
        evol_frame.grid(row=2, column=0, sticky="nsew", pady=(8,0))
        evol_frame.columnconfigure(0, weight=1); evol_frame.rowconfigure(0, weight=1)
        self.fig_water_evol = Figure(figsize=(5.0, 2.6), dpi=100)
        self.ax_water_evol = self.fig_water_evol.add_subplot(111)
        self.canvas_water_evol = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_water_evol, master=evol_frame))
        self.canvas_water_evol.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        support_frame = ttk.LabelFrame(right_frame, text="Reinforcement/support force (kN/m) per stage", padding=6)
        support_frame.grid(row=4, column=0, sticky="nsew", pady=(8,0))
        support_frame.columnconfigure(0, weight=1); support_frame.rowconfigure(1, weight=1); support_frame.rowconfigure(2, weight=1)
        self.water_support_checks_frame = ttk.Frame(support_frame)
        self.water_support_checks_frame.grid(row=0, column=0, sticky="ew")
        self.fig_water_support = Figure(figsize=(5.0, 2.7), dpi=100)
        self.ax_water_support = self.fig_water_support.add_subplot(111)
        self.canvas_water_support = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_water_support, master=support_frame))
        self.canvas_water_support.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        self.water_support_tree=ttk.Treeview(support_frame, columns=("Stage",), show="headings", height=4)
        self.water_support_tree.heading("Stage", text="Stage")
        self.water_support_tree.column("Stage", width=80, anchor="center")
        self.water_support_tree.grid(row=2,column=0,sticky="nsew", pady=(6,0))

    def _water_levels(self, H_R, H_L, z_final_left, z_final_right, n_steps, mode):
        n_steps=max(2,int(n_steps)); z_left_surface=float(H_R)-float(H_L); z0=float(H_R)
        z_final_left=max(float(z_final_left), z_left_surface); z_final_right=max(float(z_final_right),0.0)
        rows=[]
        if mode == "Simultaneous proportional rise":
            for i in range(n_steps):
                t=i/max(1,n_steps-1); rows.append((z0+t*(z_final_left-z0), z0+t*(z_final_right-z0)))
        else:
            total=max(z0-z_final_left, z0-z_final_right, 0.0)
            for i in range(n_steps):
                rise=(i/max(1,n_steps-1))*total; rows.append((max(z_final_left,z0-rise), max(z_final_right,z0-rise)))
        return rows

    def _water_solver_levels(self, zL, zR, H_R, H_L):
        eps=max(1e-6,1e-7*max(float(H_R),1.0)); z_left_surface=float(H_R)-float(H_L)
        return (max(float(zL), z_left_surface+eps), max(float(zR), eps))

    def _max_response_for_quantity(self, result, quantity):
        def vals(name):
            return [abs(float(x)) for x in list(getattr(result,name,[]) or []) if _is_finite(x)]
        if quantity=="deflection": v=vals("deflection"); return ((max(v)*1000.0) if v else float("nan"), "mm")
        if quantity=="moment": v=vals("moment"); return (max(v) if v else float("nan"), "kNm/m")
        if quantity=="shear": v=vals("shear"); return (max(v) if v else float("nan"), "kN/m")
        if quantity=="rotation": v=vals("rotation"); return (max(v) if v else float("nan"), "deg")
        if quantity=="water": v=vals("u_left")+vals("u_right"); return (max(v) if v else float("nan"), "kPa")
        if quantity=="effective": v=vals("sigma_left_eff")+vals("sigma_right_eff"); return (max(v) if v else float("nan"), "kPa")
        if quantity=="pressure": v=vals("p_left")+vals("p_right"); return (max(v) if v else float("nan"), "kPa")
        v=vals("net_pressure"); return (max(v) if v else float("nan"), "kPa")

    def _water_x_values(self, result, quantity):
        def arr(name): return [float(x) for x in list(getattr(result,name,[]) or []) if _is_finite(x)]
        if quantity=="pressure": return [-x for x in arr("p_left")]+arr("p_right")
        if quantity=="deflection": return [-1000*x for x in arr("deflection")]
        if quantity=="moment": return arr("moment")
        if quantity=="shear": return arr("shear")
        if quantity=="rotation": return arr("rotation")
        if quantity=="water": return [-x for x in arr("u_left")]+arr("u_right")
        if quantity=="effective": return [-x for x in arr("sigma_left_eff")]+arr("sigma_right_eff")
        return arr("net_pressure")

    def _smart_water_x_range(self, items, quantity, fallback=None):
        vals=[]
        for it in items or []: vals += self._water_x_values(it.get("result"), quantity)
        if not vals and fallback is not None: vals += self._water_x_values(fallback, quantity)
        vals=[v for v in vals if _is_finite(v)]
        if not vals: return -1.0, 1.0
        mn=min(vals); mx=max(vals); pad=0.14*max(mx-mn,abs(mx),abs(mn),1.0)
        mn=min(mn-pad,0.0); mx=max(mx+pad,0.0)
        if mx-mn < 1e-12: mn,mx=-1.0,1.0
        return mn,mx

    def _on_water_anim_quantity_changed(self):
        q=self.WATER_ANIM_OPTIONS.get(self.var_water_anim_quantity.get(),"pressure")
        xmin,xmax=self._smart_water_x_range(getattr(self,"water_animation_items",[]),q,self.last_result)
        self.var_water_anim_x_min.set(xmin); self.var_water_anim_x_max.set(xmax)
        self._populate_water_animation_tables()
        self._draw_water_animation_frame(max(0, int(self.var_water_anim_frame.get())-1))

    def run_water_level_animation(self):
        if self.last_model is None or self.last_result is None:
            messagebox.showinfo("Water level animation", "Run a solver first."); return
        H_R=self._height_right(); H_L=self._height_left(); z_left_surface=H_R-H_L
        if abs(float(self.var_water_anim_z_final_left.get())) < 1e-12:
            self.var_water_anim_z_final_left.set(z_left_surface)
        solvers=load_solver_module(); oldL=float(self.var_z_w_L.get()); oldR=float(self.var_z_w_R.get())
        levels=self._water_levels(H_R,H_L,float(self.var_water_anim_z_final_left.get()),float(self.var_water_anim_z_final_right.get()),int(self.var_water_anim_steps.get()),self.var_water_anim_mode.get())
        items=[]; self.water_anim_status.set("Running water-level sequence..."); self.update_idletasks()
        try:
            previous_frame_result = None
            frame_iteration_cap = 60
            for i,(zL,zR) in enumerate(levels, start=1):
                zLs,zRs=self._water_solver_levels(zL,zR,H_R,H_L)
                self.var_z_w_L.set(zLs); self.var_z_w_R.set(zRs)
                model=self.build_model_input()

                # Animation speed/robustness controls:
                # (2) warm-start each water stage from the previous stage,
                # (3) cap nonlinear iterations per animation frame.
                try:
                    if previous_frame_result is not None:
                        model.initial_deflection = list(getattr(previous_frame_result, "deflection", []) or [])
                    model.controls.max_iterations = min(int(model.controls.max_iterations), frame_iteration_cap)
                except Exception:
                    pass

                result=solvers.solve(model)
                previous_frame_result = result
                try:
                    result.summary["water_animation_warm_start"] = bool(i > 1)
                    result.summary["water_animation_iteration_cap"] = int(frame_iteration_cap)
                except Exception:
                    pass
                items.append({"step":i,"z_w_L":float(zL),"z_w_R":float(zR),"z_w_L_solver":float(zLs),"z_w_R_solver":float(zRs),"model":model,"result":result})
                self.water_anim_status.set(f"Water animation: solved step {i}/{len(levels)} (warm start, max {frame_iteration_cap} iter/frame)"); self.update_idletasks()
        finally:
            self.var_z_w_L.set(oldL); self.var_z_w_R.set(oldR); self._draw_geometry_safe()
        self.water_animation_items=items
        q=self.WATER_ANIM_OPTIONS.get(self.var_water_anim_quantity.get(),"pressure")
        xmin,xmax=self._smart_water_x_range(items,q,self.last_result); self.var_water_anim_x_min.set(xmin); self.var_water_anim_x_max.set(xmax)
        try:
            self.water_anim_slider.configure(to=max(1,len(items)))
            self.var_water_anim_frame.set(1)
        except Exception:
            pass
        self._populate_water_animation_tables(); self._draw_water_animation_frame(0)
        self.water_anim_status.set(f"Water-level animation ready: {len(items)} stored stages.")

    def _plot_quantity_on_axis(self, ax, result, model, quantity, zL, zR, xmin, xmax):
        z=list(getattr(result,"z",[]) or [])
        def arr(name): return [float(x) for x in list(getattr(result,name,[]) or [])]
        series=[]; xlabel=""
        if quantity=="pressure": series=[("Left",[-x for x in arr("p_left")]),("Right",arr("p_right"))]; xlabel="Pressure (kPa)"
        elif quantity=="deflection": series=[("Δx",[-1000*x for x in arr("deflection")])]; xlabel="Δx (mm)"
        elif quantity=="moment": series=[("M",arr("moment"))]; xlabel="Moment (kNm/m)"
        elif quantity=="shear": series=[("V",arr("shear"))]; xlabel="Shear (kN/m)"
        elif quantity=="rotation": series=[("rotation",arr("rotation"))]; xlabel="Rotation (deg)"
        elif quantity=="water": series=[("u_L",[-x for x in arr("u_left")]),("u_R",arr("u_right"))]; xlabel="u (kPa)"
        elif quantity=="effective": series=[("σh,L",[-x for x in arr("sigma_left_eff")]),("σh,R",arr("sigma_right_eff"))]; xlabel="σ'h (kPa)"
        else: series=[("p_net",arr("net_pressure"))]; xlabel="p_net (kPa)"
        H_R=float(model.geometry.H_R); H_L=float(model.geometry.H_L); z_left=H_R-H_L
        ax.axvspan(xmin,0, ymin=0, ymax=1, color="#e0f2fe", alpha=0.18)
        ax.axvspan(0,xmax, ymin=0, ymax=1, color="#e0f2fe", alpha=0.10)
        ax.fill_betweenx([max(float(zL),z_left),H_R], xmin, 0.0, color="#38bdf8", alpha=0.16)
        ax.fill_betweenx([max(float(zR),0.0),H_R], 0.0, xmax, color="#38bdf8", alpha=0.16)
        ax.hlines(zL,xmin,0.0,colors="#2563eb",linestyles="--",linewidth=1.5)
        ax.hlines(zR,0.0,xmax,colors="#2563eb",linestyles="--",linewidth=1.5)
        ax.hlines(z_left,xmin,0.0,colors="saddlebrown",linewidth=1.4); ax.hlines(0.0,0.0,xmax,colors="saddlebrown",linewidth=1.4)
        ax.axvline(0.0,color="black",linewidth=1.2)
        def _with_depth_break(xs, zs, depth):
            """Break a polyline at an excavation/water interface to avoid fake vertical branches."""
            xs2, zs2 = [], []
            for ii, (xx, zz) in enumerate(zip(xs, zs)):
                if ii > 0:
                    zprev = float(zs[ii-1])
                    zcur = float(zz)
                    if (zprev - depth) * (zcur - depth) < 0.0 or abs(zprev - depth) <= 1.0e-12 or abs(zcur - depth) <= 1.0e-12:
                        xs2.append(float("nan")); zs2.append(float("nan"))
                xs2.append(float(xx)); zs2.append(float(zz))
            return xs2, zs2

        for name,x in series:
            if len(x)==len(z):
                xp, zp = list(x), list(z)
                # On the excavation side, pressure/stress/water series are discontinuous
                # at the current excavation level.  Do not draw the artificial vertical
                # connector across that discontinuity.
                if name in ("Left", "σh,L", "u_L"):
                    xp, zp = _with_depth_break(xp, zp, z_left)
                ax.plot(xp, zp, linewidth=2, label=name)
        ax.set_xlim(float(xmin),float(xmax)); ax.set_ylim(H_R+0.25,-0.25); ax.set_xlabel(xlabel); ax.set_ylabel("z (m)")
        ax.set_title(f"{self.var_water_anim_quantity.get()}\nz_w,L={zL:.3f} m, z_w,R={zR:.3f} m")
        ax.grid(True, linestyle="--", alpha=0.3); self._safe_legend(ax, loc="best", fontsize=8)

    def _draw_water_animation_frame(self, idx):
        if not getattr(self,"water_animation_items",[]): return
        idx=max(0,min(int(idx),len(self.water_animation_items)-1)); item=self.water_animation_items[idx]
        ax=self.ax_water_anim; ax.clear()
        q=self.WATER_ANIM_OPTIONS.get(self.var_water_anim_quantity.get(),"pressure")
        self._plot_quantity_on_axis(ax,item["result"],item["model"],q,item["z_w_L"],item["z_w_R"],float(self.var_water_anim_x_min.get()),float(self.var_water_anim_x_max.get()))
        self.fig_water_anim.tight_layout(); self.canvas_water_anim.draw_idle()
        try: self.var_water_anim_frame.set(idx+1)
        except Exception: pass
        self.water_anim_status.set(f"Frame {idx+1}/{len(self.water_animation_items)}")

    def _on_water_anim_slider(self, value=None):
        try: idx=int(round(float(value if value is not None else self.var_water_anim_frame.get()))) - 1
        except Exception: idx=0
        self._draw_water_animation_frame(idx)

    def pause_water_animation(self):
        if self._water_anim_after_id is not None:
            try: self.after_cancel(self._water_anim_after_id)
            except Exception: pass
            self._water_anim_after_id=None

    def play_water_animation(self):
        if not getattr(self,"water_animation_items",[]): return
        self.pause_water_animation()
        start=0
        def step(i=start):
            self._draw_water_animation_frame(i)
            if i+1 < len(self.water_animation_items):
                self._water_anim_after_id=self.after(max(50,int(self.var_water_anim_speed_ms.get())), lambda: step(i+1))
            else:
                self._water_anim_after_id=None
        step(start)

    def _water_summary_rows(self):
        items=list(getattr(self,"water_animation_items",[]) or []); q=self.WATER_ANIM_OPTIONS.get(self.var_water_anim_quantity.get(),"pressure")
        raw=[]
        for it in items:
            mx,unit=self._max_response_for_quantity(it["result"],q); status=str(getattr(it["result"],"status",""))
            raw.append({"step":it["step"],"zL":it["z_w_L"],"zR":it["z_w_R"],"max":mx,"unit":unit,"status":status,"comment":"—"})
        for k,r in enumerate(raw):
            if r["status"].lower()=="ok": continue
            prev=[x for x in raw[:k] if x["status"].lower()=="ok" and _is_finite(x["max"])]
            nxt=[x for x in raw[k+1:] if x["status"].lower()=="ok" and _is_finite(x["max"])]
            if prev and nxt:
                p,n=prev[-1],nxt[0]; r["max"]=float(p["max"])+(r["step"]-p["step"])*(float(n["max"])-float(p["max"]))/(n["step"]-p["step"]); r["comment"]=f"not_converged; interpolated from stages {p['step']} and {n['step']}"
            elif prev:
                r["max"]=prev[-1]["max"]; r["comment"]=f"not_converged; copied from previous converged stage {prev[-1]['step']}"
            elif nxt:
                r["max"]=nxt[0]["max"]; r["comment"]=f"not_converged; copied from next converged stage {nxt[0]['step']}"
            else:
                r["comment"]="not_converged; interpolation unavailable"
        return raw

    def _support_force_rows_for_water(self):
        items=list(getattr(self,"water_animation_items",[]) or [])
        codes=[]; rows=[]
        for it in items:
            row={"Stage":it["step"]}
            for sr in self._support_result_rows(result=it["result"], model=it["model"]):
                code=str(sr.get("code","")).strip()
                if code and code not in codes: codes.append(code)
                if code: row[code]=abs(float(sr.get("Fh",0.0) or 0.0))
            rows.append(row)
        return codes, rows

    def _draw_water_evolution_chart(self):
        ax=self.ax_water_evol; ax.clear(); rows=self._water_summary_rows()
        if rows:
            xs=[r["step"] for r in rows]; ys=[r["max"] for r in rows]
            ax.plot(xs, ys, marker="o", linewidth=2)
            unit=rows[0].get("unit","")
            ax.set_xlabel("Step"); ax.set_ylabel(f"Max value ({unit})")
            ax.set_title("Step vs maximum response")
        else:
            ax.text(0.5,0.5,"No water-animation results",ha="center",va="center",transform=ax.transAxes)
        ax.grid(True, linestyle="--", alpha=0.3); self.fig_water_evol.tight_layout(); self.canvas_water_evol.draw_idle()

    def _draw_water_support_chart(self):
        ax=self.ax_water_support; ax.clear(); codes, rows=self._support_force_rows_for_water()
        selected=[c for c in codes if self.water_anim_support_selected.get(c, tk.BooleanVar(value=True)).get()]
        if rows and selected:
            xs=[r["Stage"] for r in rows]
            for code in selected:
                ys=[r.get(code, float("nan")) for r in rows]
                ax.plot(xs, ys, marker="o", linewidth=2, label=code)
            ax.set_xlabel("Stage"); ax.set_ylabel("Fh (kN/m)"); ax.set_title("Support force per stage")
            self._safe_legend(ax, loc="best", fontsize=8)
        elif codes:
            ax.text(0.5,0.5,"Select one or more supports",ha="center",va="center",transform=ax.transAxes)
        else:
            ax.text(0.5,0.5,"No support forces",ha="center",va="center",transform=ax.transAxes)
        ax.grid(True, linestyle="--", alpha=0.3); self.fig_water_support.tight_layout(); self.canvas_water_support.draw_idle()

    def _populate_support_checkboxes(self, codes):
        for w in self.water_support_checks_frame.winfo_children():
            w.destroy()
        # Preserve existing states where possible; new codes are selected by default, as in the Streamlit tickboxes.
        for i, code in enumerate(codes):
            var=self.water_anim_support_selected.get(code)
            if var is None:
                var=tk.BooleanVar(value=True); self.water_anim_support_selected[code]=var
            ttk.Checkbutton(self.water_support_checks_frame, text=code, variable=var, command=self._draw_water_support_chart).grid(row=0, column=i, sticky="w", padx=4)
        if not codes:
            ttk.Label(self.water_support_checks_frame, text="No reinforcement/support force series available.", foreground="#555").grid(row=0, column=0, sticky="w")

    def _populate_water_animation_tables(self):
        for iid in self.water_anim_tree.get_children(): self.water_anim_tree.delete(iid)
        raw=self._water_summary_rows()
        for r in raw:
            self.water_anim_tree.insert("","end",values=(r["step"],f"{r['zL']:.4g}",f"{r['zR']:.4g}",f"{r['max']:.4g} {r['unit']}" if _is_finite(r['max']) else "—",r["status"],r["comment"]))
        codes, rows = self._support_force_rows_for_water()
        self._populate_support_checkboxes(codes)
        try: self.water_support_tree.destroy()
        except Exception: pass
        parent=self.canvas_water_support.get_tk_widget().master
        cols=("Stage",)+tuple(codes) if codes else ("Stage",)
        self.water_support_tree=ttk.Treeview(parent, columns=cols, show="headings", height=4)
        for c in cols:
            self.water_support_tree.heading(c,text=c); self.water_support_tree.column(c,width=90,anchor="center")
        self.water_support_tree.grid(row=2,column=0,sticky="nsew",pady=(6,0))
        for row in rows:
            self.water_support_tree.insert("","end",values=tuple(row.get(c,"—") if c=="Stage" else (f"{row.get(c,float('nan')):.3f}" if _is_finite(row.get(c)) else "—") for c in cols))
        self._draw_water_evolution_chart()
        self._draw_water_support_chart()

    def _build_query_tab(self):
        self.tab_query.columnconfigure(0, weight=1)
        self.tab_query.rowconfigure(1, weight=1)
        top = ttk.LabelFrame(self.tab_query, text="Point queries", padding=8)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        top.columnconfigure(7, weight=1)
        self._entry(top, 0, 0, "z query (m)", self.var_query_z, width=10)
        ttk.Button(top, text="Add query", command=self.add_query_row).grid(row=0, column=2, padx=4)
        ttk.Button(top, text="Remove selected", command=self.remove_selected_query_rows).grid(row=0, column=3, padx=4)
        ttk.Button(top, text="Update all", command=self.update_query_table).grid(row=0, column=4, padx=4)
        ttk.Label(top, text="Enter one or more z-levels; the table groups primary and secondary response quantities.", style="Muted.TLabel").grid(row=0, column=5, columnspan=3, sticky="w", padx=10)

        cols = (
            "z", "pL", "pR", "pnet", "dx", "theta", "V", "M",
            "KL", "KR", "mL", "mR", "OE_L", "AE_L", "PE_L", "OE_R", "AE_R", "PE_R",
            "dxA", "dxP"
        )
        self.query_tree = ttk.Treeview(self.tab_query, columns=cols, show="headings", height=18)
        headers = {
            "z":"z query (m)", "pL":"p_L", "pR":"p_R", "pnet":"p_net", "dx":"Δx (mm)", "theta":"θ (deg)", "V":"V", "M":"M",
            "KL":"K_L", "KR":"K_R", "mL":"m_L", "mR":"m_R", "OE_L":"OE_L", "AE_L":"AE_L", "PE_L":"PE_L",
            "OE_R":"OE_R", "AE_R":"AE_R", "PE_R":"PE_R", "dxA":"Δxmax,A mm", "dxP":"Δxmax,P mm"
        }
        widths = {"z":95, "pL":85, "pR":85, "pnet":85, "dx":90, "theta":85, "V":80, "M":90,
                  "KL":70, "KR":70, "mL":70, "mR":70, "OE_L":80, "AE_L":80, "PE_L":80,
                  "OE_R":80, "AE_R":80, "PE_R":80, "dxA":95, "dxP":95}
        for c in cols:
            self.query_tree.heading(c, text=headers[c])
            self.query_tree.column(c, width=widths.get(c, 85), minwidth=widths.get(c, 85), anchor="center", stretch=False)
        self.query_tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        y = ttk.Scrollbar(self.tab_query, orient="vertical", command=self.query_tree.yview)
        x = ttk.Scrollbar(self.tab_query, orient="horizontal", command=self.query_tree.xview)
        y.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        x.grid(row=2, column=0, sticky="ew", padx=8)
        self.query_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self._query_z_values = [float(self.var_query_z.get())]

    def _build_results_table_tab(self):
        self.tab_results.columnconfigure(0, weight=1)
        self.tab_results.rowconfigure(1, weight=1)
        top = ttk.Frame(self.tab_results, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Button(top, text="Copy table", command=self.copy_results_table).pack(side="left", padx=4)
        self.results_table = ttk.Treeview(self.tab_results, columns=("z", "p_left", "p_right", "net", "V", "M", "w"), show="headings")
        heads = {"z":"z (m)", "p_left":"p_L (kPa)", "p_right":"p_R (kPa)", "net":"p_net (kPa)", "V":"V (kN/m)", "M":"M (kNm/m)", "w":"w (m)"}
        for col in self.results_table["columns"]:
            self.results_table.heading(col, text=heads[col])
            self.results_table.column(col, width=120, anchor="center")
        self.results_table.grid(row=1, column=0, sticky="nsew")
        y = ttk.Scrollbar(self.tab_results, orient="vertical", command=self.results_table.yview)
        y.grid(row=1, column=1, sticky="ns")
        self.results_table.configure(yscrollcommand=y.set)

    def _layers_changed(self):
        try:
            H_L = self.left_layers_table.height()
            H_R = self.right_layers_table.height()
            self.var_H_L_display.set(f"{H_L:.6g}")
            self.var_H_R_display.set(f"{H_R:.6g}")
            self.var_z_ex_display.set(f"{(H_R - H_L):.6g}  (total excavation depth)")
            if H_L <= 0 or H_R <= 0:
                self.var_height_status.set("Layer heights must be positive.")
            else:
                self.var_height_status.set("")
            if hasattr(self, "_sync_stages_to_final_excavation"):
                self._sync_stages_to_final_excavation()
            self._draw_geometry_safe()
        except Exception:
            pass

    def _height_left(self) -> float:
        return self.left_layers_table.height() if hasattr(self, "left_layers_table") else 6.0

    def _height_right(self) -> float:
        return self.right_layers_table.height() if hasattr(self, "right_layers_table") else 10.0

    def _left_excavation_surface_z(self) -> float:
        return self._height_right() - self._height_left()

    def _validated_left_water_depth(self) -> float:
        # The left water level is in the global z-coordinate and cannot be above the excavation surface.
        return max(float(self.var_z_w_L.get()), self._left_excavation_surface_z())


    def _read_layers(self, solvers_mod, side: str):
        table = self.left_layers_table if side == "left" else self.right_layers_table
        out = []
        for layer in table.as_dicts():
            out.append(solvers_mod.SoilLayer(
                code=layer["code"],
                thickness=layer["thickness"],
                c_prime=layer["c_prime"],
                phi_prime_deg=layer["phi_prime_deg"],
                gamma=layer["gamma"],
                gamma_sat=layer["gamma_sat"],
                E_s=layer["E_s"],
                nu=layer["nu"],
            ))
        return out

    def _select_solver_display(self, display_name: str):
        # With reinforcement active, allow both supported nonlinear differential solvers:
        # fixed-base differential and base-spring differential.  Earlier versions
        # forced every click back to the fixed-base solver, which prevented the
        # newly-developed base-spring/freeing workflow from being selected.
        if self._reinforcement_is_active():
            allowed = getattr(self, "_REINFORCEMENT_ALLOWED_SOLVERS", {self._REINFORCEMENT_REQUIRED_SOLVER})
            if display_name not in allowed:
                self.var_solver_display.set(self._REINFORCEMENT_REQUIRED_SOLVER)
                self._refresh_solver_button_selection()
                self.run_status.set(self._reinforcement_solver_lock_message())
                return
        self.var_solver_display.set(display_name)
        self._refresh_solver_button_selection()
        self.run_status.set(f"Selected solver: {display_name}")

    def _update_solver_visibility(self):
        """Show rigid movement controls only for solvers where they are meaningful."""
        try:
            name = self.var_solver_display.get()
            show_move = ("Rigid wall" in name) or ("Any wall" in name)
            show_mode = ("Rigid wall" in name)
            if hasattr(self, "rigid_move_box"):
                if show_move:
                    self.rigid_move_box.grid()
                else:
                    self.rigid_move_box.grid_remove()
            if hasattr(self, "no_bending_label") and hasattr(self, "no_bending_menu"):
                if show_mode:
                    self.no_bending_label.grid()
                    self.no_bending_menu.grid()
                else:
                    self.no_bending_label.grid_remove()
                    self.no_bending_menu.grid_remove()
        except Exception:
            pass

    def build_model_input(self):
        solvers = load_solver_module()
        left_layers = self._read_layers(solvers, "left")
        right_layers = self._read_layers(solvers, "right")
        H_L = sum(max(0.0, float(layer.thickness)) for layer in left_layers)
        H_R = sum(max(0.0, float(layer.thickness)) for layer in right_layers)
        if H_L <= 0 or H_R <= 0:
            raise ValueError("Both left and right layer total heights must be positive.")
        self._enforce_reinforcement_solver_requirement(show_status=True)
        display = self.var_solver_display.get()
        mode = solvers.SOLVER_DISPLAY_NAMES.get(display, "general_case")
        geometry = solvers.GeometryInput(H_R=H_R, H_L=H_L, z_p=float(self.var_z_pivot.get()))
        left = solvers.SideInput(beta_deg=float(self.var_beta_L.get()), q=float(self.var_q_L.get()), z_w=self._validated_left_water_depth())
        right = solvers.SideInput(beta_deg=float(self.var_beta_R.get()), q=float(self.var_q_R.get()), z_w=float(self.var_z_w_R.get()))
        seismic = solvers.SeismicInput(k_h=float(self.var_k_h.get()), k_v=float(self.var_k_v.get()))
        movement = solvers.MovementInput(dx_trans=float(self.var_dx_trans.get()), theta_rot_deg=float(self.var_theta_rot.get()), z_pivot=float(self.var_z_pivot.get()))
        wall = solvers.WallStiffnessInput(stiffness_type=self.var_stiffness_type.get(), EI=float(self.var_EI.get()), E=float(self.var_E.get()), I_or_t=float(self.var_I_or_t.get()))
        controls = solvers.SolverControls(
            dz=float(self.var_dz.get()),
            n_points=max(3, int(self.var_n_points.get())),
            max_iterations=max(1, int(self.var_N.get())),
            tolerance=float(self.var_tol.get()),
            integration_method=self.var_integration_method.get(),
            no_bending_mode=self.var_no_bending_mode.get(),
            rigid_optimization_solver=self.var_rigid_optimization_solver.get(),
            equilibrium_force_tol=float(self.var_equilibrium_force_tol.get()),
            equilibrium_moment_tol=float(self.var_equilibrium_moment_tol.get()),
            work_band_tol=float(self.var_work_band_tol.get()),
            general_case_bending_schemes=max(2, int(self.var_general_case_bending_schemes.get())),
            general_case_theta_refine_passes=max(0, int(self.var_general_case_theta_refine_passes.get())),
            general_case_theta_points=max(5, int(self.var_general_case_theta_points.get())),
            general_case_zp_points=max(5, int(self.var_general_case_zp_points.get())),
            general_case_pivot_margin_frac=max(0.0, min(0.20, float(self.var_general_case_pivot_margin_frac.get()))),
            general_case_parallel=bool(self.var_general_case_parallel.get()),
            general_case_max_workers=max(0, int(self.var_general_case_max_workers.get())),
        )
        return solvers.ModelInput(geometry=geometry, left=left, right=right, seismic=seismic, movement=movement, wall=wall, controls=controls, gamma_w=float(self.var_gamma_w.get()), left_layers=left_layers, right_layers=right_layers, reinforcement_supports=self._read_reinforcement_supports(), solver_mode=mode)

    def pause_solver(self):
        if self._solver_thread is not None and self._solver_thread.is_alive():
            self._pause_requested = not bool(self._pause_requested)
            now = time.time()
            if self._pause_requested:
                self._pause_started_at = now
                try:
                    self.progress_bar.stop()
                except Exception:
                    pass
            else:
                if self._pause_started_at is not None:
                    self._paused_elapsed += max(0.0, now - self._pause_started_at)
                self._pause_started_at = None
                if not self._progress_has_fraction:
                    try:
                        self.progress_bar.start(12)
                    except Exception:
                        pass
            self.run_status.set("Solver paused. Press Pause again to resume." if self._pause_requested else "Solver resumed.")
            self.progress_text_var.set("Progress: paused" if self._pause_requested else "Progress: running")
        else:
            self.run_status.set("No active solver to pause.")

    def stop_solver(self):
        if self._solver_thread is not None and self._solver_thread.is_alive():
            self._stop_requested = True
            self.run_status.set("Stop requested. The current calculation will stop at the next safe checkpoint.")
            self.progress_text_var.set("Progress: stopping")
        else:
            self.run_status.set("No active solver to stop.")

    def run_solver(self):
        if self._solver_thread is not None and self._solver_thread.is_alive():
            self.run_status.set("Solver is already running.")
            return
        try:
            self._pause_requested = False
            self._stop_requested = False
            self._paused_elapsed = 0.0
            self._pause_started_at = None
            self._progress_has_fraction = False
            solvers = load_solver_module()
            model = self.build_model_input()
            self.last_model = model
            self._run_started_at = time.time()
            self.progress_var.set(0.0)
            self.progress_text_var.set("Progress: running")
            self.timer_var.set("Elapsed: 00:00:00")
            self.eta_var.set("")
            try:
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start(12)
            except Exception:
                pass
            self.run_status.set(f"Running external solver: {self.var_solver_display.get()}")
            self.title(PROGRAM_VERSION + " — Solver active")

            def progress_callback(info):
                while self._pause_requested and not self._stop_requested:
                    time.sleep(0.10)
                if self._stop_requested:
                    raise RuntimeError("Solver stopped by user.")
                self._solver_queue.put(("progress", info))

            def worker():
                try:
                    result = solvers.solve(model, progress_callback=progress_callback)
                    self._solver_queue.put(("result", result))
                except Exception as exc:
                    self._solver_queue.put(("error", exc))

            self._solver_thread = threading.Thread(target=worker, daemon=True)
            self._solver_thread.start()
            self.after(100, self._poll_solver_queue)
            self.after(250, self._update_run_timer)
        except Exception as exc:
            self.run_status.set(f"Error: {exc}")
            messagebox.showerror("Solver error", str(exc))

    def _format_seconds(self, sec):
        try:
            sec = max(0, int(sec))
        except Exception:
            sec = 0
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _update_run_timer(self):
        if self._run_started_at is None:
            return
        now = self._pause_started_at if self._pause_started_at is not None else time.time()
        elapsed = max(0.0, now - self._run_started_at - float(getattr(self, "_paused_elapsed", 0.0)))
        self.timer_var.set("Elapsed: " + self._format_seconds(elapsed))
        if self._solver_thread is not None and self._solver_thread.is_alive():
            self.after(250, self._update_run_timer)

    def _poll_solver_queue(self):
        try:
            while True:
                kind, payload = self._solver_queue.get_nowait()
                if kind == "progress":
                    try:
                        self.progress_bar.stop()
                        self.progress_bar.configure(mode="determinate")
                    except Exception:
                        pass
                    self._progress_has_fraction = True
                    frac = max(0.0, min(1.0, float(payload.get("fraction", 0.0))))
                    self.progress_var.set(100.0 * frac)
                    msg = str(payload.get("message", "running"))
                    cur = payload.get("current", "")
                    total = payload.get("total", "")
                    self.progress_text_var.set(f"Progress: {msg} ({cur}/{total})")
                    self.run_status.set(msg)
                elif kind == "result":
                    self._finish_solver_success(payload)
                    return
                elif kind == "error":
                    self._finish_solver_error(payload)
                    return
        except queue.Empty:
            pass
        if self._solver_thread is not None and self._solver_thread.is_alive():
            self.after(100, self._poll_solver_queue)

    def _finish_solver_success(self, result):
        model = self.last_model
        self.last_result = result
        try:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
        except Exception:
            pass
        self.progress_var.set(100.0)
        self.progress_text_var.set("Progress: completed")
        self.title(PROGRAM_VERSION)
        self._populate_monitor(result)
        self._plot_pressure_diagram(model, result)
        self._plot_structural_diagrams(result)
        self._populate_results_table(result)
        self._populate_support_results_table(result)
        self._draw_reinforcement_preview_safe()
        self.update_query_table()
        self.run_status.set(f"{result.status}: {result.message}")
        if self.var_solver_display.get() == "Any wall (general case)":
            self._populate_general_diagnostics_from_result(result)
        self._populate_refinement_suggestion(result)
        self.nb.select(self.tab_charts)

    def _finish_solver_error(self, exc):
        try:
            self.progress_bar.stop()
        except Exception:
            pass
        self.title(PROGRAM_VERSION)
        self.run_status.set(f"Error: {exc}")
        self.progress_text_var.set("Progress: failed")
        messagebox.showerror("Solver error", str(exc))

    def _populate_refinement_suggestion(self, result):
        try:
            s = dict(getattr(result, "summary", {}) or {})
            theta = float(s.get("theta_deg", s.get("theta", 0.0)))
            zp = float(s.get("z_pivot_m", s.get("z_pivot", 0.0)))
            H = float(self._height_right())
            th_win = max(0.05, abs(theta) * 0.20)
            zp_win = max(0.05, H * 0.02)
            self.refine_theta_min.set(f"{max(0.0, theta - th_win):.4g}")
            self.refine_theta_max.set(f"{theta + th_win:.4g}")
            self.refine_zp_min.set(f"{max(0.0, zp - zp_win):.4g}")
            self.refine_zp_max.set(f"{min(H, zp + zp_win):.4g}")
            self.refine_msg_var.set(
                f"Suggested local refinement around selected mechanism: θ ≈ {theta:.4g}°, z_p ≈ {zp:.4g} m. "
                "You may edit the ranges above, then increase grid/refine settings and run again."
            )
        except Exception:
            if hasattr(self, "refine_msg_var"):
                self.refine_msg_var.set("No local refinement suggestion was available for this run.")

    def apply_refinement_suggestion(self):
        # The solver currently uses grid counts rather than direct min/max windows.
        # This button applies a safe research-grade refinement preset while keeping
        # the displayed window as the engineer's note for the rerun.
        try:
            self.var_general_case_theta_refine_passes.set(max(int(self.var_general_case_theta_refine_passes.get()), 7))
            self.var_general_case_theta_points.set(max(int(self.var_general_case_theta_points.get()), 81))
            self.var_general_case_zp_points.set(max(int(self.var_general_case_zp_points.get()), 33))
            self.var_general_case_bending_schemes.set(max(int(self.var_general_case_bending_schemes.get()), 15))
            self.run_status.set("High-accuracy refinement settings applied. Review/edit the fields, then press Shift+Enter to rerun.")
        except Exception as exc:
            messagebox.showerror("Refinement", str(exc))

    def _monitor_clear(self):
        if not hasattr(self, "monitor_tree"):
            return
        for item in self.monitor_tree.get_children():
            self.monitor_tree.delete(item)
        for row in (("Selected solver", self.var_solver_display.get()), ("Status", "Ready"), ("Note", "External solver pending")):
            self.monitor_tree.insert("", "end", values=row)

    def _populate_monitor(self, result):
        for item in self.monitor_tree.get_children():
            self.monitor_tree.delete(item)
        if hasattr(self, "candidate_tree"):
            for item in self.candidate_tree.get_children():
                self.candidate_tree.delete(item)
        s = dict(getattr(result, "summary", {}) or {})

        def add(q, v="", tag=()):
            self.monitor_tree.insert("", "end", values=(q, v), tags=tag)
        def section(title):
            add(title, "", ("section",))
        def num(v, nd=3, unit=""):
            try:
                x = float(v)
                if not math.isfinite(x):
                    return "n/a"
                ax = abs(x)
                if ax != 0 and (ax < 1e-3 or ax >= 1e5):
                    txt = f"{x:.3e}"
                else:
                    txt = f"{x:.{nd}f}"
                return (txt + (" " + unit if unit else "")).strip()
            except Exception:
                return str(v)
        def fval(key, default="n/a", nd=3, unit=""):
            return num(s.get(key, default), nd, unit) if key in s else str(default)

        section("Solver")
        add("Selected solver", self.var_solver_display.get())
        add("Internal mode", getattr(result, "solver_mode", ""))
        add("Status", getattr(result, "status", ""))
        add("Message", getattr(result, "message", ""))
        if s.get("response_classification"):
            add("Response classification", s.get("response_classification", ""))
        if s.get("engineering_converged"):
            add("Engineering convergence", s.get("engineering_convergence_reason", "accepted"), ("selected",))
        if s.get("diagnostic_warning"):
            add("Diagnostic warning", s.get("diagnostic_warning", ""), ("warning",))
        if s.get("spring_release_enabled"):
            section("Spring-release / free-base proximity")
            add("Spring factors tried", s.get("spring_factors_tried_text", ""))
            add("Spring factors accepted", s.get("spring_factors_accepted_text", ""))
            add("Final accepted spring factor", fval("final_spring_factor", nd=5))
            rejected = s.get("rejected_next_spring_factor", None)
            add("Rejected next spring factor", "none" if rejected in (None, "") else num(rejected, 5))
            add("Residual spring force R=ky·w_base", f"{fval('residual_base_spring_force_kN_per_m', nd=3, unit='kN/m')}  ({num(100.0*float(s.get('spring_force_ratio', 0.0)), 2, '% of driving force')})")
            add("Residual spring moment M=kθ·θ_base", f"{fval('residual_base_spring_moment_kNm_per_m', nd=3, unit='kNm/m')}  ({num(100.0*float(s.get('spring_moment_ratio_driving', 0.0)), 2, '% of driving moment')}; {num(100.0*float(s.get('spring_moment_ratio_wall', 0.0)), 2, '% of max wall moment')})")
            add("Spring influence ratio", f"{fval('spring_influence_percent', nd=2, unit='%')}  →  {s.get('spring_influence_classification', '')}", ("warning",) if s.get('spring_influence_classification') == 'spring-dominated' else ())
            add("Interpretation rule", s.get("spring_influence_rule", ""))

        candidates = list(s.get("general_case_solutions_table", []) or [])
        if candidates:
            section("Selected general-case solution")
            add("Ranking rule", s.get("ranking", "admissible, then least two-sided work"))
            add("Selected scheme", f"#{s.get('selected_scheme', 'n/a')}  |  γ factor = {num(s.get('selected_load_factor', 0), 3)}")
            add("Kinematic lock", "dx_trans = (H_R - z_pivot) tan(θ); dx is not an independent search variable", ("formula",))
            add("Displacement split", "w_total = w_bend + w_rigid", ("formula",))
            add("Total work formula", "W_L,total=-∫p_L w_total dz; W_R,total=∫p_R w_total dz; W_total=W_L,total+W_R,total", ("formula",))
            add("Bending energy formula", "W_bend,net=∫q_net w_bend dz; U_bend=0.5∫EIκ²dz; E_bend_res=W_bend,net-U_bend", ("formula",))
            add("Rigid work diagnostic", "W_rigid,net=∫q_net w_rigid dz; W_total = W_bend,net + W_rigid,net", ("formula",))
            add("Energy criterion", "force+moment equilibrium first; then W_bend,net≈U_bend; selected candidate has least |W_L,total|+|W_R,total| among admissible candidates", ("formula",))
            add("Movement", f"θ = {num(s.get('theta_rot_deg', 0), 4, 'deg')}; z_pivot = {num(s.get('z_pivot_m', 0), 3, 'm')}; dx_trans = {num(1000*float(s.get('dx_trans_m', 0)), 2, 'mm')}")
            add("Equilibrium residuals", f"ΣF = {num(s.get('ΣF kN/m', 0), 3, 'kN/m')}; ΣM = {num(s.get('ΣM kNm/m', 0), 3, 'kNm/m')}; |ΣF|/scale = {num(s.get('|ΣF|/scale', 0), 4)}; |ΣM|/scale = {num(s.get('|ΣM|/scale', 0), 4)}")
            add("Left/right total work", f"W_L,total = {num(s.get('W_left_signed kN·m/m', 0), 3, 'kJ/m')}; W_R,total = {num(s.get('W_right_signed kN·m/m', 0), 3, 'kJ/m')}; W_total = {num(s.get('W_total_signed kN·m/m', s.get('W_net_signed kN·m/m', 0)), 3, 'kJ/m')}")
            add("Bending energy balance", f"W_bend,net = {num(s.get('W_bend_net_signed kN·m/m', s.get('W_bending_net_signed kN·m/m', 0)), 3, 'kJ/m')}; U_bend = {num(s.get('U_bending_strain kN·m/m', 0), 3, 'kJ/m')}; E_bend_res = {num(s.get('energy_balance_residual kN·m/m', 0), 3, 'kJ/m')} ({num(s.get('energy_balance_norm', 0), 3)})")
            add("Rigid work diagnostic", f"W_rigid,net = {num(s.get('W_rigid_net_signed kN·m/m', s.get('rigid_work_residual kN·m/m', 0)), 3, 'kJ/m')}; check W_total≈W_bend,net+W_rigid,net")
            add("Least-action work", f"|W_L,total|+|W_R,total| = {num(s.get('W_sides_abs kN·m/m', 0), 3, 'kJ/m')}; diagnostic ∫|q_net w_total|dz = {num(s.get('W_total_abs diagnostic kN·m/m', 0), 3, 'kJ/m')}")
            add("Candidate count", f"{len(candidates)} ranked solutions. The zero-load scheme is retained only as a rigid-limit diagnostic.")

            for rec in candidates:
                rank = int(rec.get("rank_by_work", 0))
                lf = float(rec.get("load_factor", 0.0))
                if rank == 1:
                    tag = ("selected",)
                elif lf <= 1e-12:
                    tag = ("diagnostic",)
                else:
                    tag = ("candidate_even",) if (rank % 2 == 0) else ("candidate_odd",)
                status = "selected" if rank == 1 else ("rigid-limit" if lf <= 1e-12 else "candidate")
                self.candidate_tree.insert("", "end", values=(
                    rank,
                    num(lf, 3),
                    num(1000*float(rec.get("max_bending_deflection_m", 0.0)), 2, "mm"),
                    num(1000*float(rec.get("dx_trans_m", 0.0)), 2, "mm"),
                    num(rec.get("z_pivot_m", 0.0), 3, "m"),
                    num(rec.get("theta_rot_deg", 0.0), 4, "deg"),
                    num(rec.get("|ΣF|/scale", 0.0), 4),
                    num(rec.get("|ΣM|/scale", 0.0), 4),
                    num(rec.get("W_left_signed", 0.0), 3),
                    num(rec.get("W_right_signed", 0.0), 3),
                    num(rec.get("W_total_signed", rec.get("W_net_signed", 0.0)), 3),
                    num(rec.get("W_bend_net_signed", rec.get("W_bending_net_signed", 0.0)), 3),
                    num(rec.get("W_rigid_net_signed", 0.0), 3),
                    num(rec.get("U_bending_strain", 0.0), 3),
                    num(rec.get("energy_balance_residual", 0.0), 3),
                    num(rec.get("W_sides_abs", 0.0), 3),
                    status,
                ), tags=tag)
        else:
            section("Movement found/used")
            for key, label, unit, nd in (("dx_trans_m", "Solver Δx_trans", "m", 4), ("theta_rot_deg", "Solver θ_rot", "deg", 4), ("z_pivot_m", "Solver z_pivot", "m", 3), ("ΣF kN/m", "ΣF", "kN/m", 3), ("ΣM kNm/m", "ΣM", "kNm/m", 3)):
                if key in s:
                    add(label, num(s[key], nd, unit), ("movement",))
            if getattr(result, "solver_mode", "") == "no_bending":
                add("Rigid-wall kinematic note", "dx_trans is the horizontal displacement at the reported z_pivot level. The same straight final wall line can be represented by infinitely many equivalent z_pivot–dx_trans pairs if θ is kept fixed and dx is shifted consistently.")


        if not candidates:
            section("Essential results")
            for key, label, scale, nd, unit in (
                ("max_deflection_abs_m", "Max |Δx|", 1000.0, 2, "mm"),
                ("max_iteration_change_m", "Final Δchange", 1000.0, 4, "mm"),
                ("max_net_pressure_change_kPa", "Final pressure change", 1.0, 4, "kPa"),
                ("max_support_force_abs_kN_per_m", "Max support force", 1.0, 2, "kN/m"),
            ):
                if key in s:
                    add(label, num(scale*float(s.get(key, 0.0)), nd, unit))

        section("Problem / controls")
        for key, label, nd, unit in (
            ("H_R", "H_R", 3, "m"), ("H_L", "H_L", 3, "m"), ("EI", "EI", 3, ""),
            ("n_bending_schemes", "n bending schemes", 0, ""), ("total optimization evaluations", "candidate evaluations", 0, ""),
            ("theta refinement passes", "θ refinement passes", 0, ""), ("theta initial grid points", "θ grid points", 0, ""),
            ("z_pivot search min (m)", "z_pivot min", 3, "m"), ("z_pivot search max (m)", "z_pivot max", 3, "m"),
        ):
            if key in s:
                add(label, num(s[key], nd, unit))
        if "scheme load factors" in s:
            vals = s.get("scheme load factors") or []
            add("γ load factors", ", ".join(num(v, 3) for v in vals[:16]) + (" ..." if len(vals) > 16 else ""))

        section("Notes")
        add("Convergence charts", "For the new general-case solver they are candidate-evolution charts, not iterative deflection-convergence charts.")
        if "ranking note" in s:
            add("Ranking note", s.get("ranking note"))
    def _draw_geometry_safe(self):
        try:
            self._draw_geometry()
        except Exception:
            pass

    def _layer_property_key(self, layer: dict[str, Any]) -> tuple:
        return (
            round(parse_float(layer.get("c_prime", 0.0)), 6),
            round(parse_float(layer.get("phi_prime_deg", 0.0)), 6),
            round(parse_float(layer.get("gamma", 0.0)), 6),
            round(parse_float(layer.get("gamma_sat", 0.0)), 6),
            round(parse_float(layer.get("E_s", 0.0)), 6),
            round(parse_float(layer.get("nu", 0.0)), 6),
        )

    def _layer_color_map(self, left_layers, right_layers) -> dict[tuple, str]:
        palette = ["#fff1a8", "#d9f99d", "#bfdbfe", "#fecaca", "#ddd6fe", "#fed7aa", "#ccfbf1", "#fbcfe8"]
        color_map = {}
        for layer in list(left_layers) + list(right_layers):
            key = self._layer_property_key(layer)
            if key not in color_map:
                color_map[key] = palette[len(color_map) % len(palette)]
        return color_map

    def _draw_layer_blocks(self, ax, x0, x1, z_top, layers, beta_deg, color_map):
        """Draw soil blocks with sloping ground surface and horizontal layer bases.

        Positive beta means the ground rises away from the wall; because z is
        positive downwards, this gives smaller z away from the wall. Only the
        free ground surface follows beta. The layer bases/interfaces remain
        horizontal, so the base of the soil column at the wall is not tilted by
        the ground-slope correction.
        """
        tanb = math.tan(math.radians(float(beta_deg)))

        def surface_z(x: float) -> float:
            return float(z_top) - abs(float(x)) * tanb

        # Air above the sloping ground is not filled. For positive beta, the
        # wedge above the wall elevation is filled with the top-layer color.
        cum = 0.0
        for idx, layer in enumerate(layers):
            h = max(0.0, parse_float(layer["thickness"], 0.0))
            if h <= 0:
                continue
            color = color_map.get(self._layer_property_key(layer), "#fff1a8")
            z_upper_wall = float(z_top) + cum
            z_lower_wall = float(z_top) + cum + h

            if idx == 0:
                z_upper_a = surface_z(x0)
                z_upper_b = surface_z(x1)
            else:
                z_upper_a = z_upper_wall
                z_upper_b = z_upper_wall

            z_lower_a = z_lower_wall
            z_lower_b = z_lower_wall

            # Clip out any part above the actual ground surface for negative beta.
            # This keeps non-existing soil from being drawn.
            if idx > 0:
                z_upper_a = max(z_upper_a, surface_z(x0))
                z_upper_b = max(z_upper_b, surface_z(x1))
            z_lower_a = max(z_lower_a, z_upper_a)
            z_lower_b = max(z_lower_b, z_upper_b)

            poly = matplotlib.patches.Polygon(
                [(x0, z_upper_a), (x1, z_upper_b), (x1, z_lower_b), (x0, z_lower_a)],
                closed=True, facecolor=color, edgecolor="#8a6b2f", alpha=0.55
            )
            ax.add_patch(poly)
            z_label = 0.5 * (max(z_upper_a, z_upper_b) + min(z_lower_a, z_lower_b))
            ax.text(0.5*(x0+x1), z_label,
                    layer["code"], ha="center", va="center", fontsize=9, fontweight="bold")
            cum += h

    def _draw_geometry(self):
        if not hasattr(self, "ax_geom"):
            return
        ax = self.ax_geom
        ax.clear()
        H_L = self._height_left()
        H_R = self._height_right()
        z_p = float(self.var_z_pivot.get())
        z_pivot = float(self.var_z_pivot.get())
        z_left_surface = H_R - H_L
        # Geometry preview horizontal domain: base limits are exactly
        # xmin = -0.6*H_R and xmax = +0.6*H_R, keeping true 1:1 axis scale.
        x_extent = max(1.0, 0.60 * H_R)
        left_layers = self.left_layers_table.as_dicts() if hasattr(self, "left_layers_table") else []
        right_layers = self.right_layers_table.as_dicts() if hasattr(self, "right_layers_table") else []

        color_map = self._layer_color_map(left_layers, right_layers)
        beta_R_deg = float(self.var_beta_R.get())
        beta_L_deg = float(self.var_beta_L.get())
        self._draw_layer_blocks(ax, -x_extent, 0.0, z_left_surface, left_layers, beta_L_deg, color_map)
        self._draw_layer_blocks(ax, 0.0, x_extent, 0.0, right_layers, beta_R_deg, color_map)
        ax.plot([0, 0], [0, H_R], color="black", linewidth=3, label="wall")

        beta_R = math.radians(beta_R_deg)
        beta_L = math.radians(beta_L_deg)
        zR_end = 0.0 - x_extent * math.tan(beta_R)
        zL_end = z_left_surface - x_extent * math.tan(beta_L)
        ax.plot([0, x_extent], [0.0, zR_end], color="saddlebrown", linewidth=2.2, label="ground")
        ax.plot([0, -x_extent], [z_left_surface, zL_end], color="saddlebrown", linewidth=2.2)

        # Uniform surcharge indication: double red line, shown only when q exists.
        # Lines are drawn parallel to the corresponding ground surface.
        qR = float(self.var_q_R.get())
        qL = float(self.var_q_L.get())
        if qR > 0.0:
            off1, off2 = -0.18, -0.30
            ax.plot([0, x_extent], [0.0 + off1, zR_end + off1], color="red", linewidth=0.55)
            ax.plot([0, x_extent], [0.0 + off2, zR_end + off2], color="red", linewidth=1.5)
            ax.text(0.55*x_extent, 0.5*zR_end + off1 - 0.22, f"q_R = {qR:g} kPa", color="red", ha="center", va="bottom", fontsize=9, fontweight="bold")
        if qL > 0.0:
            off1, off2 = -0.18, -0.30
            ax.plot([0, -x_extent], [z_left_surface + off1, zL_end + off1], color="red", linewidth=0.55)
            ax.plot([0, -x_extent], [z_left_surface + off2, zL_end + off2], color="red", linewidth=1.5)
            ax.text(-0.55*x_extent, 0.5*(z_left_surface + zL_end) + off1 - 0.22, f"q_L = {qL:g} kPa", color="red", ha="center", va="bottom", fontsize=9, fontweight="bold")

        zwR = float(self.var_z_w_R.get())
        zwL = self._validated_left_water_depth()
        ax.hlines(zwR, 0.0, x_extent, color="blue", linestyle="--", linewidth=1.3, label="water level")
        ax.hlines(zwL, -x_extent, 0.0, color="blue", linestyle="--", linewidth=1.3)
        ax.plot(0, z_pivot, marker="o", markersize=8, color="red")

        zmin = min(-0.5, zR_end, zL_end) - 0.2
        zmax = H_R + 0.5
        ax.set_ylim(zmax, zmin)
        # Exact requested model-preview limits: xmin=-0.6*H_R, xmax=+0.6*H_R.
        ax.set_xlim(-x_extent, x_extent)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x (m, true scale)")
        ax.set_ylabel("z (m)")
        ax.grid(True, linestyle="--", alpha=0.3)
        handles, labels = ax.get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        self._safe_legend(ax, fontsize=8, loc="best")
        self.fig_geom.tight_layout()
        self.canvas_geom.draw_idle()

    def _redraw_charts_from_last(self):
        if self.last_model is None or self.last_result is None:
            return
        try:
            self._plot_pressure_diagram(self.last_model, self.last_result)
            self._plot_structural_diagrams(self.last_result)
        except Exception as exc:
            messagebox.showerror("Chart error", str(exc))

    def _strip_top_point(self, z, *arrays):
        """Remove only the plotted value at the top point z=min(z), not the axes."""
        z_list = list(z)
        if not z_list:
            return [z_list] + [list(a) for a in arrays]
        zmin = min(float(v) for v in z_list)
        keep = []
        for zi in z_list:
            try:
                keep.append(float(zi) > zmin + 1.0e-9)
            except Exception:
                keep.append(False)
        out = [[zi for zi, ok in zip(z_list, keep) if ok]]
        for arr in arrays:
            arr_list = list(arr)
            out.append([vi for vi, ok in zip(arr_list, keep) if ok])
        return out

    def _parse_chart_limit(self, chart_title: str, which: str):
        try:
            var = self.chart_limits.get(chart_title, {}).get(which)
            if var is None:
                return None
            txt = str(var.get()).strip().lower()
            if txt in ("", "auto", "a"):
                return None
            val = float(txt)
            return val if math.isfinite(val) else None
        except Exception:
            return None

    def _apply_chart_xlim(self, ax, chart_title: str, calculated_values):
        auto_min, auto_max = self._autoscale_x_limits(calculated_values)
        xmin = self._parse_chart_limit(chart_title, "xmin")
        xmax = self._parse_chart_limit(chart_title, "xmax")
        if xmin is None:
            xmin = auto_min
        if xmax is None:
            xmax = auto_max
        if not math.isfinite(xmin) or not math.isfinite(xmax) or abs(xmax - xmin) < 1.0e-15:
            xmin, xmax = -1.0, 1.0
        if xmin > xmax:
            xmin, xmax = xmax, xmin
        ax.set_xlim(xmin, xmax)
        ax.axvline(0.0, color="0.35", linewidth=1.0, zorder=1)

    def _autoscale_x_limits(self, values, pad=1.10):
        vals = []
        for v in values:
            try:
                x = float(v)
                if math.isfinite(x):
                    vals.append(x)
            except Exception:
                pass
        if not vals:
            return -1.0, 1.0

        # If a single top/singular value dominates the scale, ignore it for axes only.
        # The z=0 values are removed before plotting; this is an additional safety.
        if len(vals) >= 8:
            absvals = sorted(abs(v) for v in vals if abs(v) > 0.0)
            if len(absvals) >= 4:
                second = absvals[-2]
                largest = absvals[-1]
                if second > 0.0 and largest > 10.0 * second:
                    cap = 5.0 * second
                    vals = [v for v in vals if abs(v) <= cap]
        if not vals:
            return -1.0, 1.0

        xmin = min(vals)
        xmax = max(vals)
        tiny = 1.0e-15

        # If the calculated curve is identically zero, do not put zero on the plot border.
        # A symmetric interval keeps the calculated zero curve visible.
        if abs(xmin) <= tiny and abs(xmax) <= tiny:
            return -1.0, 1.0

        if xmin >= -tiny:
            return 0.0, pad * xmax if xmax > tiny else 1.0
        if xmax <= tiny:
            return pad * xmin if xmin < -tiny else -1.0, 0.0
        return pad * xmin, pad * xmax

    def _fill_to_zero(self, ax, x_values, z_values, color="0.82", alpha=0.32):
        """Soft grey fill between a calculated curve and x=0."""
        try:
            xs = []
            zs = []
            for x, z in zip(x_values, z_values):
                xf = float(x)
                zf = float(z)
                if math.isfinite(xf) and math.isfinite(zf):
                    xs.append(xf)
                    zs.append(zf)
            if len(xs) >= 2:
                ax.fill_betweenx(zs, 0.0, xs, color=color, alpha=alpha, linewidth=0.0, zorder=2)
        except Exception:
            pass

    def _plot_pressure_background(self, ax, model):
        H_R = model.geometry.H_R
        H_L = model.geometry.H_L
        z_left_surface = H_R - H_L
        x0, x1 = ax.get_xlim()
        x_left = min(0.0, float(x0))
        x_right = max(0.0, float(x1))
        beta_R = math.radians(model.right.beta_deg)
        beta_L = math.radians(model.left.beta_deg)
        # Background ground/water lines extend up to the corresponding x-axis limit.
        zR_end = 0.0 - 0.20 * H_R * math.tan(beta_R)
        zL_end = z_left_surface - 0.20 * H_R * math.tan(beta_L)
        ax.plot([0, 0], [0, H_R], color="0.15", linewidth=2.0, alpha=0.55, zorder=0)
        ax.plot([0, x_right], [0.0, zR_end], color="saddlebrown", linewidth=1.2, alpha=0.55, zorder=0)
        ax.plot([0, x_left], [z_left_surface, zL_end], color="saddlebrown", linewidth=1.2, alpha=0.55, zorder=0)
        ax.hlines(model.right.z_w, 0.0, x_right, color="blue", linestyle="--", linewidth=0.9, alpha=0.55, zorder=0)
        ax.hlines(model.left.z_w, x_left, 0.0, color="blue", linestyle="--", linewidth=0.9, alpha=0.55, zorder=0)
        ax.plot(0, model.movement.z_pivot, marker="o", markersize=6, color="red", alpha=0.9, zorder=3)

    def _plot_pressure_diagram(self, model, result):
        ax = self.ax_pressure
        ax.clear()
        z = list(result.z)
        left_calc = [-v for v in result.p_left]
        right_calc = list(result.p_right)
        left_oe = [-v for v in result.sigma_left_OE]
        right_oe = list(result.sigma_right_OE)
        left_pe = [-v for v in result.sigma_left_PE]
        right_pe = list(result.sigma_right_PE)
        left_ae = [-v for v in result.sigma_left_AE]
        right_ae = list(result.sigma_right_AE)

        z_plot, left_calc, right_calc, left_oe, right_oe, left_pe, right_pe, left_ae, right_ae = self._strip_top_point(
            z, left_calc, right_calc, left_oe, right_oe, left_pe, right_pe, left_ae, right_ae
        )

        # Axis limits are controlled only by the calculated pressure curves, not by envelopes.
        self._apply_chart_xlim(ax, "Total pressure", right_calc + left_calc)
        self._plot_pressure_background(ax, model)

        self._fill_to_zero(ax, left_calc, z_plot)
        self._fill_to_zero(ax, right_calc, z_plot)
        ax.plot(left_calc, z_plot, color="black", linewidth=2.0, linestyle="-", label="Calculated left", zorder=10)
        ax.plot(right_calc, z_plot, color="black", linewidth=2.0, linestyle="-", label="Calculated right", zorder=10)
        ax.plot(left_oe, z_plot, color="black", linewidth=1.1, linestyle="--", label="σOE", zorder=8)
        ax.plot(right_oe, z_plot, color="black", linewidth=1.1, linestyle="--", zorder=8)
        ax.plot(left_pe, z_plot, color="red", linewidth=1.1, linestyle="--", label="σPE", zorder=8)
        ax.plot(right_pe, z_plot, color="red", linewidth=1.1, linestyle="--", zorder=8)
        ax.plot(left_ae, z_plot, color="green", linewidth=1.1, linestyle="--", label="σAE", zorder=8)
        ax.plot(right_ae, z_plot, color="green", linewidth=1.1, linestyle="--", zorder=8)
        ax.set_ylim(model.geometry.H_R, min(-0.5, -0.2*model.geometry.H_R*math.tan(math.radians(model.right.beta_deg))))
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.set_xlabel("total horizontal pressure, p_h (kPa)")
        ax.set_ylabel("z (m)")
        ax.set_title("Total pressure")
        handles, labels = ax.get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        self._safe_legend(ax, fontsize=7, loc="best")
        self.fig_pressure.tight_layout()
        self.canvas_pressure.draw_idle()

    def _autoscale_x(self, ax, values, pad=1.10):
        xmin, xmax = self._autoscale_x_limits(values, pad=pad)
        ax.set_xlim(xmin, xmax)
        ax.axvline(0.0, color="0.35", linewidth=1.0, zorder=1)

    # Backward-compatible name for any older internal calls.
    def _autoscale_symmetric_x(self, ax, values, pad=1.10):
        self._autoscale_x(ax, values, pad=pad)

    def _plot_k_diagram(self, result):
        ax = self.ax_k
        ax.clear()
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.invert_yaxis()
        z = list(result.z)
        kL = [-v for v in getattr(result, "K_left", [])]
        kR = list(getattr(result, "K_right", []))
        z_plot, kL, kR = self._strip_top_point(z, kL, kR)
        self._fill_to_zero(ax, kL, z_plot)
        self._fill_to_zero(ax, kR, z_plot)
        ax.plot(kL, z_plot, color="black", linewidth=2.0, label="K_L", zorder=10)
        ax.plot(kR, z_plot, color="black", linewidth=2.0, label="K_R", zorder=10)
        self._apply_chart_xlim(ax, "K diagram", kL + kR)
        ax.set_title("K diagram")
        ax.set_xlabel("K (left negative, right positive)")
        ax.set_ylabel("z (m)")
        self._safe_legend(ax, fontsize=7, loc="best")
        self.fig_k.tight_layout()
        self.canvas_k.draw_idle()

    def _plot_mobilization_diagram(self, result):
        """Plot two demand ratios: active-side Δx/Δxmax,A and passive-side Δx/Δxmax,P."""
        ax = self.ax_mobilization
        ax.clear()
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.invert_yaxis()
        z = list(result.z)

        # Passive local depth starts at the left/excavation ground surface.
        # Do not plot the passive z_local=0 point, nor anything above it.
        z_passive_surface = 0.0
        try:
            if self.last_model is not None:
                z_passive_surface = float(self.last_model.geometry.H_R) - float(self.last_model.geometry.H_L)
        except Exception:
            z_passive_surface = 0.0

        w_vals = list(getattr(result, "deflection", []))
        dxmax_A = list(getattr(result, "dxmax_right_A", []))
        dxmax_P = list(getattr(result, "dxmax_left_P", []))
        ratio_A = []
        ratio_P = []
        for i, zi in enumerate(z):
            try:
                wi = abs(float(w_vals[i]))
            except Exception:
                wi = float("nan")

            # Active-side ratio, using the right active limiting displacement.
            try:
                limA = abs(float(dxmax_A[i])) if i < len(dxmax_A) else float("nan")
                ratio_A.append(-wi / limA if math.isfinite(wi) and math.isfinite(limA) and limA > 1.0e-15 else float("nan"))
            except Exception:
                ratio_A.append(float("nan"))

            # Passive-side ratio: only below the passive local origin.
            try:
                if float(zi) <= z_passive_surface + 1.0e-9:
                    ratio_P.append(float("nan"))
                else:
                    limP = abs(float(dxmax_P[i])) if i < len(dxmax_P) else float("nan")
                    ratio_P.append(wi / limP if math.isfinite(wi) and math.isfinite(limP) and limP > 1.0e-15 else float("nan"))
            except Exception:
                ratio_P.append(float("nan"))

        z_plot, ratio_A, ratio_P = self._strip_top_point(z, ratio_A, ratio_P)
        ax.plot(ratio_A, z_plot, color="black", linewidth=2.0, linestyle="-", label="Δx/Δxmax,A", zorder=10)
        ax.plot(ratio_P, z_plot, color="black", linewidth=2.0, linestyle="--", label="Δx/Δxmax,P", zorder=10)
        ax.axvline(-1.0, color="red", linewidth=1.2, linestyle="-", alpha=0.75, label="active limit")
        ax.axvline(1.0, color="red", linewidth=1.2, linestyle="--", alpha=0.75, label="passive limit")
        self._apply_chart_xlim(ax, "Δx/Δxmax", ratio_A + ratio_P)
        ax.set_title("Δx / Δxmax")
        ax.set_xlabel("Δx / Δxmax (-)")
        ax.set_ylabel("z (m)")
        handles, labels = ax.get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        self._safe_legend(ax, fontsize=7, loc="best")
        self.fig_mobilization.tight_layout()
        self.canvas_mobilization.draw_idle()

    def _plot_effective_water_diagrams(self, result):
        z = list(result.z)
        eff_L = list(getattr(result, "sigma_left_eff", []))
        eff_R = list(getattr(result, "sigma_right_eff", []))
        u_L = list(getattr(result, "u_left", []))
        u_R = list(getattr(result, "u_right", []))
        z_eff, eff_L, eff_R, u_L, u_R = self._strip_top_point(z, eff_L, eff_R, u_L, u_R)

        ax = self.ax_effective
        ax.clear(); ax.grid(True, linestyle="--", alpha=0.35); ax.invert_yaxis()
        left_curve = [-(v if _is_finite(v) else float("nan")) for v in eff_L]
        right_curve = [(v if _is_finite(v) else float("nan")) for v in eff_R]
        self._fill_to_zero(ax, left_curve, z_eff)
        self._fill_to_zero(ax, right_curve, z_eff)
        ax.plot(left_curve, z_eff, color="black", linewidth=2.0, linestyle="--", label="left σ'_h", zorder=10)
        ax.plot(right_curve, z_eff, color="black", linewidth=2.0, linestyle="-", label="right σ'_h", zorder=10)
        self._apply_chart_xlim(ax, "Effective stresses", left_curve + right_curve)
        ax.set_title("Effective horizontal stresses")
        ax.set_xlabel("-σ'_h,L or σ'_h,R (kPa)"); ax.set_ylabel("z (m)")
        self._safe_legend(ax, fontsize=7, loc="best")

        ax = self.ax_water
        ax.clear(); ax.grid(True, linestyle="--", alpha=0.35); ax.invert_yaxis()
        left_u = [-(v if _is_finite(v) else float("nan")) for v in u_L]
        right_u = [(v if _is_finite(v) else float("nan")) for v in u_R]
        self._fill_to_zero(ax, left_u, z_eff)
        self._fill_to_zero(ax, right_u, z_eff)
        ax.plot(left_u, z_eff, color="blue", linewidth=2.0, linestyle="--", label="left u", zorder=10)
        ax.plot(right_u, z_eff, color="blue", linewidth=2.0, linestyle="-", label="right u", zorder=10)
        self._apply_chart_xlim(ax, "Water stresses", left_u + right_u)
        ax.set_title("Water stresses")
        ax.set_xlabel("-u_L or u_R (kPa)"); ax.set_ylabel("z (m)")
        self._safe_legend(ax, fontsize=7, loc="best")

    def _plot_structural_diagrams(self, result):
        for ax in (self.ax_deflection, self.ax_rotation, self.ax_net, self.ax_shear, self.ax_moment, self.ax_mobilization, self.ax_effective, self.ax_water, self.ax_conv_change, self.ax_conv_defl):
            ax.clear()
            ax.grid(True, linestyle="--", alpha=0.35)
            ax.invert_yaxis()
        z_all = list(result.z)

        # Plot deflection to the left by convention. Remove only the z=0 plotted value.
        defl_plot = [-1000.0 * v for v in result.deflection]
        compare_defl = []
        for v in getattr(result, "deflection_compare", []):
            try:
                compare_defl.append(-1000.0 * float(v))
            except Exception:
                compare_defl.append(float("nan"))
        dxmax_A = []
        for v in getattr(result, "dxmax_right_A", []):
            try:
                dxmax_A.append(-1000.0 * abs(float(v)))
            except Exception:
                dxmax_A.append(float("nan"))
        dxmax_P = []
        for v in getattr(result, "dxmax_left_P", []):
            try:
                val = 1000.0 * abs(float(v))
                dxmax_P.append(-val if val > 0.0 else float("nan"))
            except Exception:
                dxmax_P.append(float("nan"))
        z_def, defl_plot, compare_defl, dxmax_A, dxmax_P = self._strip_top_point(z_all, defl_plot, compare_defl, dxmax_A, dxmax_P)
        # Passive Δxmax is meaningful only below the passive local origin.
        try:
            z_passive_surface = float(self.last_model.geometry.H_R) - float(self.last_model.geometry.H_L) if self.last_model is not None else 0.0
            dxmax_P = [v if float(zz) > z_passive_surface + 1.0e-9 else float("nan") for zz, v in zip(z_def, dxmax_P)]
        except Exception:
            pass
        self.ax_deflection.plot(defl_plot, z_def, color="black", linewidth=2.0, label="calculated Δx", zorder=10)
        if compare_defl and any(math.isfinite(v) for v in compare_defl):
            label = getattr(result, "deflection_compare_label", "comparison") or "comparison"
            self.ax_deflection.plot(compare_defl, z_def, color="0.35", linewidth=1.4, linestyle="-.", label=label)
        if dxmax_A and any(math.isfinite(v) for v in dxmax_A):
            self.ax_deflection.plot(dxmax_A, z_def, color="red", linewidth=1.3, linestyle="--", label="Δxmax,A")
        if dxmax_P and any(math.isfinite(v) for v in dxmax_P):
            self.ax_deflection.plot(dxmax_P, z_def, color="red", linewidth=1.3, linestyle=(0, (6, 3)), label="Δxmax,P")
        # Deflection x-axis is controlled by the calculated deflection only.
        # Special case: if the calculated deflection is identically zero, force a
        # symmetric mm-scale interval so the vertical zero-deflection curve is visible
        # and is not hidden on the plot border. User x_min/x_max values still override.
        finite_defl = [float(v) for v in defl_plot if _is_finite(v)]
        if finite_defl and max(abs(v) for v in finite_defl) <= 1.0e-12:
            xmin_user = self._parse_chart_limit("Deflection", "xmin")
            xmax_user = self._parse_chart_limit("Deflection", "xmax")
            self.ax_deflection.set_xlim(-1.0 if xmin_user is None else xmin_user, 1.0 if xmax_user is None else xmax_user)
            self.ax_deflection.axvline(0.0, color="0.35", linewidth=1.0, zorder=1)
        else:
            self._apply_chart_xlim(self.ax_deflection, "Deflection", defl_plot)
        self.ax_deflection.set_title("Deflection")
        self.ax_deflection.set_xlabel("-Δx (mm)")
        self.ax_deflection.set_ylabel("z (m)")
        self._safe_legend(self.ax_deflection, fontsize=7, loc="best")

        z_rot, rot = self._strip_top_point(z_all, [math.degrees(v) for v in result.rotation])
        self.ax_rotation.plot(rot, z_rot, color="black", linewidth=2.0, zorder=10)
        self._apply_chart_xlim(self.ax_rotation, "Rotation", rot)
        self.ax_rotation.set_title("Rotation")
        self.ax_rotation.set_xlabel("θ (deg)")
        self.ax_rotation.set_ylabel("z (m)")

        z_net, netp = self._strip_top_point(z_all, result.net_pressure)
        self._fill_to_zero(self.ax_net, netp, z_net)
        self.ax_net.plot(netp, z_net, color="black", linewidth=2.0, zorder=10)
        self._apply_chart_xlim(self.ax_net, "Net pressure", netp)
        self.ax_net.set_title("Net pressure")
        self.ax_net.set_xlabel("p_net (kPa)")
        self.ax_net.set_ylabel("z (m)")

        z_shear, shear = self._strip_top_point(z_all, result.shear)
        self._fill_to_zero(self.ax_shear, shear, z_shear)
        self.ax_shear.plot(shear, z_shear, color="black", linewidth=2.0, zorder=10)
        self._apply_chart_xlim(self.ax_shear, "Shear", shear)
        self.ax_shear.set_title("Shear")
        self.ax_shear.set_xlabel("V (kN/m)")
        self.ax_shear.set_ylabel("z (m)")

        z_mom, mom = self._strip_top_point(z_all, result.moment)
        self._fill_to_zero(self.ax_moment, mom, z_mom)
        self.ax_moment.plot(mom, z_mom, color="black", linewidth=2.0, zorder=10)
        self._apply_chart_xlim(self.ax_moment, "Moment", mom)
        self.ax_moment.set_title("Moment")
        self.ax_moment.set_xlabel("M (kNm/m)")
        self.ax_moment.set_ylabel("z (m)")

        self._plot_effective_water_diagrams(result)
        self._plot_k_diagram(result)
        self._plot_mobilization_diagram(result)
        self._plot_convergence_diagram(result)
        for fig, canvas in (
            (self.fig_deflection, self.canvas_deflection),
            (self.fig_rotation, self.canvas_rotation),
            (self.fig_net, self.canvas_net),
            (self.fig_shear, self.canvas_shear),
            (self.fig_moment, self.canvas_moment),
            (self.fig_mobilization, self.canvas_mobilization),
            (self.fig_effective, self.canvas_effective),
            (self.fig_water, self.canvas_water),
            (self.fig_conv_change, self.canvas_conv_change),
            (self.fig_conv_defl, self.canvas_conv_defl),
        ):
            fig.tight_layout()
            canvas.draw_idle()

    def _plot_convergence_diagram(self, result):
        """Professional candidate-path plots for the general-case solver.

        The general case is now a candidate enumeration/variational ranking, not
        a deflection-iteration solver.  These two chart panels therefore show
        physically meaningful solution-family information as a function of the
        load/bending factor γ, while the legacy convergence plots are retained
        for the fixed-base solvers.
        """
        s = dict(getattr(result, "summary", {}) or {})
        candidates = list(s.get("general_case_solutions_table", []) or [])
        for ax in (self.ax_conv_change, self.ax_conv_defl):
            ax.clear()
            ax.set_facecolor(SUBTLE_BG)
            ax.grid(True, linestyle="--", alpha=0.28, linewidth=0.8)
        # Remove any secondary y-axes from a previous redraw before creating a
        # fresh twinx axis below.  Without this, repeated chart updates can stack
        # invisible axes and gradually slow down the GUI.
        try:
            for extra_ax in list(self.fig_conv_defl.axes)[1:]:
                extra_ax.remove()
        except Exception:
            pass

        if candidates:
            # Sort by physical load/bending factor, not by ranking index.  This
            # makes the curves interpretable as a family of mechanisms.
            rows = sorted(candidates, key=lambda r: float(r.get("load_factor", 0.0)))
            gamma = [float(r.get("load_factor", 0.0)) for r in rows]
            Wtotal = [float(r.get("W_total_signed", r.get("W_net_signed", 0.0))) for r in rows]
            Wb = [float(r.get("W_bend_net_signed", r.get("W_bending_net_signed", 0.0))) for r in rows]
            Wr = [float(r.get("W_rigid_net_signed", 0.0)) for r in rows]
            U = [float(r.get("U_bending_strain", 0.0)) for r in rows]
            E = [float(r.get("E_bend_residual", r.get("E_residual", 0.0))) for r in rows]
            bend = [1000.0 * float(r.get("max_bending_deflection_m", 0.0)) for r in rows]
            dx = [1000.0 * float(r.get("dx_trans_m", 0.0)) for r in rows]
            theta = [float(r.get("theta_rot_deg", 0.0)) for r in rows]
            zps = [float(r.get("z_pivot_m", 0.0)) for r in rows]
            selected = None
            for i, r in enumerate(rows):
                if int(r.get("rank_by_work", 999999)) == 1:
                    selected = i
                    break

            # Panel 1: Energetic interpretation.
            self.ax_conv_change.plot(gamma, Wtotal, linewidth=2.0, marker="o", markersize=4, label="W_total")
            self.ax_conv_change.plot(gamma, Wr, linewidth=1.5, marker="^", markersize=3, label="W_rigid,net")
            self.ax_conv_change.plot(gamma, Wb, linewidth=1.8, marker="s", markersize=4, label="W_bend,net")
            self.ax_conv_change.plot(gamma, U, linewidth=1.8, marker="d", markersize=4, label="U_bend")
            self.ax_conv_change.axhline(0.0, linewidth=0.8, color="#6b7280", alpha=0.55)
            if selected is not None:
                gx = gamma[selected]
                self.ax_conv_change.axvline(gx, linewidth=1.2, color=ACCENT_DARK, alpha=0.35)
                self.ax_conv_change.scatter([gx], [Wtotal[selected]], s=70, zorder=5, edgecolors="black", label="selected")
                self.ax_conv_change.annotate(
                    f"selected γ={gx:.3f}\nE_bend res={E[selected]:.2e}",
                    xy=(gx, Wtotal[selected]), xytext=(8, 12), textcoords="offset points",
                    fontsize=8, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=BORDER, alpha=0.92),
                )
            self.ax_conv_change.set_title("Energy balance across bending schemes")
            self.ax_conv_change.set_xlabel("bending/load factor γ")
            self.ax_conv_change.set_ylabel("work / energy (kJ/m)")
            self._safe_legend(self.ax_conv_change, loc="best", fontsize=8, frameon=True)

            # Panel 2: Kinematics.  Avoid mixing metres, degrees and millimetres
            # in a confusing way: show displacements on the left axis and rotation
            # on the right axis, with selected z_pivot in the annotation.
            self.ax_conv_defl.plot(gamma, bend, linewidth=2.0, marker="o", markersize=4, label="max bending dx")
            self.ax_conv_defl.plot(gamma, dx, linewidth=1.8, marker="s", markersize=4, label="dx_trans")
            ax2 = self.ax_conv_defl.twinx()
            ax2.set_facecolor("none")
            ax2.plot(gamma, theta, linewidth=1.8, marker="^", markersize=4, label="θ")
            if selected is not None:
                gx = gamma[selected]
                self.ax_conv_defl.axvline(gx, linewidth=1.2, color=ACCENT_DARK, alpha=0.35)
                self.ax_conv_defl.scatter([gx], [bend[selected]], s=70, zorder=5, edgecolors="black")
                ax2.scatter([gx], [theta[selected]], s=55, zorder=5, edgecolors="black")
                self.ax_conv_defl.annotate(
                    f"z_pivot={zps[selected]:.3f} m\nθ={theta[selected]:.4f}°\ndx_trans={dx[selected]:.2f} mm",
                    xy=(gx, bend[selected]), xytext=(8, -42), textcoords="offset points",
                    fontsize=8, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=BORDER, alpha=0.92),
                )
            self.ax_conv_defl.set_title("Kinematic path of admissible mechanisms")
            self.ax_conv_defl.set_xlabel("bending/load factor γ")
            self.ax_conv_defl.set_ylabel("displacement (mm)")
            ax2.set_ylabel("rotation θ (deg)")
            lines, labels = self.ax_conv_defl.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            combined = [(ln, lb) for ln, lb in zip(lines + lines2, labels + labels2) if lb and not str(lb).startswith("_")]
            if combined:
                self.ax_conv_defl.legend([x[0] for x in combined], [x[1] for x in combined], loc="best", fontsize=8, frameon=True)
        else:
            hist = list(getattr(result, "convergence_history", []) or [])
            its, changes, maxdefs = [], [], []
            for rec in hist:
                try:
                    its.append(float(rec.get("iteration", len(its) + 1)))
                    changes.append(float(rec.get("max_change_m", float("nan"))))
                    maxdefs.append(float(rec.get("max_abs_deflection_m", float("nan"))))
                except Exception:
                    continue
            if its:
                y_change = [1000.0 * abs(v) if _is_finite(v) else float("nan") for v in changes]
                y_def = [1000.0 * abs(v) if _is_finite(v) else float("nan") for v in maxdefs]
                self.ax_conv_change.plot(its, y_change, color="black", linewidth=2.0, marker="o", markersize=3)
                self.ax_conv_defl.plot(its, y_def, color="black", linewidth=2.0, marker="s", markersize=3)
            else:
                for ax in (self.ax_conv_change, self.ax_conv_defl):
                    ax.text(0.5, 0.5, "No iterative convergence history\nfor this solver/mode.", ha="center", va="center", transform=ax.transAxes)
                    ax.set_xlim(0.0, 1.0); ax.set_ylim(0.0, 1.0)
            self.ax_conv_change.set_title("Convergence: Δchange")
            self.ax_conv_change.set_xlabel("iteration")
            self.ax_conv_change.set_ylabel("max Δchange (mm)")
            self.ax_conv_defl.set_title("Convergence: |Δx|")
            self.ax_conv_defl.set_xlabel("iteration")
            self.ax_conv_defl.set_ylabel("max |Δx| (mm)")
        self.fig_conv_change.tight_layout(); self.canvas_conv_change.draw_idle()
        self.fig_conv_defl.tight_layout(); self.canvas_conv_defl.draw_idle()

    def _populate_general_diagnostics_from_result(self, result):
        """Redesigned equilibrium diagnostics for the locked general-case solver.

        It uses the already-computed candidates. No extra heatmap computation is
        triggered here, so the GUI remains responsive after a long run.
        """
        if not hasattr(self, "accepted_points_tree"):
            return
        for item in self.accepted_points_tree.get_children():
            self.accepted_points_tree.delete(item)
        s = dict(getattr(result, "summary", {}) or {})
        rows = list(s.get("general_case_solutions_table", []) or [])
        self._accepted_points_records = []
        if not rows:
            self.accepted_points_status.set("No general-case candidate table is available. Use heatmaps only for legacy rigid diagnostics.")
            return
        self.accepted_points_status.set("General-case candidates ranked by energy admissibility and least two-sided work. dx_trans is locked by dx_trans=(H_R-z_pivot)tan(θ), not searched independently.")
        for r in rows:
            rec = {
                "rank": int(r.get("rank_by_work", 0)),
                "dx": float(r.get("dx_trans_m", 0.0)),
                "theta": float(r.get("theta_rot_deg", 0.0)),
                "zp": float(r.get("z_pivot_m", 0.0)),
                "F": float(r.get("ΣF kN/m", 0.0)),
                "M": float(r.get("ΣM kNm/m", 0.0)),
                "W": float(r.get("W_total_signed", r.get("W_net_signed", 0.0))),
                "Fnorm": float(r.get("|ΣF|/scale", 0.0)),
                "Mnorm": float(r.get("|ΣM|/scale", 0.0)),
                "score": float(r.get("score", 0.0)),
                "Wnorm": float(r.get("load_factor", 0.0)),
            }
            self._accepted_points_records.append(rec)
            self.accepted_points_tree.insert("", "end", values=(
                rec["rank"], f"{1000*rec['dx']:.2f} mm", f"{rec['theta']:.4f}", f"{rec['zp']:.3f}",
                f"{rec['F']:.3g}", f"{rec['M']:.3g}", f"{rec['W']:.3g}",
                f"{rec['Fnorm']:.3g}", f"{rec['Mnorm']:.3g}", f"{rec['score']:.3g}", f"γ={rec['Wnorm']:.3f}",
            ))
        # Lightweight scatter, drawn once from candidate rows.
        try:
            if self.fig_accepted_points is None:
                from matplotlib.figure import Figure
                self.fig_accepted_points = Figure(figsize=(8, 3.2), dpi=100)
                self.canvas_accepted_points = self._register_plot_canvas(FigureCanvasTkAgg(self.fig_accepted_points, master=self.accepted_points_scatter_frame))
                self.canvas_accepted_points.get_tk_widget().pack(fill="both", expand=True)
            fig = self.fig_accepted_points
            fig.clear()
            ax = fig.add_subplot(111)
            xs = [float(r.get("load_factor", 0.0)) for r in rows]
            ys = [float(r.get("E_bend_residual", r.get("E_residual", 0.0))) for r in rows]
            sizes = [40.0 + 5.0 * max(0.0, 1000.0 * float(r.get("max_bending_deflection_m", 0.0))) for r in rows]
            labels = [int(r.get("rank_by_work", 0)) for r in rows]
            ax.axhline(0.0, linewidth=1.0, color="#6b7280", alpha=0.6)
            ax.scatter(xs, ys, s=sizes, alpha=0.85, edgecolors="black", linewidths=0.4)
            for x, y, lab in zip(xs, ys, labels):
                if lab <= 3:
                    ax.annotate(str(lab), (x, y), fontsize=8, xytext=(4, 4), textcoords="offset points")
            ax.set_xlabel("bending/load factor γ")
            ax.set_ylabel("E_bend residual = W_bend,net − U_bend (kJ/m)")
            ax.set_title("Candidate energy compatibility; marker size reflects max bending")
            ax.grid(True, linestyle="--", alpha=0.30)
            fig.tight_layout()
            self.canvas_accepted_points.draw_idle()
        except Exception:
            pass

    def _populate_results_table(self, result):
        for item in self.results_table.get_children():
            self.results_table.delete(item)
        n = len(result.z)
        for i in range(n):
            vals = (
                fmt(result.z[i]),
                fmt(result.p_left[i] if i < len(result.p_left) else 0),
                fmt(result.p_right[i] if i < len(result.p_right) else 0),
                fmt(result.net_pressure[i] if i < len(result.net_pressure) else 0),
                fmt(getattr(result, "sigma_left_eff", [0]*n)[i] if i < len(getattr(result, "sigma_left_eff", [])) else 0),
                fmt(getattr(result, "sigma_right_eff", [0]*n)[i] if i < len(getattr(result, "sigma_right_eff", [])) else 0),
                fmt(getattr(result, "u_left", [0]*n)[i] if i < len(getattr(result, "u_left", [])) else 0),
                fmt(getattr(result, "u_right", [0]*n)[i] if i < len(getattr(result, "u_right", [])) else 0),
                fmt(result.K_left[i] if i < len(getattr(result, "K_left", [])) else 0),
                fmt(result.K_right[i] if i < len(getattr(result, "K_right", [])) else 0),
                fmt(result.m_left[i] if i < len(getattr(result, "m_left", [])) else 0),
                fmt(result.m_right[i] if i < len(getattr(result, "m_right", [])) else 0),
                fmt(1000.0 * getattr(result, "dxmax_right_A", [0]*n)[i] if i < len(getattr(result, "dxmax_right_A", [])) else 0),
                fmt(1000.0 * getattr(result, "dxmax_left_P", [0]*n)[i] if i < len(getattr(result, "dxmax_left_P", [])) else 0),
                fmt(result.shear[i] if i < len(result.shear) else 0),
                fmt(result.moment[i] if i < len(result.moment) else 0),
                fmt(1000.0 * result.deflection[i] if i < len(result.deflection) else 0),
                fmt(math.degrees(result.rotation[i]) if i < len(result.rotation) else 0),
            )
            self.results_table.insert("", "end", values=vals)

    def add_query_row(self):
        try:
            zq = float(self.var_query_z.get())
        except Exception:
            messagebox.showwarning("Point query", "Enter a valid z value first.")
            return
        vals = getattr(self, "_query_z_values", [])
        vals.append(zq)
        self._query_z_values = vals
        self.update_query_table()

    def remove_selected_query_rows(self):
        selected = set(self.query_tree.selection()) if hasattr(self, "query_tree") else set()
        if not selected:
            return
        keep = []
        for item in self.query_tree.get_children():
            vals = self.query_tree.item(item, "values")
            if item not in selected and vals:
                try:
                    keep.append(float(vals[0]))
                except Exception:
                    pass
        self._query_z_values = keep or [float(self.var_query_z.get())]
        self.update_query_table()

    def update_query_table(self):
        if not hasattr(self, "query_tree"):
            return
        for item in self.query_tree.get_children():
            self.query_tree.delete(item)
        result = self.last_result
        if not hasattr(self, "_query_z_values") or not self._query_z_values:
            try:
                self._query_z_values = [float(self.var_query_z.get())]
            except Exception:
                self._query_z_values = [0.0]
        if result is None or not getattr(result, "z", None):
            self.query_tree.insert("", "end", values=("No result",) + ("",)*19)
            return

        def interp(values, zq):
            if not values:
                return 0.0
            z = result.z
            if zq <= z[0]:
                return values[0]
            if zq >= z[-1]:
                return values[-1]
            for i in range(1, len(z)):
                if z[i] >= zq:
                    t = (zq - z[i-1]) / max(z[i] - z[i-1], 1e-12)
                    return values[i-1] * (1-t) + values[i] * t
            return values[-1]

        def arr(name):
            return list(getattr(result, name, []))
        for zq in self._query_z_values:
            vals = (
                fmt(zq),
                fmt(interp(result.p_left, zq)), fmt(interp(result.p_right, zq)), fmt(interp(result.net_pressure, zq)),
                fmt(1000.0 * interp(result.deflection, zq)), fmt(math.degrees(interp(result.rotation, zq))),
                fmt(interp(result.shear, zq)), fmt(interp(result.moment, zq)),
                fmt(interp(arr("K_left"), zq)), fmt(interp(arr("K_right"), zq)),
                fmt(interp(arr("m_left"), zq)), fmt(interp(arr("m_right"), zq)),
                fmt(interp(arr("sigma_left_OE"), zq)), fmt(interp(arr("sigma_left_AE"), zq)), fmt(interp(arr("sigma_left_PE"), zq)),
                fmt(interp(arr("sigma_right_OE"), zq)), fmt(interp(arr("sigma_right_AE"), zq)), fmt(interp(arr("sigma_right_PE"), zq)),
                fmt(1000.0 * interp(arr("dxmax_right_A"), zq)), fmt(1000.0 * interp(arr("dxmax_left_P"), zq)),
            )
            self.query_tree.insert("", "end", values=vals)

    def _empty_results(self):
        try:
            solvers = load_solver_module()
            model = self.build_model_input()
            result = solvers.make_placeholder_result(model, model.solver_mode, "No run yet.")
            self.last_model = model
            self.last_result = result
            self._plot_pressure_diagram(model, result)
            self._plot_structural_diagrams(result)
            self._populate_results_table(result)
            self.update_query_table()
        except Exception:
            pass

    def copy_results_table(self):
        cols = self.results_table["columns"]
        lines = ["\t".join(self.results_table.heading(c, "text") for c in cols)]
        for item in self.results_table.get_children():
            lines.append("\t".join(str(v) for v in self.results_table.item(item, "values")))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        messagebox.showinfo("Copy table", "Results table copied to clipboard.")

    def load_defaults(self):
        self.var_beta_L.set(0.0)
        self.var_beta_R.set(0.0)
        self.var_q_L.set(0.0)
        self.var_q_R.set(0.0)
        self.var_z_w_L.set(20.0)
        self.var_z_w_R.set(20.0)
        self.var_gamma_w.set(9.81)
        self.var_k_h.set(0.0)
        self.var_k_v.set(0.0)
        self.var_dx_trans.set(0.0)
        self.var_theta_rot.set(0.0)
        self.var_z_pivot.set(4.0)
        self._draw_geometry_safe()
        if hasattr(self, "var_reinf_type"):
            self.var_reinf_type.set("No reinforcement")
            self._reinforcement_type_changed()

    def show_about(self):
        messagebox.showinfo(
            "About",
            f"{PROGRAM_VERSION}\n\n"
            "Educational / research tool for CUT embedded wall calculations.\n\n"
            "Developer: Associate Professor Lysandros Pantelidis\n"
            "Department of Civil Engineering and Geomatics\n"
            "Cyprus University of Technology\n"
            "Email: lysandros.pantelidis@cut.ac.cy\n\n"
            "Free educational tool. No warranty is provided. Use at your own responsibility."
        )

    def on_closing(self):
        """Terminate GUI and remaining background threads/processes cleanly."""

        try:

            self._stop_requested = True
            self._pause_requested = False

            try:
                self.progress_bar.stop()
            except Exception:
                pass

            try:
                import matplotlib.pyplot as plt
                plt.close("all")
            except Exception:
                pass

            try:
                self.quit()
            except Exception:
                pass

            try:
                self.destroy()
            except Exception:
                pass

        finally:
            os._exit(0)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    App().mainloop()
