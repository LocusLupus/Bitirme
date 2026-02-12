"""
Tek Doğrultulu Döşeme Hesabı Modülü
===================================
Bu modül tek doğrultulu (one-way) döşemelerin moment hesabı ve donatı tasarımını içerir.
"""

from typing import Dict, Tuple, List, Optional
from struct_design import (
    one_span_coeff_by_fixity, one_way_coefficients,
    oneway_smax_main, oneway_smax_dist, rho_min_oneway,
    split_duz_pilye, select_rebar_min_area, RebarChoice
)


def build_oneway_chain(system, sid: str, direction: str) -> List[str]:
    """
    Verilen döşemeden başlayarak UZUN KENARLARINDAN sürekli tek doğrultulu döşeme zincirini oluşturur.
    
    Tek doğrultuda çalışan döşemelerde:
    - Yük KISA KENAR yönünde taşınır
    - UZUN KENARLAR birbirine bitişikse → çok açıklıklı sürekli sistem oluşur
    - KISA KENARLAR birbirine bitişikse → tek açıklıklı olarak değerlendirilir
    
    Args:
        system: SlabSystem nesnesi
        sid: Başlangıç döşeme ID'si
        direction: Taşıma doğrultusu ("X" veya "Y") - kısa kenar yönü
    
    Returns:
        Zincirdeki döşeme ID'lerinin sıralı listesi (uzun kenarlarından bitişik olanlar)
    """
    direction = direction.upper()
    if system.slabs[sid].kind != "ONEWAY":
        return [sid]

    # Uzun kenar yönü = taşıma doğrultusunun TERSİ
    # Örnek: taşıma X yönünde ise, uzun kenar Y yönüne paralel
    # Bu durumda komşuları Y yönünde aramalıyız (uzun kenar boyunca)
    long_edge_direction = "Y" if direction == "X" else "X"
    
    stack = [sid]
    seen = {sid}
    chain = []
    while stack:
        u = stack.pop()
        if system.slabs[u].kind != "ONEWAY":
            continue
        chain.append(u)
        # Uzun kenar yönündeki komşuları bul (START ve END taraflarında)
        for side in ("START", "END"):
            for nb in system.neighbor_slabs_on_side(u, long_edge_direction, side):
                if nb in seen:
                    continue
                seen.add(nb)
                if nb in system.slabs and system.slabs[nb].kind == "ONEWAY":
                    stack.append(nb)

    # Uzun kenar yönüne göre sırala
    if long_edge_direction == "X":
        chain.sort(key=lambda x: system.slabs[x].i0)
    else:
        chain.sort(key=lambda x: system.slabs[x].j0)
    return chain


def chain_panel_boundary_supports(system, chain: List[str], direction: str) -> List[int]:
    """
    Zincirdeki panel sınırlarındaki mesnet gridline'larını bulur.
    
    Args:
        direction: Taşıma doğrultusu (kısa kenar yönü)
    
    Returns:
        Uzun kenar yönündeki mesnet gridline'ları
    """
    direction = direction.upper()
    # Uzun kenar yönü = taşıma yönünün tersi
    long_edge_direction = "Y" if direction == "X" else "X"
    
    if len(chain) < 2:
        return []
    supports = []
    for a, b in zip(chain[:-1], chain[1:]):
        sa, sb = system.slabs[a], system.slabs[b]
        if long_edge_direction == "X":
            g = sa.i1 + 1
            if sb.i0 == g:
                supports.append(g)
        else:
            g = sa.j1 + 1
            if sb.j0 == g:
                supports.append(g)
    return supports


def chain_end_fixity(system, chain: List[str], direction: str) -> Tuple[Tuple[bool, bool], Tuple[bool, bool]]:
    """
    Zincirin başlangıç ve bitiş uçlarının ankastre/sürekli durumunu belirler.
    
    ONEWAY döşemelerde mesnetlenme koşulu UZUN KENAR komşularına göre belirlenir:
    - Uzun kenarda TWOWAY komşu varsa → Ankastre (fixed=True)
    - Uzun kenarda ONEWAY komşu varsa → Sürekli (continuous=True, fixed=False)
    - Uzun kenarda komşu yoksa → Serbest (fixed=False, continuous=False)
    
    Returns:
        ((fixed_start, fixed_end), (continuous_start, continuous_end))
        - fixed: Ankastre mi (TWOWAY komşu)
        - continuous: Sürekli mi (ONEWAY komşu)
    """
    direction = direction.upper()
    first, last = chain[0], chain[-1]
    
    # Uzun kenar yönü (taşıma doğrultusunun tersi)
    perp_direction = "Y" if direction == "X" else "X"
    
    # Uzun kenar komşularını bul
    start_neigh = system.neighbor_slabs_on_side(first, perp_direction, "START")
    end_neigh = system.neighbor_slabs_on_side(last, perp_direction, "END")
    
    # Başlangıç ucu için kontrol
    fixed_start = False
    continuous_start = False
    for nb in start_neigh:
        if nb in system.slabs:
            if system.slabs[nb].kind == "TWOWAY":
                fixed_start = True  # Ankastre
                break
            elif system.slabs[nb].kind in ("ONEWAY", "BALCONY"):
                continuous_start = True  # Sürekli (sabit mesnet)
    
    # Bitiş ucu için kontrol
    fixed_end = False
    continuous_end = False
    for nb in end_neigh:
        if nb in system.slabs:
            if system.slabs[nb].kind == "TWOWAY":
                fixed_end = True  # Ankastre
                break
            elif system.slabs[nb].kind in ("ONEWAY", "BALCONY"):
                continuous_end = True  # Sürekli (sabit mesnet)
    
    return (fixed_start, fixed_end), (continuous_start, continuous_end)


def owner_slab_for_segment(system, chain: List[str], direction: str, g_mid: float) -> str:
    """
    Belirli bir segment için sahip döşemeyi bulur.
    
    NOT: Mesnet gridline'ları UZUN KENAR yönünde olduğu için,
    koordinat kontrolü de uzun kenar yönünde yapılmalı.
    - direction = "X" (kısa kenar) ise uzun kenar = "Y" → j0/j1 kontrol
    - direction = "Y" (kısa kenar) ise uzun kenar = "X" → i0/i1 kontrol
    """
    direction = direction.upper()
    for sid in chain:
        s = system.slabs[sid]
        # Uzun kenar yönündeki koordinatları kontrol et (direction'ın TERSİ)
        if direction == "X":
            # Uzun kenar Y yönünde → j gridline'larını kontrol et
            if s.j0 <= g_mid <= (s.j1 + 1):
                return sid
        else:
            # Uzun kenar X yönünde → i gridline'larını kontrol et
            if s.i0 <= g_mid <= (s.i1 + 1):
                return sid
    return chain[0]


def compute_oneway_per_slab(system, sid: str, bw_val: float) -> Tuple[dict, List[str]]:
    """
    Tek doğrultulu döşeme için moment hesabı yapar.
    
    Args:
        system: SlabSystem nesnesi
        sid: Döşeme ID'si
        bw_val: Kiriş genişliği (m)
    
    Returns:
        (sonuç_dict, hesap_adımları_listesi)
    """
    steps = []
    s0 = system.slabs[sid]
    w = s0.pd * s0.b
    steps.append(f"w = pd*b = {s0.pd:.3f}*{s0.b:.3f} = {w:.3f} kN/m")

    Lx_g, Ly_g = s0.size_m_gross()
    direction = "Y" if Lx_g < Ly_g else "X"
    steps.append(f"Otomatik açıklık yönü: Lx={Lx_g:.3f}, Ly={Ly_g:.3f} -> yön={direction}")

    chain = build_oneway_chain(system, sid, direction)
    steps.append(f"Zincir: {chain}")

    (fixed_start, fixed_end), (continuous_start, continuous_end) = chain_end_fixity(system, chain, direction)
    steps.append(f"Uzun kenar mesnet durumu:")
    steps.append(f"  START: {'Ankastre (TWOWAY komşu)' if fixed_start else ('Sürekli (ONEWAY/BALCONY komşu)' if continuous_start else 'Serbest')}")
    steps.append(f"  END: {'Ankastre (TWOWAY komşu)' if fixed_end else ('Sürekli (ONEWAY/BALCONY komşu)' if continuous_end else 'Serbest')}")

    # Uzun kenar yönü = taşıma doğrultusunun tersi
    long_edge_direction = "Y" if direction == "X" else "X"
    
    # Mesnet gridline'larını uzun kenar yönünde bul
    if long_edge_direction == "X":
        start_g = min(system.slabs[x].i0 for x in chain)
        end_g = max(system.slabs[x].i1 + 1 for x in chain)
    else:
        start_g = min(system.slabs[x].j0 for x in chain)
        end_g = max(system.slabs[x].j1 + 1 for x in chain)

    supports = [start_g, end_g]
    supports.extend(chain_panel_boundary_supports(system, chain, direction))
    for x in chain:
        supports.extend(system.slab_support_gridlines_from_drawn_beams(x, long_edge_direction))
    supports = sorted(set(supports))
    steps.append(f"Mesnet gridline listesi (uzun kenar yönünde): {supports}")

    spans = []
    for a, b_g in zip(supports[:-1], supports[1:]):
        mid_g = 0.5 * (a + b_g)
        owner = owner_slab_for_segment(system, chain, direction, mid_g)
        s_owner = system.slabs[owner]
        # Kısa açıklık uzunluğunu kullan (taşıma doğrultusu)
        Lx_owner, Ly_owner = s_owner.size_m_gross()
        L_short = min(Lx_owner, Ly_owner)
        left_is_beam = system.is_beam_gridline_for_slab(owner, direction, a)
        right_is_beam = system.is_beam_gridline_for_slab(owner, direction, b_g)
        Lnet = system.net_span(L_short, left_is_beam, right_is_beam, bw_val)
        spans.append((L_short, owner, Lnet))
        steps.append(f"Span [{a}->{b_g}] owner={owner}: L_short={L_short:.3f} (hesapta kullanılan), Lnet={Lnet:.3f}")

    n_spans = len(spans)
    steps.append(f"Toplam span: {n_spans}")

    if n_spans == 1:
        # Tek açıklık için: fixed veya (fixed olmasa bile continuous) ise ankastre gibi davran
        # Aslında: fixed = ankastre katsayıları, continuous = sürekli katsayıları (farklı)
        # Şimdilik: fixed veya continuous ise ankastre katsayısı kullanalım
        effective_fixed_start = fixed_start or continuous_start
        effective_fixed_end = fixed_end or continuous_end
        (c_start, c_end), c_pos = one_span_coeff_by_fixity(effective_fixed_start, effective_fixed_end)
        L = spans[0][0]
        Mpos = c_pos * w * L**2
        Mneg_start = c_start * w * L**2
        Mneg_end = c_end * w * L**2
        steps.append(f"M+ = {Mpos:.3f}, M-start={Mneg_start:.3f}, M-end={Mneg_end:.3f}")
        return {
            "auto_dir": direction, "chain": chain,
            "fixed_start": fixed_start, "fixed_end": fixed_end,
            "continuous_start": continuous_start, "continuous_end": continuous_end,
            "w": w, "Mpos_max": Mpos, "Mneg_min": min(Mneg_start, Mneg_end)
        }, steps

    support_c, span_c = one_way_coefficients(n_spans)
    Ls = [L for (L, *_rest) in spans]
    owners = [o for (_L, o, *_rest) in spans]

    # Önce tüm momentleri hesapla (raporlamadan)
    span_Mpos = []
    for i in range(n_spans):
        M = span_c[i] * w * (Ls[i] ** 2)
        span_Mpos.append(M)

    support_Mneg = []
    for i in range(n_spans + 1):
        if i == 0:
            L2 = Ls[0] ** 2
        elif i == n_spans:
            L2 = Ls[-1] ** 2
        else:
            L2 = 0.5 * (Ls[i-1] ** 2 + Ls[i] ** 2)
        M = support_c[i] * w * L2
        support_Mneg.append(M)

    # Bu döşemeye ait span'ları bul
    owned_span_idx = [i for i, o in enumerate(owners) if o == sid]
    Mpos_max = max(span_Mpos[i] for i in owned_span_idx) if owned_span_idx else None

    # Bu döşemeye temas eden mesnetleri bul
    touching = set()
    for i in owned_span_idx:
        touching.add(i)
        touching.add(i+1)
    Mneg_min = min(support_Mneg[i] for i in touching) if touching else None
    
    # Sadece bu döşemenin kullandığı momentleri raporla
    steps.append(f"Bu döşemeye ({sid}) ait momentler:")
    for i in owned_span_idx:
        steps.append(f"  Açıklık M+ = {span_Mpos[i]:.3f} kNm/m (katsayı: 1/{1/span_c[i]:.0f})")
    for i in sorted(touching):
        steps.append(f"  Mesnet{i} M- = {support_Mneg[i]:.3f} kNm/m (katsayı: 1/{abs(1/support_c[i]):.0f})")

    return {
        "auto_dir": direction, "chain": chain,
        "w": w, "Mpos_max": Mpos_max, "Mneg_min": Mneg_min
    }, steps


def compute_oneway_report(system, sid: str, res: dict, conc: str, steel: str, 
                          h: float, cover: float, bw: float,
                          neighbor_pilye_areas: Optional[Dict[str, float]] = None) -> Tuple[dict, List[str]]:
    """
    Tek doğrultulu döşeme için donatı hesabı ve raporlama yapar.
    
    Args:
        system: SlabSystem nesnesi
        sid: Döşeme ID'si
        res: compute_oneway_per_slab sonucu
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
    
    Mpos = res["Mpos_max"] or 0.0
    Mneg = res["Mneg_min"] or 0.0
    smax = oneway_smax_main(h)
    d_mm = h - cover  # efektif derinlik
    
    # Kenar süreklilik analizi - TÜM 4 KENAR BAĞIMSIZ KONTROL
    chain = res.get("chain", [sid])
    auto_dir = res.get("auto_dir", "X")
    
    # Tüm kenarların komşuluk durumunu al
    (Lf, Rf, Tf, Bf), (La, Ra, Ta, Ba), _ = system.twoway_edge_continuity_full(sid)
    
    # Her kenardaki süreklilik durumu (komşu döşeme var mı?)
    kenar_L_surekli = Lf or La
    kenar_R_surekli = Rf or Ra
    kenar_T_surekli = Tf or Ta
    kenar_B_surekli = Bf or Ba
    
    lines.append("\n  Kenar Süreklilik Durumu:")
    lines.append(f"    Sol (L): {'Sürekli' if kenar_L_surekli else 'Süreksiz'}")
    lines.append(f"    Sağ (R): {'Sürekli' if kenar_R_surekli else 'Süreksiz'}")
    lines.append(f"    Üst (T): {'Sürekli' if kenar_T_surekli else 'Süreksiz'}")
    lines.append(f"    Alt (B): {'Sürekli' if kenar_B_surekli else 'Süreksiz'}")
    
    # Ana donatı doğrultusuna göre kenar sınıflandırması
    if auto_dir == "X":
        kisa_kenar_start_surekli = kenar_L_surekli
        kisa_kenar_end_surekli = kenar_R_surekli
        uzun_kenar_start_surekli = kenar_T_surekli
        uzun_kenar_end_surekli = kenar_B_surekli
    else:
        kisa_kenar_start_surekli = kenar_T_surekli
        kisa_kenar_end_surekli = kenar_B_surekli
        uzun_kenar_start_surekli = kenar_L_surekli
        uzun_kenar_end_surekli = kenar_R_surekli
    
    # Doğrultu belirleme
    # X yönü: Lx < Ly -> kısa kenar Y eksenine paralel, uzun kenar X eksenine paralel
    # Y yönü: Ly < Lx -> kısa kenar X eksenine paralel, uzun kenar Y eksenine paralel
    if auto_dir == "X":
        kisa_kenar_dogrultusu = "Y ekseni (dik)"
        uzun_kenar_dogrultusu = "X ekseni (yatay)"
    else:
        kisa_kenar_dogrultusu = "X ekseni (yatay)"
        uzun_kenar_dogrultusu = "Y ekseni (dik)"
    
    lines.append(f"\n  Doğrultu Bilgisi: Kısa kenar = {kisa_kenar_dogrultusu}, Uzun kenar = {uzun_kenar_dogrultusu}")
    
    # --- 1. ANA DONATI ---
    # Ana donatı kısa kenara paralel atılır
    lines.append("\n  === 1. ANA DONATI ===")
    lines.append(f"    (Doğrultu: Kısa kenara paralel -> {kisa_kenar_dogrultusu})")
    As_main, ch_main, st_main = system.design_main_rebar_from_M(
        Mpos, conc, steel, h, cover, smax, label_prefix="    ")
    lines.extend(st_main)
    
    duz, pilye = split_duz_pilye(ch_main)
    # Düz donatı boyu hesabı: Lnet + 2*bw (giriş) + 2*bw (kanca) = Lnet + 4*bw
    # Lnet bilgisi 'res' içinde yok, ama spans listesinde var. Ancak burada 'Mpos' üzerinden geldik.
    # Yaklaşık olarak temiz açıklık + mesnet genişlikleri diyebiliriz ama
    # en temizi: Kullanıcıya bilgi olarak "L + 4x bw" (her uçta bw kadar giriş + bw kadar kanca)
    # Not: bw metre cinsinden
    L_hook_add = 4.0 * bw * 1000.0 # mm cinsinden ek boy
    lines.append(f"    Ana Donatı: {ch_main.label_with_area()}")
    lines.append(f"    -> Düz: {duz.label()} (L_net + {L_hook_add:.0f} mm kanca payı)")
    lines.append(f"       (Detay: Her iki uçta kiriş içine bw={bw*100:.0f}cm giriş + bw={bw*100:.0f}cm aşağı kanca)")
    lines.append(f"    -> Pilye: {pilye.label()} (A={pilye.area_mm2_per_m:.1f} mm²/m)")
    
    # Mesnet momenti için As hesabı (mesnet ek donatısı için kullanılacak)
    As_mesnet_calc, ch_mesnet_from_M, st_mesnet_calc = system.design_main_rebar_from_M(
        abs(Mneg), conc, steel, h, cover, smax, label_prefix="    ")
    lines.append(f"\n    Mesnet Momenti için As = {As_mesnet_calc:.1f} mm²/m (M- = {abs(Mneg):.3f} kNm/m için)")
    
    # --- 2. DAĞITMA DONATISI ---
    # Dağıtma donatısı uzun kenara paralel atılır
    lines.append("\n  === 2. DAĞITMA DONATISI ===")
    lines.append(f"    (Doğrultu: Uzun kenara paralel -> {uzun_kenar_dogrultusu})")
    As_dist_req = ch_main.area_mm2_per_m / 5.0
    lines.append(f"    As_dağıtma = As_ana / 5 = {ch_main.area_mm2_per_m:.1f} / 5 = {As_dist_req:.1f} mm²/m")
    ch_dist = select_rebar_min_area(As_dist_req, oneway_smax_dist(), phi_min=8)
    if ch_dist:
        lines.append(f"    Seçim: {ch_dist.label_with_area()}")
    else:
        lines.append("    HATA: Dağıtma donatısı seçilemedi!")
    
    # Minimum donatı hesabı
    rho_min = rho_min_oneway(steel)
    As_min = rho_min * 1000.0 * d_mm
    
    # --- 3. SÜREKSİZ KISA KENAR: BOYUNA KENAR MESNET DONATISI ---
    # Boyuna kenar mesnet donatısı uzun kenara paralel atılır
    ch_kenar_start = None
    ch_kenar_end = None
    
    lines.append("\n  === 3. SÜREKSİZ KISA KENAR: BOYUNA KENAR MESNET DONATISI ===")
    lines.append(f"    (Doğrultu: Uzun kenara paralel -> {uzun_kenar_dogrultusu})")
    lines.append(f"    ρ_min = {rho_min:.4f}, As_min = {As_min:.1f} mm²/m")
    
    if not kisa_kenar_start_surekli:
        lines.append("    Kısa kenar START süreksiz -> Boyuna kenar donatısı gerekli")
        ch_kenar_start = select_rebar_min_area(As_min, smax, phi_min=8)
        if ch_kenar_start:
            lines.append(f"    Seçim (START): {ch_kenar_start.label_with_area()}")
    else:
        lines.append("    Kısa kenar START sürekli -> Boyuna kenar donatısı gerekmiyor")
    
    if not kisa_kenar_end_surekli:
        lines.append("    Kısa kenar END süreksiz -> Boyuna kenar donatısı gerekli")
        ch_kenar_end = select_rebar_min_area(As_min, smax, phi_min=8)
        if ch_kenar_end:
            lines.append(f"    Seçim (END): {ch_kenar_end.label_with_area()}")
    else:
        lines.append("    Kısa kenar END sürekli -> Boyuna kenar donatısı gerekmiyor")
    
    # --- 4. SÜREKLİ KISA KENAR: BOYUNA İÇ MESNET DONATISI ---
    # Boyuna iç mesnet donatısı uzun kenara paralel atılır
    ch_ic_mesnet_start = None
    ch_ic_mesnet_end = None
    
    lines.append("\n  === 4. SÜREKLİ KISA KENAR: BOYUNA İÇ MESNET DONATISI ===")
    lines.append(f"    (Doğrultu: Uzun kenara paralel -> {uzun_kenar_dogrultusu})")
    As_ic_mesnet = ch_main.area_mm2_per_m * 0.6
    lines.append(f"    As_iç_mesnet = As_ana × 0.6 = {ch_main.area_mm2_per_m:.1f} × 0.6 = {As_ic_mesnet:.1f} mm²/m")
    
    if kisa_kenar_start_surekli:
        lines.append("    Kısa kenar START sürekli -> Boyuna iç mesnet donatısı gerekli")
        ch_ic_mesnet_start = select_rebar_min_area(As_ic_mesnet, smax, phi_min=8)
        if ch_ic_mesnet_start:
            lines.append(f"    Seçim (START): {ch_ic_mesnet_start.label_with_area()}")
    else:
        lines.append("    Kısa kenar START süreksiz -> İç mesnet donatısı gerekmiyor")
    
    if kisa_kenar_end_surekli:
        lines.append("    Kısa kenar END sürekli -> Boyuna iç mesnet donatısı gerekli")
        ch_ic_mesnet_end = select_rebar_min_area(As_ic_mesnet, smax, phi_min=8)
        if ch_ic_mesnet_end:
            lines.append(f"    Seçim (END): {ch_ic_mesnet_end.label_with_area()}")
    else:
        lines.append("    Kısa kenar END süreksiz -> İç mesnet donatısı gerekmiyor")
    
    # --- 5. SÜREKLİ UZUN KENAR: MESNET EK DONATISI (İLAVE MESNET DONATISI) ---
    # İlave mesnet donatısı kısa kenara paralel atılır
    ch_mesnet_ek_start = None
    ch_mesnet_ek_end = None
    
    lines.append("\n  === 5. SÜREKLİ UZUN KENAR: MESNET EK DONATISI (İLAVE) ===")
    lines.append(f"    (Doğrultu: Kısa kenara paralel -> {kisa_kenar_dogrultusu})")
    As_mesnet_req = As_mesnet_calc  # Mesnet momenti için hesaplanan As kullan
    As_pilye_bu_doseme = pilye.area_mm2_per_m
    
    # Komşu döşemelerin pilye alanlarını bul (uzun kenar komşuları)
    # auto_dir = X ise uzun kenar T/B (Top/Bottom), auto_dir = Y ise uzun kenar L/R (Left/Right)
    if auto_dir == "X":
        # Uzun kenar T ve B kenarı, komşuları direction Y, START ve END
        komsular_uzun_start = system.neighbor_slabs_on_side(sid, "Y", "START")  # T kenarındaki komşular
        komsular_uzun_end = system.neighbor_slabs_on_side(sid, "Y", "END")      # B kenarındaki komşular
    else:
        # Uzun kenar L ve R kenarı, komşuları direction X, START ve END
        komsular_uzun_start = system.neighbor_slabs_on_side(sid, "X", "START")  # L kenarındaki komşular
        komsular_uzun_end = system.neighbor_slabs_on_side(sid, "X", "END")      # R kenarındaki komşular
    
    lines.append(f"    As_mesnet (hesaplanan) = {As_mesnet_req:.1f} mm²/m (M- = {abs(Mneg):.3f} kNm/m)")
    lines.append(f"    As_pilye (bu döşeme) = {As_pilye_bu_doseme:.1f} mm²/m")
    
    if uzun_kenar_start_surekli:
        lines.append("    Uzun kenar START sürekli -> Mesnet ek donatısı kontrolü")
        # START tarafındaki komşu döşemenin pilye alanını al
        As_pilye_komsu_start = 0.0
        for komsu_sid in komsular_uzun_start:
            if neighbor_pilye_areas and komsu_sid in neighbor_pilye_areas:
                As_pilye_komsu_start = neighbor_pilye_areas[komsu_sid]
                lines.append(f"    Komşu {komsu_sid} pilye alanı: {As_pilye_komsu_start:.1f} mm²/m")
                break
            else:
                lines.append(f"    Komşu {komsu_sid} pilye bilgisi yok, 0 kabul edildi")
        
        As_pilye_toplam_start = As_pilye_bu_doseme + As_pilye_komsu_start
        As_ek_req_start = max(0, As_mesnet_req - As_pilye_toplam_start)
        lines.append(f"    As_pilye (toplam: bu + komşu) = {As_pilye_bu_doseme:.1f} + {As_pilye_komsu_start:.1f} = {As_pilye_toplam_start:.1f} mm²/m")
        lines.append(f"    As_ek = max(0, {As_mesnet_req:.1f} - {As_pilye_toplam_start:.1f}) = {As_ek_req_start:.1f} mm²/m")
        
        if As_ek_req_start > 1e-6:
            ch_mesnet_ek_start = select_rebar_min_area(As_ek_req_start, smax, phi_min=8)
            if ch_mesnet_ek_start:
                lines.append(f"    Seçim (START): {ch_mesnet_ek_start.label_with_area()}")
        else:
            lines.append("    Pilye yeterli, ek donatı gerekmiyor (START)")
    else:
        lines.append("    Uzun kenar START süreksiz -> Mesnet ek donatısı gerekmiyor")
    
    if uzun_kenar_end_surekli:
        lines.append("    Uzun kenar END sürekli -> Mesnet ek donatısı kontrolü")
        # END tarafındaki komşu döşemenin pilye alanını al
        As_pilye_komsu_end = 0.0
        for komsu_sid in komsular_uzun_end:
            if neighbor_pilye_areas and komsu_sid in neighbor_pilye_areas:
                As_pilye_komsu_end = neighbor_pilye_areas[komsu_sid]
                lines.append(f"    Komşu {komsu_sid} pilye alanı: {As_pilye_komsu_end:.1f} mm²/m")
                break
            else:
                lines.append(f"    Komşu {komsu_sid} pilye bilgisi yok, 0 kabul edildi")
        
        As_pilye_toplam_end = As_pilye_bu_doseme + As_pilye_komsu_end
        As_ek_req_end = max(0, As_mesnet_req - As_pilye_toplam_end)
        lines.append(f"    As_pilye (toplam: bu + komşu) = {As_pilye_bu_doseme:.1f} + {As_pilye_komsu_end:.1f} = {As_pilye_toplam_end:.1f} mm²/m")
        lines.append(f"    As_ek = max(0, {As_mesnet_req:.1f} - {As_pilye_toplam_end:.1f}) = {As_ek_req_end:.1f} mm²/m")
        
        if As_ek_req_end > 1e-6:
            ch_mesnet_ek_end = select_rebar_min_area(As_ek_req_end, smax, phi_min=8)
            if ch_mesnet_ek_end:
                lines.append(f"    Seçim (END): {ch_mesnet_ek_end.label_with_area()}")
        else:
            lines.append("    Pilye yeterli, ek donatı gerekmiyor (END)")
    else:
        lines.append("    Uzun kenar END süreksiz -> Mesnet ek donatısı gerekmiyor")
    
    # --- ÖZET ---
    lines.append("\n  === ÖZET ===")
    lines.append(f"    Ana (Düz): {duz.label()}")
    lines.append(f"    Ana (Pilye): {pilye.label()}")
    lines.append(f"    Dağıtma: {ch_dist.label() if ch_dist else '-'}")
    lines.append(f"    Boyuna Kenar Mesnet (süreksiz kısa): START={ch_kenar_start.label() if ch_kenar_start else '-'}, END={ch_kenar_end.label() if ch_kenar_end else '-'}")
    lines.append(f"    Boyuna İç Mesnet (sürekli kısa): START={ch_ic_mesnet_start.label() if ch_ic_mesnet_start else '-'}, END={ch_ic_mesnet_end.label() if ch_ic_mesnet_end else '-'}")
    lines.append(f"    Mesnet Ek (sürekli uzun): START={ch_mesnet_ek_start.label() if ch_mesnet_ek_start else '-'}, END={ch_mesnet_ek_end.label() if ch_mesnet_ek_end else '-'}")
    lines.append("")
    
    design_res = {
        "kind": "ONEWAY", "auto_dir": res.get("auto_dir"), "cover_mm": cover,
        "choices": {
            "main": ch_main, 
            "duz": duz,
            "pilye": pilye,
            "dist": ch_dist, 
            "kenar_mesnet_start": ch_kenar_start,
            "kenar_mesnet_end": ch_kenar_end,
            "ic_mesnet_start": ch_ic_mesnet_start,
            "ic_mesnet_end": ch_ic_mesnet_end,
            "mesnet_ek_start": ch_mesnet_ek_start,
            "mesnet_ek_end": ch_mesnet_ek_end
        },
        "edge_continuity": {
            "uzun_start": uzun_kenar_start_surekli,
            "uzun_end": uzun_kenar_end_surekli,
            "kisa_start": kisa_kenar_start_surekli,
            "kisa_end": kisa_kenar_end_surekli
        },
        "dogrultular": {
            "ana_donati": kisa_kenar_dogrultusu,           # kısa kenara paralel
            "dagitma": uzun_kenar_dogrultusu,              # uzun kenara paralel
            "boyuna_kenar_mesnet": uzun_kenar_dogrultusu,  # uzun kenara paralel
            "boyuna_ic_mesnet": uzun_kenar_dogrultusu,     # uzun kenara paralel
            "ilave_mesnet": kisa_kenar_dogrultusu          # kısa kenara paralel
        }
    }
    
    return design_res, lines
