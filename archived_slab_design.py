
# import tkinter as tk
# from tkinter import ttk, simpledialog, messagebox
# from dataclasses import dataclass
# from typing import Dict, Tuple, Optional, List, Set
# import math
# import hashlib
# import os

# # =========================================================
# # TWO-WAY ALPHA TABLE + CASE descriptions
# # =========================================================
# M_POINTS = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0]

# CASE_DESC = {
#     1: "4 kenar SÜREKLİ (L,R,T,B tam kenar boyunca komşu)",
#     2: "1 kenar SÜREKSİZ (3 kenar sürekli, 1 kenar boş)",
#     3: "2 KOMŞU kenar SÜREKSİZ (L-T, T-R, R-B, B-L)",
#     4: "2 KISA kenar SÜREKSİZ (uzun kenarlar sürekli)",
#     5: "2 UZUN kenar SÜREKSİZ (kısa kenarlar sürekli)",
#     6: "3 kenar SÜREKSİZ (sadece 1 kenar sürekli)",
#     7: "4 kenar SÜREKSİZ (kenarlarda komşu yok)",
# }

# @dataclass(frozen=True)
# class AlphaRow:
#     short_neg: Optional[List[float]]
#     short_pos: Optional[List[float]]
#     long_neg: Optional[float]
#     long_pos: Optional[float]

# ALPHA_TABLE: Dict[int, AlphaRow] = {
#     1: AlphaRow(
#         short_neg=[0.033, 0.040, 0.045, 0.050, 0.054, 0.059, 0.071, 0.083],
#         short_pos=[0.025, 0.030, 0.034, 0.038, 0.041, 0.045, 0.053, 0.062],
#         long_neg=0.033, long_pos=0.025
#     ),
#     2: AlphaRow(
#         short_neg=[0.042, 0.047, 0.053, 0.057, 0.061, 0.065, 0.075, 0.085],
#         short_pos=[0.031, 0.035, 0.040, 0.043, 0.046, 0.049, 0.056, 0.064],
#         long_neg=0.042, long_pos=0.031
#     ),
#     3: AlphaRow(
#         short_neg=[0.049, 0.056, 0.062, 0.066, 0.070, 0.073, 0.082, 0.090],
#         short_pos=[0.037, 0.042, 0.047, 0.050, 0.053, 0.055, 0.062, 0.068],
#         long_neg=0.049, long_pos=0.037
#     ),
#     4: AlphaRow(
#         short_neg=[0.056, 0.061, 0.065, 0.069, 0.071, 0.073, 0.077, 0.080],
#         short_pos=[0.044, 0.046, 0.049, 0.051, 0.053, 0.055, 0.058, 0.060],
#         long_neg=None, long_pos=0.044
#     ),
#     5: AlphaRow(
#         short_neg=None,
#         short_pos=[0.044, 0.053, 0.060, 0.065, 0.068, 0.071, 0.077, 0.080],
#         long_neg=0.056, long_pos=0.044
#     ),
#     6: AlphaRow(
#         short_neg=[0.058, 0.065, 0.071, 0.077, 0.081, 0.085, 0.092, 0.098],
#         short_pos=[0.044, 0.049, 0.054, 0.058, 0.061, 0.064, 0.069, 0.074],
#         long_neg=0.058, long_pos=0.044
#     ),
#     7: AlphaRow(
#         short_neg=None,
#         short_pos=[0.050, 0.057, 0.062, 0.067, 0.071, 0.075, 0.081, 0.083],
#         long_neg=None, long_pos=0.050
#     ),
# }

# def lerp(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
#     if x1 == x0:
#         return y0
#     t = (x - x0) / (x1 - x0)
#     return y0 + t * (y1 - y0)

# def interp_alpha(m: float, m_points: List[float], a_points: List[float]) -> float:
#     if m <= m_points[0]:
#         return a_points[0]
#     if m >= m_points[-1]:
#         return a_points[-1]
#     for i in range(len(m_points) - 1):
#         x0, x1 = m_points[i], m_points[i+1]
#         if x0 <= m <= x1:
#             return lerp(x0, a_points[i], x1, a_points[i+1], m)
#     return a_points[-1]

# # =========================================================
# # ONEWAY multi-span coefficients
# # M = coeff * w * L^2   (w = pd*b for 1m strip)
# # =========================================================
# def one_way_coefficients(n_spans: int):
#     if n_spans == 2:
#         return [-1/24, -1/8, -1/24], [1/11, 1/11]
#     if n_spans == 3:
#         return [-1/24, -1/9, -1/9, -1/24], [1/11, 1/15, 1/11]
#     support_neg = [0.0] * (n_spans + 1)
#     support_neg[0] = support_neg[-1] = -1/24
#     support_neg[1] = support_neg[-2] = -1/9
#     for i in range(2, n_spans - 1):
#         support_neg[i] = -1/10
#     span_pos = [1/15] * n_spans
#     span_pos[0] = span_pos[-1] = 1/11
#     return support_neg, span_pos

# def one_span_coeff_by_fixity(fixed_start: bool, fixed_end: bool):
#     if (not fixed_start) and (not fixed_end):
#         return (0.0, 0.0), (1.0/8.0)
#     if fixed_start and fixed_end:
#         return (-1.0/12.0, -1.0/12.0), (1.0/24.0)
#     if fixed_start and (not fixed_end):
#         return (-1.0/8.0, 0.0), (9.0/128.0)
#     return (0.0, -1.0/8.0), (9.0/128.0)

# # =========================================================
# # Malzemeler
# # =========================================================
# CONCRETE_FCK = {"C20/25": 20.0, "C25/30": 25.0, "C30/37": 30.0, "C35/45": 35.0, "C40/50": 40.0}
# STEEL_FYK = {"B420C": 420.0, "B500C": 500.0}

# # =========================================================
# # SENİN VERDİĞİN TABLO (K x10^-5) ve ks
# # =========================================================
# beton_tablosu = {
#     1:  [14263.0, 12123.0, 10542.0, 8980.0, 8082.0, 7274.4, 2.75, 2.31],
#     2:  [3675.3,  3124.0,  2716.6, 2314.0, 2082.0, 1874.4, 2.76, 2.31],
#     3:  [1683.9,  1431.3,  1244.7, 1060.0, 954.2,  858.8,  2.77, 2.32],
#     4:  [976.7,   830.2,   721.9,  614.9,  553.4,  498.1,  2.78, 2.33],
#     5:  [644.6,   547.9,   476.5,  405.9,  365.3,  328.8,  2.78, 2.34],
#     6:  [461.8,   392.5,   341.3,  290.7,  261.7,  235.5,  2.79, 2.34],
#     7:  [350.0,   297.5,   258.7,  220.4,  198.4,  178.5,  2.80, 2.35],
#     8:  [276.6,   235.1,   204.4,  174.1,  156.7,  141.1,  2.81, 2.36],
#     9:  [225.6,   191.8,   166.8,  142.0,  127.8,  115.1,  2.82, 2.37],
#     10: [188.7,   160.4,   139.5,  118.8,  106.9,  96.2,   2.83, 2.37],
#     11: [161.1,   136.9,   119.1,  101.4,  91.3,   82.2,   2.84, 2.38],
#     12: [139.9,   118.9,   103.4,  88.1,   79.3,   71.3,   2.85, 2.39],
#     13: [125.2,   104.7,   91.1,   77.6,   69.8,   62.8,   2.86, 2.40],
#     14: [109.8,   93.4,    81.2,   69.2,   62.2,   56.0,   2.87, 2.40],
#     15: [99.0,    84.1,    73.2,   62.3,   56.1,   50.5,   2.88, 2.41],
#     16: [90.0,    76.5,    66.5,   56.7,   51.0,   45.9,   2.88, 2.42],
#     17: [82.6,    70.2,    61.0,   52.0,   46.8,   42.1,   2.89, 2.43],
#     18: [76.3,    64.9,    56.4,   48.0,   43.2,   38.9,   2.90, 2.44],
#     19: [71.0,    60.3,    52.5,   44.7,   40.2,   36.2,   2.91, 2.44],
#     20: [66.4,    56.5,    49.1,   41.8,   37.6,   33.9,   2.92, 2.45],
#     21: [62.5,    53.1,    46.2,   39.4,   35.4,   31.9,   2.93, 2.46],
#     22: [59.1,    50.3,    43.7,   37.2,   33.5,   30.2,   2.94, 2.47],
#     23: [56.2,    47.7,    41.5,   35.4,   31.8,   28.6,   2.95, 2.48],
#     24: [53.5,    45.5,    39.6,   33.7,   30.3,   27.3,   2.96, 2.49],
#     25: [51.2,    43.5,    37.8,   32.2,   29.0,   26.1,   2.96, 2.49],
#     26: [49.1,    41.7,    36.3,   30.9,   27.8,   25.0,   2.98, 2.50],
#     27: [47.2,    40.1,    34.9,   29.7,   26.8,   24.1,   2.99, 2.51],
#     28: [45.5,    38.7,    33.6,   28.6,   25.8,   23.2,   3.00, 2.52],
#     29: [43.9,    37.4,    32.5,   27.7,   24.9,   22.4,   3.01, 2.53],
#     30: [42.5,    36.1,    31.4,   26.8,   24.1,   21.7,   3.02, 2.54],
#     31: [41.1,    34.9,    30.4,   25.9,   23.3,   20.9,   3.03, 2.55],
#     32: [39.6,    33.7,    29.3,   24.9,   22.4,   20.2,   3.05, 2.56],
#     33: [38.1,    32.4,    28.2,   24.0,   21.6,   19.4,   3.06, 2.57],
#     34: [36.7,    31.2,    27.1,   23.1,   20.8,   18.7,   3.08, 2.58],
#     35: [35.2,    29.9,    26.0,   22.2,   20.0,   18.0,   3.10, 2.60],
#     36: [33.8,    28.7,    25.0,   21.3,   19.1,   17.2,   3.12, 2.62],
#     37: [32.3,    27.5,    23.9,   20.3,   18.3,   16.5,   3.14, 2.64],
#     38: [30.9,    26.2,    22.8,   19.4,   17.5,   15.7,   3.17, 2.66],
#     39: [29.4,    25.0,    21.7,   18.5,   16.7,   15.0,   3.20, 2.68],
#     40: [28.0,    23.8,    20.7,   17.6,   15.9,   14.3,   3.23, 2.71],
#     41: [26.5,    22.6,    19.6,   16.7,   15.0,   13.5,   3.27, 2.74],
#     42: [25.1,    21.4,    18.6,   15.8,   14.2,   12.8,   3.31, 2.78],
#     43: [23.7,    20.2,    17.5,   14.9,   13.4,   12.1,   3.37, 2.83],
#     44: [22.6,    19.2,    16.7,   14.2,   12.8,   11.5,   3.42, 2.87],
#     45: [22.3,    19.0,    16.5,   14.0,   12.6,   11.4,   3.43, 2.88],
#     46: [21.4,    18.2,    15.8,   13.5,   12.1,   10.9,   3.49, 2.92],
#     47: [20.9,    17.8,    15.5,   13.2,   11.9,   10.7,   3.52, 2.95],
#     48: [19.6,    16.6,    14.5,   12.3,   11.5,   10.0,   3.62, 3.04],
#     49: [18.7,    15.9,    13.8,   11.8,   10.6,   9.5,    3.71, 3.11],
#     50: [19.1,    16.3,    14.1,   12.0,   10.8,   9.8,    3.66, 3.07],
#     51: [20.1,    17.0,    14.8,   12.6,   11.4,   10.2,   3.58, 3.00],
# }

# _tab_col = {'C25': 0, 'C30': 1, 'C35': 2, 'C40': 3, 'C45': 4, 'C50': 5, 'S420': 6, 'B500': 7}

# def conc_to_tabcol(conc: str) -> str:
#     if conc.startswith("C20"):
#         return "C25"
#     if conc.startswith("C25"):
#         return "C25"
#     if conc.startswith("C30"):
#         return "C30"
#     if conc.startswith("C35"):
#         return "C35"
#     if conc.startswith("C40"):
#         return "C40"
#     return "C25"

# def steel_to_tabcol(steel: str) -> str:
#     return "S420" if steel == "B420C" else "B500"

# def get_table_value(row: int, colname: str) -> float:
#     return beton_tablosu[row][_tab_col[colname]]

# def interp_ks_from_K(K_calc: float, conc_col: str, steel_col: str) -> Tuple[float, List[str]]:
#     steps = []
#     pairs = []
#     for r in sorted(beton_tablosu.keys()):
#         K_r = get_table_value(r, conc_col)
#         ks_r = get_table_value(r, steel_col)
#         pairs.append((K_r, ks_r, r))
#     pairs.sort(key=lambda x: x[0], reverse=True)

#     K_max = pairs[0][0]
#     K_min = pairs[-1][0]
#     steps.append(f"Tablo aralığı: K_max={K_max:.2f}, K_min={K_min:.2f}")

#     if K_calc >= K_max:
#         ks = pairs[0][1]
#         steps.append(f"K_calc={K_calc:.2f} >= K_max -> ks=ks(row={pairs[0][2]})={ks:.3f} (clamp)")
#         return ks, steps
#     if K_calc <= K_min:
#         ks = pairs[-1][1]
#         steps.append(f"K_calc={K_calc:.2f} <= K_min -> ks=ks(row={pairs[-1][2]})={ks:.3f} (clamp)")
#         return ks, steps

#     for (K_hi, ks_hi, r_hi), (K_lo, ks_lo, r_lo) in zip(pairs[:-1], pairs[1:]):
#         if K_hi >= K_calc >= K_lo:
#             ks = lerp(K_hi, ks_hi, K_lo, ks_lo, K_calc)
#             steps.append(f"Braket: row{r_hi}(K={K_hi:.2f},ks={ks_hi:.3f}) - row{r_lo}(K={K_lo:.2f},ks={ks_lo:.3f})")
#             steps.append(f"Interpolasyon: ks = {ks:.3f}")
#             return ks, steps

#     ks = pairs[-1][1]
#     steps.append("Braket bulunamadı (beklenmeyen) -> ks clamp min")
#     return ks, steps

# # =========================================================
# # As from abacus (d override destekli)
# # =========================================================
# def as_from_abacus_steps(
#     M_kNm_per_m: Optional[float],
#     conc: str,
#     steel: str,
#     h_mm: float,
#     cover_mm: float,
#     d_override_mm: Optional[float] = None
# ) -> Tuple[Optional[float], List[str]]:
#     steps = []
#     if M_kNm_per_m is None:
#         return None, ["M=None -> As hesaplanmadı."]
#     if M_kNm_per_m <= 0:
#         return 0.0, [f"M={M_kNm_per_m} <=0 -> As=0"]

#     d_nom = h_mm - cover_mm
#     d = float(d_override_mm) if d_override_mm is not None else d_nom

#     if d_override_mm is not None:
#         steps.append(f"d override: d = {d:.1f} mm (nominal d={d_nom:.1f} mm)")
#     else:
#         steps.append(f"d = h - paspayı = {h_mm:.1f} - {cover_mm:.1f} = {d:.1f} mm (φ/2 YOK)")

#     if d <= 0:
#         raise ValueError("d<=0: h/cover yanlış veya d_override hatalı.")

#     b_mm = 1000.0
#     M_Nmm = abs(M_kNm_per_m) * 1e6
#     steps.append(f"M(Nmm) = |M|*1e6 = {abs(M_kNm_per_m):.3f}*1e6 = {M_Nmm:.1f} Nmm/m")

#     K_calc = 100 * (b_mm * (d**2)) / M_Nmm
#     conc_col = conc_to_tabcol(conc)
#     steel_col = steel_to_tabcol(steel)
#     steps.append(f"Beton kolonu = {conc_col}, Çelik kolonu = {steel_col}")
#     steps.append(f"K_calc = 1e5*(b*d^2)/M = 1e5*({b_mm:.0f}*{d:.1f}^2)/{M_Nmm:.1f} = {K_calc:.2f}")

#     ks, st_ks = interp_ks_from_K(K_calc, conc_col, steel_col)
#     steps.extend(st_ks)

#     As = ks * abs(M_kNm_per_m) * 1000.0 / d
#     steps.append(f"As = ks*M*1000/d = {ks:.3f}*{abs(M_kNm_per_m):.3f}*1000/{d:.1f} = {As:.1f} mm²/m")
#     return As, steps

# # =========================================================
# # Donatı katalogu ve seçim
# # =========================================================
# @dataclass(frozen=True)
# class RebarChoice:
#     phi_mm: int
#     s_mm: int
#     area_mm2_per_m: float

#     def label(self) -> str:
#         return f"Ø{self.phi_mm}/{self.s_mm}"

#     def label_with_area(self) -> str:
#         return f"Ø{self.phi_mm}/{self.s_mm} (Aprov={self.area_mm2_per_m:.1f} mm²/m)"

# def area_per_m(phi_mm: int, s_mm: int) -> float:
#     Ab = math.pi * (phi_mm**2) / 4.0
#     return Ab * (1000.0 / s_mm)

# PHI_LIST = [6, 7, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32]
# S_LIST = list(range(50, 305, 5))

# def select_rebar_min_area(As_req: float, s_max: int, phi_min: int = 8, phi_max: int = 32) -> Optional[RebarChoice]:
#     best = None
#     for phi in PHI_LIST:
#         if phi < phi_min or phi > phi_max:
#             continue
#         for s in S_LIST:
#             if s > s_max:
#                 continue
#             A = area_per_m(phi, s)
#             if A + 1e-9 >= As_req:
#                 cand = RebarChoice(phi, s, A)
#                 if best is None:
#                     best = cand
#                 else:
#                     if cand.area_mm2_per_m < best.area_mm2_per_m - 1e-9:
#                         best = cand
#                     elif abs(cand.area_mm2_per_m - best.area_mm2_per_m) < 1e-9:
#                         if cand.s_mm > best.s_mm:
#                             best = cand
#     return best

# def max_possible_area(s_max: int, phi_min: int = 8, phi_max: int = 32) -> float:
#     mx = 0.0
#     for phi in PHI_LIST:
#         if phi < phi_min or phi > phi_max:
#             continue
#         for s in S_LIST:
#             if s > s_max:
#                 continue
#             mx = max(mx, area_per_m(phi, s))
#     return mx

# def split_duz_pilye(choice: RebarChoice) -> Tuple[RebarChoice, RebarChoice]:
#     s2 = choice.s_mm * 2
#     halfA = choice.area_mm2_per_m / 2.0
#     duz = RebarChoice(choice.phi_mm, s2, halfA)
#     pilye = RebarChoice(choice.phi_mm, s2, halfA)
#     return duz, pilye

# # =========================================================
# # TS500 / Konstrüktif kural parametreleri
# # =========================================================
# def rho_min_oneway(steel: str) -> float:
#     return 0.002 if steel in ("B420C", "B500C") else 0.003

# def oneway_smax_main(h_mm: float) -> int:
#     return int(min(1.5*h_mm, 200))

# def oneway_smax_dist() -> int:
#     return 300

# def twoway_smax_short(h_mm: float) -> int:
#     return int(min(1.5*h_mm, 200))

# def twoway_smax_long(h_mm: float) -> int:
#     return int(min(1.5*h_mm, 250))

# def asb_min_area(steel: str) -> float:
#     if steel == "B500C":
#         return area_per_m(5, 150)
#     if steel == "B420C":
#         return area_per_m(8, 300)
#     return area_per_m(8, 200)

# # =========================================================
# # Model
# # =========================================================
# @dataclass
# class Slab:
#     slab_id: str
#     i0: int
#     j0: int
#     i1: int
#     j1: int
#     kind: str  # ONEWAY / TWOWAY / BALCONY
#     dx: float
#     dy: float
#     pd: float
#     b: float

#     def bbox(self):
#         return self.i0, self.j0, self.i1, self.j1

#     def size_cells(self):
#         return (self.i1 - self.i0 + 1), (self.j1 - self.j0 + 1)

#     def size_m_gross(self):
#         nx, ny = self.size_cells()
#         return nx * self.dx, ny * self.dy

# def color_for_id(s: str) -> str:
#     h = hashlib.md5(s.encode("utf-8")).hexdigest()
#     r = 80 + int(h[0:2], 16) % 140
#     g = 80 + int(h[2:4], 16) % 140
#     b = 80 + int(h[4:6], 16) % 140
#     return f"#{r:02x}{g:02x}{b:02x}"

# def clamp(v, lo, hi):
#     return max(lo, min(hi, v))

# def rect_normalize(a, b):
#     (x0, y0), (x1, y1) = a, b
#     return (min(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1))

# # =========================================================
# # App
# # =========================================================
# class App(tk.Tk):
#     def __init__(self):
#         super().__init__()
#         self.title("Döşeme Yerleşimi + Moment + As + Donatı Seçimi (TS500/Uygulama)")
#         self.geometry("1600x900")

#         self.Nx, self.Ny = 22, 12
#         self.cell_px = 38

#         # inputs for NEW slabs (snapshot)
#         self.dx_m = tk.DoubleVar(value=0.25)
#         self.dy_m = tk.DoubleVar(value=0.25)
#         self.pd = tk.DoubleVar(value=10.0)      # kN/m2
#         self.b_width = tk.DoubleVar(value=1.0)  # m
#         self.bw = tk.DoubleVar(value=0.30)      # beam width m

#         # rebar inputs (global)
#         self.conc = tk.StringVar(value="C25/30")
#         self.steel = tk.StringVar(value="B420C")
#         self.h_mm = tk.DoubleVar(value=120.0)
#         self.cover_mm = tk.DoubleVar(value=25.0)

#         self.mode = tk.StringVar(value="PLACE_ONEWAY")

#         self.slabs: Dict[str, Slab] = {}
#         self.cell_owner: Dict[Tuple[int, int], str] = {}
#         self.V_beam: Set[Tuple[int, int]] = set()
#         self.H_beam: Set[Tuple[int, int]] = set()

#         self.current_selection = None
#         self.drag_start_cell = None

#         # cache of last rebar design choices for DXF/AutoCAD export
#         self.last_design = {}

#         self._build_ui()
#         self.redraw()

#     # ---------------- UI ----------------
#     def _build_ui(self):
#         top = ttk.Frame(self)
#         top.pack(fill="x", padx=10, pady=8)

#         prm = ttk.LabelFrame(top, text="Yeni Döşeme Parametreleri (snapshot)")
#         prm.pack(side="left", fill="x", expand=True)

#         ttk.Label(prm, text="dx (m):").grid(row=0, column=0, padx=6, pady=3, sticky="w")
#         ttk.Entry(prm, textvariable=self.dx_m, width=8).grid(row=0, column=1, padx=6, pady=3, sticky="w")

#         ttk.Label(prm, text="dy (m):").grid(row=0, column=2, padx=6, pady=3, sticky="w")
#         ttk.Entry(prm, textvariable=self.dy_m, width=8).grid(row=0, column=3, padx=6, pady=3, sticky="w")

#         ttk.Label(prm, text="p_d (kN/m²):").grid(row=0, column=4, padx=6, pady=3, sticky="w")
#         ttk.Entry(prm, textvariable=self.pd, width=10).grid(row=0, column=5, padx=6, pady=3, sticky="w")

#         ttk.Label(prm, text="b (m) (1m şerit için genelde 1):").grid(row=0, column=6, padx=6, pady=3, sticky="w")
#         ttk.Entry(prm, textvariable=self.b_width, width=8).grid(row=0, column=7, padx=6, pady=3, sticky="w")

#         ttk.Label(prm, text="kiriş bw (m):").grid(row=0, column=8, padx=6, pady=3, sticky="w")
#         ttk.Entry(prm, textvariable=self.bw, width=8).grid(row=0, column=9, padx=6, pady=3, sticky="w")

#         ttk.Label(prm, text="ONEWAY: panel sınırları + çizilen kirişler mesnet. TWOWAY: M=α·pd·ls² (uzun yön bile ls²).").grid(
#             row=1, column=0, columnspan=10, padx=6, pady=2, sticky="w"
#         )

#         reb = ttk.LabelFrame(top, text="Malzeme / Geometri")
#         reb.pack(side="left", padx=(10, 0), fill="y")

#         ttk.Label(reb, text="Beton:").grid(row=0, column=0, padx=6, pady=2, sticky="w")
#         ttk.Combobox(reb, textvariable=self.conc, values=list(CONCRETE_FCK.keys()),
#                      width=10, state="readonly").grid(row=0, column=1, padx=6, pady=2)

#         ttk.Label(reb, text="Çelik:").grid(row=1, column=0, padx=6, pady=2, sticky="w")
#         ttk.Combobox(reb, textvariable=self.steel, values=list(STEEL_FYK.keys()),
#                      width=10, state="readonly").grid(row=1, column=1, padx=6, pady=2)

#         ttk.Label(reb, text="h (mm):").grid(row=2, column=0, padx=6, pady=2, sticky="w")
#         ttk.Entry(reb, textvariable=self.h_mm, width=12).grid(row=2, column=1, padx=6, pady=2)

#         ttk.Label(reb, text="paspayı (mm):").grid(row=3, column=0, padx=6, pady=2, sticky="w")
#         ttk.Entry(reb, textvariable=self.cover_mm, width=12).grid(row=3, column=1, padx=6, pady=2)

#         ttk.Label(reb, text="Not: As abaktan (K->ks) ile hesaplanır. d=h-cover (φ/2 yok).").grid(
#             row=4, column=0, columnspan=2, padx=6, pady=2, sticky="w"
#         )

#         tools = ttk.LabelFrame(top, text="Araçlar")
#         tools.pack(side="left", padx=(10, 0))

#         ttk.Radiobutton(tools, text="Yerleştir: ONE WAY", variable=self.mode, value="PLACE_ONEWAY").grid(row=0, column=0, sticky="w", padx=6, pady=2)
#         ttk.Radiobutton(tools, text="Yerleştir: TWO WAY", variable=self.mode, value="PLACE_TWOWAY").grid(row=1, column=0, sticky="w", padx=6, pady=2)
#         ttk.Radiobutton(tools, text="Yerleştir: BALCONY", variable=self.mode, value="PLACE_BALCONY").grid(row=2, column=0, sticky="w", padx=6, pady=2)

#         ttk.Separator(tools, orient="horizontal").grid(row=3, column=0, sticky="ew", padx=6, pady=6)

#         ttk.Radiobutton(tools, text="Dikey Kiriş (V)", variable=self.mode, value="VBEAM").grid(row=4, column=0, sticky="w", padx=6, pady=2)
#         ttk.Radiobutton(tools, text="Yatay Kiriş (H)", variable=self.mode, value="HBEAM").grid(row=5, column=0, sticky="w", padx=6, pady=2)
#         ttk.Radiobutton(tools, text="Sil (Döşeme)", variable=self.mode, value="ERASE").grid(row=6, column=0, sticky="w", padx=6, pady=2)

#         act = ttk.Frame(tools)
#         act.grid(row=7, column=0, padx=6, pady=6, sticky="ew")
#         ttk.Button(act, text="Hesapla / Raporla (Adım Adım)", command=self.compute_and_report).pack(fill="x", pady=2)
#         ttk.Button(act, text="DXF Çiz / AutoCAD Aç", command=self.export_dxf_and_open).pack(fill="x", pady=2)
#         ttk.Button(act, text="Temizle", command=self.reset_all).pack(fill="x", pady=2)

#         mid = ttk.Frame(self)
#         mid.pack(fill="both", expand=True, padx=10, pady=8)

#         self.canvas = tk.Canvas(mid, bg="white")
#         self.canvas.pack(side="left", fill="both", expand=True)
#         self.canvas.bind("<Button-1>", self.on_mouse_down)
#         self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
#         self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

#         right = ttk.Frame(mid, width=600)
#         right.pack(side="left", fill="y", padx=(10, 0))

#         slab_box = ttk.LabelFrame(right, text="Döşemeler")
#         slab_box.pack(fill="x")

#         self.slab_list = tk.Listbox(slab_box, height=10)
#         self.slab_list.pack(fill="x", padx=6, pady=6)

#         btnrow = ttk.Frame(slab_box)
#         btnrow.pack(fill="x", padx=6, pady=(0, 6))
#         ttk.Button(btnrow, text="Seçiliyi Sil", command=self.delete_selected_slab).pack(side="left")
#         ttk.Button(btnrow, text="Yenile", command=self.refresh_slab_list).pack(side="left", padx=6)

#         out_box = ttk.LabelFrame(right, text="Çıktı (Adım Adım)")
#         out_box.pack(fill="both", expand=True, pady=(10, 0))

#         self.output = tk.Text(out_box, height=36, wrap="word")
#         self.output.pack(fill="both", expand=True, padx=6, pady=6)

#         self.refresh_slab_list()

#     # ---------------- Basics ----------------
#     def reset_all(self):
#         self.slabs.clear()
#         self.cell_owner.clear()
#         self.V_beam.clear()
#         self.H_beam.clear()
#         self.output.delete("1.0", "end")
#         self.refresh_slab_list()
#         self.redraw()

#     def refresh_slab_list(self):
#         self.slab_list.delete(0, "end")
#         for sid in sorted(self.slabs.keys()):
#             s = self.slabs[sid]
#             nx, ny = s.size_cells()
#             Lx_g, Ly_g = s.size_m_gross()
#             self.slab_list.insert(
#                 "end",
#                 f"{sid} ({s.kind}) [{s.i0},{s.j0}]→[{s.i1},{s.j1}] ({nx}x{ny}) | "
#                 f"Lx={Lx_g:.2f} Ly={Ly_g:.2f} | dx={s.dx:.2f} dy={s.dy:.2f} | pd={s.pd:.1f} b={s.b:.2f}"
#             )

#     def delete_selected_slab(self):
#         idx = self.slab_list.curselection()
#         if not idx:
#             messagebox.showinfo("Bilgi", "Silmek için listeden bir döşeme seç.")
#             return
#         sid = self.slab_list.get(idx[0]).split()[0]
#         self.delete_slab_by_id(sid)

#     def delete_slab_by_id(self, sid: str):
#         if sid not in self.slabs:
#             return
#         s = self.slabs[sid]
#         for i in range(s.i0, s.i1 + 1):
#             for j in range(s.j0, s.j1 + 1):
#                 if self.cell_owner.get((i, j)) == sid:
#                     del self.cell_owner[(i, j)]
#         del self.slabs[sid]
#         self.refresh_slab_list()
#         self.redraw()

#     # ---------------- Mouse helpers ----------------
#     def cell_from_xy(self, x, y) -> Tuple[int, int]:
#         i = clamp(int(x // self.cell_px), 0, self.Nx - 1)
#         j = clamp(int(y // self.cell_px), 0, self.Ny - 1)
#         return i, j

#     def edge_from_xy(self, x, y):
#         i_f = x / self.cell_px
#         j_f = y / self.cell_px
#         i = clamp(int(i_f), 0, self.Nx - 1)
#         j = clamp(int(j_f), 0, self.Ny - 1)

#         if self.mode.get() == "VBEAM":
#             i_line = clamp(int(round(i_f)), 0, self.Nx)
#             i_edge = clamp(i_line - 1, 0, self.Nx - 2)
#             return ("V", (i_edge, j))

#         if self.mode.get() == "HBEAM":
#             j_line = clamp(int(round(j_f)), 0, self.Ny)
#             j_edge = clamp(j_line - 1, 0, self.Ny - 2)
#             return ("H", (i, j_edge))

#         return (None, None)

#     # ---------------- Drawing ----------------
#     def redraw(self):
#         self.canvas.delete("all")
#         w = self.Nx * self.cell_px
#         h = self.Ny * self.cell_px
#         self.canvas.config(width=w, height=h)

#         for (i, j), sid in self.cell_owner.items():
#             x0, y0 = i * self.cell_px, j * self.cell_px
#             x1, y1 = x0 + self.cell_px, y0 + self.cell_px
#             self.canvas.create_rectangle(x0, y0, x1, y1, fill=color_for_id(sid), outline="")

#         for i in range(self.Nx + 1):
#             x = i * self.cell_px
#             self.canvas.create_line(x, 0, x, h, fill="#dddddd")
#         for j in range(self.Ny + 1):
#             y = j * self.cell_px
#             self.canvas.create_line(0, y, w, y, fill="#dddddd")

#         for (i, j) in self.V_beam:
#             x = (i + 1) * self.cell_px
#             y0, y1 = j * self.cell_px, (j + 1) * self.cell_px
#             self.canvas.create_line(x, y0, x, y1, width=4, fill="#111111")
#         for (i, j) in self.H_beam:
#             y = (j + 1) * self.cell_px
#             x0, x1 = i * self.cell_px, (i + 1) * self.cell_px
#             self.canvas.create_line(x0, y, x1, y, width=4, fill="#111111")

#         for sid, s in self.slabs.items():
#             x0, y0 = s.i0 * self.cell_px, s.j0 * self.cell_px
#             x1, y1 = (s.i1 + 1) * self.cell_px, (s.j1 + 1) * self.cell_px
#             self.canvas.create_rectangle(x0, y0, x1, y1, outline="#000000", width=2)
#             self.canvas.create_text((x0+x1)/2, (y0+y1)/2, text=f"{sid}\n{s.kind}",
#                                     font=("Arial", 10, "bold"), fill="#000000")

#     # ---------------- Mouse events ----------------
#     def on_mouse_down(self, evt):
#         mode = self.mode.get()

#         if mode.startswith("PLACE_"):
#             self.drag_start_cell = self.cell_from_xy(evt.x, evt.y)
#             i0, j0 = self.drag_start_cell
#             x0, y0 = i0 * self.cell_px, j0 * self.cell_px
#             x1, y1 = x0 + self.cell_px, y0 + self.cell_px
#             self.current_selection = self.canvas.create_rectangle(x0, y0, x1, y1, outline="#ff0000", width=2)
#             return

#         if mode in ("VBEAM", "HBEAM"):
#             t, key = self.edge_from_xy(evt.x, evt.y)
#             if t == "V":
#                 self.V_beam.remove(key) if key in self.V_beam else self.V_beam.add(key)
#             elif t == "H":
#                 self.H_beam.remove(key) if key in self.H_beam else self.H_beam.add(key)
#             self.redraw()
#             return

#         if mode == "ERASE":
#             i, j = self.cell_from_xy(evt.x, evt.y)
#             sid = self.cell_owner.get((i, j))
#             if sid:
#                 self.delete_slab_by_id(sid)

#     def on_mouse_drag(self, evt):
#         if not self.mode.get().startswith("PLACE_") or not self.current_selection or not self.drag_start_cell:
#             return
#         i1, j1 = self.cell_from_xy(evt.x, evt.y)
#         i0, j0 = self.drag_start_cell
#         (a0, b0), (a1, b1) = rect_normalize((i0, j0), (i1, j1))
#         x0, y0 = a0 * self.cell_px, b0 * self.cell_px
#         x1, y1 = (a1 + 1) * self.cell_px, (b1 + 1) * self.cell_px
#         self.canvas.coords(self.current_selection, x0, y0, x1, y1)

#     def on_mouse_up(self, evt):
#         if not self.mode.get().startswith("PLACE_") or not self.current_selection or not self.drag_start_cell:
#             return

#         i1, j1 = self.cell_from_xy(evt.x, evt.y)
#         i0, j0 = self.drag_start_cell
#         (a0, b0), (a1, b1) = rect_normalize((i0, j0), (i1, j1))

#         self.canvas.delete(self.current_selection)
#         self.current_selection = None
#         self.drag_start_cell = None

#         sid = simpledialog.askstring("Döşeme ID", "Döşeme ID (örn: D1):", parent=self)
#         if not sid:
#             self.redraw()
#             return
#         sid = sid.strip()

#         kind = "ONEWAY" if self.mode.get() == "PLACE_ONEWAY" else ("TWOWAY" if self.mode.get() == "PLACE_TWOWAY" else "BALCONY")

#         if sid in self.slabs:
#             if not messagebox.askyesno("Var olan döşeme", f"{sid} zaten var. Üzerine yazılsın mı?"):
#                 self.redraw()
#                 return
#             self.delete_slab_by_id(sid)

#         for i in range(a0, a1 + 1):
#             for j in range(b0, b1 + 1):
#                 if (i, j) in self.cell_owner:
#                     other = self.cell_owner[(i, j)]
#                     messagebox.showerror("Çakışma", f"Seçtiğin alan {other} ile çakışıyor.")
#                     self.redraw()
#                     return

#         s = Slab(
#             slab_id=sid, i0=a0, j0=b0, i1=a1, j1=b1,
#             kind=kind,
#             dx=float(self.dx_m.get()),
#             dy=float(self.dy_m.get()),
#             pd=float(self.pd.get()),
#             b=float(self.b_width.get())
#         )
#         self.slabs[sid] = s
#         for i in range(a0, a1 + 1):
#             for j in range(b0, b1 + 1):
#                 self.cell_owner[(i, j)] = sid

#         self.refresh_slab_list()
#         self.redraw()

#     # =========================================================
#     # Adjacency helpers
#     # =========================================================
#     def neighbor_slabs_on_side(self, sid: str, direction: str, side: str) -> set:
#         s = self.slabs[sid]
#         i0, j0, i1, j1 = s.bbox()
#         direction = direction.upper()
#         side = side.upper()
#         neigh = set()

#         if direction == "X":
#             if side == "START":
#                 if i0 == 0:
#                     return neigh
#                 ii = i0 - 1
#                 for j in range(j0, j1 + 1):
#                     nb = self.cell_owner.get((ii, j))
#                     if nb and nb != sid:
#                         neigh.add(nb)
#             else:
#                 if i1 >= self.Nx - 1:
#                     return neigh
#                 ii = i1 + 1
#                 for j in range(j0, j1 + 1):
#                     nb = self.cell_owner.get((ii, j))
#                     if nb and nb != sid:
#                         neigh.add(nb)
#         else:
#             if side == "START":
#                 if j0 == 0:
#                     return neigh
#                 jj = j0 - 1
#                 for i in range(i0, i1 + 1):
#                     nb = self.cell_owner.get((i, jj))
#                     if nb and nb != sid:
#                         neigh.add(nb)
#             else:
#                 if j1 >= self.Ny - 1:
#                     return neigh
#                 jj = j1 + 1
#                 for i in range(i0, i1 + 1):
#                     nb = self.cell_owner.get((i, jj))
#                     if nb and nb != sid:
#                         neigh.add(nb)

#         return neigh

#     # =========================================================
#     # FULL edge continuity for TWOWAY (must be full edge)
#     # =========================================================
#     def edge_neighbor_coverage(self, sid: str, edge: str) -> Tuple[bool, bool, float]:
#         s = self.slabs[sid]
#         i0, j0, i1, j1 = s.bbox()
#         edge = edge.upper()

#         total, found = 0, 0
#         if edge == "L":
#             if i0 == 0:
#                 return (False, False, 0.0)
#             for j in range(j0, j1 + 1):
#                 total += 1
#                 nb = self.cell_owner.get((i0 - 1, j))
#                 if nb and nb != sid:
#                     found += 1
#         elif edge == "R":
#             if i1 >= self.Nx - 1:
#                 return (False, False, 0.0)
#             for j in range(j0, j1 + 1):
#                 total += 1
#                 nb = self.cell_owner.get((i1 + 1, j))
#                 if nb and nb != sid:
#                     found += 1
#         elif edge == "T":
#             if j0 == 0:
#                 return (False, False, 0.0)
#             for i in range(i0, i1 + 1):
#                 total += 1
#                 nb = self.cell_owner.get((i, j0 - 1))
#                 if nb and nb != sid:
#                     found += 1
#         elif edge == "B":
#             if j1 >= self.Ny - 1:
#                 return (False, False, 0.0)
#             for i in range(i0, i1 + 1):
#                 total += 1
#                 nb = self.cell_owner.get((i, j1 + 1))
#                 if nb and nb != sid:
#                     found += 1

#         any_ = found > 0
#         full = (total > 0 and found == total)
#         ratio = (found / total) if total > 0 else 0.0
#         return (full, any_, ratio)

#     def twoway_edge_continuity_full(self, sid: str):
#         Lf, La, Lr = self.edge_neighbor_coverage(sid, "L")
#         Rf, Ra, Rr = self.edge_neighbor_coverage(sid, "R")
#         Tf, Ta, Tr = self.edge_neighbor_coverage(sid, "T")
#         Bf, Ba, Br = self.edge_neighbor_coverage(sid, "B")
#         return (Lf, Rf, Tf, Bf), (La, Ra, Ta, Ba), (Lr, Rr, Tr, Br)

#     def pick_two_way_case_exact(self, Lx_net: float, Ly_net: float,
#                                cont_left: bool, cont_right: bool, cont_top: bool, cont_bottom: bool) -> int:
#         disc = {"L": not cont_left, "R": not cont_right, "T": not cont_top, "B": not cont_bottom}
#         n_disc = sum(disc.values())

#         if n_disc == 0: return 1
#         if n_disc == 4: return 7
#         if n_disc == 1: return 2
#         if n_disc == 3: return 6

#         eps = 1e-9
#         if abs(Lx_net - Ly_net) < eps:
#             short_edges, long_edges = set(), set()
#         elif Lx_net < Ly_net:
#             short_edges, long_edges = {"T", "B"}, {"L", "R"}
#         else:
#             short_edges, long_edges = {"L", "R"}, {"T", "B"}

#         disc_edges = {e for e, d in disc.items() if d}
#         if len(disc_edges) != 2:
#             return 3

#         if short_edges and disc_edges == short_edges: return 4
#         if long_edges and disc_edges == long_edges: return 5

#         adjacent_pairs = [{"L", "T"}, {"T", "R"}, {"R", "B"}, {"B", "L"}]
#         if any(disc_edges == p for p in adjacent_pairs):
#             return 3

#         if disc_edges == {"T", "B"}: return 4
#         if disc_edges == {"L", "R"}: return 5
#         return 3

#     # =========================================================
#     # Beam line detection for a slab (full edge coverage)
#     # =========================================================
#     def is_beam_gridline_for_slab(self, sid: str, direction: str, g: int) -> bool:
#         s = self.slabs[sid]
#         i0, j0, i1, j1 = s.bbox()
#         direction = direction.upper()

#         if direction == "X":
#             if g <= 0 or g >= self.Nx:
#                 return False
#             k = g - 1
#             return all((k, j) in self.V_beam for j in range(j0, j1 + 1))
#         else:
#             if g <= 0 or g >= self.Ny:
#                 return False
#             k = g - 1
#             return all((i, k) in self.H_beam for i in range(i0, i1 + 1))

#     def slab_support_gridlines_from_drawn_beams(self, sid: str, direction: str) -> List[int]:
#         s = self.slabs[sid]
#         i0, j0, i1, j1 = s.bbox()
#         direction = direction.upper()
#         if direction == "X":
#             return [g for g in range(i0 + 1, i1 + 1) if self.is_beam_gridline_for_slab(sid, "X", g)]
#         else:
#             return [g for g in range(j0 + 1, j1 + 1) if self.is_beam_gridline_for_slab(sid, "Y", g)]

#     # =========================================================
#     # ONEWAY chain building
#     # =========================================================
#     def build_oneway_chain(self, sid: str, direction: str) -> List[str]:
#         direction = direction.upper()
#         if self.slabs[sid].kind != "ONEWAY":
#             return [sid]

#         stack = [sid]
#         seen = {sid}
#         chain = []
#         while stack:
#             u = stack.pop()
#             if self.slabs[u].kind != "ONEWAY":
#                 continue
#             chain.append(u)
#             for side in ("START", "END"):
#                 for nb in self.neighbor_slabs_on_side(u, direction, side):
#                     if nb in seen:
#                         continue
#                     seen.add(nb)
#                     if nb in self.slabs and self.slabs[nb].kind == "ONEWAY":
#                         stack.append(nb)

#         if direction == "X":
#             chain.sort(key=lambda x: self.slabs[x].i0)
#         else:
#             chain.sort(key=lambda x: self.slabs[x].j0)
#         return chain

#     def chain_panel_boundary_supports(self, chain: List[str], direction: str) -> List[int]:
#         direction = direction.upper()
#         if len(chain) < 2:
#             return []
#         supports = []
#         for a, b in zip(chain[:-1], chain[1:]):
#             sa, sb = self.slabs[a], self.slabs[b]
#             if direction == "X":
#                 g = sa.i1 + 1
#                 if sb.i0 == g:
#                     supports.append(g)
#             else:
#                 g = sa.j1 + 1
#                 if sb.j0 == g:
#                     supports.append(g)
#         return supports

#     def chain_end_fixity(self, chain: List[str], direction: str) -> Tuple[bool, bool]:
#         direction = direction.upper()
#         first, last = chain[0], chain[-1]
#         start_neigh = self.neighbor_slabs_on_side(first, direction, "START")
#         end_neigh = self.neighbor_slabs_on_side(last, direction, "END")
#         fixed_start = any(self.slabs[n].kind in ("TWOWAY", "BALCONY") for n in start_neigh if n in self.slabs)
#         fixed_end = any(self.slabs[n].kind in ("TWOWAY", "BALCONY") for n in end_neigh if n in self.slabs)
#         return fixed_start, fixed_end

#     def net_span(self, Lgross: float, left_is_beam: bool, right_is_beam: bool) -> float:
#         bw = float(self.bw.get())
#         if left_is_beam and right_is_beam:
#             Lnet = Lgross - bw
#         elif left_is_beam or right_is_beam:
#             Lnet = Lgross - 0.5 * bw
#         else:
#             Lnet = Lgross
#         return max(0.05, Lnet)

#     def owner_slab_for_segment(self, chain: List[str], direction: str, g_mid: float) -> str:
#         direction = direction.upper()
#         for sid in chain:
#             s = self.slabs[sid]
#             if direction == "X":
#                 if s.i0 <= g_mid <= (s.i1 + 1):
#                     return sid
#             else:
#                 if s.j0 <= g_mid <= (s.j1 + 1):
#                     return sid
#         return chain[0]

#     # =========================================================
#     # ONEWAY compute (adımlı)
#     # =========================================================
#     def compute_oneway_per_slab(self, sid: str) -> Tuple[dict, List[str]]:
#         steps = []
#         s0 = self.slabs[sid]
#         w = s0.pd * s0.b  # kN/m
#         steps.append(f"w = pd*b = {s0.pd:.3f}*{s0.b:.3f} = {w:.3f} kN/m")

#         Lx_g, Ly_g = s0.size_m_gross()
#         direction = "X" if Lx_g <= Ly_g else "Y"
#         steps.append(f"Otomatik açıklık yönü (kısa): Lx={Lx_g:.3f}, Ly={Ly_g:.3f} -> yön={direction}")

#         chain = self.build_oneway_chain(sid, direction)
#         steps.append(f"Zincir (ONEWAY komşu panel birleşimi): {chain}")

#         fixed_start, fixed_end = self.chain_end_fixity(chain, direction)
#         steps.append(f"Uç ankastre kontrolü: START={fixed_start}, END={fixed_end} (TWOWAY/BALCONY komşusu varsa ankastre)")

#         if direction == "X":
#             start_g = min(self.slabs[x].i0 for x in chain)
#             end_g = max(self.slabs[x].i1 + 1 for x in chain)
#         else:
#             start_g = min(self.slabs[x].j0 for x in chain)
#             end_g = max(self.slabs[x].j1 + 1 for x in chain)

#         supports = [start_g, end_g]
#         supports.extend(self.chain_panel_boundary_supports(chain, direction))
#         for x in chain:
#             supports.extend(self.slab_support_gridlines_from_drawn_beams(x, direction))
#         supports = sorted(set(supports))
#         steps.append(f"Mesnet gridline listesi (uçlar + panel sınırları + çizilen kirişler): {supports}")

#         spans = []
#         for a, b_g in zip(supports[:-1], supports[1:]):
#             mid_g = 0.5 * (a + b_g)
#             owner = self.owner_slab_for_segment(chain, direction, mid_g)
#             s_owner = self.slabs[owner]
#             step = s_owner.dx if direction == "X" else s_owner.dy
#             Lgross = (b_g - a) * step
#             left_is_beam = self.is_beam_gridline_for_slab(owner, direction, a)
#             right_is_beam = self.is_beam_gridline_for_slab(owner, direction, b_g)
#             Lnet = self.net_span(Lgross, left_is_beam, right_is_beam)
#             spans.append((Lnet, owner, Lgross, left_is_beam, right_is_beam, a, b_g))
#             steps.append(
#                 f"Span [{a}->{b_g}] owner={owner}: step={step:.3f} => Lgross={(b_g-a)}*{step:.3f}={Lgross:.3f} m, "
#                 f"beamL={left_is_beam}, beamR={right_is_beam} => Lnet={Lnet:.3f} m"
#             )

#         n_spans = len(spans)
#         steps.append(f"Toplam açıklık sayısı (span): {n_spans}")

#         if n_spans == 1:
#             (c_start, c_end), c_pos = one_span_coeff_by_fixity(fixed_start, fixed_end)
#             L = spans[0][0]
#             steps.append(f"Tek açıklık katsayıları: c_pos={c_pos:.6f}, c_start={c_start:.6f}, c_end={c_end:.6f}")
#             Mpos = c_pos * w * L**2
#             Mneg_start = c_start * w * L**2
#             Mneg_end = c_end * w * L**2
#             steps.append(f"M+ = c_pos*w*L² = {c_pos:.6f}*{w:.3f}*{L:.3f}² = {Mpos:.3f} kNm/m")
#             steps.append(f"M- start = {Mneg_start:.3f} kNm/m, M- end = {Mneg_end:.3f} kNm/m")
#             return {
#                 "auto_dir": direction, "chain": chain,
#                 "fixed_start": fixed_start, "fixed_end": fixed_end,
#                 "supports": supports, "n_spans": 1,
#                 "w": w,
#                 "Mpos_max": Mpos,
#                 "Mneg_min": min(Mneg_start, Mneg_end)
#             }, steps

#         support_c, span_c = one_way_coefficients(n_spans)
#         steps.append(f"Çok açıklık katsayıları: support_c={support_c}, span_c={span_c}")

#         Ls = [L for (L, *_rest) in spans]
#         owners = [o for (_L, o, *_rest) in spans]

#         span_Mpos = []
#         for i in range(n_spans):
#             M = span_c[i] * w * (Ls[i] ** 2)
#             span_Mpos.append(M)
#             steps.append(f"Span{i+1} M+ = {span_c[i]:.6f}*{w:.3f}*{Ls[i]:.3f}² = {M:.3f} kNm/m")

#         support_Mneg = []
#         for i in range(n_spans + 1):
#             if i == 0:
#                 L2 = Ls[0] ** 2
#                 note = "uç mesnet (L1)"
#             elif i == n_spans:
#                 L2 = Ls[-1] ** 2
#                 note = "uç mesnet (Ln)"
#             else:
#                 L2 = 0.5 * (Ls[i-1] ** 2 + Ls[i] ** 2)
#                 note = "iç mesnet (ort.)"
#             M = support_c[i] * w * L2
#             support_Mneg.append(M)
#             steps.append(f"Mesnet{i} M- = {support_c[i]:.6f}*{w:.3f}*{L2:.3f} ({note}) = {M:.3f} kNm/m")

#         owned_span_idx = [i for i, o in enumerate(owners) if o == sid]
#         Mpos_max = max(span_Mpos[i] for i in owned_span_idx) if owned_span_idx else None

#         touching_supports = set()
#         for i in owned_span_idx:
#             touching_supports.add(i)
#             touching_supports.add(i+1)
#         Mneg_min = min(support_Mneg[i] for i in touching_supports) if touching_supports else None

#         steps.append(f"{sid} için açıklık (pozitif) kontrol edilen span indeksleri: {owned_span_idx}")
#         steps.append(f"{sid} için mesnet (negatif) kontrol edilen mesnet indeksleri: {sorted(touching_supports)}")
#         steps.append(f"{sid} -> M+_max={Mpos_max} , M-_min={Mneg_min}")

#         return {
#             "auto_dir": direction, "chain": chain,
#             "fixed_start": fixed_start, "fixed_end": fixed_end,
#             "supports": supports, "n_spans": n_spans,
#             "w": w,
#             "Mpos_max": Mpos_max,
#             "Mneg_min": Mneg_min
#         }, steps

#     # =========================================================
#     # TWOWAY net lengths
#     # =========================================================
#     def slab_edge_has_beam(self, sid: str, edge: str) -> bool:
#         s = self.slabs[sid]
#         i0, j0, i1, j1 = s.bbox()
#         edge = edge.upper()
#         if edge == "LEFT":
#             return (i0 != 0) and self.is_beam_gridline_for_slab(sid, "X", i0)
#         if edge == "RIGHT":
#             return (i1 < self.Nx - 1) and self.is_beam_gridline_for_slab(sid, "X", i1 + 1)
#         if edge == "TOP":
#             return (j0 != 0) and self.is_beam_gridline_for_slab(sid, "Y", j0)
#         if edge == "BOTTOM":
#             return (j1 < self.Ny - 1) and self.is_beam_gridline_for_slab(sid, "Y", j1 + 1)
#         return False

#     def twoway_net_LxLy(self, sid: str) -> Tuple[float, float, List[str]]:
#         steps = []
#         s = self.slabs[sid]
#         Lx_g, Ly_g = s.size_m_gross()
#         bw = float(self.bw.get())
#         left = self.slab_edge_has_beam(sid, "LEFT")
#         right = self.slab_edge_has_beam(sid, "RIGHT")
#         top = self.slab_edge_has_beam(sid, "TOP")
#         bottom = self.slab_edge_has_beam(sid, "BOTTOM")

#         steps.append(f"Brüt: Lx={Lx_g:.3f}, Ly={Ly_g:.3f}")
#         steps.append(f"Kenar kirişleri: LEFT={left}, RIGHT={right}, TOP={top}, BOTTOM={bottom}, bw={bw:.3f} m")

#         Lx_n = max(0.05, Lx_g - (0.5*bw if left else 0.0) - (0.5*bw if right else 0.0))
#         Ly_n = max(0.05, Ly_g - (0.5*bw if top else 0.0) - (0.5*bw if bottom else 0.0))

#         steps.append(f"Lx_net = {Lx_n:.3f}")
#         steps.append(f"Ly_net = {Ly_n:.3f}")
#         return Lx_n, Ly_n, steps

#     def compute_twoway_per_slab(self, sid: str) -> Tuple[dict, List[str]]:
#         steps = []
#         s = self.slabs[sid]
#         pd = s.pd

#         Lx_n, Ly_n, st_net = self.twoway_net_LxLy(sid)
#         steps.extend(st_net)

#         ll = max(Lx_n, Ly_n)
#         ls = min(Lx_n, Ly_n)
#         m = ll / ls if ls > 0 else 1.0
#         steps.append(f"ls=min(Lx_net,Ly_net)={ls:.3f}, ll=max(...)={ll:.3f}, m=ll/ls={m:.3f}")

#         (Lf, Rf, Tf, Bf), *_ = self.twoway_edge_continuity_full(sid)
#         steps.append(f"FULL süreklilik: L={Lf}, R={Rf}, T={Tf}, B={Bf}")
#         case = self.pick_two_way_case_exact(Lx_n, Ly_n, Lf, Rf, Tf, Bf)
#         row = ALPHA_TABLE[case]
#         steps.append(f"Case seçimi: case={case} ({CASE_DESC.get(case,'-')})")

#         a_sn = interp_alpha(m, M_POINTS, row.short_neg) if row.short_neg is not None else None
#         a_sp = interp_alpha(m, M_POINTS, row.short_pos) if row.short_pos is not None else None
#         a_ln = row.long_neg
#         a_lp = row.long_pos

#         steps.append(f"α değerleri (m={m:.3f}): a_sn={a_sn}, a_sp={a_sp}, a_ln={a_ln}, a_lp={a_lp}")
#         steps.append("Moment formülü: M = α * pd * ls² (uzun yön bile ls²)")

#         M_sn = a_sn * pd * (ls ** 2) if a_sn is not None else None
#         M_sp = a_sp * pd * (ls ** 2) if a_sp is not None else None
#         M_ln = a_ln * pd * (ls ** 2) if a_ln is not None else None
#         M_lp = a_lp * pd * (ls ** 2) if a_lp is not None else None

#         steps.append(f"pd={pd:.3f}, ls²={ls**2:.3f}")
#         steps.append(f"M_short_neg = {M_sn}")
#         steps.append(f"M_short_pos = {M_sp}")
#         steps.append(f"M_long_neg  = {M_ln}")
#         steps.append(f"M_long_pos  = {M_lp}")

#         short_dir = "X" if Lx_n <= Ly_n else "Y"
#         steps.append(f"Kısa doğrultu = {short_dir}")

#         if short_dir == "X":
#             Mx_neg, Mx_pos = M_sn, M_sp
#             My_neg, My_pos = M_ln, M_lp
#         else:
#             My_neg, My_pos = M_sn, M_sp
#             Mx_neg, Mx_pos = M_ln, M_lp

#         return {
#             "Lx_net": Lx_n, "Ly_net": Ly_n,
#             "ls": ls, "ll": ll, "m": m,
#             "pd": pd,
#             "case": case, "case_desc": CASE_DESC.get(case, "-"),
#             "edges_full": (Lf, Rf, Tf, Bf),
#             "Mx": (Mx_neg, Mx_pos),
#             "My": (My_neg, My_pos),
#             "short_dir": short_dir,
#         }, steps

#     # =========================================================
#     # BALCONY compute (adımlı)
#     # =========================================================
#     def compute_balcony_per_slab(self, sid: str) -> Tuple[dict, List[str]]:
#         steps = []
#         s = self.slabs[sid]
#         w = s.pd * s.b
#         bw = float(self.bw.get())
#         Lx_g, Ly_g = s.size_m_gross()
#         direction = "X" if Lx_g <= Ly_g else "Y"
#         Lg = min(Lx_g, Ly_g)
#         Lnet = max(0.05, Lg - 0.5 * bw)

#         steps.append(f"w = pd*b = {s.pd:.3f}*{s.b:.3f} = {w:.3f} kN/m")
#         steps.append(f"Balkon kısa boy (konsol açıklığı) Lg=min(Lx,Ly)={Lg:.3f} m")
#         steps.append(f"Lnet = Lg - 0.5*bw = {Lg:.3f} - 0.5*{bw:.3f} = {Lnet:.3f} m")
#         Mneg = 0.5 * w * Lnet**2
#         steps.append(f"M- (konsol) = w*Lnet²/2 = {w:.3f}*{Lnet:.3f}²/2 = {Mneg:.3f} kNm/m")

#         return {"dir": direction, "w": w, "L_net": Lnet, "Mneg": Mneg, "pd": s.pd, "b": s.b}, steps

#     def balcony_fixed_edge_guess(self, sid: str) -> Tuple[str, List[str]]:
#         steps = []
#         ratios = {}
#         for e in ["L", "R", "T", "B"]:
#             _full, any_, ratio = self.edge_neighbor_coverage(sid, e)
#             ratios[e] = ratio if any_ else 0.0
#             steps.append(f"Kenar {e}: komşu_oran={ratios[e]:.3f}")

#         fixed = max(ratios.items(), key=lambda kv: kv[1])[0]
#         steps.append(f"Bağlı (mesnet) kenar seçimi: {fixed} (max oran)")
#         return fixed, steps

#     def neighbor_support_moment_for_edge(self, neighbor_id: str, edge: str) -> float:
#         if neighbor_id not in self.slabs:
#             return 0.0
#         k = self.slabs[neighbor_id].kind
#         if k == "TWOWAY":
#             r, _ = self.compute_twoway_per_slab(neighbor_id)
#             mxn, _ = r["Mx"]
#             myn, _ = r["My"]
#             if edge in ("L", "R"):
#                 return abs(mxn) if mxn else 0.0
#             else:
#                 return abs(myn) if myn else 0.0
#         if k == "ONEWAY":
#             r, _ = self.compute_oneway_per_slab(neighbor_id)
#             return abs(r["Mneg_min"]) if r.get("Mneg_min") is not None else 0.0
#         if k == "BALCONY":
#             r, _ = self.compute_balcony_per_slab(neighbor_id)
#             return abs(r["Mneg"]) if r.get("Mneg") is not None else 0.0
#         return 0.0

#     def get_balcony_design_moment(self, sid: str, Mbal: float) -> Tuple[float, List[str]]:
#         steps = []
#         fixed_edge, st = self.balcony_fixed_edge_guess(sid)
#         steps.extend(st)

#         s = self.slabs[sid]
#         i0, j0, i1, j1 = s.bbox()
#         neigh = set()
#         if fixed_edge == "L" and i0 > 0:
#             for j in range(j0, j1 + 1):
#                 nb = self.cell_owner.get((i0 - 1, j))
#                 if nb and nb != sid:
#                     neigh.add(nb)
#         elif fixed_edge == "R" and i1 < self.Nx - 1:
#             for j in range(j0, j1 + 1):
#                 nb = self.cell_owner.get((i1 + 1, j))
#                 if nb and nb != sid:
#                     neigh.add(nb)
#         elif fixed_edge == "T" and j0 > 0:
#             for i in range(i0, i1 + 1):
#                 nb = self.cell_owner.get((i, j0 - 1))
#                 if nb and nb != sid:
#                     neigh.add(nb)
#         elif fixed_edge == "B" and j1 < self.Ny - 1:
#             for i in range(i0, i1 + 1):
#                 nb = self.cell_owner.get((i, j1 + 1))
#                 if nb and nb != sid:
#                     neigh.add(nb)

#         if not neigh:
#             steps.append("Bağlı kenarda komşu bulunamadı -> sadece balkon M kullanılacak.")
#             return abs(Mbal), steps

#         m_nb = 0.0
#         for nb in neigh:
#             mn = self.neighbor_support_moment_for_edge(nb, fixed_edge)
#             steps.append(f"Komşu {nb} mesnet momenti (yaklaşık) = {mn:.3f} kNm/m")
#             m_nb = max(m_nb, mn)

#         Mdesign = max(abs(Mbal), m_nb)
#         steps.append(f"M_design = max(|Mbal|={abs(Mbal):.3f}, |Mkomşu|max={m_nb:.3f}) = {Mdesign:.3f} kNm/m")
#         return Mdesign, steps

#     # =========================================================
#     # Donatı tasarım (d_delta_mm ile)
#     # =========================================================
#     def design_main_rebar_from_M(
#         self,
#         M_kNm: float,
#         conc: str,
#         steel: str,
#         h_mm: float,
#         cover_mm: float,
#         s_max: int,
#         As_min_override: Optional[float] = None,
#         label_prefix: str = "",
#         d_delta_mm: float = 0.0
#     ) -> Tuple[float, RebarChoice, List[str]]:
#         steps = []

#         d_nom = h_mm - cover_mm
#         d_eff = d_nom + d_delta_mm

#         if d_delta_mm != 0.0:
#             steps.append(f"{label_prefix}d düzeltmesi: d_eff = (h-cover)+Δd = {d_nom:.1f}+({d_delta_mm:.1f}) = {d_eff:.1f} mm")

#         As_raw, st_as = as_from_abacus_steps(M_kNm, conc, steel, h_mm, cover_mm, d_override_mm=d_eff)
#         steps.append(f"{label_prefix}--- As (Abak) Hesabı ---")
#         steps.extend([label_prefix + x for x in st_as])

#         As_req = As_raw if As_raw is not None else 0.0

#         d_mm = max(1.0, d_eff)
#         As_min = As_min_override if As_min_override is not None else rho_min_oneway(steel) * 1000.0 * d_mm
#         steps.append(f"{label_prefix}As_min = ρmin*b*d = {rho_min_oneway(steel):.4f}*1000*{d_mm:.1f} = {As_min:.1f} mm²/m")

#         As_req2 = max(As_req, As_min)
#         if As_req2 > As_req + 1e-9:
#             steps.append(f"{label_prefix}As_req -> max(As_raw, As_min) = max({As_req:.1f}, {As_min:.1f}) = {As_req2:.1f}")
#         As_req = As_req2

#         cand = select_rebar_min_area(As_req, s_max, phi_min=8)
#         steps.append(f"{label_prefix}Seçim kısıtı: Ø>=8, s<= {s_max} mm, Aprov>=As_req")
#         if cand is None:
#             mx = max_possible_area(s_max, phi_min=8)
#             raise ValueError(
#                 f"Donatı bulunamadı: As_req={As_req:.1f}, s_max={s_max}, Ø>=8. "
#                 f"Bu kısıtlarla max Aprov≈{mx:.1f} mm²/m. (Ya s_max artır, ya h artır, ya M düşür.)"
#             )

#         steps.append(f"{label_prefix}Seçilen donatı = {cand.label_with_area()}")
#         return As_req, cand, steps

#     # =========================================================
#     # RAPOR
#     # =========================================================
#     def compute_and_report(self):
#         if not self.slabs:
#             messagebox.showinfo("Bilgi", "Önce döşeme yerleştir.")
#             return

#         conc = self.conc.get()
#         steel = self.steel.get()
#         h_mm = float(self.h_mm.get())
#         cover_mm = float(self.cover_mm.get())

#         # refresh cache used for DXF/AutoCAD export
#         self.last_design = {}

#         self.output.delete("1.0", "end")
#         self.output.insert("end", "=== RAPOR (ADIM ADIM) ===\n")
#         self.output.insert("end", f"bw={float(self.bw.get()):.3f} m\n")
#         self.output.insert("end", f"Malzeme: {conc} / {steel} | h={h_mm:.0f}mm cover={cover_mm:.0f}mm\n")
#         self.output.insert("end", "As yöntemi: Abak (K->ks) | d=h-cover (φ/2 yok)\n")
#         self.output.insert("end", "Donatı seçiminde minimum çap: Ø8\n")
#         self.output.insert("end", "TWOWAY: M = α·pd·ls² (uzun yön bile ls²)\n")
#         self.output.insert("end", "ONEWAY: panel sınırları mesnet + çizilen kirişler mesnet\n")
#         self.output.insert("end", "BALKON: ana moment = max(balkon mesnet, bağlı döşeme mesnet) (sadece bağlandığı kenar)\n")
#         self.output.insert("end", "İlave donatı kuralı: önce açıklık seçilir; mesnet için ilave = max(0, As_mesnet - Aprov_açıklık)\n\n")

#         for sid in sorted(self.slabs.keys()):
#             s = self.slabs[sid]
#             nx, ny = s.size_cells()
#             Lx_g, Ly_g = s.size_m_gross()

#             self.output.insert("end", f"====================================================\n")
#             self.output.insert("end", f"[{sid}] {s.kind}\n")
#             self.output.insert("end", f"  dx={s.dx:.3f} dy={s.dy:.3f} | pd={s.pd:.3f} kN/m² | b={s.b:.3f} m\n")
#             self.output.insert("end", f"  Brüt: Lx={Lx_g:.3f} Ly={Ly_g:.3f} | Grid ({nx}x{ny})\n\n")

#             try:
#                 # ---------------- ONEWAY ----------------
#                 if s.kind == "ONEWAY":
#                     r, st_m = self.compute_oneway_per_slab(sid)

#                     self.output.insert("end", "TEK DOĞRULTU MOMENT ADIMLARI:\n")
#                     for ln in st_m:
#                         self.output.insert("end", f"  - {ln}\n")
#                     self.output.insert("end", "\n")

#                     Mpos = r["Mpos_max"] if r["Mpos_max"] is not None else 0.0
#                     Mneg = r["Mneg_min"] if r["Mneg_min"] is not None else 0.0

#                     smax_main = oneway_smax_main(h_mm)

#                     # Önce açıklık
#                     As_main_req, ch_main, st_main = self.design_main_rebar_from_M(
#                         Mpos, conc, steel, h_mm, cover_mm, smax_main, label_prefix="    "
#                     )
#                     duz_main, pilye_main = split_duz_pilye(ch_main)

#                     # Mesnet toplam gerek
#                     As_neg_req, ch_neg, st_neg = self.design_main_rebar_from_M(
#                         abs(Mneg), conc, steel, h_mm, cover_mm, smax_main, label_prefix="    "
#                     )

#                     # İlave: mevcut = açıklık Aprov
#                     As_mevcut_aciklik = ch_main.area_mm2_per_m
#                     As_ilave = max(0.0, As_neg_req - As_mevcut_aciklik)
#                     st_neg_extra = []
#                     ch_extra = None
#                     if As_ilave > 1e-6:
#                         smax_add = 330
#                         ch_extra = select_rebar_min_area(As_ilave, smax_add, phi_min=8)
#                         if ch_extra is None:
#                             mx = max_possible_area(smax_add, phi_min=8)
#                             raise ValueError(
#                                 f"İlave mesnet donatısı bulunamadı: As_ilave={As_ilave:.1f}, "
#                                 f"s_max={smax_add}, Ø>=8. maxAprov≈{mx:.1f}"
#                             )
#                         st_neg_extra.append(
#                             f"İlave: As_neg_req={As_neg_req:.1f} - mevcut_açıklık={As_mevcut_aciklik:.1f} = As_ilave={As_ilave:.1f}"
#                         )
#                         st_neg_extra.append(
#                             f"İlave seçim: s<= {smax_add} mm, Ø>=8 -> {ch_extra.label_with_area()}"
#                         )
#                     else:
#                         st_neg_extra.append(
#                             f"İlave: As_neg_req={As_neg_req:.1f} - mevcut_açıklık={As_mevcut_aciklik:.1f} = {As_ilave:.1f} -> ilave gerekmez"
#                         )

#                     As_dist_req = As_main_req / 5.0
#                     smax_dist = oneway_smax_dist()
#                     ch_dist = select_rebar_min_area(As_dist_req, smax_dist, phi_min=8)
#                     if ch_dist is None:
#                         mx = max_possible_area(smax_dist, phi_min=8)
#                         raise ValueError(f"Dağıtma donatısı bulunamadı: Asd={As_dist_req:.1f}, s_max={smax_dist}, Ø>=8. maxAprov≈{mx:.1f}")
#                     st_dist = [
#                         f"Asd = As/5 = {As_main_req:.1f}/5 = {As_dist_req:.1f} mm²/m",
#                         f"Seçim: s<= {smax_dist} mm, Ø>=8 -> {ch_dist.label_with_area()}",
#                     ]

#                     Asb_req = 0.6 * As_main_req
#                     Asb_req2 = max(Asb_req, asb_min_area(steel))
#                     ch_boy = select_rebar_min_area(Asb_req2, smax_dist, phi_min=8)
#                     if ch_boy is None:
#                         mx = max_possible_area(smax_dist, phi_min=8)
#                         raise ValueError(f"Boyuna mesnet donatısı bulunamadı: Asb_req={Asb_req2:.1f}, s_max={smax_dist}, Ø>=8. maxAprov≈{mx:.1f}")
#                     st_boy = [
#                         f"Asb = 0.6*As = 0.6*{As_main_req:.1f} = {Asb_req:.1f} mm²/m",
#                         f"Asb_min(çelik={steel}) = {asb_min_area(steel):.1f} mm²/m",
#                         f"Asb_req = max(Asb, Asb_min) = {Asb_req2:.1f} mm²/m",
#                         f"Seçim: s<= {smax_dist} mm, Ø>=8 -> {ch_boy.label_with_area()}",
#                     ]

#                     # cache for DXF export (ONEWAY)
#                     self.last_design[sid] = {
#                         'kind': 'ONEWAY',
#                         'auto_dir': r.get('auto_dir', direction),
#                         'Lx_g': Lx_g, 'Ly_g': Ly_g,
#                         'dx': s.dx, 'dy': s.dy,
#                         'bw': float(self.bw.get()),
#                         'cover_mm': cover_mm,
#                         'choices': {
#                             'main': ch_main,
#                             'main_duz': duz_main,
#                             'main_pilye': pilye_main,
#                             'support_total': ch_neg,
#                             'support_extra': ch_extra,
#                             'dist': ch_dist,
#                             'boyuna_support': ch_boy,
#                         }
#                     }

#                     self.output.insert("end", "TEK DOĞRULTU DONATI SONUÇLARI:\n")
#                     self.output.insert("end", f"  Açıklık ana donatısı: M={Mpos:.3f} kNm/m\n")
#                     self.output.insert("end", "  As ve seçim adımları:\n")
#                     for ln in st_main:
#                         self.output.insert("end", f"{ln}\n")
#                     self.output.insert("end", f"  Seçilen ana donatı: {ch_main.label_with_area()}\n")
#                     self.output.insert("end", f"    Kroki: DÜZ={duz_main.label_with_area()} | PİLYE={pilye_main.label_with_area()}\n\n")

#                     self.output.insert("end", f"  Mesnet (negatif) donatısı: M={Mneg:.3f} kNm/m\n")
#                     self.output.insert("end", "  As ve seçim adımları:\n")
#                     for ln in st_neg:
#                         self.output.insert("end", f"{ln}\n")
#                     self.output.insert("end", f"  Mesnet için gereken toplam: {ch_neg.label_with_area()}\n")
#                     self.output.insert("end", f"  Mevcut (açıklık donatısı uzatılan): {ch_main.label_with_area()}\n")
#                     for ln in st_neg_extra:
#                         self.output.insert("end", f"  {ln}\n")
#                     if ch_extra:
#                         self.output.insert("end", f"  Mesnet ilave donatı: {ch_extra.label_with_area()}\n")
#                     self.output.insert("end", "\n")

#                     self.output.insert("end", "  Dağıtma donatısı:\n")
#                     for ln in st_dist:
#                         self.output.insert("end", f"  {ln}\n")
#                     self.output.insert("end", "\n")

#                     self.output.insert("end", "  Boyuna mesnet donatısı:\n")
#                     for ln in st_boy:
#                         self.output.insert("end", f"  {ln}\n")
#                     self.output.insert("end", f"  Seçilen boyuna mesnet: {ch_boy.label_with_area()}\n\n")

#                 # ---------------- TWOWAY ----------------
#                 elif s.kind == "TWOWAY":
#                     r, st_m = self.compute_twoway_per_slab(sid)
#                     mxn, mxp = r["Mx"]
#                     myn, myp = r["My"]

#                     self.output.insert("end", "ÇİFT DOĞRULTU MOMENT ADIMLARI:\n")
#                     for ln in st_m:
#                         self.output.insert("end", f"  - {ln}\n")
#                     self.output.insert("end", "\n")

#                     # --- d düzeltmesi: küçük moment doğrultusu -10mm, eşitse Y ---
#                     Mx_mag = max(abs(mxp or 0.0), abs(mxn or 0.0))
#                     My_mag = max(abs(myp or 0.0), abs(myn or 0.0))
#                     d_delta_x = 0.0
#                     d_delta_y = 0.0
#                     if abs(Mx_mag - My_mag) < 1e-9:
#                         d_delta_y = -10.0
#                     elif Mx_mag < My_mag:
#                         d_delta_x = -10.0
#                     else:
#                         d_delta_y = -10.0

#                     self.output.insert("end", f"  d düzeltmesi (kural): Δd_x={d_delta_x:.0f} mm, Δd_y={d_delta_y:.0f} mm (küçük moment doğrultusu azaltıldı)\n\n")

#                     short_dir = r["short_dir"]
#                     smax_x = twoway_smax_short(h_mm) if short_dir == "X" else twoway_smax_long(h_mm)
#                     smax_y = twoway_smax_long(h_mm) if short_dir == "X" else twoway_smax_short(h_mm)

#                     # Açıklık donatıları (d düzeltmesi dahil)
#                     Asx_req, ch_x, st_x = self.design_main_rebar_from_M(
#                         mxp if mxp else 0.0, conc, steel, h_mm, cover_mm, smax_x, label_prefix="    ", d_delta_mm=d_delta_x
#                     )
#                     Asy_req, ch_y, st_y = self.design_main_rebar_from_M(
#                         myp if myp else 0.0, conc, steel, h_mm, cover_mm, smax_y, label_prefix="    ", d_delta_mm=d_delta_y
#                     )

#                     def twoway_min_targets(d_eff_mm: float) -> Tuple[float, float]:
#                         As_each = 0.0015 * 1000.0 * d_eff_mm
#                         As_sum = 0.0035 * 1000.0 * d_eff_mm
#                         return As_each, As_sum

#                     # Min kontrolünü nominal d ile bıraktım (istersen d_eff ile ayrı ayrı da yapılabilir)
#                     dmm_nom = max(1.0, h_mm - cover_mm)
#                     As_each_min, As_sum_min = twoway_min_targets(dmm_nom)

#                     adj_steps = []
#                     adj_steps.append(f"Min kontrol (nominal d=h-cover={dmm_nom:.1f}):")
#                     adj_steps.append(f"  As_each_min=0.0015*b*d≈{As_each_min:.1f}, As_sum_min=0.0035*b*d≈{As_sum_min:.1f}")

#                     if Asx_req < As_each_min:
#                         adj_steps.append(f"  Asx_req {Asx_req:.1f} < As_each_min -> Asx_req={As_each_min:.1f}")
#                         Asx_req = As_each_min
#                     if Asy_req < As_each_min:
#                         adj_steps.append(f"  Asy_req {Asy_req:.1f} < As_each_min -> Asy_req={As_each_min:.1f}")
#                         Asy_req = As_each_min
#                     if Asx_req + Asy_req < As_sum_min:
#                         deficit = As_sum_min - (Asx_req + Asy_req)
#                         if Asx_req <= Asy_req:
#                             Asx_req += deficit
#                             adj_steps.append(f"  Toplam yetersiz: deficit={deficit:.1f} -> Asx artırıldı -> {Asx_req:.1f}")
#                         else:
#                             Asy_req += deficit
#                             adj_steps.append(f"  Toplam yetersiz: deficit={deficit:.1f} -> Asy artırıldı -> {Asy_req:.1f}")

#                     ch_x2 = select_rebar_min_area(Asx_req, smax_x, phi_min=8)
#                     ch_y2 = select_rebar_min_area(Asy_req, smax_y, phi_min=8)
#                     if ch_x2 is None or ch_y2 is None:
#                         raise ValueError("Çift doğrultu açıklık donatısı bulunamadı (min kontrol sonrası).")

#                     duz_x, pilye_x = split_duz_pilye(ch_x2)
#                     duz_y, pilye_y = split_duz_pilye(ch_y2)

#                     # Mesnet gerekleri (d düzeltmesi dahil)
#                     Asx_neg_req, _, st_xneg = self.design_main_rebar_from_M(
#                         abs(mxn) if mxn else 0.0, conc, steel, h_mm, cover_mm, smax_x, label_prefix="    ", d_delta_mm=d_delta_x
#                     )
#                     Asy_neg_req, _, st_yneg = self.design_main_rebar_from_M(
#                         abs(myn) if myn else 0.0, conc, steel, h_mm, cover_mm, smax_y, label_prefix="    ", d_delta_mm=d_delta_y
#                     )

#                     # İlave: mevcut = açıklık Aprov
#                     def support_extra(As_neg_req: float, mevcut_aciklik_area: float, smax_add: int = 330):
#                         As_il = max(0.0, As_neg_req - mevcut_aciklik_area)
#                         if As_il <= 1e-6:
#                             return As_il, None, [f"İlave gerekmez: As_neg_req={As_neg_req:.1f} - mevcut_açıklık={mevcut_aciklik_area:.1f} = {As_il:.1f}"]
#                         ch = select_rebar_min_area(As_il, smax_add, phi_min=8)
#                         if ch is None:
#                             mx = max_possible_area(smax_add, phi_min=8)
#                             raise ValueError(f"Mesnet ilave donatısı bulunamadı: As_ilave={As_il:.1f}, s_max={smax_add}, Ø>=8. maxAprov≈{mx:.1f}")
#                         return As_il, ch, [
#                             f"İlave: As_neg_req={As_neg_req:.1f} - mevcut_açıklık={mevcut_aciklik_area:.1f} = As_ilave={As_il:.1f}",
#                             f"İlave seçim (s<={smax_add}, Ø>=8): {ch.label_with_area()}",
#                         ]

#                     _, ch_x_il, st_x_il = support_extra(Asx_neg_req, ch_x2.area_mm2_per_m)
#                     _, ch_y_il, st_y_il = support_extra(Asy_neg_req, ch_y2.area_mm2_per_m)

#                     # cache for DXF export (TWOWAY)
#                     self.last_design[sid] = {
#                         'kind': 'TWOWAY',
#                         'short_dir': r.get('short_dir'),
#                         'Lx_net': r.get('Lx_net'),
#                         'Ly_net': r.get('Ly_net'),
#                         'dx': s.dx, 'dy': s.dy,
#                         'bw': float(self.bw.get()),
#                         'cover_mm': cover_mm,
#                         'choices': {
#                             'x_span': ch_x2,
#                             'y_span': ch_y2,
#                             'x_span_duz': duz_x,
#                             'x_span_pilye': pilye_x,
#                             'y_span_duz': duz_y,
#                             'y_span_pilye': pilye_y,
#                             'x_support_extra': ch_x_il,
#                             'y_support_extra': ch_y_il,
#                         }
#                     }

#                     self.output.insert("end", "ÇİFT DOĞRULTU DONATI SONUÇLARI:\n")
#                     self.output.insert("end", "  Açıklık kesitleri:\n")
#                     self.output.insert("end", f"    X doğrultusu: M+={mxp} kNm/m\n")
#                     for ln in st_x:
#                         self.output.insert("end", f"{ln}\n")
#                     self.output.insert("end", f"    Seçilen X açıklık: {ch_x2.label_with_area()}\n")
#                     self.output.insert("end", f"      Kroki: DÜZ={duz_x.label_with_area()} | PİLYE={pilye_x.label_with_area()}\n\n")

#                     self.output.insert("end", f"    Y doğrultusu: M+={myp} kNm/m\n")
#                     for ln in st_y:
#                         self.output.insert("end", f"{ln}\n")
#                     self.output.insert("end", f"    Seçilen Y açıklık: {ch_y2.label_with_area()}\n")
#                     self.output.insert("end", f"      Kroki: DÜZ={duz_y.label_with_area()} | PİLYE={pilye_y.label_with_area()}\n\n")

#                     self.output.insert("end", "  Min donatı kontrolleri:\n")
#                     for ln in adj_steps:
#                         self.output.insert("end", f"    {ln}\n")
#                     self.output.insert("end", "\n")

#                     self.output.insert("end", "  Mesnet kesitleri:\n")
#                     self.output.insert("end", f"    X mesnet: M-={mxn} kNm/m\n")
#                     for ln in st_xneg:
#                         self.output.insert("end", f"{ln}\n")
#                     self.output.insert("end", f"    Mevcut (X açıklık uzatılan): {ch_x2.label_with_area()}\n")
#                     for ln in st_x_il:
#                         self.output.insert("end", f"    {ln}\n")
#                     if ch_x_il:
#                         self.output.insert("end", f"    X mesnet ilave: {ch_x_il.label_with_area()}\n")
#                     self.output.insert("end", "\n")

#                     self.output.insert("end", f"    Y mesnet: M-={myn} kNm/m\n")
#                     for ln in st_yneg:
#                         self.output.insert("end", f"{ln}\n")
#                     self.output.insert("end", f"    Mevcut (Y açıklık uzatılan): {ch_y2.label_with_area()}\n")
#                     for ln in st_y_il:
#                         self.output.insert("end", f"    {ln}\n")
#                     if ch_y_il:
#                         self.output.insert("end", f"    Y mesnet ilave: {ch_y_il.label_with_area()}\n")
#                     self.output.insert("end", "\n")

#                 # ---------------- BALCONY ----------------
#                 elif s.kind == "BALCONY":
#                     r, st_m = self.compute_balcony_per_slab(sid)

#                     self.output.insert("end", "BALKON MOMENT ADIMLARI:\n")
#                     for ln in st_m:
#                         self.output.insert("end", f"  - {ln}\n")
#                     self.output.insert("end", "\n")

#                     Mneg = r["Mneg"]

#                     Mdesign, st_md = self.get_balcony_design_moment(sid, Mneg)
#                     self.output.insert("end", "BALKON BAĞLI MESNET MOMENT KONTROLÜ:\n")
#                     for ln in st_md:
#                         self.output.insert("end", f"  - {ln}\n")
#                     self.output.insert("end", "\n")

#                     smax_main = oneway_smax_main(h_mm)
#                     As_req, ch_main, st_main = self.design_main_rebar_from_M(
#                         abs(Mdesign), conc, steel, h_mm, cover_mm, smax_main, label_prefix="    "
#                     )

#                     As_dist_req = As_req / 5.0
#                     ch_dist = select_rebar_min_area(As_dist_req, oneway_smax_dist(), phi_min=8)
#                     if ch_dist is None:
#                         mx = max_possible_area(oneway_smax_dist(), phi_min=8)
#                         raise ValueError(f"Balkon dağıtma donatısı bulunamadı: Asd={As_dist_req:.1f}, Ø>=8. maxAprov≈{mx:.1f}")

#                     # cache for DXF export (BALCONY)
#                     fixed_edge, _st_fe = self.balcony_fixed_edge_guess(sid)
#                     self.last_design[sid] = {
#                         'kind': 'BALCONY',
#                         'dir': r.get('dir'),
#                         'fixed_edge': fixed_edge,
#                         'L_net': r.get('L_net'),
#                         'dx': s.dx, 'dy': s.dy,
#                         'bw': float(self.bw.get()),
#                         'cover_mm': cover_mm,
#                         'choices': {
#                             'main': ch_main,
#                             'dist': ch_dist,
#                         }
#                     }

#                     self.output.insert("end", "BALKON DONATI SONUÇLARI:\n")
#                     self.output.insert("end", f"  Balkon ana donatısı: M_design={Mdesign:.3f} kNm/m\n")
#                     self.output.insert("end", "  As ve seçim adımları:\n")
#                     for ln in st_main:
#                         self.output.insert("end", f"{ln}\n")
#                     self.output.insert("end", f"  Seçilen donatı (DÜZ): {ch_main.label_with_area()}\n\n")

#                     self.output.insert("end", "  Balkon dağıtma donatısı:\n")
#                     self.output.insert("end", f"  Asd = As/5 = {As_req:.1f}/5 = {As_dist_req:.1f} mm²/m\n")
#                     self.output.insert("end", f"  Seçilen dağıtma (DÜZ): {ch_dist.label_with_area()}\n\n")

#             except Exception as e:
#                 self.output.insert("end", f"  HATA: {e}\n\n")


#     # =========================================================
#     # DXF / AutoCAD Export (Donatı Kroki)
#     # =========================================================
#     def export_dxf_and_open(self):
#         """
#         1) (Gerekirse) son tasarım önbelleğini doldurmak için compute_and_report çalıştırır
#         2) DXF üretir
#         3) AutoCAD'i açmaya çalışır (COM). Başarısız olursa dosyayı varsayılan programla açar.
#         """
#         try:
#             # Ensure cache exists
#             if not getattr(self, "last_design", None):
#                 self.compute_and_report()

#             if not self.last_design:
#                 messagebox.showinfo("Bilgi", "Önce Hesapla / Raporla çalıştır veya en az 1 döşeme yerleştir.")
#                 return

#             fname = simpledialog.askstring("DXF Dosya Adı", "DXF dosya adı (örn: donati_plani.dxf):", parent=self)
#             if not fname:
#                 return
#             fname = fname.strip()
#             if not fname.lower().endswith(".dxf"):
#                 fname += ".dxf"

#             self._export_to_dxf(fname)
#             self._open_in_autocad(fname)

#             messagebox.showinfo("Tamam", f"DXF üretildi ve açılmaya çalışıldı:\n{fname}")
#         except Exception as e:
#             messagebox.showerror("Hata", f"DXF/AutoCAD işlemi başarısız:\n{e}")

#     def _open_in_autocad(self, dxf_path: str):
#         # 1) AutoCAD COM ile dene (AutoCAD kuruluysa)
#         try:
#             import win32com.client  # type: ignore
#             acad = win32com.client.Dispatch("AutoCAD.Application")
#             acad.Visible = True
#             # DWG boş açıp DXF'i açtır
#             docs = acad.Documents
#             # DXF direkt aç
#             docs.Open(os.path.abspath(dxf_path))
#             return
#         except Exception:
#             # 2) Varsayılan programla aç (AutoCAD DXF'e ilişkilendiyse AutoCAD açılır)
#             try:
#                 os.startfile(os.path.abspath(dxf_path))  # Windows
#                 return
#             except Exception as ee:
#                 raise RuntimeError(
#                     "AutoCAD açılamadı. AutoCAD kurulu mu ve DXF ilişkilendirmesi var mı?\n"
#                     f"Detay: {ee}"
#                 )

#     # ---------- Minimal DXF (R12) Writer ----------
#     class _DXFWriter:
#         def __init__(self):
#             self.layers = set()
#             self.entities = []

#         def add_layer(self, name: str):
#             self.layers.add(name)

#         def add_line(self, x1, y1, x2, y2, layer="0"):
#             self.add_layer(layer)
#             self.entities.append(("LINE", layer, (x1, y1, x2, y2)))

#         def add_polyline(self, pts, layer="0", closed=False):
#             self.add_layer(layer)
#             self.entities.append(("POLYLINE", layer, (pts, closed)))

#         def add_text(self, x, y, text, height=200.0, layer="TEXT"):
#             self.add_layer(layer)
#             self.entities.append(("TEXT", layer, (x, y, height, text)))

#         def _w(self, f, code, value):
#             f.write(f"{code}\n{value}\n")

#         def save(self, path: str):
#             # Very small ASCII DXF R12 (AC1009)
#             with open(path, "w", encoding="utf-8") as f:
#                 self._w(f, 0, "SECTION"); self._w(f, 2, "HEADER")
#                 self._w(f, 9, "$ACADVER"); self._w(f, 1, "AC1009")
#                 self._w(f, 0, "ENDSEC")

#                 self._w(f, 0, "SECTION"); self._w(f, 2, "TABLES")
#                 # LAYER table
#                 self._w(f, 0, "TABLE"); self._w(f, 2, "LAYER"); self._w(f, 70, len(self.layers) + 1)
#                 # default layer 0
#                 self._w(f, 0, "LAYER"); self._w(f, 2, "0"); self._w(f, 70, 0); self._w(f, 62, 7); self._w(f, 6, "CONTINUOUS")
#                 for ln in sorted(self.layers):
#                     if ln == "0":
#                         continue
#                     self._w(f, 0, "LAYER"); self._w(f, 2, ln); self._w(f, 70, 0); self._w(f, 62, 7); self._w(f, 6, "CONTINUOUS")
#                 self._w(f, 0, "ENDTAB")
#                 self._w(f, 0, "ENDSEC")

#                 self._w(f, 0, "SECTION"); self._w(f, 2, "ENTITIES")
#                 for ent in self.entities:
#                     etype = ent[0]
#                     layer = ent[1]
#                     data = ent[2]
#                     if etype == "LINE":
#                         x1, y1, x2, y2 = data
#                         self._w(f, 0, "LINE")
#                         self._w(f, 8, layer)
#                         self._w(f, 10, float(x1)); self._w(f, 20, float(y1)); self._w(f, 30, 0.0)
#                         self._w(f, 11, float(x2)); self._w(f, 21, float(y2)); self._w(f, 31, 0.0)
#                     elif etype == "POLYLINE":
#                         pts, closed = data
#                         self._w(f, 0, "POLYLINE")
#                         self._w(f, 8, layer)
#                         self._w(f, 66, 1)
#                         self._w(f, 70, 1 if closed else 0)
#                         for (x, y) in pts:
#                             self._w(f, 0, "VERTEX")
#                             self._w(f, 8, layer)
#                             self._w(f, 10, float(x)); self._w(f, 20, float(y)); self._w(f, 30, 0.0)
#                         self._w(f, 0, "SEQEND")
#                     elif etype == "TEXT":
#                         x, y, h, txt = data
#                         self._w(f, 0, "TEXT")
#                         self._w(f, 8, layer)
#                         self._w(f, 10, float(x)); self._w(f, 20, float(y)); self._w(f, 30, 0.0)
#                         self._w(f, 40, float(h))
#                         self._w(f, 1, txt)
#                 self._w(f, 0, "ENDSEC")
#                 self._w(f, 0, "EOF")

#     # ---------- Geometry helpers for export ----------
#     def _grid_to_mm(self, i: float, j: float, dx_m: float, dy_m: float):
#         return i * dx_m * 1000.0, j * dy_m * 1000.0

#     def _slab_rect_mm(self, s: Slab):
#         """Gross rectangle at gridlines (as defined by slab bbox)."""
#         x0, y0 = self._grid_to_mm(s.i0, s.j0, s.dx, s.dy)
#         x1, y1 = self._grid_to_mm(s.i1 + 1, s.j1 + 1, s.dx, s.dy)
#         return x0, y0, x1, y1

#     def _edge_has_beam(self, s: Slab, edge: str) -> bool:
#         """edge in {'L','R','T','B'}: slab sınırında kiriş var mı?

#         Not:
#         - İlk yaklaşım "tam boy" (sınır boyunca her hücrede) kiriş arıyordu.
#           Bu durumda kısmi kirişlerde panel sınırı grid çizgisine oturuyor,
#           kiriş bandı ile çakışmayıp ek paralel çizgiler oluşturuyordu.
#         - Krokiyi sade ve örneklere benzer tutmak için burada "en az bir segment"
#           varsa True dönüyoruz.
#         """
#         i0, j0, i1, j1 = s.bbox()
#         edge = edge.upper()
#         if edge == "L":
#             g = i0
#             if g <= 0:
#                 return False
#             k = g - 1
#             return any((k, j) in self.V_beam for j in range(j0, j1 + 1))
#         if edge == "R":
#             g = i1 + 1
#             if g <= 0 or g >= self.Nx:
#                 return False
#             k = g - 1
#             return any((k, j) in self.V_beam for j in range(j0, j1 + 1))
#         if edge == "T":
#             g = j0
#             if g <= 0:
#                 return False
#             k = g - 1
#             return any((i, k) in self.H_beam for i in range(i0, i1 + 1))
#         if edge == "B":
#             g = j1 + 1
#             if g <= 0 or g >= self.Ny:
#                 return False
#             k = g - 1
#             return any((i, k) in self.H_beam for i in range(i0, i1 + 1))
#         return False

#     def _slab_panel_rect_mm(self, s: Slab):
#         """
#         Clear panel rectangle (beam faces) in mm.
#         If a beam exists along a boundary, the panel is offset inward by bw/2.
#         """
#         bw_mm = float(self.bw.get()) * 1000.0
#         x0, y0, x1, y1 = self._slab_rect_mm(s)
#         if self._edge_has_beam(s, "L"):
#             x0 += bw_mm / 2.0
#         if self._edge_has_beam(s, "R"):
#             x1 -= bw_mm / 2.0
#         if self._edge_has_beam(s, "T"):
#             y0 += bw_mm / 2.0
#         if self._edge_has_beam(s, "B"):
#             y1 -= bw_mm / 2.0
#         return x0, y0, x1, y1

#     def _pilye_polyline(self, x0, y0, x1, y1, d=250.0, kink="both"):
#         """Plan pilye sembolü üretir.

#         - Yatay veya düşey çubuk için çalışır.
#         - Kırık noktası: uçtan L/4.
#         - 45° kırık (d) kadar sembol ofseti.
#         - kink: 'start' | 'end' | 'both' | 'none'
#             * yatayda start=sol, end=sağ
#             * düşeyde start=alt, end=üst
#         """
#         kink = (kink or "both").lower()
#         if kink not in ("start", "end", "both", "none"):
#             kink = "both"

#         # horizontal
#         if abs(y1 - y0) < 1e-6:
#             y = y0
#             # normalize so x0 < x1
#             flip = False
#             if x1 < x0:
#                 x0, x1 = x1, x0
#                 # swap start/end meaning if we flipped
#                 flip = True
#             L = abs(x1 - x0)
#             if L < 1e-6 or kink == "none":
#                 return [(x0, y), (x1, y)]

#             dx = d / math.sqrt(2)
#             dy = d / math.sqrt(2)

#             def left_kink():
#                 p1 = (x0 + L / 4.0, y)
#                 p2 = (p1[0] + dx, y + dy)
#                 return p1, p2

#             def right_kink():
#                 p3 = (x1 - L / 4.0, y)
#                 p4 = (p3[0] - dx, y + dy)
#                 return p4, p3

#             want_start = kink in ("start", "both")
#             want_end = kink in ("end", "both")
#             if flip:
#                 # if we flipped direction, swap which end is start/end
#                 want_start, want_end = want_end, want_start

#             pts = [(x0, y)]
#             if want_start:
#                 p1, p2 = left_kink()
#                 pts.extend([p1, p2])
#             if want_end:
#                 p4, p3 = right_kink()
#                 # keep ordering continuous
#                 pts.extend([p4, p3])
#             pts.append((x1, y))
#             return pts

#         # vertical
#         x = x0
#         flip = False
#         if y1 < y0:
#             y0, y1 = y1, y0
#             flip = True
#         L = abs(y1 - y0)
#         if L < 1e-6 or kink == "none":
#             return [(x, y0), (x, y1)]

#         dx = d / math.sqrt(2)
#         dy = d / math.sqrt(2)

#         def bottom_kink():
#             p1 = (x, y0 + L / 4.0)
#             p2 = (x + dx, p1[1] + dy)
#             return p1, p2

#         def top_kink():
#             p3 = (x, y1 - L / 4.0)
#             p4 = (x + dx, p3[1] - dy)
#             return p4, p3

#         want_start = kink in ("start", "both")  # start = bottom
#         want_end = kink in ("end", "both")      # end = top
#         if flip:
#             want_start, want_end = want_end, want_start

#         pts = [(x, y0)]
#         if want_start:
#             p1, p2 = bottom_kink()
#             pts.extend([p1, p2])
#         if want_end:
#             p4, p3 = top_kink()
#             pts.extend([p4, p3])
#         pts.append((x, y1))
#         return pts

#     def _export_to_dxf(self, filename: str):
#         w = self._DXFWriter()

#         # Layers
#         for ln in ["SLAB_EDGE", "BEAM", "REB_MAIN_X", "REB_MAIN_Y", "REB_DIST", "REB_SUPPORT", "TEXT"]:
#             w.add_layer(ln)

#         # Draw beams from grid sets (global)
#         # NOTE: To avoid visual clutter, we MERGE consecutive beam segments on the same gridline
#         # into a single rectangle band.
#         gdx = float(self.dx_m.get())
#         gdy = float(self.dy_m.get())

#         bw_mm = float(self.bw.get()) * 1000.0
#         half = bw_mm / 2.0

#         def _merge_consecutive(idxs):
#             idxs = sorted(set(idxs))
#             if not idxs:
#                 return []
#             ranges = []
#             a = b = idxs[0]
#             for k in idxs[1:]:
#                 if k == b + 1:
#                     b = k
#                 else:
#                     ranges.append((a, b))
#                     a = b = k
#             ranges.append((a, b))
#             return ranges

        
#         # Helper: does a beam segment lie on a *panel boundary* (between different slabs or slab/outside)?
#         def _is_vertical_boundary_seg(i_edge: int, j_cell: int) -> bool:
#             # vertical gridline g=i_edge+1 separates cell (i_edge, j) and (i_edge+1, j)
#             left = self.cell_owner.get((i_edge, j_cell))
#             right = self.cell_owner.get((i_edge + 1, j_cell))
#             return left != right  # includes None vs slab
        
#         def _is_horizontal_boundary_seg(i_cell: int, j_edge: int) -> bool:
#             # horizontal gridline g=j_edge+1 separates cell (i, j_edge) and (i, j_edge+1)
#             top = self.cell_owner.get((i_cell, j_edge))
#             bottom = self.cell_owner.get((i_cell, j_edge + 1))
#             return top != bottom
        
#         # Vertical beams: keys are vertical gridlines (i+1) -> list of j segments (FILTERED to boundaries)
#         vmap = {}
#         for (i, j) in self.V_beam:
#             if _is_vertical_boundary_seg(i, j):
#                 vmap.setdefault(i, []).append(j)
        
#         for i, js in sorted(vmap.items()):
#             x = (i + 1) * gdx * 1000.0
#             for (j0, j1) in _merge_consecutive(js):
#                 y0 = j0 * gdy * 1000.0
#                 y1 = (j1 + 1) * gdy * 1000.0
#                 w.add_polyline([(x - half, y0), (x + half, y0), (x + half, y1), (x - half, y1)], layer="BEAM", closed=True)
        
#         # Horizontal beams: keys are horizontal gridlines (j+1) -> list of i segments (FILTERED to boundaries)
#         hmap = {}
#         for (i, j) in self.H_beam:
#             if _is_horizontal_boundary_seg(i, j):
#                 hmap.setdefault(j, []).append(i)
        
#         for j, is_ in sorted(hmap.items()):
#             y = (j + 1) * gdy * 1000.0
#             for (i0, i1) in _merge_consecutive(is_):
#                 x0 = i0 * gdx * 1000.0
#                 x1 = (i1 + 1) * gdx * 1000.0
#                 w.add_polyline([(x0, y - half), (x1, y - half), (x1, y + half), (x0, y + half)], layer="BEAM", closed=True)
        
#         # Draw slabs + rebars
#         for sid in sorted(self.slabs.keys()):
#             s = self.slabs[sid]
#             # gross rect (grid) and clear panel rect (beam faces)
#             gx0, gy0, gx1, gy1 = self._slab_rect_mm(s)
#             x0, y0, x1, y1 = self._slab_panel_rect_mm(s)

#             # slab/panel border (beam faces)
#             w.add_polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer="SLAB_EDGE", closed=True)

#             # slab id
#             w.add_text((x0+x1)/2.0, (y0+y1)/2.0, sid, height=420.0, layer="TEXT")

#             dcache = self.last_design.get(sid)
#             if not dcache:
#                 continue

#             cover = float(dcache.get("cover_mm", 25.0))
#             ix0, iy0, ix1, iy1 = x0 + cover, y0 + cover, x1 - cover, y1 - cover
#             if ix1 <= ix0 or iy1 <= iy0:
#                 continue

#             kind = dcache.get("kind")
#             if kind == "ONEWAY":
#                 auto_dir = dcache.get("auto_dir", "X")
#                 ch_main = dcache["choices"]["main"]
#                 ch_dist = dcache["choices"]["dist"]
#                 ch_extra = dcache["choices"].get("support_extra")

#                 midx = (ix0 + ix1) / 2.0
#                 midy = (iy0 + iy1) / 2.0

#                 # Sadece gösterim için 1 adet temsilî donatı çiz
#                 if auto_dir == "X":
#                     # Ana donatı (X doğrultu) -> yatay 1 çubuk
#                     pts = self._pilye_polyline(ix0, midy, ix1, midy, d=250.0, kink='both')
#                     w.add_polyline(pts, layer="REB_MAIN_X", closed=False)
#                     w.add_text(ix0, midy + 250.0, ch_main.label(), height=280.0, layer="TEXT")

#                     # Dağıtma (Y) -> düşey 1 çubuk
#                     w.add_line(midx, iy0, midx, iy1, layer="REB_DIST")
#                     w.add_text(midx + 200.0, iy1 + 200.0, f"D {ch_dist.label()}", height=260.0, layer="TEXT")

#                     # Mesnet ilave (L/4 şerit) -> solda ve sağda 1'er kısa çubuk
#                     if ch_extra:
#                         strip = (ix1 - ix0) / 4.0
#                         ptsL = self._pilye_polyline(ix0, midy, ix0 + strip, midy, d=250.0, kink='start')
#                         ptsR = self._pilye_polyline(ix1 - strip, midy, ix1, midy, d=250.0, kink='end')
#                         w.add_polyline(ptsL, layer="REB_SUPPORT", closed=False)
#                         w.add_polyline(ptsR, layer="REB_SUPPORT", closed=False)
#                         w.add_text(ix0 + strip + 200.0, midy - 350.0, f"mesnet ilave {ch_extra.label()}", height=260.0, layer="TEXT")
#                 else:
#                     # Ana donatı (Y doğrultu) -> düşey 1 çubuk
#                     pts = self._pilye_polyline(midx, iy0, midx, iy1, d=250.0, kink='both')
#                     w.add_polyline(pts, layer="REB_MAIN_Y", closed=False)
#                     w.add_text(midx + 200.0, iy0, ch_main.label(), height=280.0, layer="TEXT")

#                     # Dağıtma (X) -> yatay 1 çubuk
#                     w.add_line(ix0, midy, ix1, midy, layer="REB_DIST")
#                     w.add_text(ix0, midy + 250.0, f"D {ch_dist.label()}", height=260.0, layer="TEXT")

#                     if ch_extra:
#                         strip = (iy1 - iy0) / 4.0
#                         ptsB = self._pilye_polyline(midx, iy0, midx, iy0 + strip, d=250.0, kink='start')
#                         ptsT = self._pilye_polyline(midx, iy1 - strip, midx, iy1, d=250.0, kink='end')
#                         w.add_polyline(ptsB, layer="REB_SUPPORT", closed=False)
#                         w.add_polyline(ptsT, layer="REB_SUPPORT", closed=False)
#                         w.add_text(midx + 250.0, iy0 + strip + 200.0, f"mesnet ilave {ch_extra.label()}", height=260.0, layer="TEXT")

#             elif kind == "TWOWAY":
#                 chx = dcache["choices"]["x_span"]
#                 chy = dcache["choices"]["y_span"]
#                 chx_il = dcache["choices"].get("x_support_extra")
#                 chy_il = dcache["choices"].get("y_support_extra")

#                 midx = (ix0 + ix1) / 2.0
#                 midy = (iy0 + iy1) / 2.0

#                 # X doğrultusu (yatay) 1 çubuk
#                 ptsx = self._pilye_polyline(ix0, midy, ix1, midy, d=250.0, kink='both')
#                 w.add_polyline(ptsx, layer="REB_MAIN_X", closed=False)
#                 w.add_text(ix0, midy + 250.0, f"X {chx.label()}", height=280.0, layer="TEXT")

#                 # Y doğrultusu (düşey) 1 çubuk
#                 ptsy = self._pilye_polyline(midx, iy0, midx, iy1, d=250.0, kink='both')
#                 w.add_polyline(ptsy, layer="REB_MAIN_Y", closed=False)
#                 w.add_text(midx + 200.0, iy1 + 200.0, f"Y {chy.label()}", height=280.0, layer="TEXT")

#                 # Mesnet ilaveler (L/4 şerit) -> temsilî
#                 if chx_il:
#                     strip = (ix1 - ix0) / 4.0
#                     w.add_line(ix0, midy - 250.0, ix0 + strip, midy - 250.0, layer="REB_SUPPORT")
#                     w.add_line(ix1 - strip, midy - 250.0, ix1, midy - 250.0, layer="REB_SUPPORT")
#                     w.add_text(ix0 + strip + 200.0, midy - 550.0, f"X mesnet ilave {chx_il.label()}", height=260.0, layer="TEXT")

#                 if chy_il:
#                     strip = (iy1 - iy0) / 4.0
#                     w.add_line(midx - 250.0, iy0, midx - 250.0, iy0 + strip, layer="REB_SUPPORT")
#                     w.add_line(midx - 250.0, iy1 - strip, midx - 250.0, iy1, layer="REB_SUPPORT")
#                     w.add_text(midx - 50.0, iy0 + strip + 200.0, f"Y mesnet ilave {chy_il.label()}", height=260.0, layer="TEXT")
#             elif kind == "BALCONY":
#                 ch_main = dcache["choices"]["main"]
#                 ch_dist = dcache["choices"]["dist"]
#                 fixed_edge = (dcache.get("fixed_edge", "L") or "L").upper()

#                 midx = (ix0 + ix1) / 2.0
#                 midy = (iy0 + iy1) / 2.0

#                 # Balkon ana donatı: sadece ANKASTRE kenarda pilye (tek uç)
#                 if fixed_edge in ("L", "R"):
#                     kink = "start" if fixed_edge == "L" else "end"
#                     # Ana donatı (konsol doğrultusu) -> yatay temsilî çubuk
#                     pts = self._pilye_polyline(ix0, midy, ix1, midy, d=250.0, kink=kink)
#                     w.add_polyline(pts, layer="REB_SUPPORT", closed=False)
#                     w.add_text(ix0, midy + 250.0, f"ana {ch_main.label()}", height=280.0, layer="TEXT")
 
#                     # Dağıtma -> düşey temsilî çubuk
#                     w.add_line(midx, iy0, midx, iy1, layer="REB_DIST")
#                     w.add_text(midx + 200.0, iy1 + 200.0, f"D {ch_dist.label()}", height=260.0, layer="TEXT")
#                 else:
#                     kink = "end" if fixed_edge == "T" else "start"  # T=üst (end), B=alt (start)
#                     # Ana donatı -> düşey temsilî çubuk
#                     pts = self._pilye_polyline(midx, iy0, midx, iy1, d=250.0, kink=kink)
#                     w.add_polyline(pts, layer="REB_SUPPORT", closed=False)
#                     w.add_text(midx + 200.0, iy0, f"ana {ch_main.label()}", height=280.0, layer="TEXT")

#                     # Dağıtma -> yatay temsilî çubuk
#                     w.add_line(ix0, midy, ix1, midy, layer="REB_DIST")
#                     w.add_text(ix0, midy + 250.0, f"D {ch_dist.label()}", height=260.0, layer="TEXT")

#         w.save(filename)

# # =========================================================
# # END
# # =========================================================
# if __name__ == "__main__":
#     App().mainloop()