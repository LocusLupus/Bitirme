"""
Döşeme Sistemi Modülü
=====================
Bu modül döşeme sistemi veri yapısını ve ana hesaplama fonksiyonlarını içerir.
Hesap mantığı ayrı modüllerde bulunur:
- oneway_slab.py: Tek doğrultulu döşeme hesabı
- twoway_slab.py: Çift doğrultulu döşeme hesabı
- balcony_slab.py: Balkon hesabı
"""

from dataclasses import dataclass
from typing import Dict, Tuple, List, Set, Optional
import hashlib
from constants import ALPHA_TABLE, M_POINTS, CASE_DESC
from struct_design import (
    interp_alpha, one_span_coeff_by_fixity, one_way_coefficients,
    as_from_abacus_steps, rho_min_oneway, select_rebar_min_area,
    max_possible_area, RebarChoice
)

@dataclass
class Slab:
    slab_id: str
    i0: int
    j0: int
    i1: int
    j1: int
    kind: str  # ONEWAY / TWOWAY / BALCONY
    dx: float
    dy: float
    pd: float
    b: float

    def bbox(self):
        return self.i0, self.j0, self.i1, self.j1

    def size_cells(self):
        return (self.i1 - self.i0 + 1), (self.j1 - self.j0 + 1)

    def size_m_gross(self):
        nx, ny = self.size_cells()
        return nx * self.dx, ny * self.dy

def color_for_id(s: str) -> str:
    h = hashlib.md5(s.encode("utf-8")).hexdigest()
    r = 80 + int(h[0:2], 16) % 140
    g = 80 + int(h[2:4], 16) % 140
    b = 80 + int(h[4:6], 16) % 140
    return f"#{r:02x}{g:02x}{b:02x}"

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def rect_normalize(a, b):
    (x0, y0), (x1, y1) = a, b
    return (min(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1))

class SlabSystem:
    def __init__(self, nx: int, ny: int):
        self.Nx = nx
        self.Ny = ny
        self.slabs: Dict[str, Slab] = {}
        self.cell_owner: Dict[Tuple[int, int], str] = {}
        self.V_beam: Set[Tuple[int, int]] = set()
        self.H_beam: Set[Tuple[int, int]] = set()

    def add_slab(self, s: Slab):
        self.slabs[s.slab_id] = s
        for i in range(s.i0, s.i1 + 1):
            for j in range(s.j0, s.j1 + 1):
                self.cell_owner[(i, j)] = s.slab_id

    def delete_slab(self, sid: str):
        if sid not in self.slabs:
            return
        s = self.slabs[sid]
        for i in range(s.i0, s.i1 + 1):
            for j in range(s.j0, s.j1 + 1):
                if self.cell_owner.get((i, j)) == sid:
                    del self.cell_owner[(i, j)]
        del self.slabs[sid]

    def neighbor_slabs_on_side(self, sid: str, direction: str, side: str) -> set:
        s = self.slabs[sid]
        i0, j0, i1, j1 = s.bbox()
        direction = direction.upper()
        side = side.upper()
        neigh = set()

        if direction == "X":
            if side == "START":
                if i0 == 0: return neigh
                ii = i0 - 1
                for j in range(j0, j1 + 1):
                    nb = self.cell_owner.get((ii, j))
                    if nb and nb != sid: neigh.add(nb)
            else:
                if i1 >= self.Nx - 1: return neigh
                ii = i1 + 1
                for j in range(j0, j1 + 1):
                    nb = self.cell_owner.get((ii, j))
                    if nb and nb != sid: neigh.add(nb)
        else:
            if side == "START":
                if j0 == 0: return neigh
                jj = j0 - 1
                for i in range(i0, i1 + 1):
                    nb = self.cell_owner.get((i, jj))
                    if nb and nb != sid: neigh.add(nb)
            else:
                if j1 >= self.Ny - 1: return neigh
                jj = j1 + 1
                for i in range(i0, i1 + 1):
                    nb = self.cell_owner.get((i, jj))
                    if nb and nb != sid: neigh.add(nb)
        return neigh

    def edge_neighbor_coverage(self, sid: str, edge: str) -> Tuple[bool, bool, float]:
        s = self.slabs[sid]
        i0, j0, i1, j1 = s.bbox()
        edge = edge.upper()
        total, found = 0, 0

        if edge == "L":
            if i0 == 0: return (False, False, 0.0)
            for j in range(j0, j1 + 1):
                total += 1
                nb = self.cell_owner.get((i0 - 1, j))
                if nb and nb != sid: found += 1
        elif edge == "R":
            if i1 >= self.Nx - 1: return (False, False, 0.0)
            for j in range(j0, j1 + 1):
                total += 1
                nb = self.cell_owner.get((i1 + 1, j))
                if nb and nb != sid: found += 1
        elif edge == "T":
            if j0 == 0: return (False, False, 0.0)
            for i in range(i0, i1 + 1):
                total += 1
                nb = self.cell_owner.get((i, j0 - 1))
                if nb and nb != sid: found += 1
        elif edge == "B":
            if j1 >= self.Ny - 1: return (False, False, 0.0)
            for i in range(i0, i1 + 1):
                total += 1
                nb = self.cell_owner.get((i, j1 + 1))
                if nb and nb != sid: found += 1

        any_ = found > 0
        full = (total > 0 and found == total)
        ratio = (found / total) if total > 0 else 0.0
        return (full, any_, ratio)

    def twoway_edge_continuity_full(self, sid: str):
        Lf, La, Lr = self.edge_neighbor_coverage(sid, "L")
        Rf, Ra, Rr = self.edge_neighbor_coverage(sid, "R")
        Tf, Ta, Tr = self.edge_neighbor_coverage(sid, "T")
        Bf, Ba, Br = self.edge_neighbor_coverage(sid, "B")
        return (Lf, Rf, Tf, Bf), (La, Ra, Ta, Ba), (Lr, Rr, Tr, Br)

    def pick_two_way_case_exact(self, Lx_net: float, Ly_net: float,
                               cont_left: bool, cont_right: bool, cont_top: bool, cont_bottom: bool) -> int:
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

    # =========================================================
    # Beam line detection
    # =========================================================
    def is_beam_gridline_for_slab(self, sid: str, direction: str, g: int) -> bool:
        s = self.slabs[sid]
        i0, j0, i1, j1 = s.bbox()
        direction = direction.upper()

        if direction == "X":
            if g < 0 or g > self.Nx: return False
            k = g - 1
            return all((k, j) in self.V_beam for j in range(j0, j1 + 1))
        else:
            if g < 0 or g > self.Ny: return False
            k = g - 1
            return all((i, k) in self.H_beam for i in range(i0, i1 + 1))

    def slab_support_gridlines_from_drawn_beams(self, sid: str, direction: str) -> List[int]:
        s = self.slabs[sid]
        i0, j0, i1, j1 = s.bbox()
        direction = direction.upper()
        if direction == "X":
            return [g for g in range(i0 + 1, i1 + 1) if self.is_beam_gridline_for_slab(sid, "X", g)]
        else:
            return [g for g in range(j0 + 1, j1 + 1) if self.is_beam_gridline_for_slab(sid, "Y", g)]

    def net_span(self, Lgross: float, left_is_beam: bool, right_is_beam: bool, bw: float) -> float:
        """Net açıklık hesabı - kiriş genişliği düşülür."""
        if left_is_beam and right_is_beam:
            Lnet = Lgross - bw
        elif left_is_beam or right_is_beam:
            Lnet = Lgross - 0.5 * bw
        else:
            Lnet = Lgross
        return max(0.05, Lnet)

    # =========================================================
    # ONEWAY logic - wrapper metodlar (hesap oneway_slab.py'de)
    # =========================================================
    def build_oneway_chain(self, sid: str, direction: str) -> List[str]:
        """Wrapper: oneway_slab modülüne yönlendirir."""
        from oneway_slab import build_oneway_chain
        return build_oneway_chain(self, sid, direction)

    def chain_panel_boundary_supports(self, chain: List[str], direction: str) -> List[int]:
        """Wrapper: oneway_slab modülüne yönlendirir."""
        from oneway_slab import chain_panel_boundary_supports
        return chain_panel_boundary_supports(self, chain, direction)

    def chain_end_fixity(self, chain: List[str], direction: str) -> Tuple[bool, bool]:
        """Wrapper: oneway_slab modülüne yönlendirir."""
        from oneway_slab import chain_end_fixity
        return chain_end_fixity(self, chain, direction)

    def owner_slab_for_segment(self, chain: List[str], direction: str, g_mid: float) -> str:
        """Wrapper: oneway_slab modülüne yönlendirir."""
        from oneway_slab import owner_slab_for_segment
        return owner_slab_for_segment(self, chain, direction, g_mid)

    def compute_oneway_per_slab(self, sid: str, bw_val: float) -> Tuple[dict, List[str]]:
        """Wrapper: oneway_slab modülüne yönlendirir."""
        from oneway_slab import compute_oneway_per_slab
        return compute_oneway_per_slab(self, sid, bw_val)

    # =========================================================
    # TWOWAY logic - wrapper metodlar (hesap twoway_slab.py'de)
    # =========================================================
    def slab_edge_has_beam(self, sid: str, edge: str) -> bool:
        """Wrapper: twoway_slab modülüne yönlendirir."""
        from twoway_slab import slab_edge_has_beam
        return slab_edge_has_beam(self, sid, edge)

    def twoway_net_LxLy(self, sid: str, bw: float) -> Tuple[float, float, List[str]]:
        """Wrapper: twoway_slab modülüne yönlendirir."""
        from twoway_slab import twoway_net_LxLy
        return twoway_net_LxLy(self, sid, bw)

    def compute_twoway_per_slab(self, sid: str, bw: float) -> Tuple[dict, List[str]]:
        """Wrapper: twoway_slab modülüne yönlendirir."""
        from twoway_slab import compute_twoway_per_slab
        return compute_twoway_per_slab(self, sid, bw)

    # =========================================================
    # BALCONY logic - wrapper metodlar (hesap balcony_slab.py'de)
    # =========================================================
    def compute_balcony_per_slab(self, sid: str, bw: float) -> Tuple[dict, List[str]]:
        """Wrapper: balcony_slab modülüne yönlendirir."""
        from balcony_slab import compute_balcony_per_slab
        return compute_balcony_per_slab(self, sid, bw)

    def balcony_fixed_edge_guess(self, sid: str) -> Tuple[str, List[str]]:
        """Wrapper: balcony_slab modülüne yönlendirir."""
        from balcony_slab import balcony_fixed_edge_guess
        return balcony_fixed_edge_guess(self, sid)

    def neighbor_support_moment_for_edge(self, neighbor_id: str, edge: str, bw: float) -> float:
        """Wrapper: balcony_slab modülüne yönlendirir."""
        from balcony_slab import neighbor_support_moment_for_edge
        return neighbor_support_moment_for_edge(self, neighbor_id, edge, bw)

    def get_balcony_design_moment(self, sid: str, Mbal: float, bw: float) -> Tuple[float, List[str]]:
        """Wrapper: balcony_slab modülüne yönlendirir."""
        from balcony_slab import get_balcony_design_moment
        return get_balcony_design_moment(self, sid, Mbal, bw)

    # =========================================================
    # Design Wrapper
    # =========================================================
    def design_main_rebar_from_M(
        self,
        M_kNm: float,
        conc: str,
        steel: str,
        h_mm: float,
        cover_mm: float,
        s_max: int,
        As_min_override: Optional[float] = None,
        label_prefix: str = "",
        d_delta_mm: float = 0.0
    ) -> Tuple[float, RebarChoice, List[str]]:
        steps = []
        d_nom = h_mm - cover_mm
        d_eff = d_nom + d_delta_mm
        if d_delta_mm != 0.0:
            steps.append(f"{label_prefix}d düzeltmesi: {d_nom:.1f} -> {d_eff:.1f}")

        As_raw, st_as = as_from_abacus_steps(M_kNm, conc, steel, h_mm, cover_mm, d_override_mm=d_eff)
        steps.extend([label_prefix + x for x in st_as])
        
        As_req = As_raw if As_raw is not None else 0.0
        d_mm = max(1.0, d_eff)
        
        # As_min hesabı: TS500'e göre rho_min * b * d
        # Ancak kullanıcı d_delta ile d'yi azaltıyorsa (çift yönlü döşemede iç donatı gibi),
        # As_min de azalır. 
        # Eğer raporlamada "240" (d=120 için) yazıp, seçimde 220 (d=110 için) kullanıyorsak tutarsızlık olur.
        # FİKS: Her zaman raporlanan (veya override edilen) As_min değerini esas al.
        
        As_min_calc = rho_min_oneway(steel) * 1000.0 * d_mm
        
        if As_min_override is not None:
            As_min_use = As_min_override
            As_min_source = "override"
        else:
            # Sadece ONEWAY/TWOWAY ayrımı yapılabilir ama şimdilik hesaplanan d üzerinden gidiyoruz.
            # EĞER kullanıcı "Gerekli As" olarak 240 görüp 220'ye göre seçim yapılmasını istemiyorsa,
            # çağıran yer (twoway_slab.py) As_min_override göndermeliydi veya d_delta yapmamalıydı.
            # AMA BURADAKİ SORUN: Kullanıcı 240 görüyor (raporlamada belki manuel hesapladı veya başka yerden gördü?)
            # Biz burada d_eff kullanıyoruz.
            
            # KULLANICI İSTEĞİNE ÖZEL DÜZELTME:
            # Tekil/Çift yönlü döşemelerde minimum donatı genellikle brüt kesit veya ana d üzerinden istenir.
            # İç donatı için d azalsa bile, bence min donatı kısıtlamasını ana d (d_nom) üzerinden tutmak daha güvenli ve tutarlı.
            # Böylece X ve Y yönü için min donatı aynı görünür (240).
            
            As_min_nom = rho_min_oneway(steel) * 1000.0 * d_nom
            As_min_use = As_min_nom 
            As_min_source = "nominal d"

        As_req2 = max(As_req, As_min_use)
        
        # Raporlama
        if As_req2 > As_req + 1e-9:
             steps.append(f"{label_prefix}As_min kontrolü ({As_min_source}): {As_req:.1f} < {As_min_use:.1f} -> Gerekli={As_req2:.1f}")
        
        cand = select_rebar_min_area(As_req2, s_max, phi_min=8)
        if cand is None:
            raise ValueError(f"Donatı bulunamadı: As={As_req2:.1f}, s_max={s_max}")
        
        steps.append(f"{label_prefix}Seçim: {cand.label_with_area()}")
        return As_req2, cand, steps
