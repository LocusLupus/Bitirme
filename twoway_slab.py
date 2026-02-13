"""
Çift Doğrultulu Döşeme Hesabı Modülü
====================================
Bu modül çift doğrultulu (two-way) döşemelerin moment hesabı ve donatı tasarımını içerir.
"""

from typing import Dict, Tuple, List, Optional
from constants import ALPHA_TABLE, M_POINTS, CASE_DESC
from struct_design import (
    interp_alpha, twoway_smax_short, twoway_smax_long,
    select_rebar_min_area, RebarChoice
)


def slab_edge_has_beam(system, sid: str, edge: str) -> bool:
    """
    Döşemenin belirli bir kenarında kiriş olup olmadığını kontrol eder.
    """
    s = system.slabs[sid]
    i0, j0, i1, j1 = s.bbox()
    edge = edge.upper()
    if edge == "LEFT":
        return system.is_beam_gridline_for_slab(sid, "X", i0)
    if edge == "RIGHT":
        return system.is_beam_gridline_for_slab(sid, "X", i1 + 1)
    if edge == "TOP":
        return system.is_beam_gridline_for_slab(sid, "Y", j0)
    if edge == "BOTTOM":
        return system.is_beam_gridline_for_slab(sid, "Y", j1 + 1)
    return False


def twoway_net_LxLy(system, sid: str, bw: float) -> Tuple[float, float, List[str]]:
    """
    Çift doğrultulu döşeme için net açıklıkları hesaplar.
    """
    steps = []
    s = system.slabs[sid]
    Lx_g, Ly_g = s.size_m_gross()
    left = slab_edge_has_beam(system, sid, "LEFT")
    right = slab_edge_has_beam(system, sid, "RIGHT")
    top = slab_edge_has_beam(system, sid, "TOP")
    bottom = slab_edge_has_beam(system, sid, "BOTTOM")

    steps.append(f"Brüt: Lx={Lx_g:.3f}, Ly={Ly_g:.3f}")
    Lx_n = max(0.05, Lx_g - (0.5*bw if left else 0.0) - (0.5*bw if right else 0.0))
    Ly_n = max(0.05, Ly_g - (0.5*bw if top else 0.0) - (0.5*bw if bottom else 0.0))
    steps.append(f"Lx_net = {Lx_n:.3f}, Ly_net = {Ly_n:.3f}")
    return Lx_n, Ly_n, steps


def twoway_edge_continuity_full(system, sid: str):
    """
    Döşemenin tüm kenarlarının süreklilik durumunu kontrol eder.
    """
    Lf, La, Lr = system.edge_neighbor_coverage(sid, "L")
    Rf, Ra, Rr = system.edge_neighbor_coverage(sid, "R")
    Tf, Ta, Tr = system.edge_neighbor_coverage(sid, "T")
    Bf, Ba, Br = system.edge_neighbor_coverage(sid, "B")
    return (Lf, Rf, Tf, Bf), (La, Ra, Ta, Ba), (Lr, Rr, Tr, Br)


def pick_two_way_case_exact(Lx_net: float, Ly_net: float,
                            cont_left: bool, cont_right: bool, 
                            cont_top: bool, cont_bottom: bool) -> int:
    """
    Çift doğrultulu döşeme için durum numarasını belirler (1-7).
    """
    disc = {"L": not cont_left, "R": not cont_right, "T": not cont_top, "B": not cont_bottom}
    n_disc = sum(disc.values())

    if n_disc == 0: return 1
    if n_disc == 4: return 7
    if n_disc == 1: return 2
    if n_disc == 3: return 6

    eps = 1e-9
    if abs(Lx_net - Ly_net) < eps:
        short_edges, long_edges = set(), set()
    elif Lx_net < Ly_net:
        short_edges, long_edges = {"T", "B"}, {"L", "R"}
    else:
        short_edges, long_edges = {"L", "R"}, {"T", "B"}

    disc_edges = {e for e, d in disc.items() if d}
    if len(disc_edges) != 2:
        return 3

    if short_edges and disc_edges == short_edges: return 4
    if long_edges and disc_edges == long_edges: return 5

    adjacent_pairs = [{"L", "T"}, {"T", "R"}, {"R", "B"}, {"B", "L"}]
    if any(disc_edges == p for p in adjacent_pairs):
        return 3

    if disc_edges == {"T", "B"}: return 4
    if disc_edges == {"L", "R"}: return 5
    return 3


def compute_twoway_per_slab(system, sid: str, bw: float) -> Tuple[dict, List[str]]:
    """
    Çift doğrultulu döşeme için moment hesabı yapar.
    
    Args:
        system: SlabSystem nesnesi
        sid: Döşeme ID'si
        bw: Kiriş genişliği (m)
    
    Returns:
        (sonuç_dict, hesap_adımları_listesi)
    """
    steps = []
    s = system.slabs[sid]
    pd = s.pd
    Lx_n, Ly_n, st_net = twoway_net_LxLy(system, sid, bw)
    steps.extend(st_net)

    ll = max(Lx_n, Ly_n)
    ls = min(Lx_n, Ly_n)
    m = ll / ls if ls > 0 else 1.0
    steps.append(f"m = {ll:.3f}/{ls:.3f} = {m:.3f}")

    (Lf, Rf, Tf, Bf), *_ = twoway_edge_continuity_full(system, sid)
    steps.append(f"Full süreklilik: L={Lf}, R={Rf}, T={Tf}, B={Bf}")
    case = pick_two_way_case_exact(Lx_n, Ly_n, Lf, Rf, Tf, Bf)
    row = ALPHA_TABLE[case]
    steps.append(f"Case {case}: {CASE_DESC.get(case,'-')}")

    a_sn = interp_alpha(m, M_POINTS, row.short_neg) if row.short_neg is not None else None
    a_sp = interp_alpha(m, M_POINTS, row.short_pos) if row.short_pos is not None else None
    a_ln = row.long_neg
    a_lp = row.long_pos

    steps.append(f"Alphas: sn={a_sn}, sp={a_sp}, ln={a_ln}, lp={a_lp}")

    # Moment hesabı: M = α × pd × ls²
    ls_sq = ls ** 2
    steps.append(f"pd = {pd:.3f} kN/m², ls = {ls:.3f} m, ls² = {ls_sq:.4f} m²")
    
    M_sn = a_sn * pd * ls_sq if a_sn is not None else None
    M_sp = a_sp * pd * ls_sq if a_sp is not None else None
    M_ln = a_ln * pd * ls_sq if a_ln is not None else None
    M_lp = a_lp * pd * ls_sq if a_lp is not None else None

    # Moment değerlerini göster
    steps.append(f"M_sn = {a_sn}×{pd:.3f}×{ls_sq:.4f} = {M_sn:.3f} kNm/m" if M_sn is not None else "M_sn = -")
    steps.append(f"M_sp = {a_sp}×{pd:.3f}×{ls_sq:.4f} = {M_sp:.3f} kNm/m" if M_sp is not None else "M_sp = -")
    steps.append(f"M_ln = {a_ln}×{pd:.3f}×{ls_sq:.4f} = {M_ln:.3f} kNm/m" if M_ln is not None else "M_ln = -")
    steps.append(f"M_lp = {a_lp}×{pd:.3f}×{ls_sq:.4f} = {M_lp:.3f} kNm/m" if M_lp is not None else "M_lp = -")

    short_dir = "X" if Lx_n <= Ly_n else "Y"
    steps.append(f"Kısa doğrultu: {short_dir}")
    
    # Eksenlere atama - her zaman hem X hem Y göster
    def fmt_moment(val, name):
        return f"{val:.3f}" if val is not None else "-"
    
    if short_dir == "X":
        steps.append(f"  Mx_neg = M_sn = {fmt_moment(M_sn, 'M_sn')}, Mx_pos = M_sp = {fmt_moment(M_sp, 'M_sp')}")
        steps.append(f"  My_neg = M_ln = {fmt_moment(M_ln, 'M_ln')}, My_pos = M_lp = {fmt_moment(M_lp, 'M_lp')}")
    else:
        steps.append(f"  My_neg = M_sn = {fmt_moment(M_sn, 'M_sn')}, My_pos = M_sp = {fmt_moment(M_sp, 'M_sp')}")
        steps.append(f"  Mx_neg = M_ln = {fmt_moment(M_ln, 'M_ln')}, Mx_pos = M_lp = {fmt_moment(M_lp, 'M_lp')}")

    if short_dir == "X":
        Mx_neg, Mx_pos = M_sn, M_sp
        My_neg, My_pos = M_ln, M_lp
    else:
        My_neg, My_pos = M_sn, M_sp
        Mx_neg, Mx_pos = M_ln, M_lp

    return {
        "Lx_net": Lx_n, "Ly_net": Ly_n, "ls": ls, "m": m,
        "case": case, "Mx": (Mx_neg, Mx_pos), "My": (My_neg, My_pos),
        "short_dir": short_dir
    }, steps


def get_neighbor_on_edge_twoway(system, sid: str, edge: str):
    """
    Belirli bir kenarın komşu döşemesini ve türünü döndürür.
    
    Args:
        system: SlabSystem nesnesi
        sid: Döşeme ID'si
        edge: Kenar ("L", "R", "T", "B")
    
    Returns:
        (komşu_sid, komşu_kind) veya (None, None) eğer komşu yoksa
    """
    edge = edge.upper()
    s = system.slabs[sid]
    i0, j0, i1, j1 = s.bbox()
    
    if edge == "L":
        if i0 == 0:
            return None, None
        for j in range(j0, j1 + 1):
            nb = system.cell_owner.get((i0 - 1, j))
            if nb and nb != sid and nb in system.slabs:
                return nb, system.slabs[nb].kind
    elif edge == "R":
        if i1 >= system.Nx - 1:
            return None, None
        for j in range(j0, j1 + 1):
            nb = system.cell_owner.get((i1 + 1, j))
            if nb and nb != sid and nb in system.slabs:
                return nb, system.slabs[nb].kind
    elif edge == "T":
        if j0 == 0:
            return None, None
        for i in range(i0, i1 + 1):
            nb = system.cell_owner.get((i, j0 - 1))
            if nb and nb != sid and nb in system.slabs:
                return nb, system.slabs[nb].kind
    elif edge == "B":
        if j1 >= system.Ny - 1:
            return None, None
        for i in range(i0, i1 + 1):
            nb = system.cell_owner.get((i, j1 + 1))
            if nb and nb != sid and nb in system.slabs:
                return nb, system.slabs[nb].kind
    
    return None, None


def compute_twoway_report(system, sid: str, res: dict, conc: str, steel: str,
                          h: float, cover: float, bw: float,
                          neighbor_pilye_areas: Optional[dict] = None) -> Tuple[dict, List[str]]:
    """
    Çift doğrultulu döşeme için donatı hesabı ve raporlama yapar.
    
    Args:
        system: SlabSystem nesnesi
        sid: Döşeme ID'si
        res: compute_twoway_per_slab sonucu
        conc: Beton sınıfı
        steel: Çelik sınıfı
        h: Döşeme kalınlığı (mm)
        cover: Pas payı (mm)
        bw: Kiriş genişliği (m)
        neighbor_pilye_areas: Komşu döşemelerin pilye alanları {sid: area_mm2_per_m}
    
    Returns:
        (tasarım_sonucu_dict, rapor_satırları_listesi)
    """
    lines = []
    
    if neighbor_pilye_areas is None:
        neighbor_pilye_areas = {}
    
    mxn, mxp = res["Mx"]
    myn, myp = res["My"]
    
    smax_x = twoway_smax_short(h) if res["short_dir"] == "X" else twoway_smax_long(h)
    smax_y = twoway_smax_long(h) if res["short_dir"] == "X" else twoway_smax_short(h)
    
    lines.append(f"smax_x = {smax_x} mm, smax_y = {smax_y} mm")
    lines.append("")
    
    # X doğrultusu: d = h - cover (normal)
    # Y doğrultusu açıklık: d = h - cover - 10 (üst üste binen donatı için)
    # Y doğrultusu mesnet: d = h - cover (normal)
    
    # X açıklık donatısı
    lines.append("--- X Açıklık Donatısı (Mx_pos) ---")
    asx, ch_x, steps_x = system.design_main_rebar_from_M(mxp or 0, conc, steel, h, cover, smax_x, label_prefix="", d_delta_mm=0.0)
    for step in steps_x:
        lines.append(f"  {step}")
    lines.append(f"  Seçilen: {ch_x.label()}")
    
    # X açıklık donatısını düz ve pilye olarak eşit şekilde ayır
    ch_x_duz = RebarChoice(ch_x.phi_mm, ch_x.s_mm * 2, ch_x.area_mm2_per_m / 2)
    ch_x_pilye = RebarChoice(ch_x.phi_mm, ch_x.s_mm * 2, ch_x.area_mm2_per_m / 2)
    lines.append(f"  → Düz: {ch_x_duz.label()}, Pilye: {ch_x_pilye.label()}")
    lines.append("")
    
    # Y açıklık donatısı (d - 10mm)
    lines.append("--- Y Açıklık Donatısı (My_pos) [d-10mm] ---")
    asy, ch_y, steps_y = system.design_main_rebar_from_M(myp or 0, conc, steel, h, cover, smax_y, label_prefix="", d_delta_mm=-10.0)
    for step in steps_y:
        lines.append(f"  {step}")
    lines.append(f"  Seçilen: {ch_y.label()}")
    
    # Y açıklık donatısını düz ve pilye olarak eşit şekilde ayır
    ch_y_duz = RebarChoice(ch_y.phi_mm, ch_y.s_mm * 2, ch_y.area_mm2_per_m / 2)
    ch_y_pilye = RebarChoice(ch_y.phi_mm, ch_y.s_mm * 2, ch_y.area_mm2_per_m / 2)
    lines.append(f"  → Düz: {ch_y_duz.label()}, Pilye: {ch_y_pilye.label()}")
    lines.append("")
    
    # X mesnet donatısı gereksinimi ve ek donatı kontrolü
    lines.append("--- X Mesnet Donatısı (Mx_neg) ---")
    asxn, ch_xn, steps_xn = system.design_main_rebar_from_M(abs(mxn or 0), conc, steel, h, cover, smax_x, label_prefix="", d_delta_mm=0.0)
    for step in steps_xn:
        lines.append(f"  {step}")
    lines.append(f"  Gerekli As_mesnet = {asxn:.1f} mm²/m")
    
    # X mesnet donatı kontrolü (L/R kenarları)
    As_pilye_x = ch_x_pilye.area_mm2_per_m
    choices_il = {"L": None, "R": None, "T": None, "B": None}
    
    for edge in ["L", "R"]:
        neighbor_id, neighbor_kind = get_neighbor_on_edge_twoway(system, sid, edge)
        
        if neighbor_id is None:
            # Süreksiz kenar - mesnet ek donatısı gerekmez
            lines.append(f"  {edge} kenarı: Süreksiz → Mesnet ek donatısı gerekmez")
            continue
            
        As_pilye_komsu = 0.0
        neighbor_info = ""
        
        if neighbor_kind == "BALCONY":
            neighbor_info = f"BALCONY ({neighbor_id})"
        else:
            As_pilye_komsu = neighbor_pilye_areas.get(neighbor_id, 0.0)
            neighbor_info = f"{neighbor_kind} ({neighbor_id})"
            
        As_mevcut = As_pilye_x + As_pilye_komsu
        As_ek = max(0, asxn - As_mevcut)
        
        lines.append(f"  {edge} kenarı: {neighbor_info}")
        lines.append(f"    Gerekli: {asxn:.1f} - Mevcut: (Kendi:{As_pilye_x:.1f} + Komşu:{As_pilye_komsu:.1f} = {As_mevcut:.1f}) = Fark: {asxn - As_mevcut:.1f}")
        
        if As_ek > 1e-6:
            ch_il = select_rebar_min_area(As_ek, 300)
            if ch_il:
                choices_il[edge] = ch_il
                lines.append(f"    → Seçilen Ek Donatı ({edge}): {ch_il.label_with_area()}")
        else:
            lines.append(f"    → Pilye yeterli, ek donatı gerekmiyor.")
    lines.append("")
    
    # Y mesnet donatısı gereksinimi ve ek donatı kontrolü
    lines.append("--- Y Mesnet Donatısı (My_neg) ---")
    asyn, ch_yn, steps_yn = system.design_main_rebar_from_M(abs(myn or 0), conc, steel, h, cover, smax_y, label_prefix="", d_delta_mm=0.0)
    for step in steps_yn:
        lines.append(f"  {step}")
    lines.append(f"  Gerekli As_mesnet = {asyn:.1f} mm²/m")
    
    # Y mesnet ek donatı kontrolü (T/B kenarları)
    As_pilye_y = ch_y_pilye.area_mm2_per_m
    
    for edge in ["T", "B"]:
        neighbor_id, neighbor_kind = get_neighbor_on_edge_twoway(system, sid, edge)
        
        if neighbor_id is None:
            # Süreksiz kenar - mesnet ek donatısı gerekmez
            lines.append(f"  {edge} kenarı: Süreksiz → Mesnet ek donatısı gerekmez")
            continue
            
        As_pilye_komsu = 0.0
        neighbor_info = ""
        
        if neighbor_kind == "BALCONY":
            neighbor_info = f"BALCONY ({neighbor_id})"
        else:
            As_pilye_komsu = neighbor_pilye_areas.get(neighbor_id, 0.0)
            neighbor_info = f"{neighbor_kind} ({neighbor_id})"
            
        As_mevcut = As_pilye_y + As_pilye_komsu
        As_ek = max(0, asyn - As_mevcut)
        
        lines.append(f"  {edge} kenarı: {neighbor_info}")
        lines.append(f"    Gerekli: {asyn:.1f} - Mevcut: (Kendi:{As_pilye_y:.1f} + Komşu:{As_pilye_komsu:.1f} = {As_mevcut:.1f}) = Fark: {asyn - As_mevcut:.1f}")
        
        if As_ek > 1e-6:
            ch_il = select_rebar_min_area(As_ek, 300)
            if ch_il:
                choices_il[edge] = ch_il
                lines.append(f"    → Seçilen Ek Donatı ({edge}): {ch_il.label_with_area()}")
        else:
            lines.append(f"    → Pilye yeterli, ek donatı gerekmiyor.")
    lines.append("")

    (Lf, Rf, Tf, Bf), _, _ = twoway_edge_continuity_full(system, sid)

    design_res = {
        "kind": "TWOWAY", "short_dir": res["short_dir"], "cover_mm": cover,
        "choices": {
            "x_span": ch_x, 
            "x_span_duz": ch_x_duz, 
            "x_span_pilye": ch_x_pilye,
            "y_span": ch_y, 
            "y_span_duz": ch_y_duz, 
            "y_span_pilye": ch_y_pilye,
            "support_extra": choices_il  # Store dict for all 4 edges
        },
        "edge_continuity": {
            "L": Lf, "R": Rf, "T": Tf, "B": Bf
        }
    }
    lines.append(f"SONUÇ: X: {ch_x_duz.label()} duz + {ch_x_pilye.label()} pilye | Y: {ch_y_duz.label()} duz + {ch_y_pilye.label()} pilye")
    for edge, ch in choices_il.items():
        if ch:
            lines.append(f"       Ek ({edge}): {ch.label()}")
    lines.append("")
    
    return design_res, lines
