import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import os
import math
import json
from typing import Tuple, Optional, Dict

from constants import CONCRETE_FCK, STEEL_FYK
from struct_design import (
    oneway_smax_main, oneway_smax_dist, twoway_smax_short, twoway_smax_long,
    asb_min_area, split_duz_pilye, select_rebar_min_area, max_possible_area,
    rho_min_oneway
)
from slab_model import SlabSystem, Slab, color_for_id, clamp, rect_normalize
from dxf_out import export_to_dxf

# Yeni modüller - hesap ve raporlama
from oneway_slab import compute_oneway_report
from twoway_slab import compute_twoway_report
from moment_balance_slab import balance_support_moments
from balcony_slab import compute_balcony_report
import json_loader

# ---------------------------------------------------------------------------
# Gerçek koordinat tabanlı döşeme bilgisi (metre cinsinden)
# ---------------------------------------------------------------------------
class RealSlab:
    """Metre cinsinden gerçek koordinatlarla döşeme."""
    def __init__(self, sid: str, x: float, y: float, w: float, h: float,
                 kind: str, pd: float, b: float):
        self.sid = sid
        self.x = x      # sol üst köşe X (metre)
        self.y = y      # sol üst köşe Y (metre)
        self.w = w      # genişlik (metre) - X yönü
        self.h = h      # yükseklik (metre) - Y yönü
        self.kind = kind
        self.pd = pd
        self.b = b

    def edges(self):
        """L, R, T, B kenarlarının (x0,y0,x1,y1) koordinatları."""
        return {
            "L": (self.x, self.y, self.x, self.y + self.h),
            "R": (self.x + self.w, self.y, self.x + self.w, self.y + self.h),
            "T": (self.x, self.y, self.x + self.w, self.y),
            "B": (self.x, self.y + self.h, self.x + self.w, self.y + self.h),
        }

    def edge_length(self, edge: str) -> float:
        if edge in ("L", "R"):
            return self.h
        return self.w

    def center(self):
        return self.x + self.w / 2, self.y + self.h / 2


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Döşeme Yerleşimi + Moment + As + Donatı Seçimi (TS500/Uygulama)")
        self.geometry("1600x900")

        # Grid parameters (hücre sistemi arka planda korunuyor)
        self.Nx, self.Ny = 60, 60
        self.system = SlabSystem(self.Nx, self.Ny)

        # inputs
        self.pd = tk.DoubleVar(value=10.0)
        self.b_width = tk.DoubleVar(value=1.0)
        self.bw = tk.DoubleVar(value=0.30)

        # rebar inputs
        self.conc = tk.StringVar(value="C25/30")
        self.steel = tk.StringVar(value="B420C")
        self.h_mm = tk.DoubleVar(value=120.0)
        self.cover_mm = tk.DoubleVar(value=25.0)

        self.mode = tk.StringVar(value="PLACE_SLAB")
        self.last_design = {}

        # Orantılı çizim verileri
        self.real_slabs: Dict[str, RealSlab] = {}
        self.scale = 80.0             # metre -> pixel
        self.canvas_pad = 60          # kenar boşluğu (px)
        self.highlighted_edge = None  # (sid, edge_name) or None
        self.selected_edge = None     # (sid, edge_name) or None

        # Kiriş kenarları: set of normalized edge tuples ((x0,y0,x1,y1))
        self.beam_edges: set = set()

        # Yeni döşeme boyutu dialogda kullanılacak
        self.new_slab_width = tk.DoubleVar(value=4.0)
        self.new_slab_height = tk.DoubleVar(value=5.0)

        self._build_ui()
        self.redraw()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        # Parameters
        prm = ttk.LabelFrame(top, text="Yeni Döşeme Parametreleri")
        prm.pack(side="left", fill="x", expand=True)

        r = 0
        ttk.Label(prm, text="Lx (m):").grid(row=r, column=0, padx=2)
        ttk.Entry(prm, textvariable=self.new_slab_width, width=6).grid(row=r, column=1, padx=2)
        ttk.Label(prm, text="Ly (m):").grid(row=r, column=2, padx=2)
        ttk.Entry(prm, textvariable=self.new_slab_height, width=6).grid(row=r, column=3, padx=2)
        ttk.Label(prm, text="pd:").grid(row=r, column=4, padx=2)
        ttk.Entry(prm, textvariable=self.pd, width=6).grid(row=r, column=5, padx=2)
        ttk.Label(prm, text="b:").grid(row=r, column=6, padx=2)
        ttk.Entry(prm, textvariable=self.b_width, width=6).grid(row=r, column=7, padx=2)
        ttk.Label(prm, text="bw:").grid(row=r, column=8, padx=2)
        ttk.Entry(prm, textvariable=self.bw, width=6).grid(row=r, column=9, padx=2)

        # Materials
        reb = ttk.LabelFrame(top, text="Malzeme / h")
        reb.pack(side="left", padx=10)
        ttk.Combobox(reb, textvariable=self.conc, values=list(CONCRETE_FCK.keys()), width=8).grid(row=0, column=0)
        ttk.Combobox(reb, textvariable=self.steel, values=list(STEEL_FYK.keys()), width=8).grid(row=1, column=0)
        ttk.Entry(reb, textvariable=self.h_mm, width=6).grid(row=0, column=1)
        ttk.Label(reb, text="h(mm)").grid(row=0, column=2)
        ttk.Entry(reb, textvariable=self.cover_mm, width=6).grid(row=1, column=1)
        ttk.Label(reb, text="cover").grid(row=1, column=2)

        # Tools
        tools = ttk.LabelFrame(top, text="Araçlar")
        tools.pack(side="left", padx=10)
        modes = [
            ("DÖŞEME", "PLACE_SLAB"),
            ("BALCONY", "PLACE_BALCONY"),
            ("Kiriş Ekle/Sil", "BEAM"),
        ]
        for i, (txt, val) in enumerate(modes):
            ttk.Radiobutton(tools, text=txt, variable=self.mode, value=val).grid(
                row=0, column=i, sticky="w", padx=4)

        act = ttk.Frame(top)
        act.pack(side="right")
        ttk.Button(act, text="Döşeme Ekle", command=self.add_first_slab).pack(fill="x", pady=1)
        ttk.Button(act, text="JSON'dan Yükle", command=self.load_from_json).pack(fill="x", pady=1)
        ttk.Button(act, text="Hesapla", command=self.compute_and_report).pack(fill="x", pady=1)
        ttk.Button(act, text="DXF", command=self.export_dxf_and_open).pack(fill="x", pady=1)
        ttk.Button(act, text="Temizle", command=self.reset_all).pack(fill="x", pady=1)

        # Main Area
        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, padx=10, pady=8)

        # Canvas with scrollbar
        canvas_frame = ttk.Frame(mid)
        canvas_frame.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="white", cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Configure>", lambda e: self.redraw())

        right = ttk.Frame(mid, width=500)
        right.pack(side="left", fill="y", padx=10)

        # Slab list
        list_frame = ttk.LabelFrame(right, text="Döşemeler")
        list_frame.pack(fill="x")
        self.slab_list = tk.Listbox(list_frame, height=8, font=("Consolas", 9))
        self.slab_list.pack(fill="x", padx=4, pady=4)
        ttk.Button(list_frame, text="Seçiliyi Sil", command=self.delete_selected_slab).pack(pady=2)

        self.output = tk.Text(right, wrap="word", height=30, font=("Consolas", 9))
        self.output.pack(fill="both", expand=True, pady=5)

    # =========================================================
    # Orantılı çizim yardımcıları
    # =========================================================
    def _compute_scale(self):
        """Canvas boyutuna göre ölçek hesapla - tüm döşemeler sığacak şekilde."""
        if not self.real_slabs:
            return

        # Tüm döşemelerin kaplama alanını bul
        min_x = min(rs.x for rs in self.real_slabs.values())
        min_y = min(rs.y for rs in self.real_slabs.values())
        max_x = max(rs.x + rs.w for rs in self.real_slabs.values())
        max_y = max(rs.y + rs.h for rs in self.real_slabs.values())

        total_w = max_x - min_x
        total_h = max_y - min_y

        if total_w < 0.01 or total_h < 0.01:
            return

        cw = self.canvas.winfo_width() - 2 * self.canvas_pad
        ch = self.canvas.winfo_height() - 2 * self.canvas_pad

        if cw < 100: cw = 600
        if ch < 100: ch = 500

        scale_x = cw / total_w
        scale_y = ch / total_h
        self.scale = min(scale_x, scale_y) * 0.9  # %90 doluluk

        # Merkeze offset
        drawn_w = total_w * self.scale
        drawn_h = total_h * self.scale
        self.origin_x = (self.canvas.winfo_width() - drawn_w) / 2 - min_x * self.scale
        self.origin_y = (self.canvas.winfo_height() - drawn_h) / 2 - min_y * self.scale

    def m_to_px(self, mx: float, my: float) -> Tuple[float, float]:
        """Metre koordinatını pixel koordinatına dönüştür."""
        if not hasattr(self, 'origin_x'):
            self.origin_x = self.canvas_pad
            self.origin_y = self.canvas_pad
        return self.origin_x + mx * self.scale, self.origin_y + my * self.scale

    def px_to_m(self, px: float, py: float) -> Tuple[float, float]:
        """Pixel koordinatını metre koordinatına dönüştür."""
        if not hasattr(self, 'origin_x'):
            self.origin_x = self.canvas_pad
            self.origin_y = self.canvas_pad
        return (px - self.origin_x) / self.scale, (py - self.origin_y) / self.scale

    # =========================================================
    # Çizim
    # =========================================================
    def redraw(self):
        self.canvas.delete("all")

        if not self.real_slabs:
            # Boş canvas - yardım mesajı
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw > 100 and ch > 100:
                self.canvas.create_text(
                    cw / 2, ch / 2,
                    text="Lx ve Ly değerlerini girip 'Döşeme Ekle' butonuna basın\n"
                         "veya mevcut döşemenin kenarına tıklayarak komşu döşeme ekleyin.",
                    font=("Arial", 12), fill="#999999", justify="center")
            return

        self._compute_scale()

        # Döşemeleri çiz
        for sid, rs in self.real_slabs.items():
            self._draw_slab(rs)

        # Kirişleri çiz (kalın siyah çizgi)
        for edge_key in self.beam_edges:
            self._draw_beam_line(edge_key)

        # Vurgulanan kenarı çiz
        if self.highlighted_edge:
            sid, edge = self.highlighted_edge
            if sid in self.real_slabs:
                color = "#0066FF" if self.mode.get() == "BEAM" else "#FF6600"
                self._draw_edge_highlight(self.real_slabs[sid], edge, color=color, width=4)

        # Seçilen kenarı çiz
        if self.selected_edge:
            sid, edge = self.selected_edge
            if sid in self.real_slabs:
                self._draw_edge_highlight(self.real_slabs[sid], edge, color="#FF0000", width=5)

    def _draw_slab(self, rs: RealSlab):
        """Tek bir döşemeyi orantılı çiz."""
        x0, y0 = self.m_to_px(rs.x, rs.y)
        x1, y1 = self.m_to_px(rs.x + rs.w, rs.y + rs.h)

        fill_color = color_for_id(rs.sid)

        # Dolgu
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill_color,
                                     outline="#333333", width=2)

        # Etiket - m oranı ve yön bilgisi ile
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if rs.kind == "BALCONY":
            label = f"{rs.sid}\nBALKON\n{rs.w:.2f}×{rs.h:.2f} m"
        else:
            Ls = min(rs.w, rs.h)
            Ll = max(rs.w, rs.h)
            m_ratio = Ll / Ls if Ls > 0 else 0
            if rs.kind == "ONEWAY":
                dir_text = "Tek Doğrultuda Çalışan"
            else:
                dir_text = "Çift Doğrultuda Çalışan"
            label = f"{rs.sid}\n{rs.kind} (m={m_ratio:.2f})\n{dir_text}\n{rs.w:.2f}×{rs.h:.2f} m"
        self.canvas.create_text(cx, cy, text=label,
                                font=("Arial", 10, "bold"), justify="center")

        # Boyut çizgileri (kenar dışında)
        dim_offset = 18
        # Üst kenar - genişlik
        self.canvas.create_line(x0, y0 - dim_offset, x1, y0 - dim_offset,
                                fill="#666666", width=1, arrow="both")
        self.canvas.create_text((x0 + x1) / 2, y0 - dim_offset - 10,
                                text=f"{rs.w:.2f} m", font=("Arial", 8), fill="#666666")
        # Sol kenar - yükseklik
        self.canvas.create_line(x0 - dim_offset, y0, x0 - dim_offset, y1,
                                fill="#666666", width=1, arrow="both")
        self.canvas.create_text(x0 - dim_offset - 10, (y0 + y1) / 2,
                                text=f"{rs.h:.2f} m", font=("Arial", 8), fill="#666666",
                                angle=90)

    def _draw_edge_highlight(self, rs: RealSlab, edge: str, color: str, width: int):
        """Bir döşemenin belirli kenarını vurgula."""
        edges = rs.edges()
        ex0, ey0, ex1, ey1 = edges[edge]
        px0, py0 = self.m_to_px(ex0, ey0)
        px1, py1 = self.m_to_px(ex1, ey1)
        self.canvas.create_line(px0, py0, px1, py1, fill=color, width=width)

    def _draw_beam_line(self, edge_key):
        """Kiriş çizgisini kalın siyah çizgi olarak çiz."""
        x0, y0, x1, y1 = edge_key
        px0, py0 = self.m_to_px(x0, y0)
        px1, py1 = self.m_to_px(x1, y1)
        self.canvas.create_line(px0, py0, px1, py1, fill="#111111", width=5)

    # =========================================================
    # Kenar algılama
    # =========================================================
    def _find_nearest_edge(self, px: float, py: float, threshold_px: float = 15.0) -> Optional[Tuple[str, str]]:
        """Tıklanan noktaya en yakın döşeme kenarını bul."""
        mx, my = self.px_to_m(px, py)
        best_dist = float('inf')
        best = None

        for sid, rs in self.real_slabs.items():
            edges = rs.edges()
            for edge_name, (ex0, ey0, ex1, ey1) in edges.items():
                dist = self._point_to_segment_dist(mx, my, ex0, ey0, ex1, ey1)
                dist_px = dist * self.scale
                if dist_px < threshold_px and dist_px < best_dist:
                    best_dist = dist_px
                    best = (sid, edge_name)

        return best

    def _point_to_segment_dist(self, px, py, x0, y0, x1, y1) -> float:
        """Noktanın doğru parçasına uzaklığı (metre)."""
        dx = x1 - x0
        dy = y1 - y0
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return math.hypot(px - x0, py - y0)

        t = max(0, min(1, ((px - x0) * dx + (py - y0) * dy) / len_sq))
        proj_x = x0 + t * dx
        proj_y = y0 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def _find_slab_at(self, px: float, py: float) -> Optional[str]:
        """Tıklanan noktadaki döşemeyi bul."""
        mx, my = self.px_to_m(px, py)
        for sid, rs in self.real_slabs.items():
            if rs.x <= mx <= rs.x + rs.w and rs.y <= my <= rs.y + rs.h:
                return sid
        return None

    def _determine_slab_kind(self, w: float, h: float) -> str:
        """Döşeme tipini Ll/Ls oranına göre otomatik belirle.
        
        Ls: Kısa doğrultudaki döşeme açıklığı
        Ll: Uzun doğrultudaki döşeme açıklığı
        m = Ll / Ls
        m > 2  → Tek Doğrultuda (ONEWAY)
        m ≤ 2  → Çift Doğrultuda (TWOWAY)
        """
        Ls = min(w, h)
        Ll = max(w, h)
        if Ls <= 0:
            return "ONEWAY"
        m = Ll / Ls
        return "ONEWAY" if m > 2 else "TWOWAY"

    # =========================================================
    # Mouse olayları
    # =========================================================
    def on_canvas_motion(self, evt):
        """Mouse hareket ettikçe en yakın kenarı vurgula."""
        if not self.real_slabs:
            return

        edge = self._find_nearest_edge(evt.x, evt.y)
        if edge != self.highlighted_edge:
            self.highlighted_edge = edge
            self.redraw()

    def on_canvas_click(self, evt):
        """Canvas'a tıklandığında moda göre işlem yap."""
        if not self.real_slabs:
            return

        edge = self._find_nearest_edge(evt.x, evt.y)
        if not edge:
            self.selected_edge = None
            self.redraw()
            return

        if self.mode.get() == "BEAM":
            # Kiriş modu: kenarı kiriş olarak ekle/kaldır
            self._toggle_beam(edge)
        else:
            # Döşeme modu: kenar seç ve komşu döşeme ekle
            self.selected_edge = edge
            self.redraw()
            self.after(100, lambda: self._add_adjacent_slab_dialog(edge, (evt.x, evt.y)))

    # =========================================================
    # Kiriş yönetimi
    # =========================================================
    def _edge_to_key(self, sid: str, edge_name: str):
        """Döşeme kenarını normalize edilmiş (x0,y0,x1,y1) tuple'a dönüştür."""
        rs = self.real_slabs[sid]
        edges = rs.edges()
        ex0, ey0, ex1, ey1 = edges[edge_name]
        # Normalize: küçük koordinat önce
        return (round(min(ex0, ex1), 4), round(min(ey0, ey1), 4),
                round(max(ex0, ex1), 4), round(max(ey0, ey1), 4))

    def _toggle_beam(self, edge_info):
        """Kenardaki kirişi ekle veya kaldır."""
        sid, edge_name = edge_info
        key = self._edge_to_key(sid, edge_name)
        if key in self.beam_edges:
            self.beam_edges.discard(key)
        else:
            self.beam_edges.add(key)
        self._sync_to_cell_system()
        self.redraw()

    # =========================================================
    # Döşeme ekleme
    # =========================================================
    def add_first_slab(self):
        """İlk döşemeyi veya bağımsız döşemeyi (0,0)'a ekle."""
        w = self.new_slab_width.get()
        h = self.new_slab_height.get()

        if w <= 0 or h <= 0:
            messagebox.showerror("Hata", "Lx ve Ly pozitif olmalı!")
            return

        sid = simpledialog.askstring("ID", "Döşeme ID:", parent=self)
        if not sid:
            return

        if sid in self.real_slabs:
            if not messagebox.askyesno("Overwrite", f"{sid} zaten var. Ezilsin mi?"):
                return
            self._delete_real_slab(sid)

        if "BALCONY" in self.mode.get():
            kind = "BALCONY"
        else:
            kind = self._determine_slab_kind(w, h)

        # İlk döşeme ise (0,0); değilse mevcut döşemelerin sağına ekle
        if not self.real_slabs:
            x, y = 0.0, 0.0
        else:
            # Mevcut döşemelerin en sağına ekle
            max_x = max(rs.x + rs.w for rs in self.real_slabs.values())
            x = max_x
            y = 0.0

        rs = RealSlab(sid, x, y, w, h, kind, self.pd.get(), self.b_width.get())
        self.real_slabs[sid] = rs
        self._sync_to_cell_system()
        self.refresh_slab_list()
        self.redraw()

    def _add_adjacent_slab_dialog(self, edge_info: Tuple[str, str], click_pos: Tuple[int, int] = None):
        """Seçilen kenara komşu yeni döşeme ekle."""
        ref_sid, ref_edge = edge_info
        ref = self.real_slabs[ref_sid]

        # Varsayılan hizalamayı tıklandığı konuma göre belirle
        default_align = "Üst" if ref_edge in ("L", "R") else "Sol"
        if click_pos:
            cx, cy = click_pos
            mx, my = self.px_to_m(cx, cy)
            if ref_edge in ("L", "R"):
                # Dikey kenar: Ortadan aşağıdaysa "Alt", yukarıdaysa "Üst"
                mid_y = ref.y + ref.h / 2
                default_align = "Alt" if my > mid_y else "Üst"
            else:
                # Yatay kenar: Ortadan sağdaysa "Sağ", soldaysa "Sol"
                mid_x = ref.x + ref.w / 2
                default_align = "Sağ" if mx > mid_x else "Sol"

        # Yeni döşemenin ortak kenar boyutu otomatik (sadece referans için gösterilecek)
        if ref_edge in ("L", "R"):
            shared_len = ref.h  # Ortak kenar Y yönünde
            default_lx = 4.0
            default_ly = shared_len
            align_options = ["Üst", "Alt"]
        else:
            shared_len = ref.w  # Ortak kenar X yönünde
            default_lx = shared_len
            default_ly = 4.0
            align_options = ["Sol", "Sağ"]

        # Dialog
        dlg = tk.Toplevel(self)
        dlg.title("Komşu Döşeme Ekle")
        dlg.geometry("350x330")
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Referans: {ref_sid} - {ref_edge} kenarı",
                  font=("Arial", 10, "bold")).pack(pady=5)
        ttk.Label(dlg, text=f"Ortak kenar uzunluğu: {shared_len:.2f} m").pack()

        frame = ttk.Frame(dlg)
        frame.pack(pady=10, padx=20, fill="x")

        # Row 0: ID
        ttk.Label(frame, text="Döşeme ID:").grid(row=0, column=0, sticky="w", pady=3)
        sid_var = tk.StringVar()
        ttk.Entry(frame, textvariable=sid_var, width=10).grid(row=0, column=1, pady=3)

        # Row 1: Lx
        ttk.Label(frame, text="Lx (genişlik, m):").grid(row=1, column=0, sticky="w", pady=3)
        lx_var = tk.DoubleVar(value=default_lx)
        ttk.Entry(frame, textvariable=lx_var, width=10).grid(row=1, column=1, pady=3)

        # Row 2: Ly
        ttk.Label(frame, text="Ly (yükseklik, m):").grid(row=2, column=0, sticky="w", pady=3)
        ly_var = tk.DoubleVar(value=default_ly)
        ttk.Entry(frame, textvariable=ly_var, width=10).grid(row=2, column=1, pady=3)

        # Row 3: Alignment
        ttk.Label(frame, text="Hizalama:").grid(row=3, column=0, sticky="w", pady=3)
        align_var = tk.StringVar(value=default_align)
        align_combo = ttk.Combobox(frame, textvariable=align_var, values=align_options, width=10, state="readonly")
        align_combo.grid(row=3, column=1, pady=3)

        # Row 4: Type (otomatik belirlenir, sadece bilgi amaçlı)
        ttk.Label(frame, text="Tip:").grid(row=4, column=0, sticky="w", pady=3)
        auto_kind = "BALCONY" if "BALCONY" in self.mode.get() else self._determine_slab_kind(lx_var.get(), ly_var.get())
        kind_var = tk.StringVar(value=auto_kind)
        kind_label = ttk.Label(frame, textvariable=kind_var, font=("Arial", 9, "bold"))
        kind_label.grid(row=4, column=1, pady=3)

        def _update_kind(*args):
            try:
                lx = lx_var.get()
                ly = ly_var.get()
                if lx > 0 and ly > 0 and "BALCONY" not in self.mode.get():
                    kind_var.set(self._determine_slab_kind(lx, ly))
            except Exception:
                pass
        lx_var.trace_add("write", _update_kind)
        ly_var.trace_add("write", _update_kind)

        def do_add():
            new_sid = sid_var.get().strip()
            val_lx = lx_var.get()
            val_ly = ly_var.get()
            align = align_var.get()

            if not new_sid:
                messagebox.showerror("Hata", "ID boş olamaz!", parent=dlg)
                return
            if val_lx <= 0 or val_ly <= 0:
                messagebox.showerror("Hata", "Boyutlar pozitif olmalı!", parent=dlg)
                return

            if new_sid in self.real_slabs:
                if not messagebox.askyesno("Overwrite", f"{new_sid} zaten var. Ezilsin mi?", parent=dlg):
                    return
                self._delete_real_slab(new_sid)

            # Yeni döşemenin konum ve boyutunu hesapla
            nx, ny = 0.0, 0.0
            nw, nh = val_lx, val_ly

            if ref_edge == "R":
                # Sağ kenara ekle
                nx = ref.x + ref.w
                if align == "Üst":
                    ny = ref.y
                else: # Alt
                    ny = ref.y + ref.h - nh

            elif ref_edge == "L":
                # Sol kenara ekle
                nx = ref.x - nw
                if align == "Üst":
                    ny = ref.y
                else: # Alt
                    ny = ref.y + ref.h - nh

            elif ref_edge == "B":
                # Alt kenara ekle
                ny = ref.y + ref.h
                if align == "Sol":
                    nx = ref.x
                else: # Sağ
                    nx = ref.x + ref.w - nw

            elif ref_edge == "T":
                # Üst kenara ekle
                ny = ref.y - nh
                if align == "Sol":
                    nx = ref.x
                else: # Sağ
                    nx = ref.x + ref.w - nw
            else:
                return

            # Çakışma kontrolü
            for osid, ors in self.real_slabs.items():
                if self._rects_overlap(nx, ny, nw, nh, ors.x, ors.y, ors.w, ors.h):
                    messagebox.showerror("Hata", f"Çakışma: {osid}", parent=dlg)
                    return

            rs = RealSlab(new_sid, nx, ny, nw, nh, kind_var.get(),
                          self.pd.get(), self.b_width.get())
            self.real_slabs[new_sid] = rs
            self.selected_edge = None
            self._sync_to_cell_system()
            self.refresh_slab_list()
            self.redraw()
            dlg.destroy()

        ttk.Button(dlg, text="Ekle", command=do_add).pack(pady=10)

    def _rects_overlap(self, x1, y1, w1, h1, x2, y2, w2, h2) -> bool:
        """İki dikdörtgenin çakışıp çakışmadığını kontrol et (kenar teması hariç)."""
        eps = 0.001
        return not (x1 + w1 <= x2 + eps or x2 + w2 <= x1 + eps or
                    y1 + h1 <= y2 + eps or y2 + h2 <= y1 + eps)

    # =========================================================
    # Hücre sistemi senkronizasyonu
    # =========================================================
    def _sync_to_cell_system(self):
        """real_slabs'ı hücre tabanlı SlabSystem'e senkronize et.
        
        Her döşemenin metre koordinatlarını hücre indekslerine çevirir.
        Bu, mevcut hesaplama altyapısının (oneway, twoway, balcony) 
        değişmeden çalışmasını sağlar.
        """
        # Eski sistemdeki tüm slabları temizle
        for sid in list(self.system.slabs.keys()):
            self.system.delete_slab(sid)
        self.system.V_beam.clear()
        self.system.H_beam.clear()

        if not self.real_slabs:
            return

        # Tüm benzersiz X ve Y koordinatlarını topla
        x_coords = set()
        y_coords = set()
        for rs in self.real_slabs.values():
            x_coords.add(round(rs.x, 6))
            x_coords.add(round(rs.x + rs.w, 6))
            y_coords.add(round(rs.y, 6))
            y_coords.add(round(rs.y + rs.h, 6))

        x_sorted = sorted(x_coords)
        y_sorted = sorted(y_coords)

        # Grid boyutunu güncelle
        self.Nx = max(len(x_sorted), 2)
        self.Ny = max(len(y_sorted), 2)
        self.system = SlabSystem(self.Nx + 10, self.Ny + 10)

        # Her döşeme için hücre indekslerini bul
        for sid, rs in self.real_slabs.items():
            i0 = x_sorted.index(round(rs.x, 6))
            i1 = x_sorted.index(round(rs.x + rs.w, 6)) - 1
            j0 = y_sorted.index(round(rs.y, 6))
            j1 = y_sorted.index(round(rs.y + rs.h, 6)) - 1

            if i1 < i0:
                i1 = i0
            if j1 < j0:
                j1 = j0

            # dx/dy otomatik hesapla: toplam boyut / hücre sayısı
            nx_cells = i1 - i0 + 1
            ny_cells = j1 - j0 + 1
            auto_dx = rs.w / nx_cells
            auto_dy = rs.h / ny_cells

            s = Slab(sid, i0, j0, i1, j1, rs.kind, auto_dx, auto_dy, rs.pd, rs.b)
            self.system.add_slab(s)

        # Komşu döşemeler arasındaki ortak kenarları kiriş olarak işaretle
        for sid, rs in self.real_slabs.items():
            s = self.system.slabs.get(sid)
            if not s:
                continue
            for osid, ors in self.real_slabs.items():
                if osid == sid:
                    continue
                # Sağ kenar = diğerinin sol kenarı
                if abs((rs.x + rs.w) - ors.x) < 0.001:
                    # Dikey ortak kenar - V_beam ekle
                    x_idx = x_sorted.index(round(rs.x + rs.w, 6))
                    ov_y_start = max(round(rs.y, 6), round(ors.y, 6))
                    ov_y_end = min(round(rs.y + rs.h, 6), round(ors.y + ors.h, 6))
                    if ov_y_end > ov_y_start:
                        j_start = y_sorted.index(round(ov_y_start, 6))
                        j_end_idx = y_sorted.index(round(ov_y_end, 6))
                        for jj in range(j_start, j_end_idx):
                            self.system.V_beam.add((x_idx - 1, jj))

                # Alt kenar = diğerinin üst kenarı
                if abs((rs.y + rs.h) - ors.y) < 0.001:
                    y_idx = y_sorted.index(round(rs.y + rs.h, 6))
                    ov_x_start = max(round(rs.x, 6), round(ors.x, 6))
                    ov_x_end = min(round(rs.x + rs.w, 6), round(ors.x + ors.w, 6))
                    if ov_x_end > ov_x_start:
                        i_start = x_sorted.index(round(ov_x_start, 6))
                        i_end_idx = x_sorted.index(round(ov_x_end, 6))
                        for ii in range(i_start, i_end_idx):
                            self.system.H_beam.add((ii, y_idx - 1))

        # Manuel kiriş kenarlarını V_beam/H_beam'e dönüştür
        for bx0, by0, bx1, by1 in self.beam_edges:
            is_vertical = abs(bx0 - bx1) < 0.001
            is_horizontal = abs(by0 - by1) < 0.001

            if is_vertical:
                # Dikey kiriş
                bx_r = round(bx0, 6)
                if bx_r in x_coords:
                    x_idx = x_sorted.index(bx_r)
                    by_start_r = round(by0, 6)
                    by_end_r = round(by1, 6)
                    if by_start_r in y_coords and by_end_r in y_coords:
                        j_start = y_sorted.index(by_start_r)
                        j_end = y_sorted.index(by_end_r)
                        for jj in range(j_start, j_end):
                            if x_idx > 0:
                                self.system.V_beam.add((x_idx - 1, jj))

            elif is_horizontal:
                # Yatay kiriş
                by_r = round(by0, 6)
                if by_r in y_coords:
                    y_idx = y_sorted.index(by_r)
                    bx_start_r = round(bx0, 6)
                    bx_end_r = round(bx1, 6)
                    if bx_start_r in x_coords and bx_end_r in x_coords:
                        i_start = x_sorted.index(bx_start_r)
                        i_end = x_sorted.index(bx_end_r)
                        for ii in range(i_start, i_end):
                            if y_idx > 0:
                                self.system.H_beam.add((ii, y_idx - 1))

    # =========================================================
    # Slab yönetimi
    # =========================================================
    def _delete_real_slab(self, sid: str):
        """Bir döşemeyi sil."""
        if sid in self.real_slabs:
            del self.real_slabs[sid]
        self._sync_to_cell_system()

    def reset_all(self):
        self.real_slabs.clear()
        self.beam_edges.clear()
        self.system = SlabSystem(self.Nx, self.Ny)
        self.output.delete("1.0", "end")
        self.selected_edge = None
        self.highlighted_edge = None
        self.refresh_slab_list()
        self.redraw()

    def refresh_slab_list(self):
        self.slab_list.delete(0, "end")
        for sid in sorted(self.real_slabs.keys()):
            rs = self.real_slabs[sid]
            self.slab_list.insert("end", f"{sid} ({rs.kind}) {rs.w:.2f}×{rs.h:.2f} m")

    def delete_selected_slab(self):
        idx = self.slab_list.curselection()
        if not idx:
            return
        text = self.slab_list.get(idx[0])
        sid = text.split()[0]
        self._delete_real_slab(sid)
        self.refresh_slab_list()
        self.redraw()

    # =========================================================
    # Hesaplama (mevcut mantık korunuyor)
    # =========================================================
    def compute_and_report(self):
        if not self.system.slabs:
            return

        self.output.delete("1.0", "end")
        conc = self.conc.get(); steel = self.steel.get()
        h = self.h_mm.get(); cover = self.cover_mm.get()
        bw = self.bw.get()

        self.output.insert("end", f"Hesap Raporu\nBeton: {conc}, Çelik: {steel}, h={h}mm, cover={cover}mm\n\n")
        self.last_design = {}

        # ==== İKİ GEÇİŞLİ HESAPLAMA ====
        # 1. Geçiş: Tüm döşemelerin temel donatılarını hesapla ve pilye alanlarını topla
        pilye_areas = {}  # {sid: pilye_area_mm2_per_m}
        moment_results = {}  # {sid: (res, steps)}

        for sid in sorted(self.system.slabs.keys()):
            s = self.system.slabs[sid]
            try:
                if s.kind == "ONEWAY":
                    res, steps = self.system.compute_oneway_per_slab(sid, bw)
                    moment_results[sid] = (res, steps)
                    from oneway_slab import oneway_smax_main
                    from struct_design import split_duz_pilye, twoway_smax_short
                    Mpos = res["Mpos_max"] or 0.0
                    smax = oneway_smax_main(h)
                    As_main, ch_main, _ = self.system.design_main_rebar_from_M(
                        Mpos, conc, steel, h, cover, smax, label_prefix="")
                    _, pilye = split_duz_pilye(ch_main)
                    pilye_areas[sid] = pilye.area_mm2_per_m
                elif s.kind == "TWOWAY":
                    res, steps = self.system.compute_twoway_per_slab(sid, bw)
                    moment_results[sid] = (res, steps)
                    from struct_design import split_duz_pilye, twoway_smax_short, twoway_smax_long
                    short_dir = res.get("short_dir", "X")
                    mxn, mxp = res["Mx"]
                    myn, myp = res["My"]
                    if short_dir == "X":
                        Mpos_short = mxp or 0.0
                        smax_short = twoway_smax_short(h)
                    else:
                        Mpos_short = myp or 0.0
                        smax_short = twoway_smax_short(h)
                    As_main, ch_main, _ = self.system.design_main_rebar_from_M(
                        Mpos_short, conc, steel, h, cover, smax_short, label_prefix="")
                    _, pilye = split_duz_pilye(ch_main)
                    pilye_areas[sid] = pilye.area_mm2_per_m
                elif s.kind == "BALCONY":
                    res, steps = self.system.compute_balcony_per_slab(sid, bw)
                    moment_results[sid] = (res, steps)
            except Exception as e:
                moment_results[sid] = None

        # 1.5 Geçiş: TWOWAY döşemeler için mesnet dengelemesi (TS500)
        raw_twoway_moments = {sid: res for sid, (res, _) in moment_results.items()
                              if res is not None and self.system.slabs.get(sid) and self.system.slabs[sid].kind == "TWOWAY"}

        for sid, val in moment_results.items():
            if val is not None and self.system.slabs.get(sid) and self.system.slabs[sid].kind == "ONEWAY":
                raw_twoway_moments[sid] = val[0]

        balanced_moments = {}
        balance_log = []
        if raw_twoway_moments:
            balanced_moments, balance_log = balance_support_moments(self.system, raw_twoway_moments, bw)

        if balance_log:
            self.output.insert("end", "=== MESNET DENGELEMESİ (TS500) ===\n")
            for line in balance_log:
                self.output.insert("end", line + "\n")
            self.output.insert("end", "\n")

        # 2. Geçiş: Tüm döşemelerin tam donatı hesabını yap (pilye bilgileriyle)
        for sid in sorted(self.system.slabs.keys()):
            s = self.system.slabs[sid]
            self.output.insert("end", f"--- {sid} ({s.kind}) ---\n")
            try:
                if moment_results.get(sid) is None:
                    self.output.insert("end", "HATA: Moment hesabı başarısız\n\n")
                    continue

                res, steps = moment_results[sid]
                design_res = {}

                if s.kind == "ONEWAY":
                    for l in steps:
                        self.output.insert("end", l + "\n")

                    design_res, report_lines = compute_oneway_report(
                        self.system, sid, res, conc, steel, h, cover, bw,
                        neighbor_pilye_areas=pilye_areas
                    )
                    for l in report_lines:
                        self.output.insert("end", l + "\n")

                elif s.kind == "TWOWAY":
                    for l in steps:
                        self.output.insert("end", l + "\n")

                    balanced_res = balanced_moments.get(sid, res)
                    if balanced_res:
                        mxn_bal, mxp_bal = balanced_res.get("Mx", (None, None))
                        myn_bal, myp_bal = balanced_res.get("My", (None, None))
                        mxn_orig, _ = res.get("Mx", (None, None))
                        myn_orig, _ = res.get("My", (None, None))
                        if mxn_bal != mxn_orig or myn_bal != myn_orig:
                            mxn_str = f"{mxn_bal:.3f}" if mxn_bal is not None else "-"
                            myn_str = f"{myn_bal:.3f}" if myn_bal is not None else "-"
                            self.output.insert("end", f"Dengelenmiş momentler: Mx_neg={mxn_str}, My_neg={myn_str}\n")
                        res = balanced_res

                    design_res, report_lines = compute_twoway_report(
                        self.system, sid, res, conc, steel, h, cover, bw,
                        neighbor_pilye_areas=pilye_areas
                    )
                    for l in report_lines:
                        self.output.insert("end", l + "\n")

                elif s.kind == "BALCONY":
                    for l in steps:
                        self.output.insert("end", l + "\n")

                    design_res, report_lines = compute_balcony_report(
                        self.system, sid, res, conc, steel, h, cover, bw
                    )
                    for l in report_lines:
                        self.output.insert("end", l + "\n")

                self.last_design[sid] = design_res

            except Exception as e:
                self.output.insert("end", f"HATA: {e}\n\n")

    def export_dxf_and_open(self):
        if not self.last_design:
            self.compute_and_report()
        if not self.last_design:
            return

        fname = simpledialog.askstring("DXF", "Dosya adı (örn: plan.dxf):", parent=self)
        if not fname:
            return
        if not fname.lower().endswith(".dxf"):
            fname += ".dxf"

        try:
            export_to_dxf(self.system, fname, self.last_design, self.bw.get(),
                          real_slabs=self.real_slabs)
            messagebox.showinfo("OK", f"Kaydedildi: {fname}")
            try:
                os.startfile(os.path.abspath(fname))
            except:
                pass
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def load_from_json(self):
        """JSON dosyasından döşeme planını yükler."""
        fname = filedialog.askopenfilename(
            title="Slab JSON Dosyası Seç",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not fname:
            return

        try:
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)

            slabs, beams = json_loader.parse_slab_json(data)

            if not slabs:
                messagebox.showwarning("Uyarı", "Dosyada geçerli döşeme verisi bulunamadı.")
                return

            # Mevcutları sorarak temizle
            if self.real_slabs:
                if messagebox.askyesno("Temizle", "Mevcut döşemeler temizlensin mi?"):
                    self.real_slabs.clear()
                    self.beam_edges.clear()

            # JSON'da bulunmayan parametreleri kullanıcıya sor
            params_ok = self._ask_design_params_dialog()
            if not params_ok:
                # Kullanıcı iptal etti – döşemeleri yine de yükle, mevcut değerleri kullan
                pass

            # Kullanıcının dialogda girdiği Pd değerini al
            user_pd = self.pd.get()

            for s in slabs:
                # Pd: JSON'da bu alan tipik olarak yoktur (varsayılan 10.0 gelir),
                # bu yüzden kullanıcının dialogda girdiği değer her zaman kullanılır.
                rs = RealSlab(
                    s["sid"], s["x"], s["y"], s["w"], s["h"],
                    s["kind"], user_pd, s["b"]
                )
                self.real_slabs[rs.sid] = rs

            # Kirişleri ekle
            for b in beams:
                self.beam_edges.add(b)

            self._sync_to_cell_system()
            self.refresh_slab_list()
            self.redraw()
            messagebox.showinfo("Başarılı", f"{len(slabs)} döşeme yüklendi.")

        except Exception as e:
            messagebox.showerror("Hata", f"JSON yüklenirken hata oluştu:\n{e}")

    def _ask_design_params_dialog(self) -> bool:
        """
        JSON'da bulunmayan tasarım parametrelerini kullanıcıya soran dialog.
        Döndürür: True → Kullanıcı Tamam'a bastı, False → İptal etti.
        """
        dlg = tk.Toplevel(self)
        dlg.title("Tasarım Parametreleri (JSON'da Bulunmayan Değerler)")
        dlg.geometry("420x340")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        result = {"ok": False}

        # ── Açıklama ──
        ttk.Label(
            dlg,
            text="Aşağıdaki değerler JSON dosyasında yer almamaktadır.\n"
                 "Lütfen hesapta kullanılacak değerleri giriniz.",
            justify="center", wraplength=380
        ).pack(pady=(12, 6))

        frm = ttk.Frame(dlg)
        frm.pack(padx=20, pady=4, fill="x")

        # Geçici değişkenler (mevcut GUI değerlerini varsayılan olarak al)
        t_h    = tk.DoubleVar(value=self.h_mm.get())
        t_pd   = tk.DoubleVar(value=self.pd.get())
        t_d    = tk.DoubleVar(value=self.cover_mm.get())
        t_conc = tk.StringVar(value=self.conc.get())
        t_steel= tk.StringVar(value=self.steel.get())
        t_bw   = tk.DoubleVar(value=self.bw.get())

        rows = [
            ("h  – Döşeme kalınlığı (mm):",          t_h,    "entry"),
            ("Pd – Hareketli yük (kN/m²):",           t_pd,   "entry"),
            ("d  – Paspayı / Örtü (mm):",             t_d,    "entry"),
            ("Beton sınıfı:",                          t_conc, "combo_conc"),
            ("Çelik sınıfı:",                          t_steel,"combo_steel"),
            ("bw – Kiriş genişliği (m):",             t_bw,   "entry"),
        ]

        for i, (lbl_text, var, widget_type) in enumerate(rows):
            ttk.Label(frm, text=lbl_text, anchor="w").grid(
                row=i, column=0, sticky="w", pady=3, padx=(0, 10))
            if widget_type == "entry":
                ttk.Entry(frm, textvariable=var, width=14).grid(
                    row=i, column=1, sticky="w")
            elif widget_type == "combo_conc":
                ttk.Combobox(frm, textvariable=var,
                             values=list(CONCRETE_FCK.keys()),
                             width=12, state="readonly").grid(
                    row=i, column=1, sticky="w")
            elif widget_type == "combo_steel":
                ttk.Combobox(frm, textvariable=var,
                             values=list(STEEL_FYK.keys()),
                             width=12, state="readonly").grid(
                    row=i, column=1, sticky="w")

        # ── Butonlar ──
        btn_frm = ttk.Frame(dlg)
        btn_frm.pack(pady=14)

        def on_ok():
            try:
                h_val   = t_h.get()
                pd_val  = t_pd.get()
                d_val   = t_d.get()
                bw_val  = t_bw.get()
                if h_val <= 0 or pd_val < 0 or d_val < 0 or bw_val <= 0:
                    messagebox.showerror("Hata",
                        "h ve bw pozitif, Pd ve paspayı sıfır veya pozitif olmalıdır.",
                        parent=dlg)
                    return
                # Değerleri GUI değişkenlerine aktar
                self.h_mm.set(h_val)
                self.pd.set(pd_val)
                self.cover_mm.set(d_val)
                self.conc.set(t_conc.get())
                self.steel.set(t_steel.get())
                self.bw.set(bw_val)
                result["ok"] = True
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Hata", str(exc), parent=dlg)

        def on_cancel():
            dlg.destroy()

        ttk.Button(btn_frm, text="Tamam",  command=on_ok,    width=12).pack(side="left", padx=8)
        ttk.Button(btn_frm, text="İptal", command=on_cancel, width=12).pack(side="left", padx=8)

        dlg.wait_window()
        return result["ok"]
