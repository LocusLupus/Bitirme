import math
import ezdxf
from typing import List, Tuple, Optional
from slab_model import SlabSystem, Slab

class _DXFWriter:
    """ezdxf kÃ¼tÃ¼phanesi kullanarak DXF dosyasÄ± oluÅŸturan sÄ±nÄ±f."""
    
    def __init__(self, max_height=None):
        self.doc = ezdxf.new('R2010')  # AutoCAD 2010 formatÄ±
        self.msp = self.doc.modelspace()
        self.layers_created = set()
        self.max_height = max_height

    def _fy(self, y):
        """Y koordinatÄ±nÄ± ters Ã§evir (GUI -> DXF dÃ¶nÃ¼ÅŸÃ¼mÃ¼ iÃ§in)."""
        if self.max_height is not None:
            return self.max_height - y
        return y

    def add_layer(self, name: str, color: int = 7, lineweight: int = -3):
        """
        color: AutoCAD Color Index (ACI). 1=Red, 2=Yellow, 3=Green, 4=Cyan, 5=Blue, 6=Magenta, 7=White/Black
        lineweight: mm * 100. e.g. 50 = 0.50mm. -3 = Default.
        """
        if name not in self.layers_created and name != "0":
            layer = self.doc.layers.add(name)
            layer.color = color
            layer.lineweight = lineweight
            self.layers_created.add(name)

    def add_line(self, x1, y1, x2, y2, layer="0"):
        if layer not in self.layers_created and layer != "0":
             self.add_layer(layer)

        y1 = self._fy(y1)
        y2 = self._fy(y2)
        self.msp.add_line((x1, y1), (x2, y2), dxfattribs={'layer': layer})

    def add_polyline(self, pts, layer="0", closed=False):
        if layer not in self.layers_created and layer != "0":
             self.add_layer(layer)

        # pts listesi (x, y) tuple'larÄ±ndan oluÅŸur
        new_pts = [(x, self._fy(y)) for x, y in pts]
        self.msp.add_lwpolyline(new_pts, dxfattribs={'layer': layer}, close=closed)

    def add_text(self, x, y, text, height=100.0, layer="TEXT", rotation=0.0, center=False, align_code=None):
        if layer not in self.layers_created and layer != "0":
             self.add_layer(layer)

        y = self._fy(y)
        
        txt = self.msp.add_text(text, dxfattribs={
            'layer': layer,
            'height': height,
            'rotation': rotation
        })
        if align_code:
             txt.set_placement((x, y), align=align_code)
        elif center:
            txt.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        else:
            txt.set_placement((x, y))

    def save(self, path: str):
        self.doc.saveas(path)


# =========================================================
# DonatÄ± Ã‡izim YardÄ±mcÄ± FonksiyonlarÄ±
# =========================================================

def _pilye_polyline(x0, y0, x1, y1, d=250.0, kink="both", hook_len=100.0, beam_ext=0.0, mirror=False):
    """
    Pilye Ã§ubuÄŸu Ã§izer:
    - Ãœst seviyede Ln/5 + beam_ext kadar dÃ¼z gider (beam_ext kÄ±smÄ± kiriÅŸin iÃ§inde)
    - Ln/5 noktasÄ±nda 45 derece kÄ±rÄ±lÄ±r
    - Alt seviyede dÃ¼z devam eder
    - UÃ§larda kiriÅŸ iÃ§ine doÄŸru kanca yapar
    
    kink parametresi:
    - "start": sol/alt tarafta kÄ±rÄ±lma
    - "end": saÄŸ/Ã¼st tarafta kÄ±rÄ±lma
    - "both": her iki tarafta kÄ±rÄ±lma
    - "none": dÃ¼z Ã§ubuk
    
    d: pilye kÄ±rÄ±lma yÃ¼ksekliÄŸi (45 derece iÃ§in dx=dy=d)
    hook_len: kanca uzunluÄŸu (kiriÅŸ iÃ§ine doÄŸru)
    beam_ext: kiriÅŸ iÃ§ine uzanma mesafesi (kanca kÄ±rÄ±lma noktasÄ± kiriÅŸin iÃ§inde olur)
    mirror: True ise pilye kÄ±rÄ±lma yÃ¶nÃ¼ ters Ã§evrilir (aÅŸaÄŸÄ±â†’yukarÄ±, saÄŸaâ†’sola)
    """
    kink = (kink or "both").lower()
    if kink not in ("start", "end", "both", "none"): kink = "both"
    
    # mirror: dik bileÅŸenlerin iÅŸaretini Ã§evir
    s = -1 if mirror else 1

    if abs(y1 - y0) < 1e-6:  # Horizontal bar (X yÃ¶nÃ¼nde)
        if x1 < x0: x0, x1 = x1, x0; flip = True
        else: flip = False
        
        L = abs(x1 - x0)
        if L < 1e-6 or kink == "none": return [(x0, y0), (x1, y0)]
        
        want_start = kink in ("start", "both")
        want_end = kink in ("end", "both")
        if flip: want_start, want_end = want_end, want_start
        
        # Ln/5 mesafesi (pilye kÄ±rÄ±lma noktasÄ± - kiriÅŸten uzaklÄ±k)
        Ln5 = L / 5.0
        
        pts = []
        
        if want_start:
            # Sol taraf: kanca kiriÅŸin iÃ§inde, beam_ext kadar sola uzanÄ±r
            pts.append((x0 - beam_ext, y0 - s * hook_len))  # Kanca ucu
            pts.append((x0 - beam_ext, y0))                  # Kanca dÃ¶nÃ¼ÅŸÃ¼
            pts.append((x0 + Ln5 - d, y0))                   # Bar seviyesinde dÃ¼z git
            pts.append((x0 + Ln5, y0 - s * d))               # 45 derece kÄ±rÄ±l
        else:
            pts.append((x0, y0 - s * d))              # Offset seviyede baÅŸla
        
        if want_end:
            pts.append((x1 - Ln5, y0 - s * d))               # Offset seviyede dÃ¼z kÄ±sÄ±m sonu
            pts.append((x1 - Ln5 + d, y0))                   # 45 derece bar seviyesine dÃ¶n
            pts.append((x1 + beam_ext, y0))                   # Bar seviyesinde bit
            pts.append((x1 + beam_ext, y0 - s * hook_len))   # Kanca ucu
        else:
            pts.append((x1, y0 - s * d))              # Offset seviyede bit
        
        return pts
        
    else:  # Vertical bar (Y yÃ¶nÃ¼nde)
        if y1 < y0: y0, y1 = y1, y0; flip = True
        else: flip = False
        
        L = abs(y1 - y0)
        if L < 1e-6 or kink == "none": return [(x0, y0), (x0, y1)]
        
        want_start = kink in ("start", "both")
        want_end = kink in ("end", "both")
        if flip: want_start, want_end = want_end, want_start
        
        # Ln/5 mesafesi (pilye kÄ±rÄ±lma noktasÄ± - kiriÅŸten uzaklÄ±k)
        Ln5 = L / 5.0
        
        pts = []
        
        if want_start:
            # Alt taraf: kanca kiriÅŸin iÃ§inde
            pts.append((x0 + s * hook_len, y0 - beam_ext))  # Kanca ucu
            pts.append((x0, y0 - beam_ext))                  # Kanca dÃ¶nÃ¼ÅŸÃ¼
            pts.append((x0, y0 + Ln5 - d))                   # Bar seviyesinde dÃ¼z git
            pts.append((x0 + s * d, y0 + Ln5))               # 45 derece kÄ±rÄ±l
        else:
            pts.append((x0 + s * d, y0))              # Offset seviyede baÅŸla
        
        if want_end:
            pts.append((x0 + s * d, y1 - Ln5))               # Offset seviyede dÃ¼z kÄ±sÄ±m sonu
            pts.append((x0, y1 - Ln5 + d))                   # 45 derece bar seviyesine dÃ¶n
            pts.append((x0, y1 + beam_ext))                   # Bar seviyesinde bit
            pts.append((x0 + s * hook_len, y1 + beam_ext))   # Kanca ucu
        else:
            pts.append((x0 + s * d, y1))              # Offset seviyede bit
        
        return pts


def _draw_straight_hit_polyline(x0, y0, x1, y1, ext, hook):
    """
    DÃ¼z donatÄ± iÃ§in kancalÄ± Ã§izim (Plan gÃ¶rÃ¼nÃ¼ÅŸte sembolik).
    - KiriÅŸ iÃ§ine 'ext' kadar girer.
    - Sonra 90 derece 'hook' kadar kÄ±rÄ±lÄ±r.
    - YÃ¶n: 'Legs down' (negatif yÃ¶n).
    """
    if abs(y1 - y0) < 1e-6: # Horizontal (X yÃ¶nÃ¼nde)
        if x1 < x0: x0, x1 = x1, x0
        # Legs down -> -Y yÃ¶nÃ¼nde kanca
        return [
            (x0 - ext, y0 - hook),
            (x0 - ext, y0),
            (x1 + ext, y0),
            (x1 + ext, y0 - hook)
        ]
    else: # Vertical (Y yÃ¶nÃ¼nde)
        if y1 < y0: y0, y1 = y1, y0
        # Legs down -> -X yÃ¶nÃ¼nde kanca (veya +X? Pilye Ã§izimine uyumlu olsun)
        # Pilye vb. genelde saÄŸa/sola kÄ±rÄ±lÄ±r. 
        # Referans "rotated 180 degrees" -> horizontal iÃ§in bariz "aÅŸaÄŸÄ±".
        # Vertical iÃ§in "negatif X" (sola) seÃ§elim.
        return [
            (x0 - hook, y0 - ext),
            (x0, y0 - ext),
            (x0, y1 + ext),
            (x0 - hook, y1 + ext)
        ]



def _draw_dimension_line(w: _DXFWriter, x0, y0, x1, y1, label: str, offset=150.0, layer="DIM"):
    """Ã–lÃ§Ã¼ Ã§izgisi Ã§izer (Ã§izgi + etiket)"""
    # Ana Ã§izgi
    w.add_line(x0, y0, x1, y1, layer=layer)
    
    # UÃ§ Ã§izgiler (tick marks)
    if abs(y1 - y0) < 1e-6:  # Horizontal
        w.add_line(x0, y0 - 50, x0, y0 + 50, layer=layer)
        w.add_line(x1, y1 - 50, x1, y1 + 50, layer=layer)
        mid_x = (x0 + x1) / 2
        w.add_text(mid_x, y0 + offset, label, height=300, layer=layer)
    else:  # Vertical
        w.add_line(x0 - 50, y0, x0 + 50, y0, layer=layer)
        w.add_line(x1 - 50, y1, x1 + 50, y1, layer=layer)
        mid_y = (y0 + y1) / 2
        w.add_text(x0 + offset, mid_y, label, height=300, layer=layer, rotation=90)


def _draw_support_rebar_horizontal(w: _DXFWriter, x0, y0, x1, y1, count: int, layer: str, label: str = None, 
                                   hook_start=False, hook_end=False, hook_len=100.0):
    """
    Yatay mesnet donatÄ±sÄ± Ã§izer (birden fazla Ã§izgi ile gÃ¶sterir).
    hook_start: Sol uÃ§ta kanca (aÅŸaÄŸÄ± doÄŸru)
    hook_end: SaÄŸ uÃ§ta kanca (aÅŸaÄŸÄ± doÄŸru)
    """
    if count < 1: count = 1
    if count > 5: count = 5
    
    dy = (y1 - y0) / (count + 1)
    
    for i in range(1, count + 1):
        y = y0 + i * dy
        pts = []
        if hook_start:
            pts.append((x0, y - hook_len))
            pts.append((x0, y))
        else:
            pts.append((x0, y))
            
        if hook_end:
            pts.append((x1, y))
            pts.append((x1, y - hook_len))
        else:
            pts.append((x1, y))
            
        w.add_polyline(pts, layer=layer)
    
    if label:
        mid_y = (y0 + y1) / 2
        w.add_text(x0 - 50, mid_y, label, height=300, layer="TEXT", rotation=90)


def _draw_support_rebar_vertical(w: _DXFWriter, x0, y0, x1, y1, count: int, layer: str, label: str = None,
                                 hook_start=False, hook_end=False, hook_len=100.0):
    """
    Dikey mesnet donatÄ±sÄ± Ã§izer (birden fazla Ã§izgi ile gÃ¶sterir).
    hook_start: Ãœst uÃ§ta kanca (sola/ters yÃ¶ne doÄŸru - kullanÄ±cÄ± isteÄŸine gÃ¶re ayarlanabilir, ÅŸimdilik sol)
    hook_end: Alt uÃ§ta kanca (sola/ters yÃ¶ne doÄŸru)
    """
    if count < 1: count = 1
    if count > 5: count = 5
    
    dx = (x1 - x0) / (count + 1)
    
    for i in range(1, count + 1):
        x = x0 + i * dx
        pts = []
        # Dikeyde "start" Ã¼st (kÃ¼Ã§Ã¼k y?), "end" alt (bÃ¼yÃ¼k y?)
        # Parametreler y0 (Ã¼st), y1 (alt) varsayÄ±mÄ±yla:
        
        if hook_start:
            pts.append((x - hook_len, y0)) # Sola kÄ±vrÄ±k
            pts.append((x, y0))
        else:
            pts.append((x, y0))
            
        if hook_end:
            pts.append((x, y1))
            pts.append((x - hook_len, y1)) # Sola kÄ±vrÄ±k
        else:
            pts.append((x, y1))
            
        w.add_polyline(pts, layer=layer)
    
    if label:
        mid_x = (x0 + x1) / 2
        w.add_text(mid_x, y1 + 50, label, height=300, layer="TEXT")


# =========================================================
# Ek DonatÄ± YardÄ±mcÄ±larÄ± (Ln/4 KuralÄ±)
# =========================================================

def _get_single_side_ext(system: SlabSystem, sid: str, axis: str) -> float:
    """
    DÃ¶ÅŸemenin belirtilen eksenindeki (Lx veya Ly) brÃ¼t aÃ§Ä±klÄ±ÄŸÄ±nÄ±n 1/4'Ã¼nÃ¼ dÃ¶ndÃ¼rÃ¼r.
    """
    if not system or not sid or sid not in system.slabs:
        return 500.0  # Default fallback
    s = system.slabs[sid]
    lx_g, ly_g = s.size_m_gross()
    val = (lx_g if axis.upper() == "X" else ly_g) * 1000.0
    return val / 4.0

def _draw_oneway_reinforcement_detail(
    w: _DXFWriter,
    sid: str,
    s: Slab,
    dcache: dict,
    x0: float, y0: float, x1: float, y1: float,
    bw_mm: float,
    slab_index: int = 0,
    system: SlabSystem = None,
    drawn_supports: set = None
):
    """
    Tek doÄŸrultulu dÃ¶ÅŸeme iÃ§in detaylÄ± donatÄ± krokisi Ã§izer.
    """
    cover = float(dcache.get("cover_mm", 25.0))
    auto_dir = dcache.get("auto_dir", "X")
    choices = dcache.get("choices", {})
    edge_cont = dcache.get("edge_continuity", {})
    
    # Ä°Ã§ sÄ±nÄ±rlar
    ix0, iy0, ix1, iy1 = x0 + cover, y0 + cover, x1 - cover, y1 - cover
    if ix1 <= ix0 or iy1 <= iy0:
        return
    
    Lx = ix1 - ix0
    Ly = iy1 - iy0
    
    ch_duz = choices.get("duz")
    ch_pilye = choices.get("pilye")
    ch_dist = choices.get("dist")
    ch_kenar_start = choices.get("kenar_mesnet_start")
    ch_kenar_end = choices.get("kenar_mesnet_end")
    ch_ic_start = choices.get("ic_mesnet_start")
    ch_ic_end = choices.get("ic_mesnet_end")
    ch_ek_start = choices.get("mesnet_ek_start")
    ch_ek_end = choices.get("mesnet_ek_end")
    
    kenar_cont = dcache.get("edge_continuity", {})
    cont_L = kenar_cont.get("uzun_start", False) if auto_dir=="X" else kenar_cont.get("kisa_start", False)
    # Bu cont mantÄ±ÄŸÄ± biraz karÄ±ÅŸÄ±k. En iyisi dcache'ten doÄŸrudan alalÄ±m.
    # _draw_oneway call'unda dcache iÃ§indeki edge_continuity kullanÄ±lÄ±yor.
    
    midx = (ix0 + ix1) / 2.0
    midy = (iy0 + iy1) / 2.0
    
    # Kanca ve uzama
    hook_ext = bw_mm - 30.0
    d_crank = 200.0

    if auto_dir == "X":
        # Span = Y. Main rebar is Vertical.
        # Main rebar is Vertical (along Y). Crossing horizontal beams (T/B).
        # Distribution/Side supports are Horizontal (along X). Crossing vertical beams (L/R).
        x_duz = midx - 1.5 * bw_mm + (400.0 if (slab_index % 2 == 0) else -400.0)
        x_pilye = midx + 1.5 * bw_mm + (400.0 if (slab_index % 2 == 0) else -400.0)
        
        # 1. Main Rebar (Vertical)
        if ch_duz:
            pts = _draw_straight_hit_polyline(x_duz, iy0, x_duz, iy1, bw_mm, bw_mm)
            w.add_polyline(pts, layer="REB_MAIN_DUZ")
            w.add_text(x_duz - 200, iy0 + Ly/6, f"duz {ch_duz.label()}", height=150, layer="TEXT", rotation=90)
        if ch_pilye:
            pts = _pilye_polyline(x_pilye, iy0, x_pilye, iy1, d=200.0, kink="both", hook_len=bw_mm, beam_ext=bw_mm, mirror=False)
            w.add_polyline(pts, layer="REB_MAIN_PILYE")
            w.add_text(x_pilye + 200, iy0 + Ly/6, f"pilye {ch_pilye.label()}", height=150, layer="TEXT", rotation=90)
            
        # 2. Distribution (Horizontal) - crossing L/R
        if ch_dist:
            y_dist = midy + 1.5 * bw_mm
            pts = []
            if not edge_cont.get("kisa_start"): # Left
                pts.append((x0 - hook_ext, y_dist - hook_ext)); pts.append((x0 - hook_ext, y_dist))
            else: pts.append((x0, y_dist)) # Changed from x0-hook_ext to x0
            
            pts.append((x1, y_dist)) # Add the main horizontal segment
            
            if not edge_cont.get("kisa_end"): # Right
                pts.append((x1 + hook_ext, y_dist)); pts.append((x1 + hook_ext, y_dist - hook_ext))
            else: pts.append((x1, y_dist)) # Changed from x1+hook_ext to x1
            w.add_polyline(pts, layer="REB_DIST")
            w.add_text(midx, y_dist + 150, f"dagitma {ch_dist.label()}", height=150, layer="TEXT", center=True)

        # 3 & 4. Supports on L/R (Horizontal)
        y_k = midy - 1.5 * bw_mm
        # Left
        if ch_ic_start and edge_cont.get("kisa_start"): # Interior
            L_self = _get_single_side_ext(system, sid, "X")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "L")
            L_nb = _get_single_side_ext(system, nb_id, "X") if nb_id else L_self
            _draw_hat_bar(w, x0 - bw_mm/2, y_k, bw_mm, ch_ic_start, L_ext_left=L_nb, L_ext_right=L_self, axis="X", drawn_supports=drawn_supports)
        elif ch_kenar_start and not edge_cont.get("kisa_start"): # Edge
            L_self = _get_single_side_ext(system, sid, "X") # Ln/4
            L10 = L_self / 2.5 # (Ln/4) / 2.5 = Ln/10
            pts = [(x0 - hook_ext, y_k + bw_mm), (x0 - hook_ext, y_k), (ix0 + L_self - d_crank, y_k), (ix0 + L_self, y_k + d_crank), (ix0 + L_self + L10, y_k + d_crank)]
            w.add_polyline(pts, layer="REB_KENAR")
            w.add_text(x0 + L_self/2, y_k + 100, ch_kenar_start.label(), height=125, layer="TEXT", center=True)

        # Right
        if ch_ic_end and edge_cont.get("kisa_end"): # Interior
            L_self = _get_single_side_ext(system, sid, "X")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "R")
            L_nb = _get_single_side_ext(system, nb_id, "X") if nb_id else L_self
            _draw_hat_bar(w, x1 + bw_mm/2, y_k, bw_mm, ch_ic_end, L_ext_left=L_self, L_ext_right=L_nb, axis="X", drawn_supports=drawn_supports)
        elif ch_kenar_end and not edge_cont.get("kisa_end"): # Edge
            L_self = _get_single_side_ext(system, sid, "X") # Ln/4
            L10 = L_self / 2.5 # (Ln/4) / 2.5 = Ln/10
            pts = [(x1 + hook_ext, y_k + bw_mm), (x1 + hook_ext, y_k), (ix1 - L_self + d_crank, y_k), (ix1 - L_self, y_k + d_crank), (ix1 - L_self - L10, y_k + d_crank)]
            w.add_polyline(pts, layer="REB_KENAR")
            w.add_text(x1 - L_self/2, y_k + 100, ch_kenar_end.label(), height=125, layer="TEXT", center=True)

        # 5. Mesnet Ek on T/B (Vertical) - load direction
        max_x_main = 0.0
        if ch_duz:
            max_x_main = max(max_x_main, abs(x_duz - midx))
        if ch_pilye:
            max_x_main = max(max_x_main, abs(x_pilye - midx))
        offset_val = max_x_main + 2.0 * bw_mm
        # Top
        if ch_ek_start and edge_cont.get("uzun_start"):
            L_self = _get_single_side_ext(system, sid, "Y")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "T")
            L_nb = _get_single_side_ext(system, nb_id, "Y") if nb_id else L_self
            _draw_hat_bar(w, midx + offset_val, y0 - bw_mm/2, bw_mm, ch_ek_start, L_ext_left=L_nb, L_ext_right=L_self, axis="Y", drawn_supports=drawn_supports)
        
        # Bottom
        if ch_ek_end and edge_cont.get("uzun_end"):
            L_self = _get_single_side_ext(system, sid, "Y")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "B")
            L_nb = _get_single_side_ext(system, nb_id, "Y") if nb_id else L_self
            _draw_hat_bar(w, midx + offset_val, y1 + bw_mm/2, bw_mm, ch_ek_end, L_ext_left=L_self, L_ext_right=L_nb, axis="Y", drawn_supports=drawn_supports)

    else: # auto_dir == "Y"
        # Span = X. Main rebar is Horizontal.
        # Main rebar is Horizontal (along X). Crossing vertical beams (L/R).
        # Distribution/Side supports are Vertical (along Y). Crossing horizontal beams (T/B).
        y_duz = midy + 1.5 * bw_mm + (400.0 if (slab_index % 2 == 0) else -400.0)
        y_pilye = midy - 1.5 * bw_mm + (400.0 if (slab_index % 2 == 0) else -400.0)
        
        # 1. Main Rebar (Horizontal)
        if ch_duz:
            pts = _draw_straight_hit_polyline(ix0, y_duz, ix1, y_duz, bw_mm, bw_mm)
            w.add_polyline(pts, layer="REB_MAIN_DUZ")
            w.add_text(midx, y_duz + 100, f"duz {ch_duz.label()}", height=150, layer="TEXT", center=True)
        if ch_pilye:
            pts = _pilye_polyline(ix0, y_pilye, ix1, y_pilye, d=200.0, kink="both", hook_len=bw_mm, beam_ext=bw_mm, mirror=True)
            w.add_polyline(pts, layer="REB_MAIN_PILYE")
            w.add_text(midx, y_pilye + 100, f"pilye {ch_pilye.label()}", height=150, layer="TEXT", center=True)

        # 2. Distribution (Vertical) - crossing T/B
        if ch_dist:
            x_dist = midx + 1.5 * bw_mm
            pts = []
            if not edge_cont.get("kisa_start"): # Top
                pts.extend([(x_dist - hook_ext, y0 - hook_ext), (x_dist, y0 - hook_ext), (x_dist, y0)])
            else: pts.append((x_dist, y0))
            
            pts.append((x_dist, y1)) # Add the main vertical segment
            
            if not edge_cont.get("kisa_end"): # Bottom
                pts.extend([(x_dist, y1), (x_dist, y1 + hook_ext), (x_dist - hook_ext, y1 + hook_ext)])
            else: pts.append((x_dist, y1))
            w.add_polyline(pts, layer="REB_DIST")
            w.add_text(x_dist + 200, y0 + Ly/6, f"dagitma {ch_dist.label()}", height=150, layer="TEXT", rotation=90)

        # 3 & 4. Supports on T/B (Vertical)
        x_k = midx - 1.5 * bw_mm
        # Top
        if ch_ic_start and edge_cont.get("kisa_start"): # Interior
            L_self = _get_single_side_ext(system, sid, "Y")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "T")
            L_nb = _get_single_side_ext(system, nb_id, "Y") if nb_id else L_self
            _draw_hat_bar(w, x_k, y0 - bw_mm/2, bw_mm, ch_ic_start, L_ext_left=L_nb, L_ext_right=L_self, axis="Y", drawn_supports=drawn_supports)
        elif ch_kenar_start and not edge_cont.get("kisa_start"): # Edge
            L_self = _get_single_side_ext(system, sid, "Y") # Ln/4
            L10 = L_self / 2.5 # (Ln/4) / 2.5 = Ln/10
            pts = [(x_k + bw_mm, y0 - hook_ext), (x_k, y0 - hook_ext), (x_k, iy0 + L_self - d_crank), (x_k + d_crank, iy0 + L_self), (x_k + d_crank, iy0 + L_self + L10)]
            w.add_polyline(pts, layer="REB_KENAR")
            w.add_text(x_k - 200, y0 + L_self/2, ch_kenar_start.label(), height=125, layer="TEXT", rotation=90)
        # Bottom
        if ch_ic_end and edge_cont.get("kisa_end"): # Interior
            L_self = _get_single_side_ext(system, sid, "Y")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "B")
            L_nb = _get_single_side_ext(system, nb_id, "Y") if nb_id else L_self
            _draw_hat_bar(w, x_k, y1 + bw_mm/2, bw_mm, ch_ic_end, L_ext_left=L_self, L_ext_right=L_nb, axis="Y", drawn_supports=drawn_supports)
        elif ch_kenar_end and not edge_cont.get("kisa_end"): # Edge
            L_self = _get_single_side_ext(system, sid, "Y") # Ln/4
            L10 = L_self / 2.5 # (Ln/4) / 2.5 = Ln/10
            pts = [(x_k + bw_mm, y1 + hook_ext), (x_k, y1 + hook_ext), (x_k, iy1 - L_self + d_crank), (x_k + d_crank, iy1 - L_self), (x_k + d_crank, iy1 - L_self - L10)]
            w.add_polyline(pts, layer="REB_KENAR")
            w.add_text(x_k - 200, y1 - L_self/2, ch_kenar_end.label(), height=125, layer="TEXT", rotation=90)

        # 5. Mesnet Ek on L/R (Horizontal) - load direction
        max_y_main = 0.0
        if ch_duz:
            max_y_main = max(max_y_main, abs(y_duz - midy))
        if ch_pilye:
            max_y_main = max(max_y_main, abs(y_pilye - midy))
            
        offset_val = max_y_main + 2.0 * bw_mm
        # Left
        if ch_ek_start and edge_cont.get("uzun_start"):
            L_self = _get_single_side_ext(system, sid, "X")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "L")
            L_nb = _get_single_side_ext(system, nb_id, "X") if nb_id else L_self
            _draw_hat_bar(w, x0 - bw_mm/2, midy + offset_val, bw_mm, ch_ek_start, L_ext_left=L_nb, L_ext_right=L_self, axis="X", drawn_supports=drawn_supports)
                
        # Right
        if ch_ek_end and edge_cont.get("uzun_end"):
            L_self = _get_single_side_ext(system, sid, "X")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "R")
            L_nb = _get_single_side_ext(system, nb_id, "X") if nb_id else L_self
            _draw_hat_bar(w, x1 + bw_mm/2, midy + offset_val, bw_mm, ch_ek_end, L_ext_left=L_self, L_ext_right=L_nb, axis="X", drawn_supports=drawn_supports)


def export_to_dxf(system: SlabSystem, filename: str, design_cache: dict, bw_val: float,
                  real_slabs: dict = None):
    from twoway_slab import slab_edge_has_beam

    # KiriÅŸ olan kenarlara bw/2 ekle â†’ Lx = Lxnet + bw etkisi
    # ======================================================================
    # Ã‡izilmiÅŸ kiriÅŸleri ve mesnet donatÄ±larÄ±nÄ± takip et (mÃ¼kerrerliliÄŸi Ã¶nlemek iÃ§in)
    drawn_beams = set()
    drawn_supports = set()

    # Toplam YÃ¼ksekliÄŸi Hesapla (Y ekseni simetrisi iÃ§in)
    max_y_mm = 0.0
    if real_slabs:
        max_h = 0.0
        for rs in real_slabs.values():
            bottom = rs.y + rs.h
            if bottom > max_h:
                max_h = bottom
        max_y_mm = max_h * 1000.0
    else:
        # Fallback
        _, total_my = system.size_m_gross()
        max_y_mm = total_my * 1000.0

    # Margin ekle (isteÄŸe baÄŸlÄ±, ÅŸimdilik tam sÄ±nÄ±r)
    max_y_mm += 0.0 

    w = _DXFWriter(max_height=max_y_mm)
    
    # KatmanlarÄ± ekle
    # Renk KodlarÄ± (ACI): 1=Red, 2=Yellow, 3=Green, 4=Cyan, 5=Blue, 6=Magenta, 7=White
    layer_defs = [
        ("SLAB_EDGE", 7, 25),       # White, Thin
        ("BEAM", 7, 50),            # White, Thick (0.50mm)
        ("REB_MAIN_DUZ", 1, -3),    # Red
        ("REB_MAIN_PILYE", 1, -3),  # Red
        ("REB_DIST", 2, -3),        # Yellow
        ("REB_KENAR", 3, -3),       # Green
        ("REB_IC_MESNET", 5, -3),   # Blue
        ("REB_EK_MESNET", 4, -3),   # Cyan
        ("REB_BALCONY_MAIN", 6, -3),# Magenta
        ("REB_BALCONY_DIST", 30, -3),# Orange (30 is usually orange-ish)
        ("TEXT", 7, -3),
        ("DIM", 7, -3)
    ]
    
    for name, color, weight in layer_defs:
        w.add_layer(name, color=color, lineweight=weight)

    bw_mm = bw_val * 1000.0
    half = bw_mm / 2.0

    if not system.slabs:
        w.save(filename)
        return

    # DÃ¶ÅŸemeleri pozisyonuna gÃ¶re sÄ±rala (soldan saÄŸa)
    sorted_sids = sorted(system.slabs.keys(),
                         key=lambda sid: (system.slabs[sid].i0, system.slabs[sid].j0))

    for idx, sid in enumerate(sorted_sids):
        s = system.slabs[sid]
        Lx_m, Ly_m = s.size_m_gross()

        # Kenar kiriÅŸ durumlarÄ±nÄ± kontrol et
        if s.kind == "BALCONY":
            has_left = False
            has_right = False
            has_top = False
            has_bottom = False
        else:
            has_left = True
            has_right = True
            has_top = True
            has_bottom = True


            
        # =========================================================
        # Yeni MantÄ±k (KullanÄ±cÄ± Ä°steÄŸi):
        # Girdi Lx/Ly = Aks-aks mesafesi (brÃ¼t) kabul edilir.
        # Net dÃ¶ÅŸeme = BrÃ¼t - (varsa kiriÅŸ/2)
        # KiriÅŸler = Akslar Ã¼zerine oturtulur.
        # =========================================================
        
        # Grid hatlarÄ± (BrÃ¼t sÄ±nÄ±rlar) - mm cinsinden
        if real_slabs and sid in real_slabs:
            rs = real_slabs[sid]
            grid_x0 = rs.x * 1000.0
            grid_y0 = rs.y * 1000.0
            grid_x1 = grid_x0 + (rs.w * 1000.0)
            grid_y1 = grid_y0 + (rs.h * 1000.0)
        else:
            # Fallback (yan yana diz)
            # Bu modda Lx net kabul ediliyordu eskiden, ama tutarlÄ±lÄ±k iÃ§in
            # burayÄ± da brÃ¼t gibi dÃ¼ÅŸÃ¼nebiliriz veya olduÄŸu gibi bÄ±rakabiliriz.
            # Åimdilik basitÃ§e yan yana koyuyoruz.
            grid_x0 = idx * (Lx_m * 1000.0) 
            grid_y0 = 0.0
            grid_x1 = grid_x0 + (Lx_m * 1000.0)
            grid_y1 = grid_y0 + (Ly_m * 1000.0)

        # Net DÃ¶ÅŸeme KoordinatlarÄ± (Shrink)
        # KiriÅŸ olan kenarlardan iÃ§eri Ã§ek
        x0 = grid_x0 + (half if has_left else 0)
        y0 = grid_y0 + (half if has_top else 0)
        x1 = grid_x1 - (half if has_right else 0)
        y1 = grid_y1 - (half if has_bottom else 0)

        # DÃ¶ÅŸeme sÄ±nÄ±r Ã§izgisi
        w.add_polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                       layer="SLAB_EDGE", closed=True)

        # KiriÅŸleri Ã‡iz (Grid hatlarÄ± Ã¼zerine ortalanmÄ±ÅŸ)
        # Her kiriÅŸ, aks boyunca (grid_x/y) tam boyutta Ã§izilir.
        # KesiÅŸim noktalarÄ±nda Ã¼st Ã¼ste binmeleri saÄŸlamak iÃ§in uzatmalar (extensions) eklenir.
        
        ext_left = half if has_left else 0.0
        ext_right = half if has_right else 0.0
        ext_top = half if has_top else 0.0
        ext_bottom = half if has_bottom else 0.0

        if has_left:
            # Sol Dikey KiriÅŸ: grid_x0 Ã¼zerinde
            # YukarÄ± ve aÅŸaÄŸÄ± uzantÄ±lar: Top/Bottom kiriÅŸ varsa onlarÄ±n iÃ§ine kadar uzan
            # AslÄ±nda kÃ¶ÅŸe birleÅŸiminde "kimin Ã¼stte olduÄŸu" DXF'de Ã¶nemli deÄŸil,
            # sadece taranmÄ±ÅŸ alanÄ±n (hatch/solid) veya sÄ±nÄ±rlarÄ±n birleÅŸimi Ã¶nemli.
            # Biz polyline Ã§iziyoruz. KÃ¶ÅŸede L birleÅŸim varsa:
            # V-kiriÅŸ: [y0 - half, y1 + half] (eÄŸer Ã¼st/alt kiriÅŸ varsa)
            # H-kiriÅŸ: [x0 - half, x1 + half] (eÄŸer sol/saÄŸ kiriÅŸ varsa)
            # BÃ¶ylece (x0,y0) kÃ¶ÅŸesinde tam bir kare (w*w) Ã¶rtÃ¼ÅŸme olur.
            
            y_start = grid_y0 - ext_top
            y_end = grid_y1 + ext_bottom
            
            beam_key = ("V", round(grid_x0, 1), round(y_start, 1), round(y_end, 1))
            if beam_key not in drawn_beams:
                drawn_beams.add(beam_key)
                w.add_polyline([
                    (grid_x0 - half, y_start), (grid_x0 + half, y_start),
                    (grid_x0 + half, y_end), (grid_x0 - half, y_end)
                ], layer="BEAM", closed=True)

        if has_right:
            # SaÄŸ Dikey KiriÅŸ: grid_x1 Ã¼zerinde
            y_start = grid_y0 - ext_top
            y_end = grid_y1 + ext_bottom
            
            beam_key = ("V", round(grid_x1, 1), round(y_start, 1), round(y_end, 1))
            if beam_key not in drawn_beams:
                drawn_beams.add(beam_key)
                w.add_polyline([
                    (grid_x1 - half, y_start), (grid_x1 + half, y_start),
                    (grid_x1 + half, y_end), (grid_x1 - half, y_end)
                ], layer="BEAM", closed=True)

        if has_top:
            # Ãœst Yatay KiriÅŸ: grid_y0 Ã¼zerinde
            x_start = grid_x0 - ext_left
            x_end = grid_x1 + ext_right
            
            beam_key = ("H", round(x_start, 1), round(grid_y0, 1), round(x_end, 1))
            if beam_key not in drawn_beams:
                drawn_beams.add(beam_key)
                w.add_polyline([
                    (x_start, grid_y0 - half), (x_end, grid_y0 - half),
                    (x_end, grid_y0 + half), (x_start, grid_y0 + half)
                ], layer="BEAM", closed=True)

        if has_bottom:
            # Alt Yatay KiriÅŸ: grid_y1 Ã¼zerinde
            x_start = grid_x0 - ext_left
            x_end = grid_x1 + ext_right
            
            beam_key = ("H", round(x_start, 1), round(grid_y1, 1), round(x_end, 1))
            if beam_key not in drawn_beams:
                drawn_beams.add(beam_key)
                w.add_polyline([
                    (x_start, grid_y1 - half), (x_end, grid_y1 - half),
                    (x_end, grid_y1 + half), (x_start, grid_y1 + half)
                ], layer="BEAM", closed=True)

        # DÃ¶ÅŸeme ismi - saÄŸ alt kÃ¶ÅŸeye daha yakÄ±n (Ã§akÄ±ÅŸma iÃ§in yer deÄŸiÅŸtirildi)
        w.add_text(x0 + 150, y1 - 150, sid, height=150, layer="TEXT")

        dcache = design_cache.get(sid)
        if not dcache:
            continue

        kind = dcache.get("kind")

        if kind == "ONEWAY":
            _draw_oneway_reinforcement_detail(w, sid, s, dcache, x0, y0, x1, y1, bw_mm, slab_index=idx, system=system, drawn_supports=drawn_supports)

        elif kind == "TWOWAY":
            _draw_twoway_reinforcement_detail(w, sid, s, dcache, x0, y0, x1, y1, bw_mm, slab_index=idx, system=system, drawn_supports=drawn_supports)

        elif kind == "BALCONY":
            _draw_balcony_reinforcement_detail(w, sid, s, dcache, x0, y0, x1, y1, bw_mm, system=system, real_slabs=real_slabs, drawn_supports=drawn_supports)

    w.save(filename)


def _draw_twoway_reinforcement_detail(
    w: _DXFWriter,
    sid: str,
    s: Slab,
    dcache: dict,
    x0: float, y0: float, x1: float, y1: float,
    bw_mm: float,
    slab_index: int = 0,
    system: "SlabSystem" = None,
    drawn_supports: set = None
):
    """
    Ã‡ift doÄŸrultulu dÃ¶ÅŸeme iÃ§in detaylÄ± donatÄ± krokisi Ã§izer.
    Hem X hem Y yÃ¶nÃ¼nde ana donatÄ± (dÃ¼z + pilye) bulunur.
    """
    cover = float(dcache.get("cover_mm", 25.0))
    choices = dcache.get("choices", {})
    edge_cont = dcache.get("edge_continuity", {})

    # Ä°Ã§ sÄ±nÄ±rlar (pas payÄ± dÃ¼ÅŸÃ¼lmÃ¼ÅŸ)
    ix0, iy0, ix1, iy1 = x0 + cover, y0 + cover, x1 - cover, y1 - cover
    if ix1 <= ix0 or iy1 <= iy0:
        return

    Lx = ix1 - ix0
    Ly = iy1 - iy0
    midx = (ix0 + ix1) / 2.0
    midy = (iy0 + iy1) / 2.0

    # SÃ¼reklilik durumlarÄ± (True=SÃ¼rekli, False=SÃ¼reksiz)
    cont_L = edge_cont.get("L", False)
    cont_R = edge_cont.get("R", False)
    cont_T = edge_cont.get("T", False)
    cont_B = edge_cont.get("B", False)

    # Kanca uzunluÄŸu (dÃ¼z ve pilye iÃ§in aynÄ± kanca boyu)
    hook_len = bw_mm - 30.0 
    
    # KiriÅŸ iÃ§ine uzama (Staggered)
    beam_ext_pilye = bw_mm - 30.0
    beam_ext_duz = bw_mm - 30.0 - 50.0

    # =========================================================
    # 1. X YÃ–NÃœ DONATILARI (Yatay Ã‡izilenler)
    # =========================================================
    ch_x_duz = choices.get("x_span_duz")
    ch_x_pilye = choices.get("x_span_pilye")
    ch_x_ek = choices.get("x_support_extra")

    # Spacing hesapla (Offset iÃ§in)
    # DÃ¼z ve Pilye arasÄ± mesafe 's' kadar olsun. 
    sx = ch_x_pilye.s_mm if ch_x_pilye else 200.0
    if ch_x_duz: sx = ch_x_duz.s_mm
    
    # Y koordinatlarÄ±: Pilye Ã¼stte (+), DÃ¼z altta (-)
    # Zincir dÃ¶ÅŸemeler iÃ§in Â±350mm (35cm) stagger
    stagger_x = 400.0 if (slab_index % 2 == 0) else -400.0
    y_pilye_x = midy - (sx / 2.0) - 100 + stagger_x
    y_duz_x = midy + (sx / 2.0) + 100 + stagger_x

    # X YÃ¶nÃ¼ DÃ¼z DonatÄ±
    if ch_x_duz:
        pts = []
        # Sol (L)
        if cont_L:
            pts.append((x0 - beam_ext_duz, y_duz_x))
        else:
            # SÃ¼reksiz: Kanca AÅAÄI (DÃ¼z donatÄ±)
            pts.append((x0 - beam_ext_duz, y_duz_x - hook_len)) 
            pts.append((x0 - beam_ext_duz, y_duz_x))            
        
        # SaÄŸ (R)
        if cont_R:
            pts.append((x1 + beam_ext_duz, y_duz_x))
        else:
            # SÃ¼reksiz: Kanca AÅAÄI
            pts.append((x1 + beam_ext_duz, y_duz_x))            
            pts.append((x1 + beam_ext_duz, y_duz_x - hook_len)) 

        w.add_polyline(pts, layer="REB_MAIN_DUZ")
        # Label: Line AltÄ± (-30), BaÅŸlangÄ±Ã§tan (x0) Lx/6 saÄŸda
        w.add_text(midx, y_duz_x - 100, f"X duz {ch_x_duz.label()}", height=150, layer="TEXT", center=True)

    # X YÃ¶nÃ¼ Pilye DonatÄ±
    if ch_x_pilye:
        # Pilye kancalarÄ±: Pilye (Ã¼st), sÃ¼reksiz kenarda kanca AÅAÄI.
        pts = _pilye_polyline(x0, y_pilye_x, x1, y_pilye_x, d=200.0, kink="both", hook_len=hook_len, beam_ext=beam_ext_pilye, mirror=True)
        w.add_polyline(pts, layer="REB_MAIN_PILYE")
        # Label: Line ÃœstÃ¼ (+30), BaÅŸlangÄ±Ã§tan (x0) Lx/6 saÄŸda
        w.add_text(midx, y_pilye_x + 100, f"X pilye {ch_x_pilye.label()}", height=150, layer="TEXT", center=True)

    # X YÃ¶nÃ¼ Mesnet Ek DonatÄ±larÄ± (L ve R kenarlarÄ±)
    support_extra = choices.get("support_extra", {})
    
    for edge in ["L", "R"]:
        choice_ek = support_extra.get(edge)
        if not choice_ek:
            continue
            
        neighbor_id, _ = _get_neighbor_id_on_edge(system, sid, edge)
        L_self = _get_single_side_ext(system, sid, "X")
        L_nb = _get_single_side_ext(system, neighbor_id, "X") if neighbor_id else L_self
        
        # cx: KiriÅŸ merkezi
        if edge == "L":
            cx = x0 - (bw_mm / 2.0)
            le, re = L_nb, L_self  # Solda komÅŸu, saÄŸda self
        else: # R
            cx = x1 + (bw_mm / 2.0)
            le, re = L_self, L_nb  # Solda self, saÄŸda komÅŸu
        
        max_y_main = 0.0
        if ch_x_duz: max_y_main = max(max_y_main, abs(y_duz_x - midy))
        if ch_x_pilye: max_y_main = max(max_y_main, abs(y_pilye_x - midy))
        cy = midy + max_y_main + 2.0 * bw_mm
        
        _draw_hat_bar(w, cx, cy, bw_mm, choice_ek, L_ext_left=le, L_ext_right=re, axis="X", drawn_supports=drawn_supports)

    # ... (Y Ana DonatÄ±lar aynen devam eder) ...


    # =========================================================
    # 2. Y YÃ–NÃœ DONATILARI (Dikey Ã‡izilenler)
    # =========================================================
    ch_y_duz = choices.get("y_span_duz")
    ch_y_pilye = choices.get("y_span_pilye")

    # Spacing
    sy = ch_y_pilye.s_mm if ch_y_pilye else 200.0
    if ch_y_duz: sy = ch_y_duz.s_mm

    # X koordinatlarÄ± (Dikey Ã§izgiler iÃ§in)
    # Pilye SaÄŸda (+), DÃ¼z Solda (-)
    # Zincir dÃ¶ÅŸemeler iÃ§in Â±350mm (35cm) stagger
    stagger_y = 400.0 if (slab_index % 2 == 0) else -400.0
    x_pilye_y = midx - (sy / 2.0) - 100 + stagger_y
    x_duz_y = midx + (sy / 2.0) + 100 + stagger_y

    # Y YÃ¶nÃ¼ DÃ¼z DonatÄ±
    if ch_y_duz:
        pts = []
        # Ãœst (T)
        if cont_T:
            pts.append((x_duz_y, y0 - beam_ext_duz))
        else:
            # SÃ¼reksiz: Kanca Ä°Ã‡E (SOLA)
            pts.append((x_duz_y - hook_len, y0 - beam_ext_duz))
            pts.append((x_duz_y, y0 - beam_ext_duz))
        
        # Alt (B)
        if cont_B:
            pts.append((x_duz_y, y1 + beam_ext_duz))
        else:
            pts.append((x_duz_y, y1 + beam_ext_duz))
            pts.append((x_duz_y - hook_len, y1 + beam_ext_duz))

        w.add_polyline(pts, layer="REB_MAIN_DUZ")
        # Label: Line Solu (-100), BaÅŸlangÄ±Ã§tan (y0) Ly/6 aÅŸaÄŸÄ±da
        lbl_y = y0 + (Ly / 6.0)
        w.add_text(x_duz_y - 200, lbl_y, f"Y duz {ch_y_duz.label()}", height=150, layer="TEXT", rotation=90, center=True)

    # Y YÃ¶nÃ¼ Pilye DonatÄ±
    if ch_y_pilye:
        pts = _pilye_polyline(x_pilye_y, y0, x_pilye_y, y1, d=200.0, kink="both", hook_len=hook_len, beam_ext=beam_ext_pilye)
        w.add_polyline(pts, layer="REB_MAIN_PILYE")
        # Label: Line SaÄŸÄ± (+100), Ly/6
        lbl_y = y0 + (Ly / 6.0)
        w.add_text(x_pilye_y + 200, lbl_y, f"Y pilye {ch_y_pilye.label()}", height=150, layer="TEXT", rotation=90, center=True)

    # Y YÃ¶nÃ¼ Mesnet Ek DonatÄ±larÄ± (T ve B kenarlarÄ±)
    for edge in ["T", "B"]:
        choice_ek = support_extra.get(edge)
        if not choice_ek:
            continue
            
        neighbor_id, _ = _get_neighbor_id_on_edge(system, sid, edge)
        L_self = _get_single_side_ext(system, sid, "Y")
        L_nb = _get_single_side_ext(system, neighbor_id, "Y") if neighbor_id else L_self
        
        if edge == "T":
            cy = y0 - (bw_mm / 2.0)
            le, re = L_nb, L_self  # Ãœstte komÅŸu, altta self
        else: # B
            cy = y1 + (bw_mm / 2.0)
            le, re = L_self, L_nb  # Ãœstte self, altta komÅŸu
        
        max_x_main = 0.0
        if ch_y_duz: max_x_main = max(max_x_main, abs(x_duz_y - midx))
        if ch_y_pilye: max_x_main = max(max_x_main, abs(x_pilye_y - midx))
        cx = midx - (max_x_main + 2.0 * bw_mm)
        
        _draw_hat_bar(w, cx, cy, bw_mm, choice_ek, L_ext_left=le, L_ext_right=re, axis="Y", drawn_supports=drawn_supports)

    # DÃ¶ÅŸeme ID'si kaldÄ±rÄ±ldÄ± (kullanÄ±cÄ± isteÄŸi)


def _draw_support_extra_x(w, x_ref, y_ref, bw_mm, choice, Ln_long, is_left=True):
    """
    Mesnet Ek DonatÄ±sÄ± (Yatay) - 134Â° Pilyeli:
    - KiriÅŸ merkezinden baÅŸlar.
    - KiriÅŸ yÃ¼zÃ¼nden Ln/4 kadar dÃ¼z ilerler.
    - 134Â° pilye (46Â° kÄ±rÄ±lma) yapar.
    - Ln/8 kadar dÃ¼z uzar.
    - UÃ§ dÃ¼z biter (kanca yok).
    """
    half = bw_mm / 2.0
    L4 = Ln_long / 4.0   # Pilye kÄ±rÄ±lma noktasÄ± (kiriÅŸ yÃ¼zÃ¼nden itibaren)
    L8 = Ln_long / 8.0   # Pilye sonrasÄ± dÃ¼z uzatma
    d_crank = 200.0       # Pilye dikey bileÅŸeni
    # 134Â° aÃ§Ä± -> kÄ±rÄ±lma aÃ§Ä±sÄ± 46Â° -> yatay bileÅŸen = d / tan(46Â°)
    dx_crank = d_crank / math.tan(math.radians(46))
    
    pts = []
    if is_left:
        # Sol kenar (x_ref = x0, dÃ¶ÅŸeme yÃ¼zÃ¼)
        x_beam_center = x_ref - half
        # KiriÅŸ merkezi -> kiriÅŸ yÃ¼zÃ¼ -> Ln/4 dÃ¼z -> 134Â° pilye -> Ln/10 dÃ¼z
        pts = [
            (x_beam_center, y_ref),                              # KiriÅŸ merkezi
            (x_ref + L4, y_ref),                                 # Ln/4 dÃ¼z (kiriÅŸ yÃ¼zÃ¼nden)
            (x_ref + L4 + dx_crank, y_ref + d_crank),           # 134Â° pilye kÄ±rÄ±lma
            (x_ref + L4 + dx_crank + L10, y_ref + d_crank),      # Ln/10 dÃ¼z uzatma (dÃ¼z uÃ§)
        ]
    else:
        # SaÄŸ kenar (x_ref = x1, dÃ¶ÅŸeme yÃ¼zÃ¼)
        x_beam_center = x_ref + half
        # KiriÅŸ merkezi -> kiriÅŸ yÃ¼zÃ¼ -> Ln/4 dÃ¼z -> 134Â° pilye -> Ln/10 dÃ¼z
        pts = [
            (x_beam_center, y_ref),                              # KiriÅŸ merkezi
            (x_ref - L4, y_ref),                                 # Ln/4 dÃ¼z (kiriÅŸ yÃ¼zÃ¼nden)
            (x_ref - L4 - dx_crank, y_ref + d_crank),           # 134Â° pilye kÄ±rÄ±lma
            (x_ref - L4 - dx_crank - L10, y_ref + d_crank),      # Ln/10 dÃ¼z uzatma (dÃ¼z uÃ§)
        ]
    
    w.add_polyline(pts, layer="REB_EK_MESNET")
    # Label - 30mm above the flat part (y_ref or y_ref+d_crank depending on segment)
    # The label is usually for the part inside the slab.
    lbl_x = x_ref + (L4/2.0) if is_left else x_ref - (L4/2.0)
    w.add_text(lbl_x, y_ref + 100, f"Ek {choice.label()}", height=125, layer="TEXT", center=True)


def _draw_support_extra_y(w, x_ref, y_ref, bw_mm, choice, Ln_long, is_top=True):
    """
    Mesnet Ek DonatÄ±sÄ± (Dikey) - 134Â° Pilyeli:
    - KiriÅŸ merkezinden baÅŸlar.
    - KiriÅŸ yÃ¼zÃ¼nden Ln/4 kadar dÃ¼z ilerler.
    - 134Â° pilye (46Â° kÄ±rÄ±lma) yapar.
    - Ln/10 kadar dÃ¼z uzar.
    - UÃ§ dÃ¼z biter (kanca yok).
    """
    half = bw_mm / 2.0
    L4 = Ln_long / 4.0   # Pilye kÄ±rÄ±lma noktasÄ± (kiriÅŸ yÃ¼zÃ¼nden itibaren)
    L10 = Ln_long / 10.0 # Pilye sonrasÄ± dÃ¼z uzatma (tail length)
    d_crank = 200.0       # Pilye yatay bileÅŸeni (dikey donatÄ±da yatay kayma)
    # 134Â° aÃ§Ä± -> kÄ±rÄ±lma aÃ§Ä±sÄ± 46Â° -> dikey bileÅŸen = d / tan(46Â°)
    dy_crank = d_crank / math.tan(math.radians(46))
    
    pts = []
    if is_top:
        # Ãœst kenar (y_ref = y0, dÃ¶ÅŸeme yÃ¼zÃ¼)
        y_beam_center = y_ref - half
        # KiriÅŸ merkezi -> kiriÅŸ yÃ¼zÃ¼ -> Ln/4 dÃ¼z -> 134Â° pilye -> Ln/10 dÃ¼z
        pts = [
            (x_ref, y_beam_center),                              # KiriÅŸ merkezi
            (x_ref, y_ref + L4),                                 # Ln/4 dÃ¼z (kiriÅŸ yÃ¼zÃ¼nden)
            (x_ref + d_crank, y_ref + L4 + dy_crank),           # 134Â° pilye kÄ±rÄ±lma (Ters Ã§evrildi: +)
            (x_ref + d_crank, y_ref + L4 + dy_crank + L10),      # Ln/10 dÃ¼z uzatma (dÃ¼z uÃ§)
        ]
    else:
        # Alt kenar (y_ref = y1, dÃ¶ÅŸeme yÃ¼zÃ¼)
        y_beam_center = y_ref + half
        # KiriÅŸ merkezi -> kiriÅŸ yÃ¼zÃ¼ -> Ln/4 dÃ¼z -> 134Â° pilye -> Ln/10 dÃ¼z
        pts = [
            (x_ref, y_beam_center),                              # KiriÅŸ merkezi
            (x_ref, y_ref - L4),                                 # Ln/4 dÃ¼z (kiriÅŸ yÃ¼zÃ¼nden)
            (x_ref + d_crank, y_ref - L4 - dy_crank),           # 134Â° pilye kÄ±rÄ±lma (Ters Ã§evrildi: +)
            (x_ref + d_crank, y_ref - L4 - dy_crank - L10),      # Ln/10 dÃ¼z uzatma (dÃ¼z uÃ§)
        ]
    
    w.add_polyline(pts, layer="REB_EK_MESNET")
    lbl_y = y_ref + (L4/2.0) if is_top else y_ref - (L4/2.0)
    # Vertical Ek: text to the left now (-100) to avoid shifted line (+d_crank)
    w.add_text(x_ref - 200, lbl_y, f"Ek {choice.label()}", height=125, layer="TEXT", rotation=90, center=True)



def _draw_balcony_reinforcement_detail(
    w: _DXFWriter,
    sid: str,
    s: Slab,
    dcache: dict,
    x0: float, y0: float, x1: float, y1: float,
    bw_mm: float,
    system: "SlabSystem" = None,
    real_slabs: dict = None,
    drawn_supports: set = None
):
    """
    Balkon donatÄ±sÄ±:
    - Mesnet (sabit) kenarda komÅŸuya pilye ile uzanÄ±r (Ã¼st donatÄ±).
    - Serbest kenarda kanca yapar.
    - DaÄŸÄ±tma donatÄ±sÄ± diÄŸer yÃ¶nde, uÃ§larda kanca ile.
    """
    cover = float(dcache.get("cover_mm", 25.0))
    ix0, iy0, ix1, iy1 = x0 + cover, y0 + cover, x1 - cover, y1 - cover
    midx = (ix0 + ix1) / 2.0
    midy = (iy0 + iy1) / 2.0
    
    Lx = ix1 - ix0
    Ly = iy1 - iy0
    
    choices = dcache.get("choices", {})
    ch_main = choices.get("main")
    ch_dist = choices.get("dist")
    fixed = dcache.get("fixed_edge", "L") # Hangi kenar ankastre (bina tarafÄ±)

    beam_ext = bw_mm - 30.0
    hook_len = bw_mm - 30.0
    d_crank = 200.0   # Pilye kÄ±rÄ±lma yÃ¼ksekliÄŸi (plan gÃ¶rÃ¼nÃ¼ÅŸte offset)
    free_hook = 150.0  # Serbest uÃ§ kanca boyu

    # KomÅŸu dÃ¶ÅŸemenin Ln/5'ini hesapla (pilye kÄ±rÄ±lma noktasÄ±)
    L_anchor = 1000.0  # VarsayÄ±lan
    neighbor_id, _ = _get_neighbor_id_on_edge(system, sid, fixed)
    if neighbor_id and system and real_slabs and neighbor_id in real_slabs:
        rs_n = real_slabs[neighbor_id]
        if fixed in ("L", "R"):
            # KomÅŸunun X yÃ¶nÃ¼ net aÃ§Ä±klÄ±ÄŸÄ±
            neighbor_Ln = rs_n.w * 1000.0 - bw_mm
        else:
            # KomÅŸunun Y yÃ¶nÃ¼ net aÃ§Ä±klÄ±ÄŸÄ±
            neighbor_Ln = rs_n.h * 1000.0 - bw_mm
        if neighbor_Ln > 0:
            L_anchor = neighbor_Ln / 5.0

    # KomÅŸu dÃ¶ÅŸemenin Ln/10'unu hesapla (pilye kÄ±rÄ±ktan sonra dÃ¼z uzatma)
    Ln10 = L_anchor / 2.0  # Ln/5 / 2 = Ln/10

    # 1. ANA DONATI (ÃœST) - Tek pilye kÄ±rÄ±ÄŸÄ± komÅŸu dÃ¶ÅŸeme tarafÄ±nda,
    #    balkon iÃ§inde sadece kanca
    if ch_main:
        layer = "REB_BALCONY_MAIN"
        
        if fixed == "L":
            # Sol taraf sabit, SaÄŸ taraf serbest
            y_pos = midy - 3 * bw_mm
            # Serbest uÃ§ (saÄŸ) â†’ dÃ¼z â†’ sabit kenar (sol) â†’ Ln/5 komÅŸuya uzanma â†’
            # pilye kÄ±rÄ±ÄŸÄ± â†’ Ln/10 dÃ¼z uzatma
            pts = [
                (x1 - 50, y_pos + free_hook),                  # Serbest uÃ§ta kanca ucu
                (x1 - 50, y_pos),                              # Kanca dÃ¶nÃ¼ÅŸÃ¼
                (x0 - L_anchor, y_pos),                        # KomÅŸu iÃ§inde Ln/5 dÃ¼z
                (x0 - L_anchor - d_crank, y_pos + d_crank),    # 45Â° pilye kÄ±rÄ±ÄŸÄ±
                (x0 - L_anchor - d_crank - Ln10, y_pos + d_crank),  # KÄ±rÄ±ktan sonra Ln/10 dÃ¼z
            ]
            w.add_polyline(pts, layer=layer)
            w.add_text(x0 + (Lx / 6.0), y_pos + 100, f"Ana {ch_main.label()}", height=150, layer="TEXT")
            
            # DaÄŸÄ±tma (Dikey) - uÃ§larda kanca
            if ch_dist:
                x_dist = midx
                pts_dist = [
                    (x_dist + free_hook, iy0),   # Ãœst kenarda kanca (saÄŸa)
                    (x_dist, iy0),
                    (x_dist, iy1),
                    (x_dist + free_hook, iy1),   # Alt kenarda kanca (saÄŸa)
                ]
                w.add_polyline(pts_dist, layer="REB_BALCONY_DIST")
                w.add_text(x_dist + 150, iy0 + (Ly / 6.0), f"dagitma {ch_dist.label()}", height=125, layer="TEXT", rotation=90)

        elif fixed == "R":
            # SaÄŸ taraf sabit, Sol taraf serbest
            y_pos = midy - 3 * bw_mm
            # Serbest uÃ§ (sol) â†’ dÃ¼z â†’ sabit kenar (saÄŸ) â†’ Ln/5 komÅŸuya uzanma â†’
            # pilye kÄ±rÄ±ÄŸÄ± â†’ Ln/10 dÃ¼z uzatma
            pts = [
                (x0 + 50, y_pos + free_hook),                  # Serbest uÃ§ta kanca ucu
                (x0 + 50, y_pos),                              # Kanca dÃ¶nÃ¼ÅŸÃ¼
                (x1 + L_anchor, y_pos),                        # KomÅŸu iÃ§inde Ln/5 dÃ¼z
                (x1 + L_anchor + d_crank, y_pos + d_crank),    # 45Â° pilye kÄ±rÄ±ÄŸÄ±
                (x1 + L_anchor + d_crank + Ln10, y_pos + d_crank),  # KÄ±rÄ±ktan sonra Ln/10 dÃ¼z
            ]
            w.add_polyline(pts, layer=layer)
            w.add_text(x1 - (Lx / 6.0) - 100, y_pos + 100, f"Ana {ch_main.label()}", height=150, layer="TEXT")
            
            # DaÄŸÄ±tma (Dikey) - uÃ§larda kanca
            if ch_dist:
                x_dist = midx
                pts_dist = [
                    (x_dist + free_hook, iy0),
                    (x_dist, iy0),
                    (x_dist, iy1),
                    (x_dist + free_hook, iy1),
                ]
                w.add_polyline(pts_dist, layer="REB_BALCONY_DIST")
                w.add_text(x_dist + 150, iy0 + (Ly / 6.0), f"dagitma {ch_dist.label()}", height=125, layer="TEXT", rotation=90)

        elif fixed == "T":
            # Ãœst taraf sabit, Alt taraf serbest
            x_pos = midx - 3 * bw_mm
            # Serbest uÃ§ (alt) â†’ dÃ¼z â†’ sabit kenar (Ã¼st) â†’ Ln/5 komÅŸuya uzanma â†’
            # pilye kÄ±rÄ±ÄŸÄ± â†’ Ln/10 dÃ¼z uzatma
            pts = [
                (x_pos + free_hook, y1 - 50),                  # Serbest uÃ§ta kanca ucu
                (x_pos, y1 - 50),                              # Kanca dÃ¶nÃ¼ÅŸÃ¼
                (x_pos, y0 - L_anchor),                        # KomÅŸu iÃ§inde Ln/5 dÃ¼z
                (x_pos + d_crank, y0 - L_anchor - d_crank),    # 45Â° pilye kÄ±rÄ±ÄŸÄ±
                (x_pos + d_crank, y0 - L_anchor - d_crank - Ln10),  # KÄ±rÄ±ktan sonra Ln/10 dÃ¼z
            ]
            w.add_polyline(pts, layer=layer)
            w.add_text(x_pos + 100, y0 + (Ly / 6.0), f"Ana {ch_main.label()}", height=150, layer="TEXT", rotation=90)

            # DaÄŸÄ±tma (Yatay) - uÃ§larda kanca
            if ch_dist:
                y_dist = midy
                pts_dist = [
                    (ix0, y_dist + free_hook),   # Sol kenarda kanca (aÅŸaÄŸÄ± - ters)
                    (ix0, y_dist),
                    (ix1, y_dist),
                    (ix1, y_dist + free_hook),   # SaÄŸ kenarda kanca (aÅŸaÄŸÄ± - ters)
                ]
                w.add_polyline(pts_dist, layer="REB_BALCONY_DIST")
                w.add_text(ix0 + (Lx / 6.0), y_dist - 150, f"dagitma {ch_dist.label()}", height=125, layer="TEXT")

        elif fixed == "B":
            # Alt taraf sabit, Ãœst taraf serbest
            x_pos = midx - 3 * bw_mm
            # Serbest uÃ§ (Ã¼st) â†’ dÃ¼z â†’ sabit kenar (alt) â†’ Ln/5 komÅŸuya uzanma â†’
            # pilye kÄ±rÄ±ÄŸÄ± â†’ Ln/10 dÃ¼z uzatma
            pts = [
                (x_pos + free_hook, y0 + 50),                  # Serbest uÃ§ta kanca ucu
                (x_pos, y0 + 50),                              # Kanca dÃ¶nÃ¼ÅŸÃ¼
                (x_pos, y1 + L_anchor),                        # KomÅŸu iÃ§inde Ln/5 dÃ¼z
                (x_pos + d_crank, y1 + L_anchor + d_crank),    # 45Â° pilye kÄ±rÄ±ÄŸÄ±
                (x_pos + d_crank, y1 + L_anchor + d_crank + Ln10),  # KÄ±rÄ±ktan sonra Ln/10 dÃ¼z
            ]
            w.add_polyline(pts, layer=layer)
            w.add_text(x_pos + 100, y1 - (Ly/6.0) - 200, f"Ana {ch_main.label()}", height=150, layer="TEXT", rotation=90)

            # DaÄŸÄ±tma (Yatay) - uÃ§larda kanca
            if ch_dist:
                y_dist = midy
                pts_dist = [
                    (ix0, y_dist + free_hook),
                    (ix0, y_dist),
                    (ix1, y_dist),
                    (ix1, y_dist + free_hook),
                ]
                w.add_polyline(pts_dist, layer="REB_BALCONY_DIST")
                w.add_text(ix0 + (Lx / 6.0), y_dist - 150, f"dagitma {ch_dist.label()}", height=125, layer="TEXT")


def _get_neighbor_id_on_edge(system, sid, edge):
    """YardÄ±mcÄ±: Belirtilen kenardaki komÅŸunun ID'sini dÃ¶ndÃ¼rÃ¼r."""
    if not system: return None, None
    try:
        # twoway_slab.get_neighbor_on_edge_twoway fonksiyonunu kullanabiliriz
        # ama o fonksiyon sistem importu gerektirir.
        # Burada manuel yapalÄ±m veya sistemi kullanalÄ±m.
        # system.cell_owner vs.
        neigh_set = system.neighbor_slabs_on_side(sid, "X" if edge in "LR" else "Y", "START" if edge in "LT" else "END")
        # Genelde 1 komÅŸu vardÄ±r ama set dÃ¶ner. Ä°lkini alalÄ±m.
        if neigh_set:
            nid = list(neigh_set)[0]
            nkind = system.slabs[nid].kind
            return nid, nkind
    except:
        pass
    return None, None


def _draw_hat_bar(w, cx, cy, bw_mm, choice, L_ext_left, L_ext_right, axis="X", drawn_supports: set = None):
    """
    Hat (Pilye) Åeklinde Mesnet Ek DonatÄ±sÄ± Ã‡izer.
    
    TasarÄ±m:
    - Merkez (cx, cy) kiriÅŸ ekseni Ã¼zerindedir.
    - DonatÄ±, kiriÅŸin soluna/Ã¼stÃ¼ne ve saÄŸÄ±na/altÄ±na doÄŸru uzanÄ±r.
    - Åekil:
      - Sol/Ãœst Kuyruk (Tail)
      - Sol/Ãœst KÄ±rÄ±lma (Crank Up)
      - Sol/Ãœst DÃ¼z (Top - beam Ã¼stÃ¼)
      - SaÄŸ/Alt DÃ¼z (Top)
      - SaÄŸ/Alt KÄ±rÄ±lma (Crank Down)
      - SaÄŸ/Alt Kuyruk (Tail)
    
    Parametreler:
    - L_ext_left: Sol/Ãœst dÃ¶ÅŸemedeki DÃœZ kÄ±smÄ±n uzunluÄŸu (Lb/5)
    - L_ext_right: SaÄŸ/Alt dÃ¶ÅŸemedeki DÃœZ kÄ±smÄ±n uzunluÄŸu (Ln/5)
    - Kuyruklar: Lb/4 kadar uzatÄ±lÄ±r (sabit kabul veya parametrik).
    - d_crank: KÄ±rÄ±lma yÃ¼ksekliÄŸi (200mm)
    """
    if drawn_supports is not None:
        # Koordinat yuvarlama (100mm) ile yakÄ±n donatÄ±larÄ± birleÅŸtir
        key = (int(cx/100)*100, int(cy/100)*100, axis)
        if key in drawn_supports:
             return
        drawn_supports.add(key)
    
    d = 200.0  # Crank height/depth
    # Ln/4 * 0.4 = Ln/10. User requested Ln/10 tail length.
    tail_factor = 0.4 
    
    tail_left = L_ext_left * tail_factor
    tail_right = L_ext_right * tail_factor
    
    half = bw_mm / 2.0
    
    # Koordinatlar (Merkeze gÃ¶re)
    # Sol taraf (Left/Top)
    # DÃ¼z kÄ±sÄ±m bitiÅŸi (Start of Crank): Center - half - L_ext_left
    # Kuyruk baÅŸlangÄ±cÄ± (End of Crank): Start_Crank - d
    # Kuyruk ucu: End_Crank - tail_left
    
    pts = []
    
    if axis == "X":
        # Yatay Ã‡izim
        # Sol Taraf
        x_flat_start = cx - half - L_ext_left
        x_crank_end = x_flat_start - d
        x_tail_end = x_crank_end - tail_left
        
        # SaÄŸ Taraf
        x_flat_end = cx + half + L_ext_right
        x_crank_start_R = x_flat_end + d
        x_tail_end_R = x_crank_start_R + tail_right
        
        # Y koordinatlarÄ±
        # Ãœst (Flat kÄ±sÄ±m): cy (veya cy + offset?) -> Merkezde olsun
        # Alt (Kuyruklar): cy - d (AÅŸaÄŸÄ± kÄ±rÄ±lma) - User isteÄŸi: 45 derece
        
        # Noktalar (Soldan SaÄŸa)
        pts.append((x_tail_end, cy + d))        # Sol Kuyruk Ucu (YukarÄ±)
        pts.append((x_crank_end, cy + d))       # Sol KÄ±rÄ±lma Ãœst
        pts.append((x_flat_start, cy))          # Sol KÄ±rÄ±lma Alt
        pts.append((x_flat_end, cy))            # SaÄŸ KÄ±rÄ±lma Alt
        pts.append((x_crank_start_R, cy + d))   # SaÄŸ KÄ±rÄ±lma Ãœst
        pts.append((x_tail_end_R, cy + d))      # SaÄŸ Kuyruk Ucu (YukarÄ±)
        
        # Layer
        w.add_polyline(pts, layer="REB_EK_MESNET")
        
        # Text
        w.add_text(cx, cy + 100, f"Ek {choice.label()}", height=150, layer="TEXT", center=True)
        # Boyut Ã§izgisi eklenebilir
        
    else: # Axis Y (Dikey)
        # Dikey Ã‡izim (Y-axis down in GUI, but let's think logic)
        # Left arg -> Top (Smaller Y)
        # Right arg -> Bottom (Larger Y)
        
        # Ãœst Taraf (Top / Negative rel to center)
        y_flat_start = cy - half - L_ext_left
        y_crank_end = y_flat_start - d
        y_tail_end = y_crank_end - tail_left
        
        # Alt Taraf (Bottom / Positive rel to center)
        y_flat_end = cy + half + L_ext_right
        y_crank_start_B = y_flat_end + d
        y_tail_end_B = y_crank_start_B + tail_right
        
        # X koordinatlarÄ±
        # Flat (Center): cx
        # Tail (Offset): cx - d (Sola kÄ±rÄ±lma? veya SaÄŸa?)
        # Genelde pilye gÃ¶rÃ¼nÃ¼ÅŸÃ¼: Kesit gibi.
        # Plan gÃ¶rÃ¼nÃ¼ÅŸte: Pilye yatÄ±rÄ±lÄ±r.
        # Dikey donatÄ± pilyesi X yÃ¶nÃ¼nde kÄ±rÄ±lÄ±r.
        # SaÄŸa mÄ± sola mÄ±? 
        # Standart: SaÄŸa kÄ±r (cx + d)
        
        x_main = cx
        x_shifted = cx + d # SaÄŸa kÄ±rÄ±lmÄ±ÅŸ hali (Ters Ã§evrildi: +)
        
        # Noktalar (Ãœstten Alta)
        pts.append((x_shifted, y_tail_end))      # Ãœst Kuyruk Ucu
        pts.append((x_shifted, y_crank_end))     # Ãœst KÄ±rÄ±lma Alt
        pts.append((x_main, y_flat_start))       # Ãœst KÄ±rÄ±lma Ãœst
        pts.append((x_main, y_flat_end))         # Alt KÄ±rÄ±lma Ãœst
        pts.append((x_shifted, y_crank_start_B)) # Alt KÄ±rÄ±lma Alt
        pts.append((x_shifted, y_tail_end_B))    # Alt Kuyruk Ucu
        
        w.add_polyline(pts, layer="REB_EK_MESNET")
        w.add_text(x_main - 200, cy, f"Ek {choice.label()}", height=150, layer="TEXT", rotation=90, center=True)

