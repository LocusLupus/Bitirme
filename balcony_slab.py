"""
Balkon Döşeme Hesabı Modülü
===========================
Bu modül balkon döşemelerinin moment hesabı ve donatı tasarımını içerir.
////
"""

from typing import Dict, Tuple, List, Optional
from struct_design import (
    oneway_smax_main, oneway_smax_dist,
    select_rebar_min_area, RebarChoice
)


def balcony_fixed_edge_guess(system, sid: str) -> Tuple[str, List[str]]:
    """
    Balkon döşemesi için ankastre (sabit) kenarı tahmin eder.
    En yüksek komşuluk oranına sahip kenar seçilir.
    """
    steps = []
    ratios = {}
    for e in ["L", "R", "T", "B"]:
        _full, any_, ratio = system.edge_neighbor_coverage(sid, e)
        ratios[e] = ratio if any_ else 0.0
        steps.append(f"{e} ratio: {ratios[e]:.3f}")
    fixed = max(ratios.items(), key=lambda kv: kv[1])[0]
    steps.append(f"Selected fixed edge: {fixed}")
    return fixed, steps


def neighbor_support_moment_for_edge(system, neighbor_id: str, edge: str, bw: float) -> float:
    """
    Komşu döşemenin belirli bir kenardaki mesnet momentini hesaplar.
    """
    if neighbor_id not in system.slabs:
        return 0.0
    k = system.slabs[neighbor_id].kind
    
    # Döngüsel import'u önlemek için yerel import
    if k == "TWOWAY":
        from twoway_slab import compute_twoway_per_slab
        r, _ = compute_twoway_per_slab(system, neighbor_id, bw)
        mxn, _ = r["Mx"]
        myn, _ = r["My"]
        if edge in ("L", "R"):
            return abs(mxn) if mxn else 0.0
        else:
            return abs(myn) if myn else 0.0
    if k == "ONEWAY":
        from oneway_slab import compute_oneway_per_slab
        r, _ = compute_oneway_per_slab(system, neighbor_id, bw)
        return abs(r["Mneg_min"]) if r.get("Mneg_min") is not None else 0.0
    if k == "BALCONY":
        r, _ = compute_balcony_per_slab(system, neighbor_id, bw)
        return abs(r["Mneg"]) if r.get("Mneg") is not None else 0.0
    return 0.0


def compute_balcony_per_slab(system, sid: str, bw: float) -> Tuple[dict, List[str]]:
    """
    Balkon döşemesi için moment hesabı yapar.
    
    Args:
        system: SlabSystem nesnesi
        sid: Döşeme ID'si
        bw: Kiriş genişliği (m)
    
    Returns:
        (sonuç_dict, hesap_adımları_listesi)
    """
    steps = []
    s = system.slabs[sid]
    w = s.pd * s.b
    Lx_g, Ly_g = s.size_m_gross()
    direction = "Y" if Lx_g < Ly_g else "X"
    Lg = min(Lx_g, Ly_g)
    Lnet = max(0.05, Lg - 0.5 * bw)
    
    steps.append(f"w={w:.3f}")
    steps.append(f"Lg={Lg:.3f}, Lnet={Lnet:.3f}")
    Mneg = 0.5 * w * Lnet**2
    steps.append(f"M- = {Mneg:.3f}")
    return {"dir": direction, "w": w, "L_net": Lnet, "Mneg": Mneg}, steps


def get_balcony_design_moment(system, sid: str, Mbal: float, bw: float) -> Tuple[float, List[str]]:
    """
    Balkon döşemesi için tasarım momentini hesaplar.
    Komşu döşemelerin mesnet momentleri de dikkate alınır.
    """
    steps = []
    fixed_edge, st = balcony_fixed_edge_guess(system, sid)
    steps.extend(st)
    
    s = system.slabs[sid]
    i0, j0, i1, j1 = s.bbox()
    neigh = set()
    
    # Sabit kenardaki komşuları bul
    if fixed_edge == "L" and i0 > 0:
        for j in range(j0, j1 + 1):
            nb = system.cell_owner.get((i0 - 1, j))
            if nb and nb != sid:
                neigh.add(nb)
    elif fixed_edge == "R" and i1 < system.Nx - 1:
        for j in range(j0, j1 + 1):
            nb = system.cell_owner.get((i1 + 1, j))
            if nb and nb != sid:
                neigh.add(nb)
    elif fixed_edge == "T" and j0 > 0:
        for i in range(i0, i1 + 1):
            nb = system.cell_owner.get((i, j0 - 1))
            if nb and nb != sid:
                neigh.add(nb)
    elif fixed_edge == "B" and j1 < system.Ny - 1:
        for i in range(i0, i1 + 1):
            nb = system.cell_owner.get((i, j1 + 1))
            if nb and nb != sid:
                neigh.add(nb)

    if not neigh:
        steps.append("No neighbor on fixed edge.")
        return abs(Mbal), steps

    m_nb = 0.0
    for nb in neigh:
        mn = neighbor_support_moment_for_edge(system, nb, fixed_edge, bw)
        steps.append(f"Neighbor {nb} M={mn:.3f}")
        m_nb = max(m_nb, mn)
    
    Mdesign = max(abs(Mbal), m_nb)
    steps.append(f"M_design = max(|Mbal|={abs(Mbal):.3f}, neighbor_max={m_nb:.3f}) = {Mdesign:.3f}")
    return Mdesign, steps


def compute_balcony_report(system, sid: str, res: dict, conc: str, steel: str,
                           h: float, cover: float, bw: float) -> Tuple[dict, List[str]]:
    """
    Balkon döşemesi için donatı hesabı ve raporlama yapar.
    
    Args:
        system: SlabSystem nesnesi
        sid: Döşeme ID'si
        res: compute_balcony_per_slab sonucu
        conc: Beton sınıfı
        steel: Çelik sınıfı
        h: Döşeme kalınlığı (mm)
        cover: Pas payı (mm)
        bw: Kiriş genişliği (m)
    
    Returns:
        (tasarım_sonucu_dict, rapor_satırları_listesi)
    """
    lines = []
    
    Mdes, std = get_balcony_design_moment(system, sid, res["Mneg"], bw)
    lines.extend(std)
    
    lines.append(f"--- Ana Donatı Hesabı ---")
    asb, ch_main, steps_main = system.design_main_rebar_from_M(Mdes, conc, steel, h, cover, oneway_smax_main(h), label_prefix="  ")
    for step in steps_main:
        lines.append(f"  {step}")
    lines.append(f"  As_gerekli = {asb:.1f} mm²/m")
    lines.append(f"  Seçilen: {ch_main.label()} (As_prov = {ch_main.area_mm2_per_m:.1f} mm²/m)")
    lines.append("")
    
    # Dağıtma donatısı (ana donatının 1/5'i)
    asd = ch_main.area_mm2_per_m / 5.0
    ch_dist = select_rebar_min_area(asd, oneway_smax_dist(), phi_min=8)
    lines.append(f"--- Dağıtma Donatısı ---")
    lines.append(f"  As_dist = As_main / 5 = {ch_main.area_mm2_per_m:.1f} / 5 = {asd:.1f} mm²/m")
    if ch_dist:
        lines.append(f"  Seçilen: {ch_dist.label()} (As_prov = {ch_dist.area_mm2_per_m:.1f} mm²/m)")
    else:
        lines.append(f"  HATA: Dağıtma donatısı seçilemedi!")
    lines.append("")
    
    fixed, _ = balcony_fixed_edge_guess(system, sid)
    
    design_res = {
        "kind": "BALCONY", "cover_mm": cover, "fixed_edge": fixed,
        "choices": {"main": ch_main, "dist": ch_dist}
    }
    lines.append(f"SONUÇ: Ana: {ch_main.label()}, Dağıtma: {ch_dist.label() if ch_dist else '-'}")
    lines.append("")
    
    return design_res, lines

