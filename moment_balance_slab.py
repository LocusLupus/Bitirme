"""
Mesnet Moment Dengelemesi Modülü
================================
Bu modül TS500'e göre komşu döşemeler arasında mesnet moment dengelemesi yapar.
TWOWAY-TWOWAY ve TWOWAY-ONEWAY arası dengeleme desteklenir.
"""

from typing import Dict, Tuple, List, Optional


def get_neighbor_on_edge(system, sid: str, edge: str) -> Tuple[Optional[str], Optional[str]]:
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
    
    # Kenar komşularını bul
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


def get_opposite_edge(edge: str) -> str:
    """Karşı kenarı döndürür."""
    opposite = {"L": "R", "R": "L", "T": "B", "B": "T"}
    return opposite.get(edge.upper(), edge)


def get_moment_for_edge(res: dict, edge: str) -> Optional[float]:
    """
    Döşeme sonuç dict'inden belirli bir kenarın mesnet momentini döndürür.
    
    Mx = X doğrultusundaki moment (L/R kenarları için)
    My = Y doğrultusundaki moment (T/B kenarları için)
    """
    edge = edge.upper()
    mxn, mxp = res.get("Mx", (None, None))
    myn, myp = res.get("My", (None, None))
    
    # L ve R kenarları X doğrultusunda, T ve B kenarları Y doğrultusunda
    if edge in ("L", "R"):
        return mxn  # X negatif (mesnet) momenti
    else:  # T, B
        return myn  # Y negatif (mesnet) momenti


def get_oneway_support_moment(system, neighbor_id: str, bw: float) -> Optional[float]:
    """
    ONEWAY döşemenin mesnet momentini hesaplar.
    """
    from oneway_slab import compute_oneway_per_slab
    
    try:
        res, _ = compute_oneway_per_slab(system, neighbor_id, bw)
        Mneg = res.get("Mneg_min")
        return abs(Mneg) if Mneg is not None else None
    except:
        return None


def calculate_stiffness_ratio(L1: float, L2: float) -> Tuple[float, float]:
    """
    İki döşeme arasındaki şerit rijitliği oranını hesaplar.
    Aynı kalınlık varsayımıyla K = I/L, K1/K2 = L2/L1
    
    Returns:
        (DF1, DF2): Dağıtım faktörleri (toplamı 1)
    """
    if L1 <= 0 or L2 <= 0:
        return 0.5, 0.5
    
    K1 = 1.0 / L1  # I sabit kabul edildi
    K2 = 1.0 / L2
    total = K1 + K2
    
    if total < 1e-9:
        return 0.5, 0.5
    
    return K1 / total, K2 / total


def balance_support_moments(system, raw_moments: Dict[str, dict], bw: float) -> Tuple[Dict[str, dict], List[str]]:
    """
    TWOWAY döşemelerin mesnet momentlerini TS500'e göre dengeler.
    
    TS500 Kuralı:
    - M_min < 0.8 × M_max ise: Farkın 2/3'ü rijitlik oranına göre dağıtılır
    - Tasarımda büyük değer kullanılır
    
    Args:
        system: SlabSystem nesnesi
        raw_moments: {sid: compute_twoway_per_slab sonucu}
        bw: Kiriş genişliği (m)
    
    Returns:
        (balanced_moments, log_lines)
    """
    balanced = {}
    log = []
    
    # Dengelenmiş momentleri saklamak için
    # {(sid, edge): balanced_moment}
    edge_balanced = {}
    
    # İşlenmiş kenar çiftleri (tekrar işlememek için)
    processed_pairs = set()
    
    for sid, res in raw_moments.items():
        if res is None:
            continue
        
        # Sadece TWOWAY döşemeler için
        if sid not in system.slabs or system.slabs[sid].kind != "TWOWAY":
            continue
        
        Lx_net = res.get("Lx_net", 1.0)
        Ly_net = res.get("Ly_net", 1.0)
        
        for edge in ("L", "R", "T", "B"):
            # Bu kenar çifti zaten işlendi mi?
            neighbor_id, neighbor_kind = get_neighbor_on_edge(system, sid, edge)
            
            if neighbor_id is None:
                continue
            
            # Sadece TWOWAY veya ONEWAY komşular için dengeleme yap
            if neighbor_kind not in ("TWOWAY", "ONEWAY"):
                continue
            
            # Çift kontrolü (A-L-B aynı B-R-A ile)
            pair_key = tuple(sorted([sid, neighbor_id])) + (edge if sid < neighbor_id else get_opposite_edge(edge),)
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)
            
            # Bu döşemenin mesnet momenti
            M1 = get_moment_for_edge(res, edge)
            if M1 is None:
                continue
            M1 = abs(M1)
            
            # Komşu döşemenin mesnet momenti
            if neighbor_kind == "TWOWAY" and neighbor_id in raw_moments:
                neighbor_res = raw_moments[neighbor_id]
                if neighbor_res is None:
                    continue
                opposite_edge = get_opposite_edge(edge)
                M2 = get_moment_for_edge(neighbor_res, opposite_edge)
                if M2 is None:
                    continue
                M2 = abs(M2)
                
                # Komşu döşemenin açıklığı
                L2 = neighbor_res.get("Lx_net" if edge in ("L", "R") else "Ly_net", 1.0)
            elif neighbor_kind == "ONEWAY":
                M2 = get_oneway_support_moment(system, neighbor_id, bw)
                if M2 is None:
                    continue
                M2 = abs(M2)
                
                # ONEWAY döşeme açıklığı
                neighbor_slab = system.slabs[neighbor_id]
                Lx_n, Ly_n = neighbor_slab.size_m_gross()
                L2 = min(Lx_n, Ly_n)  # Kısa açıklık
            else:
                continue
            
            # Bu döşemenin açıklığı (ilgili yönde)
            L1 = Lx_net if edge in ("L", "R") else Ly_net
            
            # M_max ve M_min belirleme
            M_max = max(M1, M2)
            M_min = min(M1, M2)
            
            log.append(f"Kenar {sid}-{edge} <-> {neighbor_id}-{get_opposite_edge(edge)}:")
            log.append(f"  M1 ({sid}) = {M1:.3f}, M2 ({neighbor_id}) = {M2:.3f}")
            
            # TS500 kontrolü
            if M_min < 0.8 * M_max:
                # Fark fazla, dağıtım yapılacak
                delta_M = M_max - M_min
                
                # Rijitlik oranı hesabı
                DF1, DF2 = calculate_stiffness_ratio(L1, L2)
                log.append(f"  L1 = {L1:.3f}, L2 = {L2:.3f}")
                log.append(f"  DF1 = {DF1:.3f}, DF2 = {DF2:.3f}")
                
                # 2/3 fark dağıtılır
                distribute = (2.0 / 3.0) * delta_M
                
                if M1 > M2:
                    # M1 büyük, ondan düş, M2'ye ekle
                    M1_adj = -distribute * DF1
                    M2_adj = distribute * DF2
                else:
                    # M2 büyük
                    M1_adj = distribute * DF1
                    M2_adj = -distribute * DF2
                
                M1_new = M1 + M1_adj
                M2_new = M2 + M2_adj
                
                log.append(f"  M_min ({M_min:.3f}) < 0.8 × M_max ({0.8*M_max:.3f}) → Dağıtım yapılıyor")
                log.append(f"  ΔM = {delta_M:.3f}, Dağıtılacak = {distribute:.3f}")
                log.append(f"  M1_yeni = {M1_new:.3f}, M2_yeni = {M2_new:.3f}")
                
                # Tasarımda büyük değer kullanılır
                M_design = max(M1_new, M2_new)
                log.append(f"  Tasarım momenti: {M_design:.3f} kNm/m")
            else:
                # Fark az, büyük olanı kullan
                M_design = M_max
                log.append(f"  M_min ({M_min:.3f}) >= 0.8 × M_max ({0.8*M_max:.3f}) → Büyük değer kullanılıyor")
                log.append(f"  Tasarım momenti: {M_design:.3f} kNm/m")
            
            # Dengelenmiş momentleri sakla
            edge_balanced[(sid, edge)] = M_design
            edge_balanced[(neighbor_id, get_opposite_edge(edge))] = M_design
            log.append("")
    
    # Orijinal momentleri kopyala ve dengelenmiş değerleri uygula
    for sid, res in raw_moments.items():
        if res is None:
            balanced[sid] = None
            continue
        
        # Derin kopya
        balanced[sid] = dict(res)
        
        if sid not in system.slabs or system.slabs[sid].kind != "TWOWAY":
            continue
        
        mxn, mxp = res.get("Mx", (None, None))
        myn, myp = res.get("My", (None, None))
        
        # L veya R kenarı için dengelenmiş moment kontrolü
        for edge in ("L", "R"):
            if (sid, edge) in edge_balanced:
                mxn = -edge_balanced[(sid, edge)]  # Negatif moment olarak sakla
                break
        
        # T veya B kenarı için dengelenmiş moment kontrolü
        for edge in ("T", "B"):
            if (sid, edge) in edge_balanced:
                myn = -edge_balanced[(sid, edge)]  # Negatif moment olarak sakla
                break
        
        balanced[sid]["Mx"] = (mxn, mxp)
        balanced[sid]["My"] = (myn, myp)
    
    return balanced, log
