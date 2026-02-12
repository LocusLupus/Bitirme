
def _draw_twoway_reinforcement_detail(
    w: _DXFWriter,
    sid: str,
    s: Slab,
    dcache: dict,
    x0: float, y0: float, x1: float, y1: float,
    bw_mm: float,
    slab_index: int = 0
):
    """
    Çift doğrultulu döşeme için detaylı donatı krokisi çizer.
    Hem X hem Y yönünde ana donatı (düz + pilye) bulunur.
    """
    cover = float(dcache.get("cover_mm", 25.0))
    choices = dcache.get("choices", {})
    # twoway_slab.py içinde "edge_continuity" eklenmiş olmalı
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

    # Kanca uzunluğu ve kiriş içine uzama
    hook_len = bw_mm - 30.0 # Kiriş içinde kanca boyu
    beam_ext = bw_mm # Kiriş içine düz uzama miktarı

    # =========================================================
    # 1. X YÖNÜ DONATILARI (Yatay Çizilenler)
    # =========================================================
    ch_x_duz = choices.get("x_span_duz")
    ch_x_pilye = choices.get("x_span_pilye")
    ch_x_ek = choices.get("x_support_extra")

    # X Yönü Düz Donatı
    if ch_x_duz:
        # Tek bir temsilci çubuk çizelim (ortanın biraz altı)
        y_pos = midy - 150.0
        pts = []
        
        # Sol taraf (L)
        if cont_L:
            # Sürekli: Düz devam et (kiriş içine)
            pts.append((x0 - beam_ext, y_pos))
        else:
            # Süreksiz: Kanca YUKARI (Düz donatı altta olduğu için kanca yukarı döner)
            pts.append((x0 - beam_ext, y_pos + hook_len)) # Kanca ucu
            pts.append((x0 - beam_ext, y_pos))            # Kiriş içi dönüş
        
        # Sağ taraf (R)
        if cont_R:
            # Sürekli: Düz devam et
            pts.append((x1 + beam_ext, y_pos))
        else:
            # Süreksiz: Kanca YUKARI
            pts.append((x1 + beam_ext, y_pos))            # Kiriş içi dönüş
            pts.append((x1 + beam_ext, y_pos + hook_len)) # Kanca ucu

        w.add_polyline(pts, layer="REB_DUZ")
        w.add_text(midx, y_pos + 10, f"X düz {ch_x_duz.label()}", height=100, layer="TEXT", center=True)

    # X Yönü Pilye Donatı
    if ch_x_pilye:
        y_pos = midy
        # Pilye kancaları: Pilye uçları üstte biter.
        # Süreksiz kenarda üst donatı kancası AŞAĞI (kiriş içine) döner.
        
        # Kırılma tipi belirle
        # Sol taraf: Sürekli ise kırılmaz (komşuya geçer), süreksiz ise kırılır (mesnet olur)
        # Ancak pilye mantığı biraz farklı:
        # Pilye her açıklıkta mutlaka kırılır ve üste çıkar.
        # Komşu sürekli ise üstten devam eder.
        # Komşu süreksiz ise üstte kanca yapar (aşağı).
        # _pilye_polyline fonksiyonu "kink" parametresi ile sadece şekli (kırılmayı) yönetiyor.
        # Kanca yönlerini manuel ayarlamamız gerekebilir veya _pilye_polyline'i güncelledik.
        
        # _pilye_polyline varsayılanı:
        # Horizontal bar:
        # want_start (sol): kanca (x0-ext, y0-hook) -> (x0-ext, y0) ...
        # Burada y0-hook "aşağı" demek. Bizim istediğimiz de bu (üstten aşağı).
        # Yani Pilye kancası varsayılan olarak aşağı doğru.
        # Ancak beam_ext kontrolü önemli.
        
        # Kink mantığı: 
        # "both": Her iki uçta da yukarı kırılır. Standart pilye.
        pts = _pilye_polyline(x0, y_pos, x1, y_pos, d=200.0, kink="both", hook_len=hook_len, beam_ext=beam_ext)
        w.add_polyline(pts, layer="REB_PILYE")
        w.add_text(midx, y_pos - 60, f"X pilye {ch_x_pilye.label()}", height=100, layer="TEXT", center=True)

    # X Yönü Mesnet Ek (Varsa)
    if ch_x_ek:
        # Bu genelde sürekli kenarlarda olur.
        # Sol (L) Sürekli ise
        if cont_L:
             _draw_support_extra_x(w, x0, midy + 300, bw_mm, ch_x_ek, is_left=True)
        # Sağ (R) Sürekli ise
        if cont_R:
             _draw_support_extra_x(w, x1, midy + 300, bw_mm, ch_x_ek, is_left=False)


    # =========================================================
    # 2. Y YÖNÜ DONATILARI (Dikey Çizilenler)
    # =========================================================
    ch_y_duz = choices.get("y_span_duz")
    ch_y_pilye = choices.get("y_span_pilye")
    ch_y_ek = choices.get("y_support_extra")

    # Y Yönü Düz Donatı
    if ch_y_duz:
        x_pos = midx + 150.0
        pts = []
        
        # Üst taraf (T) - Y0
        if cont_T:
            pts.append((x_pos, y0 - beam_ext))
        else:
            # Süreksiz: Kanca YUKARI?? Hayır.
            # Dikey çizimde "yukarı/aşağı" kavramı "sola/sağa" kanca olur.
            # Düz donatı "altta". Kanca "içe" doğru kıvrılmalı.
            # Kesit görünüşte kanca yukarı. Plan görünüşte?
            # Standart: Düz donatı kancası 135 veya 180 derece kıvrılır veya 90 derece yukarı.
            # Planda gösterim: Genelde kanca sembolü kullanılır.
            # _draw_straight_hit_polyline fonksiyonu "Sol" (-X) yönüne kanca yapıyordu.
            # Biz bunu "REB_DUZ" layerında kullanıyoruz.
            # Eğer bu üstte (Y0) ise ve kanca yapacaksak:
            # (x_pos, y0-beam_ext) -> return (hook). 
            # Kanca yönü: Sola (-X) yapalım.
            pts.append((x_pos - hook_len, y0 - beam_ext))
            pts.append((x_pos, y0 - beam_ext))
        
        # Alt taraf (B) - Y1
        if cont_B:
            pts.append((x_pos, y1 + beam_ext))
        else:
            pts.append((x_pos, y1 + beam_ext))
            pts.append((x_pos - hook_len, y1 + beam_ext))

        w.add_polyline(pts, layer="REB_DUZ")
        w.add_text(x_pos - 30, midy, f"Y düz {ch_y_duz.label()}", height=100, layer="TEXT", rotation=90, center=True)

    # Y Yönü Pilye Donatı
    if ch_y_pilye:
        x_pos = midx
        # Vertical pilye:
        # _pilye_polyline dikey modda çalışır.
        # want_start (üst/y0): kanca (x0+hook, y0-beam_ext) -> (x0, y0-beam_ext)
        # Burada x0+hook "sağa" demek.
        # Pilye üstte olduğu için kanca aşağı (döşeme içine) girmeli.
        # Planda "aşağı"yı "sağa" veya "sola" yatırarak gösteririz.
        # Genelde pilye kancaları "zıt" yöne bakar.
        # _pilye_polyline:
        # Start (Üst): (x+hook, y-ext) -> (x, y-ext). Kanca ucu SAĞDA.
        # End (Alt): (x, y+ext) -> (x+hook, y+ext). Kanca ucu SAĞDA.
        # Bu tutarlı.
        pts = _pilye_polyline(x_pos, y0, x_pos, y1, d=200.0, kink="both", hook_len=hook_len, beam_ext=beam_ext)
        w.add_polyline(pts, layer="REB_PILYE")
        w.add_text(x_pos + 60, midy, f"Y pilye {ch_y_pilye.label()}", height=100, layer="TEXT", rotation=90, center=True)

    # Y Yönü Mesnet Ek
    if ch_y_ek:
        if cont_T:
            _draw_support_extra_y(w, midx - 300, y0, bw_mm, ch_y_ek, is_top=True)
        if cont_B:
            _draw_support_extra_y(w, midx - 300, y1, bw_mm, ch_y_ek, is_top=False)

    w.add_text(midx, midy, sid, height=150, layer="TEXT", center=True)


def _draw_support_extra_x(w, x_ref, y_ref, bw_mm, choice, is_left=True):
    L_stub = 800.0 # Temsili boy
    d_crank = 200.0
    pts = []
    if is_left:
        # Sol mesnetten sağa doğru
        x_start = x_ref - bw_mm/2
        pts = [(x_start, y_ref), (x_start + L_stub, y_ref), 
               (x_start + L_stub + d_crank, y_ref - d_crank),
               (x_start + L_stub + d_crank + 200, y_ref - d_crank)]
    else:
        # Sağ mesnetten sola doğru
        x_start = x_ref + bw_mm/2
        pts = [(x_start, y_ref), (x_start - L_stub, y_ref),
               (x_start - L_stub - d_crank, y_ref - d_crank),
               (x_start - L_stub - d_crank - 200, y_ref - d_crank)]
    
    w.add_polyline(pts, layer="REB_EK_MESNET")
    w.add_text(x_start, y_ref + 20, f"Ek {choice.label()}", height=80, layer="TEXT", center=True)


def _draw_support_extra_y(w, x_ref, y_ref, bw_mm, choice, is_top=True):
    L_stub = 800.0
    d_crank = 200.0
    pts = []
    if is_top:
        y_start = y_ref - bw_mm/2
        pts = [(x_ref, y_start), (x_ref, y_start + L_stub),
               (x_ref - d_crank, y_start + L_stub + d_crank),
               (x_ref - d_crank, y_start + L_stub + d_crank + 200)]
    else:
        y_start = y_ref + bw_mm/2
        pts = [(x_ref, y_start), (x_ref, y_start - L_stub),
               (x_ref - d_crank, y_start - L_stub - d_crank),
               (x_ref - d_crank, y_start - L_stub - d_crank - 200)]
    
    w.add_polyline(pts, layer="REB_EK_MESNET")
    w.add_text(x_ref + 20, y_start, f"Ek {choice.label()}", height=80, layer="TEXT", rotation=90, center=True)


def _draw_balcony_reinforcement_detail(
    w: _DXFWriter,
    sid: str,
    s: Slab,
    dcache: dict,
    x0: float, y0: float, x1: float, y1: float,
    bw_mm: float
):
    """
    Balkon donatısı:
    - Mesnet (sabit) kenarda komşuya uzanır (üst donatı).
    - Serbest kenarda kanca yapar (AŞAĞI).
    - Dağıtma donatısı diğer yönde.
    """
    cover = float(dcache.get("cover_mm", 25.0))
    ix0, iy0, ix1, iy1 = x0 + cover, y0 + cover, x1 - cover, y1 - cover
    midx = (ix0 + ix1) / 2.0
    midy = (iy0 + iy1) / 2.0
    
    choices = dcache.get("choices", {})
    ch_main = choices.get("main")
    ch_dist = choices.get("dist")
    fixed = dcache.get("fixed_edge", "L") # Hangi kenar ankastre (bina tarafı)

    beam_ext = bw_mm
    hook_len = bw_mm - 30.0
    L_anchor = 1000.0 # Komşuya uzama boyu (temsili)

    # 1. ANA DONATI (ÜST)
    if ch_main:
        pts = []
        layer = "REB_SUPPORT"
        lbl_rot = 0
        lbl_pos = (midx, midy)

        if fixed == "L":
            # Sol taraf sabit, Sağ taraf serbest
            # Solda komşuya uzan (düz)
            # Sağda kanca AŞAĞI
            y_pos = midy
            pts.append((x0 - L_anchor, y_pos)) # Komşu içi
            pts.append((x1 + beam_ext, y_pos)) # Sağ uç (kiriş/döşeme ucu)
            pts.append((x1 + beam_ext, y_pos + hook_len)) # Kanca AŞAĞI (Y artıyor -> ekran koordinatında aşağı)
            
            w.add_polyline(pts, layer=layer)
            w.add_text(midx, y_pos - 20, f"Ana {ch_main.label()}", height=100, layer="TEXT", center=True)
            
            # Dağıtma (Dikey)
            if ch_dist:
                count = 3
                dx = (x1 - x0) / (count + 1)
                for i in range(1, count + 1):
                    xi = x0 + i * dx
                    # Düz çubuk
                    w.add_line(xi, iy0, xi, iy1, layer="REB_DIST")
                w.add_text(midx, midy + 100, f"Dağ. {ch_dist.label()}", height=80, layer="TEXT", center=True)

        elif fixed == "R":
            # Sağ taraf sabit, Sol taraf serbest
            y_pos = midy
            pts.append((x1 + L_anchor, y_pos)) # Komşu içi
            pts.append((x0 - beam_ext, y_pos)) # Sol uç
            pts.append((x0 - beam_ext, y_pos + hook_len)) # Kanca AŞAĞI
            
            w.add_polyline(pts, layer=layer)
            w.add_text(midx, y_pos - 20, f"Ana {ch_main.label()}", height=100, layer="TEXT", center=True)
             # Dağıtma (Dikey)
            if ch_dist:
                count = 3
                dx = (x1 - x0) / (count + 1)
                for i in range(1, count + 1):
                    xi = x0 + i * dx
                    w.add_line(xi, iy0, xi, iy1, layer="REB_DIST")

        elif fixed == "T":
            # Üst taraf sabit, Alt taraf serbest
            x_pos = midx
            pts.append((x_pos, y0 - L_anchor)) # Komşu içi (Yukarı)
            pts.append((x_pos, y1 + beam_ext)) # Alt uç
            # Vertical çizimde kanca "Sağa" kıvrılsın (Aşağı temsili)
            pts.append((x_pos + hook_len, y1 + beam_ext)) 
            
            w.add_polyline(pts, layer=layer)
            w.add_text(x_pos + 20, midy, f"Ana {ch_main.label()}", height=100, layer="TEXT", rotation=90, center=True)

            # Dağıtma (Yatay)
            if ch_dist:
                count = 3
                dy = (y1 - y0) / (count + 1)
                for i in range(1, count + 1):
                    yi = y0 + i * dy
                    w.add_line(ix0, yi, ix1, yi, layer="REB_DIST")

        elif fixed == "B":
            # Alt taraf sabit, Üst taraf serbest
            x_pos = midx
            pts.append((x_pos, y1 + L_anchor)) # Komşu içi (Aşağı)
            pts.append((x_pos, y0 - beam_ext)) # Üst uç
            pts.append((x_pos + hook_len, y0 - beam_ext)) # Kanca "Sağa"
            
            w.add_polyline(pts, layer=layer)
            w.add_text(x_pos + 20, midy, f"Ana {ch_main.label()}", height=100, layer="TEXT", rotation=90, center=True)

             # Dağıtma (Yatay)
            if ch_dist:
                count = 3
                dy = (y1 - y0) / (count + 1)
                for i in range(1, count + 1):
                    yi = y0 + i * dy
                    w.add_line(ix0, yi, ix1, yi, layer="REB_DIST")

    w.add_text(midx, midy, sid, height=150, layer="TEXT", center=True)
