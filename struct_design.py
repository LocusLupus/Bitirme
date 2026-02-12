import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from constants import (
    beton_tablosu, _tab_col,
    PHI_LIST, S_LIST
)

@dataclass(frozen=True)
class RebarChoice:
    phi_mm: int
    s_mm: int
    area_mm2_per_m: float

    def label(self) -> str:
        return f"Ø{self.phi_mm}/{self.s_mm}"

    def label_with_area(self) -> str:
        return f"Ø{self.phi_mm}/{self.s_mm} (Aprov={self.area_mm2_per_m:.1f} mm²/m)"

# =========================================================
# Math Helpers
# =========================================================
def lerp(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)

def interp_alpha(m: float, m_points: List[float], a_points: List[float]) -> float:
    if m <= m_points[0]:
        return a_points[0]
    if m >= m_points[-1]:
        return a_points[-1]
    for i in range(len(m_points) - 1):
        x0, x1 = m_points[i], m_points[i+1]
        if x0 <= m <= x1:
            return lerp(x0, a_points[i], x1, a_points[i+1], m)
    return a_points[-1]

# =========================================================
# ONEWAY multi-span coefficients
# =========================================================
def one_way_coefficients(n_spans: int):
    """
    Tek doğrultuda çalışan döşemeler için moment katsayıları.
    Uzun kenarlarından sürekli döşeme sayısına göre katsayılar belirlenir.
    
    Kurallar:
    - 1 açıklık: M+ = pl²/8, mesnet momenti yok (ayrı işlenir)
    - 2 açıklık: Tüm M+ = pl²/11, orta mesnet = pl²/8, dış mesnetler = pl²/24
    - 3 açıklık: Kenar M+ = pl²/11, orta M+ = pl²/15, dış mesnetler = pl²/24, iç mesnetler = pl²/9
    - 4+ açıklık: Kenar M+ = pl²/11, diğer M+ = pl²/15, 
                  dış mesnetler = pl²/24, tam orta mesnet = pl²/10, diğer iç mesnetler = pl²/9
    
    Returns:
        (support_neg, span_pos): Mesnet ve açıklık katsayıları (negatif/pozitif işaretli)
    """
    if n_spans == 1:
        # Tek açıklık: mesnet momenti yok, açıklık momenti 1/8
        return [0.0, 0.0], [1/8]
    
    if n_spans == 2:
        # 2 açıklık: orta mesnet 1/8, dış mesnetler 1/24
        return [-1/24, -1/8, -1/24], [1/11, 1/11]
    
    if n_spans == 3:
        # 3 açıklık: dış mesnetler 1/24, iç mesnetler 1/9
        return [-1/24, -1/9, -1/9, -1/24], [1/11, 1/15, 1/11]
    
    # 4+ açıklık
    support_neg = [0.0] * (n_spans + 1)
    support_neg[0] = support_neg[-1] = -1/24  # Dış mesnetler
    
    # İç mesnetler
    for i in range(1, n_spans):
        support_neg[i] = -1/9  # Varsayılan iç mesnet
    
    # Tam ortadaki mesnet (varsa) 1/10
    if n_spans % 2 == 0:
        # Çift sayıda açıklık: tam ortada tek bir mesnet var
        mid_support = n_spans // 2
        support_neg[mid_support] = -1/10
    # Tek sayıda açıklık için orta yok, hepsi 1/9 kalır
    
    # Açıklık katsayıları
    span_pos = [1/15] * n_spans
    span_pos[0] = span_pos[-1] = 1/11  # Kenar açıklıklar
    
    return support_neg, span_pos

def one_span_coeff_by_fixity(fixed_start: bool, fixed_end: bool):
    if (not fixed_start) and (not fixed_end):
        return (0.0, 0.0), (1.0/8.0)
    if fixed_start and fixed_end:
        return (-1.0/12.0, -1.0/12.0), (1.0/24.0)
    if fixed_start and (not fixed_end):
        return (-1.0/8.0, 0.0), (9.0/128.0)
    return (0.0, -1.0/8.0), (9.0/128.0)

# =========================================================
# Table Lookup and Interpolation
# =========================================================
def get_table_value(row: int, colname: str) -> float:
    return beton_tablosu[row][_tab_col[colname]]

def conc_to_tabcol(conc: str) -> str:
    if conc.startswith("C20"): return "C25"
    if conc.startswith("C25"): return "C25"
    if conc.startswith("C30"): return "C30"
    if conc.startswith("C35"): return "C35"
    if conc.startswith("C40"): return "C40"
    return "C25"

def steel_to_tabcol(steel: str) -> str:
    return "S420" if steel == "B420C" else "B500"

def interp_ks_from_K(K_calc: float, conc_col: str, steel_col: str) -> Tuple[float, List[str]]:
    """K değerine göre ks katsayısını tablodan interpolasyon ile bulur."""
    steps = []
    pairs = []
    for r in sorted(beton_tablosu.keys()):
        K_r = get_table_value(r, conc_col)
        ks_r = get_table_value(r, steel_col)
        pairs.append((K_r, ks_r, r))
    pairs.sort(key=lambda x: x[0], reverse=True)

    K_max = pairs[0][0]
    K_min = pairs[-1][0]

    if K_calc >= K_max:
        ks = pairs[0][1]
        steps.append(f"K={K_calc:.2f} >= K_max={K_max:.2f} → ks={ks:.3f}")
        return ks, steps
    if K_calc <= K_min:
        ks = pairs[-1][1]
        steps.append(f"K={K_calc:.2f} <= K_min={K_min:.2f} → ks={ks:.3f}")
        return ks, steps

    for (K_hi, ks_hi, r_hi), (K_lo, ks_lo, r_lo) in zip(pairs[:-1], pairs[1:]):
        if K_hi >= K_calc >= K_lo:
            # Lineer interpolasyon
            ks = lerp(K_hi, ks_hi, K_lo, ks_lo, K_calc)
            steps.append(f"Tablo: K={K_hi:.1f}→ks={ks_hi:.2f}, K={K_lo:.1f}→ks={ks_lo:.2f}")
            steps.append(f"ks = {ks_hi:.2f} + ({K_calc:.2f}-{K_hi:.1f})/({K_lo:.1f}-{K_hi:.1f})×({ks_lo:.2f}-{ks_hi:.2f}) = {ks:.3f}")
            return ks, steps

    ks = pairs[-1][1]
    steps.append(f"Braket bulunamadı → ks={ks:.3f}")
    return ks, steps

# =========================================================
# As from abacus
# =========================================================
def as_from_abacus_steps(
    M_kNm_per_m: Optional[float],
    conc: str,
    steel: str,
    h_mm: float,
    cover_mm: float,
    d_override_mm: Optional[float] = None
) -> Tuple[Optional[float], List[str]]:
    steps = []
    if M_kNm_per_m is None:
        return None, ["M=None -> As hesaplanmadı."]
    if M_kNm_per_m <= 0:
        return 0.0, [f"M={M_kNm_per_m} <=0 -> As=0"]

    d_nom = h_mm - cover_mm
    d = float(d_override_mm) if d_override_mm is not None else d_nom

    if d_override_mm is not None:
        steps.append(f"d override: d = {d:.1f} mm (nominal d={d_nom:.1f} mm)")
    else:
        steps.append(f"d = h - paspayı = {h_mm:.1f} - {cover_mm:.1f} = {d:.1f} mm (φ/2 YOK)")

    if d <= 0:
        raise ValueError("d<=0: h/cover yanlış veya d_override hatalı.")

    b_mm = 1000.0
    M_Nmm = abs(M_kNm_per_m) * 1e6
    steps.append(f"M = {abs(M_kNm_per_m):.3f} kNm/m = {M_Nmm:.0f} Nmm/m")

    # K = 100 × (b × d²) / M_Nmm
    K_calc = 100 * (b_mm * (d**2)) / M_Nmm
    conc_col = conc_to_tabcol(conc)
    steel_col = steel_to_tabcol(steel)
    steps.append(f"K = 100×(b×d²)/M = 100×({b_mm:.0f}×{d:.1f}²)/{M_Nmm:.0f} = {K_calc:.2f}")

    ks, st_ks = interp_ks_from_K(K_calc, conc_col, steel_col)
    steps.extend(st_ks)

    As = ks * abs(M_kNm_per_m) * 1000.0 / d
    steps.append(f"As = ks×M×1000/d = {ks:.3f}×{abs(M_kNm_per_m):.3f}×1000/{d:.1f} = {As:.1f} mm²/m")
    return As, steps

# =========================================================
# Donatı katalogu ve seçim
# =========================================================
def area_per_m(phi_mm: int, s_mm: int) -> float:
    Ab = math.pi * (phi_mm**2) / 4.0
    return Ab * (1000.0 / s_mm)

def select_rebar_min_area(As_req: float, s_max: int, phi_min: int = 8, phi_max: int = 32) -> Optional[RebarChoice]:
    best = None
    for phi in PHI_LIST:
        if phi < phi_min or phi > phi_max:
            continue
        for s in S_LIST:
            if s > s_max:
                continue
            A = area_per_m(phi, s)
            if A + 1e-9 >= As_req:
                cand = RebarChoice(phi, s, A)
                if best is None:
                    best = cand
                else:
                    if cand.area_mm2_per_m < best.area_mm2_per_m - 1e-9:
                        best = cand
                    elif abs(cand.area_mm2_per_m - best.area_mm2_per_m) < 1e-9:
                        if cand.s_mm > best.s_mm:
                            best = cand
    return best

def max_possible_area(s_max: int, phi_min: int = 8, phi_max: int = 32) -> float:
    mx = 0.0
    for phi in PHI_LIST:
        if phi < phi_min or phi > phi_max:
            continue
        for s in S_LIST:
            if s > s_max:
                continue
            mx = max(mx, area_per_m(phi, s))
    return mx

def split_duz_pilye(choice: RebarChoice) -> Tuple[RebarChoice, RebarChoice]:
    s2 = choice.s_mm * 2
    halfA = choice.area_mm2_per_m / 2.0
    duz = RebarChoice(choice.phi_mm, s2, halfA)
    pilye = RebarChoice(choice.phi_mm, s2, halfA)
    return duz, pilye

# =========================================================
# TS500 / Konstrüktif kural parametreleri
# =========================================================
def rho_min_oneway(steel: str) -> float:
    return 0.002 if steel in ("B420C", "B500C") else 0.003

def oneway_smax_main(h_mm: float) -> int:
    return int(min(1.5*h_mm, 200))

def oneway_smax_dist() -> int:
    return 300

def twoway_smax_short(h_mm: float) -> int:
    return int(min(1.5*h_mm, 200))

def twoway_smax_long(h_mm: float) -> int:
    return int(min(1.5*h_mm, 250))

def asb_min_area(steel: str) -> float:
    if steel == "B500C":
        return area_per_m(5, 150)
    if steel == "B420C":
        return area_per_m(8, 300)
    return area_per_m(8, 200)
