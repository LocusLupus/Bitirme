import math
import ezdxf
from typing import List, Tuple, Optional
from slab_model import SlabSystem, Slab

class _DXFWriter:
    """ezdxf kütüphanesi kullanarak DXF dosyası oluşturan sınıf."""
    
    def __init__(self, max_height=None):
        self.doc = ezdxf.new('R2010')  # AutoCAD 2010 formatı
        self.msp = self.doc.modelspace()
        self.layers_created = set()
        self.max_height = max_height

    def _fy(self, y):
        """Y koordinatını ters çevir (GUI -> DXF dönüşümü için)."""
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

        # pts listesi (x, y) tuple'larından oluşur
        new_pts = [(x, self._fy(y)) for x, y in pts]
        self.msp.add_lwpolyline(new_pts, dxfattribs={'layer': layer}, close=closed)

    def add_text(self, x, y, text, height=200.0, layer="TEXT", rotation=0.0, center=False, align_code=None):
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
# Donatı Çizim Yardımcı Fonksiyonları
# =========================================================

def _pilye_polyline(x0, y0, x1, y1, d=250.0, kink="both", hook_len=100.0, beam_ext=0.0, mirror=False):
    """
    Pilye çubuğu çizer:
    - Üst seviyede Ln/5 + beam_ext kadar düz gider (beam_ext kısmı kirişin içinde)
    - Ln/5 noktasında 45 derece kırılır
    - Alt seviyede düz devam eder
    - Uçlarda kiriş içine doğru kanca yapar
    
    kink parametresi:
    - "start": sol/alt tarafta kırılma
    - "end": sağ/üst tarafta kırılma
    - "both": her iki tarafta kırılma
    - "none": düz çubuk
    
    d: pilye kırılma yüksekliği (45 derece için dx=dy=d)
    hook_len: kanca uzunluğu (kiriş içine doğru)
    beam_ext: kiriş içine uzanma mesafesi (kanca kırılma noktası kirişin içinde olur)
    mirror: True ise pilye kırılma yönü ters çevrilir (aşağı→yukarı, sağa→sola)
    """
    kink = (kink or "both").lower()
    if kink not in ("start", "end", "both", "none"): kink = "both"
    
    # mirror: dik bileşenlerin işaretini çevir
    s = -1 if mirror else 1

    if abs(y1 - y0) < 1e-6:  # Horizontal bar (X yönünde)
        if x1 < x0: x0, x1 = x1, x0; flip = True
        else: flip = False
        
        L = abs(x1 - x0)
        if L < 1e-6 or kink == "none": return [(x0, y0), (x1, y0)]
        
        want_start = kink in ("start", "both")
        want_end = kink in ("end", "both")
        if flip: want_start, want_end = want_end, want_start
        
        # Ln/5 mesafesi (pilye kırılma noktası - kirişten uzaklık)
        Ln5 = L / 5.0
        
        pts = []
        
        if want_start:
            # Sol taraf: kanca kirişin içinde, beam_ext kadar sola uzanır
            pts.append((x0 - beam_ext, y0 - s * hook_len))  # Kanca ucu
            pts.append((x0 - beam_ext, y0))                  # Kanca dönüşü
            pts.append((x0 + Ln5 - d, y0))                   # Bar seviyesinde düz git
            pts.append((x0 + Ln5, y0 - s * d))               # 45 derece kırıl
        else:
            pts.append((x0, y0 - s * d))              # Offset seviyede başla
        
        if want_end:
            pts.append((x1 - Ln5, y0 - s * d))               # Offset seviyede düz kısım sonu
            pts.append((x1 - Ln5 + d, y0))                   # 45 derece bar seviyesine dön
            pts.append((x1 + beam_ext, y0))                   # Bar seviyesinde bit
            pts.append((x1 + beam_ext, y0 - s * hook_len))   # Kanca ucu
        else:
            pts.append((x1, y0 - s * d))              # Offset seviyede bit
        
        return pts
        
    else:  # Vertical bar (Y yönünde)
        if y1 < y0: y0, y1 = y1, y0; flip = True
        else: flip = False
        
        L = abs(y1 - y0)
        if L < 1e-6 or kink == "none": return [(x0, y0), (x0, y1)]
        
        want_start = kink in ("start", "both")
        want_end = kink in ("end", "both")
        if flip: want_start, want_end = want_end, want_start
        
        # Ln/5 mesafesi (pilye kırılma noktası - kirişten uzaklık)
        Ln5 = L / 5.0
        
        pts = []
        
        if want_start:
            # Alt taraf: kanca kirişin içinde
            pts.append((x0 + s * hook_len, y0 - beam_ext))  # Kanca ucu
            pts.append((x0, y0 - beam_ext))                  # Kanca dönüşü
            pts.append((x0, y0 + Ln5 - d))                   # Bar seviyesinde düz git
            pts.append((x0 + s * d, y0 + Ln5))               # 45 derece kırıl
        else:
            pts.append((x0 + s * d, y0))              # Offset seviyede başla
        
        if want_end:
            pts.append((x0 + s * d, y1 - Ln5))               # Offset seviyede düz kısım sonu
            pts.append((x0, y1 - Ln5 + d))                   # 45 derece bar seviyesine dön
            pts.append((x0, y1 + beam_ext))                   # Bar seviyesinde bit
            pts.append((x0 + s * hook_len, y1 + beam_ext))   # Kanca ucu
        else:
            pts.append((x0 + s * d, y1))              # Offset seviyede bit
        
        return pts


def _draw_straight_hit_polyline(x0, y0, x1, y1, ext, hook):
    """
    Düz donatı için kancalı çizim (Plan görünüşte sembolik).
    - Kiriş içine 'ext' kadar girer.
    - Sonra 90 derece 'hook' kadar kırılır.
    - Yön: 'Legs down' (negatif yön).
    """
    if abs(y1 - y0) < 1e-6: # Horizontal (X yönünde)
        if x1 < x0: x0, x1 = x1, x0
        # Legs down -> -Y yönünde kanca
        return [
            (x0 - ext, y0 - hook),
            (x0 - ext, y0),
            (x1 + ext, y0),
            (x1 + ext, y0 - hook)
        ]
    else: # Vertical (Y yönünde)
        if y1 < y0: y0, y1 = y1, y0
        # Legs down -> -X yönünde kanca (veya +X? Pilye çizimine uyumlu olsun)
        # Pilye vb. genelde sağa/sola kırılır. 
        # Referans "rotated 180 degrees" -> horizontal için bariz "aşağı".
        # Vertical için "negatif X" (sola) seçelim.
        return [
            (x0 - hook, y0 - ext),
            (x0, y0 - ext),
            (x0, y1 + ext),
            (x0 - hook, y1 + ext)
        ]



def _draw_dimension_line(w: _DXFWriter, x0, y0, x1, y1, label: str, offset=150.0, layer="DIM"):
    """Ölçü çizgisi çizer (çizgi + etiket)"""
    # Ana çizgi
    w.add_line(x0, y0, x1, y1, layer=layer)
    
    # Uç çizgiler (tick marks)
    if abs(y1 - y0) < 1e-6:  # Horizontal
        w.add_line(x0, y0 - 50, x0, y0 + 50, layer=layer)
        w.add_line(x1, y1 - 50, x1, y1 + 50, layer=layer)
        mid_x = (x0 + x1) / 2
        w.add_text(mid_x, y0 + offset, label, height=120, layer=layer)
    else:  # Vertical
        w.add_line(x0 - 50, y0, x0 + 50, y0, layer=layer)
        w.add_line(x1 - 50, y1, x1 + 50, y1, layer=layer)
        mid_y = (y0 + y1) / 2
        w.add_text(x0 + offset, mid_y, label, height=120, layer=layer, rotation=90)


def _draw_support_rebar_horizontal(w: _DXFWriter, x0, y0, x1, y1, count: int, layer: str, label: str = None, 
                                   hook_start=False, hook_end=False, hook_len=100.0):
    """
    Yatay mesnet donatısı çizer (birden fazla çizgi ile gösterir).
    hook_start: Sol uçta kanca (aşağı doğru)
    hook_end: Sağ uçta kanca (aşağı doğru)
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
        w.add_text(x0 - 50, mid_y, label, height=100, layer="TEXT", rotation=90)


def _draw_support_rebar_vertical(w: _DXFWriter, x0, y0, x1, y1, count: int, layer: str, label: str = None,
                                 hook_start=False, hook_end=False, hook_len=100.0):
    """
    Dikey mesnet donatısı çizer (birden fazla çizgi ile gösterir).
    hook_start: Üst uçta kanca (sola/ters yöne doğru - kullanıcı isteğine göre ayarlanabilir, şimdilik sol)
    hook_end: Alt uçta kanca (sola/ters yöne doğru)
    """
    if count < 1: count = 1
    if count > 5: count = 5
    
    dx = (x1 - x0) / (count + 1)
    
    for i in range(1, count + 1):
        x = x0 + i * dx
        pts = []
        # Dikeyde "start" üst (küçük y?), "end" alt (büyük y?)
        # Parametreler y0 (üst), y1 (alt) varsayımıyla:
        
        if hook_start:
            pts.append((x - hook_len, y0)) # Sola kıvrık
            pts.append((x, y0))
        else:
            pts.append((x, y0))
            
        if hook_end:
            pts.append((x, y1))
            pts.append((x - hook_len, y1)) # Sola kıvrık
        else:
            pts.append((x, y1))
            
        w.add_polyline(pts, layer=layer)
    
    if label:
        mid_x = (x0 + x1) / 2
        w.add_text(mid_x, y1 + 50, label, height=100, layer="TEXT")


# =========================================================
# Ek Donatı Yardımcıları (Ln/4 Kuralı)
# =========================================================

def _get_single_side_ext(system: SlabSystem, sid: str, axis: str) -> float:
    """
    Döşemenin belirtilen eksenindeki (Lx veya Ly) brüt açıklığının 1/4'ünü döndürür.
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
    system: SlabSystem = None # system eklendi
):
    """
    Tek doğrultulu döşeme için detaylı donatı krokisi çizer.
    """
    cover = float(dcache.get("cover_mm", 25.0))
    auto_dir = dcache.get("auto_dir", "X")
    choices = dcache.get("choices", {})
    edge_cont = dcache.get("edge_continuity", {})
    
    # İç sınırlar
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
    # Bu cont mantığı biraz karışık. En iyisi dcache'ten doğrudan alalım.
    # _draw_oneway call'unda dcache içindeki edge_continuity kullanılıyor.
    
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
            w.add_text(x_duz - 100, iy0 + Ly/6, f"duz {ch_duz.label()}", height=100, layer="TEXT", rotation=90)
        if ch_pilye:
            pts = _pilye_polyline(x_pilye, iy0, x_pilye, iy1, d=200.0, kink="both", hook_len=bw_mm, beam_ext=bw_mm, mirror=False)
            w.add_polyline(pts, layer="REB_MAIN_PILYE")
            w.add_text(x_pilye + 100, iy0 + Ly/6, f"pilye {ch_pilye.label()}", height=100, layer="TEXT", rotation=90)
            
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
            w.add_text(x0 + Lx/6, y_dist + 30, f"dagitma {ch_dist.label()}", height=100, layer="TEXT", center=True)

        # 3 & 4. Supports on L/R (Horizontal)
        y_k = midy - 1.5 * bw_mm
        # Left
        if ch_ic_start and edge_cont.get("kisa_start"): # Interior
            L_self = _get_single_side_ext(system, sid, "X")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "L")
            L_nb = _get_single_side_ext(system, nb_id, "X") if nb_id else L_self
            # Let's use _draw_hat_bar logic instead
            _draw_hat_bar(w, x0 - bw_mm/2, y_k, bw_mm, ch_ic_start, L_ext_left=L_nb, L_ext_right=L_self, axis="X")
        elif ch_kenar_start and not edge_cont.get("kisa_start"): # Edge
            L_self = _get_single_side_ext(system, sid, "X") # Ln/4
            L10 = L_self / 2.5 # (Ln/4) / 2.5 = Ln/10
            pts = [(x0 - hook_ext, y_k + bw_mm), (x0 - hook_ext, y_k), (ix0 + L_self - d_crank, y_k), (ix0 + L_self, y_k + d_crank), (ix0 + L_self + L10, y_k + d_crank)]
            w.add_polyline(pts, layer="REB_KENAR")
            w.add_text(x0 + L_self/2, y_k + 30, ch_kenar_start.label(), height=80, layer="TEXT", center=True)

        # Right
        if ch_ic_end and edge_cont.get("kisa_end"): # Interior
            L_self = _get_single_side_ext(system, sid, "X")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "R")
            L_nb = _get_single_side_ext(system, nb_id, "X") if nb_id else L_self
            _draw_hat_bar(w, x1 + bw_mm/2, y_k, bw_mm, ch_ic_end, L_ext_left=L_self, L_ext_right=L_nb, axis="X")
        elif ch_kenar_end and not edge_cont.get("kisa_end"): # Edge
            L_self = _get_single_side_ext(system, sid, "X") # Ln/4
            L10 = L_self / 2.5 # (Ln/4) / 2.5 = Ln/10
            pts = [(x1 + hook_ext, y_k + bw_mm), (x1 + hook_ext, y_k), (ix1 - L_self + d_crank, y_k), (ix1 - L_self, y_k + d_crank), (ix1 - L_self - L10, y_k + d_crank)]
            w.add_polyline(pts, layer="REB_KENAR")
            w.add_text(x1 - L_self/2, y_k + 30, ch_kenar_end.label(), height=80, layer="TEXT", center=True)

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
            _draw_hat_bar(w, midx + offset_val, y0 - bw_mm/2, bw_mm, ch_ek_start, L_ext_left=L_nb, L_ext_right=L_self, axis="Y")
        # Bottom
        if ch_ek_end and edge_cont.get("uzun_end"):
            L_self = _get_single_side_ext(system, sid, "Y")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "B")
            L_nb = _get_single_side_ext(system, nb_id, "Y") if nb_id else L_self
            _draw_hat_bar(w, midx + offset_val, y1 + bw_mm/2, bw_mm, ch_ek_end, L_ext_left=L_self, L_ext_right=L_nb, axis="Y")

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
            w.add_text(x0 + Lx/6, y_duz + 30, f"duz {ch_duz.label()}", height=100, layer="TEXT", center=True)
        if ch_pilye:
            pts = _pilye_polyline(ix0, y_pilye, ix1, y_pilye, d=200.0, kink="both", hook_len=bw_mm, beam_ext=bw_mm, mirror=True)
            w.add_polyline(pts, layer="REB_MAIN_PILYE")
            w.add_text(x0 + Lx/6, y_pilye + 30, f"pilye {ch_pilye.label()}", height=100, layer="TEXT", center=True)

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
            w.add_text(x_dist + 100, y0 + Ly/6, f"dagitma {ch_dist.label()}", height=100, layer="TEXT", rotation=90)

        # 3 & 4. Supports on T/B (Vertical)
        x_k = midx - 1.5 * bw_mm
        # Top
        if ch_ic_start and edge_cont.get("kisa_start"): # Interior
            L_self = _get_single_side_ext(system, sid, "Y")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "T")
            L_nb = _get_single_side_ext(system, nb_id, "Y") if nb_id else L_self
            _draw_hat_bar(w, x_k, y0 - bw_mm/2, bw_mm, ch_ic_start, L_ext_left=L_nb, L_ext_right=L_self, axis="Y")
        elif ch_kenar_start and not edge_cont.get("kisa_start"): # Edge
            L_self = _get_single_side_ext(system, sid, "Y") # Ln/4
            L10 = L_self / 2.5 # (Ln/4) / 2.5 = Ln/10
            pts = [(x_k + bw_mm, y0 - hook_ext), (x_k, y0 - hook_ext), (x_k, iy0 + L_self - d_crank), (x_k + d_crank, iy0 + L_self), (x_k + d_crank, iy0 + L_self + L10)]
            w.add_polyline(pts, layer="REB_KENAR")
            w.add_text(x_k - 100, y0 + L_self/2, ch_kenar_start.label(), height=80, layer="TEXT", rotation=90)
        # Bottom
        if ch_ic_end and edge_cont.get("kisa_end"): # Interior
            L_self = _get_single_side_ext(system, sid, "Y")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "B")
            L_nb = _get_single_side_ext(system, nb_id, "Y") if nb_id else L_self
            _draw_hat_bar(w, x_k, y1 + bw_mm/2, bw_mm, ch_ic_end, L_ext_left=L_self, L_ext_right=L_nb, axis="Y")
        elif ch_kenar_end and not edge_cont.get("kisa_end"): # Edge
            L_self = _get_single_side_ext(system, sid, "Y") # Ln/4
            L10 = L_self / 2.5 # (Ln/4) / 2.5 = Ln/10
            pts = [(x_k + bw_mm, y1 + hook_ext), (x_k, y1 + hook_ext), (x_k, iy1 - L_self + d_crank), (x_k + d_crank, iy1 - L_self), (x_k + d_crank, iy1 - L_self - L10)]
            w.add_polyline(pts, layer="REB_KENAR")
            w.add_text(x_k - 100, y1 - L_self/2, ch_kenar_end.label(), height=80, layer="TEXT", rotation=90)

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
            _draw_hat_bar(w, x0 - bw_mm/2, midy + offset_val, bw_mm, ch_ek_start, L_ext_left=L_nb, L_ext_right=L_self, axis="X")
                
        # Right
        if ch_ek_end and edge_cont.get("uzun_end"):
            L_self = _get_single_side_ext(system, sid, "X")
            nb_id, _ = _get_neighbor_id_on_edge(system, sid, "R")
            L_nb = _get_single_side_ext(system, nb_id, "X") if nb_id else L_self
            _draw_hat_bar(w, x1 + bw_mm/2, midy + offset_val, bw_mm, ch_ek_end, L_ext_left=L_self, L_ext_right=L_nb, axis="X")


def export_to_dxf(system: SlabSystem, filename: str, design_cache: dict, bw_val: float,
                  real_slabs: dict = None):
    from twoway_slab import slab_edge_has_beam

    # Kiriş olan kenarlara bw/2 ekle → Lx = Lxnet + bw etkisi
    # ======================================================================
    # Çizilmiş kirişleri takip et (aynı kirişi iki kez çizmemek için)
    drawn_beams = set()

    # Toplam Yüksekliği Hesapla (Y ekseni simetrisi için)
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

    # Margin ekle (isteğe bağlı, şimdilik tam sınır)
    max_y_mm += 0.0 

    w = _DXFWriter(max_height=max_y_mm)
    
    # Katmanları ekle
    # Renk Kodları (ACI): 1=Red, 2=Yellow, 3=Green, 4=Cyan, 5=Blue, 6=Magenta, 7=White
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

    # Döşemeleri pozisyonuna göre sırala (soldan sağa)
    sorted_sids = sorted(system.slabs.keys(),
                         key=lambda sid: (system.slabs[sid].i0, system.slabs[sid].j0))

    for idx, sid in enumerate(sorted_sids):
        s = system.slabs[sid]
        Lx_m, Ly_m = s.size_m_gross()

        # Kenar kiriş durumlarını kontrol et
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
        # Yeni Mantık (Kullanıcı İsteği):
        # Girdi Lx/Ly = Aks-aks mesafesi (brüt) kabul edilir.
        # Net döşeme = Brüt - (varsa kiriş/2)
        # Kirişler = Akslar üzerine oturtulur.
        # =========================================================
        
        # Grid hatları (Brüt sınırlar) - mm cinsinden
        if real_slabs and sid in real_slabs:
            rs = real_slabs[sid]
            grid_x0 = rs.x * 1000.0
            grid_y0 = rs.y * 1000.0
            grid_x1 = grid_x0 + (rs.w * 1000.0)
            grid_y1 = grid_y0 + (rs.h * 1000.0)
        else:
            # Fallback (yan yana diz)
            # Bu modda Lx net kabul ediliyordu eskiden, ama tutarlılık için
            # burayı da brüt gibi düşünebiliriz veya olduğu gibi bırakabiliriz.
            # Şimdilik basitçe yan yana koyuyoruz.
            grid_x0 = idx * (Lx_m * 1000.0) 
            grid_y0 = 0.0
            grid_x1 = grid_x0 + (Lx_m * 1000.0)
            grid_y1 = grid_y0 + (Ly_m * 1000.0)

        # Net Döşeme Koordinatları (Shrink)
        # Kiriş olan kenarlardan içeri çek
        x0 = grid_x0 + (half if has_left else 0)
        y0 = grid_y0 + (half if has_top else 0)
        x1 = grid_x1 - (half if has_right else 0)
        y1 = grid_y1 - (half if has_bottom else 0)

        # Döşeme sınır çizgisi
        w.add_polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                       layer="SLAB_EDGE", closed=True)

        # Kirişleri Çiz (Grid hatları üzerine ortalanmış)
        # Her kiriş, aks boyunca (grid_x/y) tam boyutta çizilir.
        # Kesişim noktalarında üst üste binmeleri sağlamak için uzatmalar (extensions) eklenir.
        
        ext_left = half if has_left else 0.0
        ext_right = half if has_right else 0.0
        ext_top = half if has_top else 0.0
        ext_bottom = half if has_bottom else 0.0

        if has_left:
            # Sol Dikey Kiriş: grid_x0 üzerinde
            # Yukarı ve aşağı uzantılar: Top/Bottom kiriş varsa onların içine kadar uzan
            # Aslında köşe birleşiminde "kimin üstte olduğu" DXF'de önemli değil,
            # sadece taranmış alanın (hatch/solid) veya sınırların birleşimi önemli.
            # Biz polyline çiziyoruz. Köşede L birleşim varsa:
            # V-kiriş: [y0 - half, y1 + half] (eğer üst/alt kiriş varsa)
            # H-kiriş: [x0 - half, x1 + half] (eğer sol/sağ kiriş varsa)
            # Böylece (x0,y0) köşesinde tam bir kare (w*w) örtüşme olur.
            
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
            # Sağ Dikey Kiriş: grid_x1 üzerinde
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
            # Üst Yatay Kiriş: grid_y0 üzerinde
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
            # Alt Yatay Kiriş: grid_y1 üzerinde
            x_start = grid_x0 - ext_left
            x_end = grid_x1 + ext_right
            
            beam_key = ("H", round(x_start, 1), round(grid_y1, 1), round(x_end, 1))
            if beam_key not in drawn_beams:
                drawn_beams.add(beam_key)
                w.add_polyline([
                    (x_start, grid_y1 - half), (x_end, grid_y1 - half),
                    (x_end, grid_y1 + half), (x_start, grid_y1 + half)
                ], layer="BEAM", closed=True)

        # Döşeme ismi - sol üst köşeden 50mm sağ, 100mm aşağı
        w.add_text(x0 + 50, y1 - 100, sid, height=125, layer="TEXT")

        dcache = design_cache.get(sid)
        if not dcache:
            continue

        kind = dcache.get("kind")

        if kind == "ONEWAY":
            _draw_oneway_reinforcement_detail(w, sid, s, dcache, x0, y0, x1, y1, bw_mm, slab_index=idx, system=system)

        elif kind == "TWOWAY":
            _draw_twoway_reinforcement_detail(w, sid, s, dcache, x0, y0, x1, y1, bw_mm, slab_index=idx, system=system)

        elif kind == "BALCONY":
            _draw_balcony_reinforcement_detail(w, sid, s, dcache, x0, y0, x1, y1, bw_mm, system=system, real_slabs=real_slabs)

    w.save(filename)


def _draw_twoway_reinforcement_detail(
    w: _DXFWriter,
    sid: str,
    s: Slab,
    dcache: dict,
    x0: float, y0: float, x1: float, y1: float,
    bw_mm: float,
    slab_index: int = 0,
    system: "SlabSystem" = None
):
    """
    Çift doğrultulu döşeme için detaylı donatı krokisi çizer.
    Hem X hem Y yönünde ana donatı (düz + pilye) bulunur.
    """
    cover = float(dcache.get("cover_mm", 25.0))
    choices = dcache.get("choices", {})
    edge_cont = dcache.get("edge_continuity", {})

    # İç sınırlar (pas payı düşülmüş)
    ix0, iy0, ix1, iy1 = x0 + cover, y0 + cover, x1 - cover, y1 - cover
    if ix1 <= ix0 or iy1 <= iy0:
        return

    Lx = ix1 - ix0
    Ly = iy1 - iy0
    midx = (ix0 + ix1) / 2.0
    midy = (iy0 + iy1) / 2.0

    # Süreklilik durumları (True=Sürekli, False=Süreksiz)
    cont_L = edge_cont.get("L", False)
    cont_R = edge_cont.get("R", False)
    cont_T = edge_cont.get("T", False)
    cont_B = edge_cont.get("B", False)

    # Kanca uzunluğu (düz ve pilye için aynı kanca boyu)
    hook_len = bw_mm - 30.0 
    
    # Kiriş içine uzama (Staggered)
    beam_ext_pilye = bw_mm - 30.0
    beam_ext_duz = bw_mm - 30.0 - 50.0

    # =========================================================
    # 1. X YÖNÜ DONATILARI (Yatay Çizilenler)
    # =========================================================
    ch_x_duz = choices.get("x_span_duz")
    ch_x_pilye = choices.get("x_span_pilye")
    ch_x_ek = choices.get("x_support_extra")

    # Spacing hesapla (Offset için)
    # Düz ve Pilye arası mesafe 's' kadar olsun. 
    sx = ch_x_pilye.s_mm if ch_x_pilye else 200.0
    if ch_x_duz: sx = ch_x_duz.s_mm
    
    # Y koordinatları: Pilye üstte (+), Düz altta (-)
    # Zincir döşemeler için ±350mm (35cm) stagger
    stagger_x = 400.0 if (slab_index % 2 == 0) else -400.0
    y_pilye_x = midy - (sx / 2.0) - 100 + stagger_x
    y_duz_x = midy + (sx / 2.0) + 100 + stagger_x

    # X Yönü Düz Donatı
    if ch_x_duz:
        pts = []
        # Sol (L)
        if cont_L:
            pts.append((x0 - beam_ext_duz, y_duz_x))
        else:
            # Süreksiz: Kanca AŞAĞI (Düz donatı)
            pts.append((x0 - beam_ext_duz, y_duz_x - hook_len)) 
            pts.append((x0 - beam_ext_duz, y_duz_x))            
        
        # Sağ (R)
        if cont_R:
            pts.append((x1 + beam_ext_duz, y_duz_x))
        else:
            # Süreksiz: Kanca AŞAĞI
            pts.append((x1 + beam_ext_duz, y_duz_x))            
            pts.append((x1 + beam_ext_duz, y_duz_x - hook_len)) 

        w.add_polyline(pts, layer="REB_MAIN_DUZ")
        # Label: Line Altı (-30), Başlangıçtan (x0) Lx/6 sağda
        w.add_text(x0 + (Lx / 6.0), y_duz_x - 30, f"X duz {ch_x_duz.label()}", height=100, layer="TEXT", center=True)

    # X Yönü Pilye Donatı
    if ch_x_pilye:
        # Pilye kancaları: Pilye (üst), süreksiz kenarda kanca AŞAĞI.
        pts = _pilye_polyline(x0, y_pilye_x, x1, y_pilye_x, d=200.0, kink="both", hook_len=hook_len, beam_ext=beam_ext_pilye, mirror=True)
        w.add_polyline(pts, layer="REB_MAIN_PILYE")
        # Label: Line Üstü (+30), Başlangıçtan (x0) Lx/6 sağda
        w.add_text(x0 + (Lx / 6.0), y_pilye_x + 30, f"X pilye {ch_x_pilye.label()}", height=100, layer="TEXT", center=True)

    # X Yönü Mesnet Ek Donatıları (L ve R kenarları)
    support_extra = choices.get("support_extra", {})
    
    for edge in ["L", "R"]:
        choice_ek = support_extra.get(edge)
        if not choice_ek:
            continue
            
        neighbor_id, _ = _get_neighbor_id_on_edge(system, sid, edge)
        L_self = _get_single_side_ext(system, sid, "X")
        L_nb = _get_single_side_ext(system, neighbor_id, "X") if neighbor_id else L_self
        
        # cx: Kiriş merkezi
        if edge == "L":
            cx = x0 - (bw_mm / 2.0)
            le, re = L_nb, L_self  # Solda komşu, sağda self
        else: # R
            cx = x1 + (bw_mm / 2.0)
            le, re = L_self, L_nb  # Solda self, sağda komşu
        
        max_y_main = 0.0
        if ch_x_duz: max_y_main = max(max_y_main, abs(y_duz_x - midy))
        if ch_x_pilye: max_y_main = max(max_y_main, abs(y_pilye_x - midy))
        cy = midy + max_y_main + 2.0 * bw_mm
        
        _draw_hat_bar(w, cx, cy, bw_mm, choice_ek, L_ext_left=le, L_ext_right=re, axis="X")

    # ... (Y Ana Donatılar aynen devam eder) ...


    # =========================================================
    # 2. Y YÖNÜ DONATILARI (Dikey Çizilenler)
    # =========================================================
    ch_y_duz = choices.get("y_span_duz")
    ch_y_pilye = choices.get("y_span_pilye")

    # Spacing
    sy = ch_y_pilye.s_mm if ch_y_pilye else 200.0
    if ch_y_duz: sy = ch_y_duz.s_mm

    # X koordinatları (Dikey çizgiler için)
    # Pilye Sağda (+), Düz Solda (-)
    # Zincir döşemeler için ±350mm (35cm) stagger
    stagger_y = 400.0 if (slab_index % 2 == 0) else -400.0
    x_pilye_y = midx - (sy / 2.0) - 100 + stagger_y
    x_duz_y = midx + (sy / 2.0) + 100 + stagger_y

    # Y Yönü Düz Donatı
    if ch_y_duz:
        pts = []
        # Üst (T)
        if cont_T:
            pts.append((x_duz_y, y0 - beam_ext_duz))
        else:
            # Süreksiz: Kanca İÇE (SOLA)
            pts.append((x_duz_y - hook_len, y0 - beam_ext_duz))
            pts.append((x_duz_y, y0 - beam_ext_duz))
        
        # Alt (B)
        if cont_B:
            pts.append((x_duz_y, y1 + beam_ext_duz))
        else:
            pts.append((x_duz_y, y1 + beam_ext_duz))
            pts.append((x_duz_y - hook_len, y1 + beam_ext_duz))

        w.add_polyline(pts, layer="REB_MAIN_DUZ")
        # Label: Line Solu (-100), Başlangıçtan (y0) Ly/6 aşağıda
        lbl_y = y0 + (Ly / 6.0)
        w.add_text(x_duz_y - 100, lbl_y, f"Y duz {ch_y_duz.label()}", height=100, layer="TEXT", rotation=90, center=True)

    # Y Yönü Pilye Donatı
    if ch_y_pilye:
        pts = _pilye_polyline(x_pilye_y, y0, x_pilye_y, y1, d=200.0, kink="both", hook_len=hook_len, beam_ext=beam_ext_pilye)
        w.add_polyline(pts, layer="REB_MAIN_PILYE")
        # Label: Line Sağı (+100), Ly/6
        lbl_y = y0 + (Ly / 6.0)
        w.add_text(x_pilye_y + 100, lbl_y, f"Y pilye {ch_y_pilye.label()}", height=100, layer="TEXT", rotation=90, center=True)

    # Y Yönü Mesnet Ek Donatıları (T ve B kenarları)
    for edge in ["T", "B"]:
        choice_ek = support_extra.get(edge)
        if not choice_ek:
            continue
            
        neighbor_id, _ = _get_neighbor_id_on_edge(system, sid, edge)
        L_self = _get_single_side_ext(system, sid, "Y")
        L_nb = _get_single_side_ext(system, neighbor_id, "Y") if neighbor_id else L_self
        
        if edge == "T":
            cy = y0 - (bw_mm / 2.0)
            le, re = L_nb, L_self  # Üstte komşu, altta self
        else: # B
            cy = y1 + (bw_mm / 2.0)
            le, re = L_self, L_nb  # Üstte self, altta komşu
        
        max_x_main = 0.0
        if ch_y_duz: max_x_main = max(max_x_main, abs(x_duz_y - midx))
        if ch_y_pilye: max_x_main = max(max_x_main, abs(x_pilye_y - midx))
        cx = midx - (max_x_main + 2.0 * bw_mm)
        
        _draw_hat_bar(w, cx, cy, bw_mm, choice_ek, L_ext_left=le, L_ext_right=re, axis="Y")

    # Döşeme ID'si kaldırıldı (kullanıcı isteği)


def _draw_support_extra_x(w, x_ref, y_ref, bw_mm, choice, Ln_long, is_left=True):
    """
    Mesnet Ek Donatısı (Yatay) - 134° Pilyeli:
    - Kiriş merkezinden başlar.
    - Kiriş yüzünden Ln/4 kadar düz ilerler.
    - 134° pilye (46° kırılma) yapar.
    - Ln/8 kadar düz uzar.
    - Uç düz biter (kanca yok).
    """
    half = bw_mm / 2.0
    L4 = Ln_long / 4.0   # Pilye kırılma noktası (kiriş yüzünden itibaren)
    L8 = Ln_long / 8.0   # Pilye sonrası düz uzatma
    d_crank = 200.0       # Pilye dikey bileşeni
    # 134° açı -> kırılma açısı 46° -> yatay bileşen = d / tan(46°)
    dx_crank = d_crank / math.tan(math.radians(46))
    
    pts = []
    if is_left:
        # Sol kenar (x_ref = x0, döşeme yüzü)
        x_beam_center = x_ref - half
        # Kiriş merkezi -> kiriş yüzü -> Ln/4 düz -> 134° pilye -> Ln/10 düz
        pts = [
            (x_beam_center, y_ref),                              # Kiriş merkezi
            (x_ref + L4, y_ref),                                 # Ln/4 düz (kiriş yüzünden)
            (x_ref + L4 + dx_crank, y_ref + d_crank),           # 134° pilye kırılma
            (x_ref + L4 + dx_crank + L10, y_ref + d_crank),      # Ln/10 düz uzatma (düz uç)
        ]
    else:
        # Sağ kenar (x_ref = x1, döşeme yüzü)
        x_beam_center = x_ref + half
        # Kiriş merkezi -> kiriş yüzü -> Ln/4 düz -> 134° pilye -> Ln/10 düz
        pts = [
            (x_beam_center, y_ref),                              # Kiriş merkezi
            (x_ref - L4, y_ref),                                 # Ln/4 düz (kiriş yüzünden)
            (x_ref - L4 - dx_crank, y_ref + d_crank),           # 134° pilye kırılma
            (x_ref - L4 - dx_crank - L10, y_ref + d_crank),      # Ln/10 düz uzatma (düz uç)
        ]
    
    w.add_polyline(pts, layer="REB_EK_MESNET")
    # Label - 30mm above the flat part (y_ref or y_ref+d_crank depending on segment)
    # The label is usually for the part inside the slab.
    lbl_x = x_ref + (L4/2.0) if is_left else x_ref - (L4/2.0)
    w.add_text(lbl_x, y_ref + 30, f"Ek {choice.label()}", height=80, layer="TEXT", center=True)


def _draw_support_extra_y(w, x_ref, y_ref, bw_mm, choice, Ln_long, is_top=True):
    """
    Mesnet Ek Donatısı (Dikey) - 134° Pilyeli:
    - Kiriş merkezinden başlar.
    - Kiriş yüzünden Ln/4 kadar düz ilerler.
    - 134° pilye (46° kırılma) yapar.
    - Ln/10 kadar düz uzar.
    - Uç düz biter (kanca yok).
    """
    half = bw_mm / 2.0
    L4 = Ln_long / 4.0   # Pilye kırılma noktası (kiriş yüzünden itibaren)
    L10 = Ln_long / 10.0 # Pilye sonrası düz uzatma (tail length)
    d_crank = 200.0       # Pilye yatay bileşeni (dikey donatıda yatay kayma)
    # 134° açı -> kırılma açısı 46° -> dikey bileşen = d / tan(46°)
    dy_crank = d_crank / math.tan(math.radians(46))
    
    pts = []
    if is_top:
        # Üst kenar (y_ref = y0, döşeme yüzü)
        y_beam_center = y_ref - half
        # Kiriş merkezi -> kiriş yüzü -> Ln/4 düz -> 134° pilye -> Ln/10 düz
        pts = [
            (x_ref, y_beam_center),                              # Kiriş merkezi
            (x_ref, y_ref + L4),                                 # Ln/4 düz (kiriş yüzünden)
            (x_ref + d_crank, y_ref + L4 + dy_crank),           # 134° pilye kırılma (Ters çevrildi: +)
            (x_ref + d_crank, y_ref + L4 + dy_crank + L10),      # Ln/10 düz uzatma (düz uç)
        ]
    else:
        # Alt kenar (y_ref = y1, döşeme yüzü)
        y_beam_center = y_ref + half
        # Kiriş merkezi -> kiriş yüzü -> Ln/4 düz -> 134° pilye -> Ln/10 düz
        pts = [
            (x_ref, y_beam_center),                              # Kiriş merkezi
            (x_ref, y_ref - L4),                                 # Ln/4 düz (kiriş yüzünden)
            (x_ref + d_crank, y_ref - L4 - dy_crank),           # 134° pilye kırılma (Ters çevrildi: +)
            (x_ref + d_crank, y_ref - L4 - dy_crank - L10),      # Ln/10 düz uzatma (düz uç)
        ]
    
    w.add_polyline(pts, layer="REB_EK_MESNET")
    lbl_y = y_ref + (L4/2.0) if is_top else y_ref - (L4/2.0)
    # Vertical Ek: text to the left now (-100) to avoid shifted line (+d_crank)
    w.add_text(x_ref - 100, lbl_y, f"Ek {choice.label()}", height=80, layer="TEXT", rotation=90, center=True)



def _draw_balcony_reinforcement_detail(
    w: _DXFWriter,
    sid: str,
    s: Slab,
    dcache: dict,
    x0: float, y0: float, x1: float, y1: float,
    bw_mm: float,
    system: "SlabSystem" = None,
    real_slabs: dict = None
):
    """
    Balkon donatısı:
    - Mesnet (sabit) kenarda komşuya pilye ile uzanır (üst donatı).
    - Serbest kenarda kanca yapar.
    - Dağıtma donatısı diğer yönde, uçlarda kanca ile.
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
    fixed = dcache.get("fixed_edge", "L") # Hangi kenar ankastre (bina tarafı)

    beam_ext = bw_mm - 30.0
    hook_len = bw_mm - 30.0
    d_crank = 200.0   # Pilye kırılma yüksekliği (plan görünüşte offset)
    free_hook = 150.0  # Serbest uç kanca boyu

    # Komşu döşemenin Ln/5'ini hesapla (pilye kırılma noktası)
    L_anchor = 1000.0  # Varsayılan
    neighbor_id, _ = _get_neighbor_id_on_edge(system, sid, fixed)
    if neighbor_id and system and real_slabs and neighbor_id in real_slabs:
        rs_n = real_slabs[neighbor_id]
        if fixed in ("L", "R"):
            # Komşunun X yönü net açıklığı
            neighbor_Ln = rs_n.w * 1000.0 - bw_mm
        else:
            # Komşunun Y yönü net açıklığı
            neighbor_Ln = rs_n.h * 1000.0 - bw_mm
        if neighbor_Ln > 0:
            L_anchor = neighbor_Ln / 5.0

    # Komşu döşemenin Ln/10'unu hesapla (pilye kırıktan sonra düz uzatma)
    Ln10 = L_anchor / 2.0  # Ln/5 / 2 = Ln/10

    # 1. ANA DONATI (ÜST) - Tek pilye kırığı komşu döşeme tarafında,
    #    balkon içinde sadece kanca
    if ch_main:
        layer = "REB_BALCONY_MAIN"
        
        if fixed == "L":
            # Sol taraf sabit, Sağ taraf serbest
            y_pos = midy - 3 * bw_mm
            # Serbest uç (sağ) → düz → sabit kenar (sol) → Ln/5 komşuya uzanma →
            # pilye kırığı → Ln/10 düz uzatma
            pts = [
                (x1 - 50, y_pos + free_hook),                  # Serbest uçta kanca ucu
                (x1 - 50, y_pos),                              # Kanca dönüşü
                (x0 - L_anchor, y_pos),                        # Komşu içinde Ln/5 düz
                (x0 - L_anchor - d_crank, y_pos + d_crank),    # 45° pilye kırığı
                (x0 - L_anchor - d_crank - Ln10, y_pos + d_crank),  # Kırıktan sonra Ln/10 düz
            ]
            w.add_polyline(pts, layer=layer)
            w.add_text(x0 + (Lx / 6.0), y_pos + 30, f"Ana {ch_main.label()}", height=100, layer="TEXT")
            
            # Dağıtma (Dikey) - uçlarda kanca
            if ch_dist:
                x_dist = midx
                pts_dist = [
                    (x_dist + free_hook, iy0),   # Üst kenarda kanca (sağa)
                    (x_dist, iy0),
                    (x_dist, iy1),
                    (x_dist + free_hook, iy1),   # Alt kenarda kanca (sağa)
                ]
                w.add_polyline(pts_dist, layer="REB_BALCONY_DIST")
                w.add_text(x_dist + 30, iy0 + (Ly / 6.0), f"dagitma {ch_dist.label()}", height=80, layer="TEXT", rotation=90)

        elif fixed == "R":
            # Sağ taraf sabit, Sol taraf serbest
            y_pos = midy - 3 * bw_mm
            # Serbest uç (sol) → düz → sabit kenar (sağ) → Ln/5 komşuya uzanma →
            # pilye kırığı → Ln/10 düz uzatma
            pts = [
                (x0 + 50, y_pos + free_hook),                  # Serbest uçta kanca ucu
                (x0 + 50, y_pos),                              # Kanca dönüşü
                (x1 + L_anchor, y_pos),                        # Komşu içinde Ln/5 düz
                (x1 + L_anchor + d_crank, y_pos + d_crank),    # 45° pilye kırığı
                (x1 + L_anchor + d_crank + Ln10, y_pos + d_crank),  # Kırıktan sonra Ln/10 düz
            ]
            w.add_polyline(pts, layer=layer)
            w.add_text(x1 - (Lx / 6.0) - 100, y_pos + 30, f"Ana {ch_main.label()}", height=100, layer="TEXT")
            
            # Dağıtma (Dikey) - uçlarda kanca
            if ch_dist:
                x_dist = midx
                pts_dist = [
                    (x_dist + free_hook, iy0),
                    (x_dist, iy0),
                    (x_dist, iy1),
                    (x_dist + free_hook, iy1),
                ]
                w.add_polyline(pts_dist, layer="REB_BALCONY_DIST")
                w.add_text(x_dist + 30, iy0 + (Ly / 6.0), f"dagitma {ch_dist.label()}", height=80, layer="TEXT", rotation=90)

        elif fixed == "T":
            # Üst taraf sabit, Alt taraf serbest
            x_pos = midx - 3 * bw_mm
            # Serbest uç (alt) → düz → sabit kenar (üst) → Ln/5 komşuya uzanma →
            # pilye kırığı → Ln/10 düz uzatma
            pts = [
                (x_pos + free_hook, y1 - 50),                  # Serbest uçta kanca ucu
                (x_pos, y1 - 50),                              # Kanca dönüşü
                (x_pos, y0 - L_anchor),                        # Komşu içinde Ln/5 düz
                (x_pos + d_crank, y0 - L_anchor - d_crank),    # 45° pilye kırığı
                (x_pos + d_crank, y0 - L_anchor - d_crank - Ln10),  # Kırıktan sonra Ln/10 düz
            ]
            w.add_polyline(pts, layer=layer)
            w.add_text(x_pos + 30, y0 + (Ly / 6.0), f"Ana {ch_main.label()}", height=100, layer="TEXT", rotation=90)

            # Dağıtma (Yatay) - uçlarda kanca
            if ch_dist:
                y_dist = midy
                pts_dist = [
                    (ix0, y_dist + free_hook),   # Sol kenarda kanca (aşağı - ters)
                    (ix0, y_dist),
                    (ix1, y_dist),
                    (ix1, y_dist + free_hook),   # Sağ kenarda kanca (aşağı - ters)
                ]
                w.add_polyline(pts_dist, layer="REB_BALCONY_DIST")
                w.add_text(ix0 + (Lx / 6.0), y_dist - 30, f"dagitma {ch_dist.label()}", height=80, layer="TEXT")

        elif fixed == "B":
            # Alt taraf sabit, Üst taraf serbest
            x_pos = midx - 3 * bw_mm
            # Serbest uç (üst) → düz → sabit kenar (alt) → Ln/5 komşuya uzanma →
            # pilye kırığı → Ln/10 düz uzatma
            pts = [
                (x_pos + free_hook, y0 + 50),                  # Serbest uçta kanca ucu
                (x_pos, y0 + 50),                              # Kanca dönüşü
                (x_pos, y1 + L_anchor),                        # Komşu içinde Ln/5 düz
                (x_pos + d_crank, y1 + L_anchor + d_crank),    # 45° pilye kırığı
                (x_pos + d_crank, y1 + L_anchor + d_crank + Ln10),  # Kırıktan sonra Ln/10 düz
            ]
            w.add_polyline(pts, layer=layer)
            w.add_text(x_pos + 30, y1 - (Ly/6.0) - 200, f"Ana {ch_main.label()}", height=100, layer="TEXT", rotation=90)

            # Dağıtma (Yatay) - uçlarda kanca
            if ch_dist:
                y_dist = midy
                pts_dist = [
                    (ix0, y_dist + free_hook),
                    (ix0, y_dist),
                    (ix1, y_dist),
                    (ix1, y_dist + free_hook),
                ]
                w.add_polyline(pts_dist, layer="REB_BALCONY_DIST")
                w.add_text(ix0 + (Lx / 6.0), y_dist - 30, f"dagitma {ch_dist.label()}", height=80, layer="TEXT")


def _get_neighbor_id_on_edge(system, sid, edge):
    """Yardımcı: Belirtilen kenardaki komşunun ID'sini döndürür."""
    if not system: return None, None
    try:
        # twoway_slab.get_neighbor_on_edge_twoway fonksiyonunu kullanabiliriz
        # ama o fonksiyon sistem importu gerektirir.
        # Burada manuel yapalım veya sistemi kullanalım.
        # system.cell_owner vs.
        neigh_set = system.neighbor_slabs_on_side(sid, "X" if edge in "LR" else "Y", "START" if edge in "LT" else "END")
        # Genelde 1 komşu vardır ama set döner. İlkini alalım.
        if neigh_set:
            nid = list(neigh_set)[0]
            nkind = system.slabs[nid].kind
            return nid, nkind
    except:
        pass
    return None, None


def _draw_hat_bar(w, cx, cy, bw_mm, choice, L_ext_left, L_ext_right, axis="X"):
    """
    Hat (Pilye) Şeklinde Mesnet Ek Donatısı Çizer.
    
    Tasarım:
    - Merkez (cx, cy) kiriş ekseni üzerindedir.
    - Donatı, kirişin soluna/üstüne ve sağına/altına doğru uzanır.
    - Şekil:
      - Sol/Üst Kuyruk (Tail)
      - Sol/Üst Kırılma (Crank Up)
      - Sol/Üst Düz (Top - beam üstü)
      - Sağ/Alt Düz (Top)
      - Sağ/Alt Kırılma (Crank Down)
      - Sağ/Alt Kuyruk (Tail)
    
    Parametreler:
    - L_ext_left: Sol/Üst döşemedeki DÜZ kısmın uzunluğu (Lb/5)
    - L_ext_right: Sağ/Alt döşemedeki DÜZ kısmın uzunluğu (Ln/5)
    - Kuyruklar: Lb/4 kadar uzatılır (sabit kabul veya parametrik).
    - d_crank: Kırılma yüksekliği (200mm)
    """
    
    d = 200.0  # Crank height/depth
    # Ln/4 * 0.4 = Ln/10. User requested Ln/10 tail length.
    tail_factor = 0.4 
    
    tail_left = L_ext_left * tail_factor
    tail_right = L_ext_right * tail_factor
    
    half = bw_mm / 2.0
    
    # Koordinatlar (Merkeze göre)
    # Sol taraf (Left/Top)
    # Düz kısım bitişi (Start of Crank): Center - half - L_ext_left
    # Kuyruk başlangıcı (End of Crank): Start_Crank - d
    # Kuyruk ucu: End_Crank - tail_left
    
    pts = []
    
    if axis == "X":
        # Yatay Çizim
        # Sol Taraf
        x_flat_start = cx - half - L_ext_left
        x_crank_end = x_flat_start - d
        x_tail_end = x_crank_end - tail_left
        
        # Sağ Taraf
        x_flat_end = cx + half + L_ext_right
        x_crank_start_R = x_flat_end + d
        x_tail_end_R = x_crank_start_R + tail_right
        
        # Y koordinatları
        # Üst (Flat kısım): cy (veya cy + offset?) -> Merkezde olsun
        # Alt (Kuyruklar): cy - d (Aşağı kırılma) - User isteği: 45 derece
        
        # Noktalar (Soldan Sağa)
        pts.append((x_tail_end, cy + d))        # Sol Kuyruk Ucu (Yukarı)
        pts.append((x_crank_end, cy + d))       # Sol Kırılma Üst
        pts.append((x_flat_start, cy))          # Sol Kırılma Alt
        pts.append((x_flat_end, cy))            # Sağ Kırılma Alt
        pts.append((x_crank_start_R, cy + d))   # Sağ Kırılma Üst
        pts.append((x_tail_end_R, cy + d))      # Sağ Kuyruk Ucu (Yukarı)
        
        # Layer
        w.add_polyline(pts, layer="REB_EK_MESNET")
        
        # Text
        w.add_text(cx, cy + 30, f"Ek {choice.label()}", height=100, layer="TEXT", center=True)
        # Boyut çizgisi eklenebilir
        
    else: # Axis Y (Dikey)
        # Dikey Çizim (Y-axis down in GUI, but let's think logic)
        # Left arg -> Top (Smaller Y)
        # Right arg -> Bottom (Larger Y)
        
        # Üst Taraf (Top / Negative rel to center)
        y_flat_start = cy - half - L_ext_left
        y_crank_end = y_flat_start - d
        y_tail_end = y_crank_end - tail_left
        
        # Alt Taraf (Bottom / Positive rel to center)
        y_flat_end = cy + half + L_ext_right
        y_crank_start_B = y_flat_end + d
        y_tail_end_B = y_crank_start_B + tail_right
        
        # X koordinatları
        # Flat (Center): cx
        # Tail (Offset): cx - d (Sola kırılma? veya Sağa?)
        # Genelde pilye görünüşü: Kesit gibi.
        # Plan görünüşte: Pilye yatırılır.
        # Dikey donatı pilyesi X yönünde kırılır.
        # Sağa mı sola mı? 
        # Standart: Sağa kır (cx + d)
        
        x_main = cx
        x_shifted = cx + d # Sağa kırılmış hali (Ters çevrildi: +)
        
        # Noktalar (Üstten Alta)
        pts.append((x_shifted, y_tail_end))      # Üst Kuyruk Ucu
        pts.append((x_shifted, y_crank_end))     # Üst Kırılma Alt
        pts.append((x_main, y_flat_start))       # Üst Kırılma Üst
        pts.append((x_main, y_flat_end))         # Alt Kırılma Üst
        pts.append((x_shifted, y_crank_start_B)) # Alt Kırılma Alt
        pts.append((x_shifted, y_tail_end_B))    # Alt Kuyruk Ucu
        
        w.add_polyline(pts, layer="REB_EK_MESNET")
        w.add_text(x_main - 100, cy, f"Ek {choice.label()}", height=100, layer="TEXT", rotation=90, center=True)
