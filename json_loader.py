import json
import re
from typing import Dict, List, Tuple, Any


def parse_slab_json(json_data: Dict[str, Any]):
    """
    Kalıp planı JSON çıktısını okuyup RealSlab oluşturmaya uygun
    sözlük listesine dönüştürür.

    Desteklenen formatlar:

    ──────────────────────────────────────────────
    FORMAT 1 (cell_types tabanlı – yeni format)
    ──────────────────────────────────────────────
    {
      "units": "cm",
      "axes": {
          "x_labels": ["1","2","3",...],
          "y_labels": ["A","B","C",...],
          "x_spans_cm": [280, 250, ...],   // veya x_span_details
          "y_spans_cm": [580, 480, ...],   // veya y_span_details
          ...
      },
      "cell_types": [
          [  // satır 0 (A-B arası)
              {"cell": "1A-2B", "type": "slab"},
              {"cell": "2A-3B", "type": "void"},
              ...
          ],
          ...
      ],
      "openings": [...],
      ...
    }

    ──────────────────────────────────────────────
    FORMAT 2 (slabs dizisi – eski format)
    ──────────────────────────────────────────────
    {
      "units": "cm",
      "grid": { "dx_m": 0.1, "dy_m": 0.1, ... },
      "slabs": [
          { "id": "D31", "kind": "TWOWAY", "bbox_ij": [...], ... },
          ...
      ],
      ...
    }

    Dönüş: (slab_list, beam_edges_set)
      slab_list : list of dict  →  her biri {"sid","x","y","w","h","kind","pd","b"}
      beam_edges_set : set       →  şimdilik boş
    """

    # ── Hangi format kullanılıyor? ──
    if "cell_types" in json_data and json_data["cell_types"]:
        return _parse_cell_types_format(json_data)
    else:
        return _parse_legacy_slabs_format(json_data)


# ═══════════════════════════════════════════════════════════
#  FORMAT 1 – cell_types tabanlı
# ═══════════════════════════════════════════════════════════

def _parse_cell_types_format(json_data: Dict[str, Any]):
    """cell_types[][] dizisinden döşeme listesi oluşturur."""

    axes = json_data.get("axes", {})
    units = json_data.get("units", "cm").lower()

    # ── Aks etiketleri ──
    x_labels: List[str] = axes.get("x_labels", [])
    y_labels: List[str] = axes.get("y_labels", [])

    # ── Aks arası mesafeler (cm veya m) ──
    x_spans = _get_spans(axes, "x", len(x_labels))
    y_spans = _get_spans(axes, "y", len(y_labels))

    if not x_spans or not y_spans:
        return [], set()

    # cm → m dönüşümü
    to_m = 0.01 if units == "cm" else 1.0
    x_spans_m = [s * to_m for s in x_spans]
    y_spans_m = [s * to_m for s in y_spans]

    # ── Etiket → indeks haritaları ──
    x_idx = {lbl: i for i, lbl in enumerate(x_labels)}
    y_idx = {lbl: i for i, lbl in enumerate(y_labels)}

    # ── Notlardan varsayılan kind ──
    notes = json_data.get("notes", {})
    kind_default_raw = notes.get("kind_default", "TWOWAY")
    kind_default = kind_default_raw.split()[0].upper()

    cell_types_rows = json_data.get("cell_types", [])

    # ── Aks Snapping (Boşlukları Kapatma) ──
    # Döşeme içermeyen ve dar olan aks aralıklarını 0 kabul ederek döşemeleri bitiştiririz.
    SNAP_THRESHOLD = 0.60  # 60cm altındaki boşlukları kapat
    x_occupied = [False] * len(x_spans_m)
    y_occupied = [False] * len(y_spans_m)

    # Önce hangi aks aralıklarında döşeme olduğunu bul
    for row in cell_types_rows:
        for cell_info in row:
            if cell_info.get("type", "").lower() == "slab":
                parsed = _parse_cell_name(cell_info.get("cell", ""))
                if parsed:
                    xi0_lbl, yi0_lbl, xi1_lbl, yi1_lbl = parsed
                    ix0, ix1 = x_idx.get(xi0_lbl), x_idx.get(xi1_lbl)
                    iy0, iy1 = y_idx.get(yi0_lbl), y_idx.get(yi1_lbl)
                    if ix0 is not None and ix1 is not None:
                        for i in range(ix0, ix1): x_occupied[i] = True
                    if iy0 is not None and iy1 is not None:
                        for j in range(iy0, iy1): y_occupied[j] = True

    # Boş aks aralıklarını daraltılmış yeni listeler
    collapsed_x_spans = []
    for i, s_m in enumerate(x_spans_m):
        if not x_occupied[i] and s_m < SNAP_THRESHOLD:
            collapsed_x_spans.append(0.0)
        else:
            collapsed_x_spans.append(s_m)

    collapsed_y_spans = []
    for j, s_m in enumerate(y_spans_m):
        if not y_occupied[j] and s_m < SNAP_THRESHOLD:
            collapsed_y_spans.append(0.0)
        else:
            collapsed_y_spans.append(s_m)

    # Yeni kümülatif koordinatlar
    x_coords = _cumulative([0.0], collapsed_x_spans)
    y_coords = _cumulative([0.0], collapsed_y_spans)

    # Kiriş çizgilerini belirle (daraltılan kısımlar aslında kiriştir)
    beam_edges_set = set()
    
    # X daraltmaları için dikey kiriş parçaları
    for i, s_m in enumerate(x_spans_m):
        if not x_occupied[i] and s_m < SNAP_THRESHOLD:
            x_val = round(x_coords[i], 4)
            for j in range(len(y_spans_m)):
                # Bu hücrenin sağında veya solunda en az bir yapısal eleman (döşeme/boşluk vb.) varsa kiriş çiz
                has_structural_adjacent = False
                # Solundaki sütun (i-1)
                if i > 0 and cell_types_rows[j][i-1].get("type", "").lower() not in ("", "void"):
                    has_structural_adjacent = True
                # Sağındaki sütun (i+1)
                if i < len(x_spans_m) - 1 and cell_types_rows[j][i+1].get("type", "").lower() not in ("", "void"):
                    has_structural_adjacent = True
                
                if has_structural_adjacent:
                    y0, y1 = round(y_coords[j], 4), round(y_coords[j+1], 4)
                    if y1 > y0:
                        beam_edges_set.add((x_val, y0, x_val, y1))

    # Y daraltmaları için yatay kiriş parçaları
    for j, s_m in enumerate(y_spans_m):
        if not y_occupied[j] and s_m < SNAP_THRESHOLD:
            y_val = round(y_coords[j], 4)
            for i in range(len(x_spans_m)):
                # Bu hücrenin üstünde veya altında en az bir yapısal eleman varsa kiriş çiz
                has_structural_adjacent = False
                # Üstündeki satır (j-1)
                if j > 0 and cell_types_rows[j-1][i].get("type", "").lower() not in ("", "void"):
                    has_structural_adjacent = True
                # Altındaki satır (j+1)
                if j < len(y_spans_m) - 1 and cell_types_rows[j+1][i].get("type", "").lower() not in ("", "void"):
                    has_structural_adjacent = True
                
                if has_structural_adjacent:
                    x0, x1 = round(x_coords[i], 4), round(x_coords[i+1], 4)
                    if x1 > x0:
                        beam_edges_set.add((x0, y_val, x1, y_val))

    slab_list: List[Dict[str, Any]] = []
    slab_counter = 0

    for row in cell_types_rows:
        for cell_info in row:
            cell_name = cell_info.get("cell", "")
            cell_type = cell_info.get("type", "").lower()
            if cell_type != "slab":
                continue

            parsed = _parse_cell_name(cell_name)
            if parsed is None:
                continue

            x_start_lbl, y_start_lbl, x_end_lbl, y_end_lbl = parsed
            xi0, yi0 = x_idx.get(x_start_lbl), y_idx.get(y_start_lbl)
            xi1, yi1 = x_idx.get(x_end_lbl), y_idx.get(y_end_lbl)

            if any(v is None for v in (xi0, yi0, xi1, yi1)):
                continue

            x, y = x_coords[xi0], y_coords[yi0]
            w = x_coords[xi1] - x_coords[xi0]
            h = y_coords[yi1] - y_coords[yi0]

            if w <= 0 or h <= 0:
                continue

            kind = _determine_kind(w, h, kind_default)
            slab_counter += 1
            slab_list.append({
                "sid":  cell_name,
                "x":    round(x, 6),
                "y":    round(y, 6),
                "w":    round(w, 6),
                "h":    round(h, 6),
                "kind": kind,
                "pd":   cell_info.get("pd", 10.0),
                "b":    cell_info.get("b", 1.0),
            })

    # Balconies snapping logic
    x_lines_px = axes.get("x_lines_px", [])
    y_lines_px = axes.get("y_lines_px", [])
    def closest_line_index(px, lines):
        if not lines: return -1
        return min(range(len(lines)), key=lambda i: abs(lines[i] - px))

    balconies = json_data.get("balconies", [])
    for b_data in balconies:
        b_id = b_data.get("id", f"BL_{slab_counter}")
        slab_counter += 1
        edge_type = b_data.get("edge")
        bbox = b_data.get("bbox_px")
        
        if edge_type in ("left", "right"):
            w_m, h_m = b_data.get("depth_cm", 0) / 100.0, b_data.get("width_cm", 0) / 100.0
        else:
            w_m, h_m = b_data.get("width_cm", 0) / 100.0, b_data.get("depth_cm", 0) / 100.0
            
        if w_m <= 0 or h_m <= 0 or not bbox or not x_lines_px or not y_lines_px:
            continue
            
        xmin, ymin, xmax, ymax = bbox
        if edge_type in ("top", "bottom"):
            xi = closest_line_index(xmin, x_lines_px)
            x_m = x_coords[xi] if 0 <= xi < len(x_coords) else 0.0
            if edge_type == "top":
                yi = closest_line_index(ymax, y_lines_px)
                y_m = (y_coords[yi] - h_m) if 0 <= yi < len(y_coords) else 0.0
            else:
                yi = closest_line_index(ymin, y_lines_px)
                y_m = y_coords[yi] if 0 <= yi < len(y_coords) else 0.0
        else:
            yi = closest_line_index(ymin, y_lines_px)
            y_m = y_coords[yi] if 0 <= yi < len(y_coords) else 0.0
            if edge_type == "left":
                xi = closest_line_index(xmax, x_lines_px)
                x_m = (x_coords[xi] - w_m) if 0 <= xi < len(x_coords) else 0.0
            else:
                xi = closest_line_index(xmin, x_lines_px)
                x_m = x_coords[xi] if 0 <= xi < len(x_coords) else 0.0
                
        slab_list.append({
            "sid": b_id, "x": round(x_m, 6), "y": round(y_m, 6),
            "w": round(w_m, 6), "h": round(h_m, 6), "kind": "BALCONY",
            "pd": b_data.get("pd", 5.0), "b": b_data.get("b", 1.0)
        })

    return slab_list, beam_edges_set


def _get_spans(axes: dict, axis: str, n_labels: int) -> List[float]:
    """Aks arası mesafeleri çeşitli kaynaklardan bul."""
    # Öncelik 1: x_spans_cm / y_spans_cm dizisi
    spans = axes.get(f"{axis}_spans_cm")
    if spans and len(spans) == n_labels - 1:
        return spans

    # Öncelik 2: x_span_details / y_span_details sözlüğü
    details = axes.get(f"{axis}_span_details")
    if details and isinstance(details, dict):
        # Sıralı anahtar listesinden çıkar (örn: "1-2": 280, "2-3": 250, ...)
        labels = axes.get(f"{axis}_labels", [])
        result = []
        for i in range(len(labels) - 1):
            key = f"{labels[i]}-{labels[i+1]}"
            val = details.get(key)
            if val is not None:
                result.append(val)
            else:
                return []  # Eksik anahtar
        if len(result) == n_labels - 1:
            return result

    return []


def _cumulative(start: List[float], increments: List[float]) -> List[float]:
    """Kümülatif toplam dizisi oluştur."""
    result = list(start)
    for inc in increments:
        result.append(result[-1] + inc)
    return result


_CELL_RE = re.compile(
    r'^(\d+)([A-Za-z]+)-(\d+)([A-Za-z]+)$'
)

def _parse_cell_name(name: str):
    """
    "1A-2B" → ("1", "A", "2", "B")
    "4A-5B" → ("4", "A", "5", "B")
    Başarısızsa None döner.
    """
    m = _CELL_RE.match(name.strip())
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3), m.group(4)


def _determine_kind(w: float, h: float, default: str = "TWOWAY") -> str:
    """
    Döşeme tipini boyutlara göre belirle.
    m = Ll / Ls
    m > 2  → ONEWAY
    m ≤ 2  → TWOWAY (veya verilen default)
    """
    Ls = min(w, h)
    Ll = max(w, h)
    if Ls <= 0:
        return "ONEWAY"
    m = Ll / Ls
    if m > 2:
        return "ONEWAY"
    return default


# ═══════════════════════════════════════════════════════════
#  FORMAT 2 – eski slabs[] tabanlı
# ═══════════════════════════════════════════════════════════

def _parse_legacy_slabs_format(json_data: Dict[str, Any]):
    """Eski format: slabs[] dizisinden döşeme listesi oluşturur."""

    grid = json_data.get("grid", {})

    # Hücre boyutları (metre)
    dx_m = grid.get("dx_m", 0.1)
    dy_m = grid.get("dy_m", dx_m)          # dy yoksa dx ile aynı kabul et

    slab_list: List[Dict[str, Any]] = []

    for s_data in json_data.get("slabs", []):
        try:
            # ---- koordinat bilgisi ----
            bbox = s_data.get("bbox_ij")
            if bbox and len(bbox) == 4:
                i0, j0, i1, j1 = bbox
            else:
                # Eski format desteği (ayrı alanlar)
                i0 = s_data["i0"]
                j0 = s_data["j0"]
                i1 = s_data["i1"]
                j1 = s_data["j1"]

            # Döşemeye özel dx/dy varsa onu kullan, yoksa grid'den al
            sdx = s_data.get("dx", dx_m)
            sdy = s_data.get("dy", dy_m)

            x = i0 * sdx                       # sol kenar (m)
            y = j0 * sdy                        # üst kenar (m)
            w = (i1 - i0 + 1) * sdx             # genişlik (m)
            h = (j1 - j0 + 1) * sdy             # yükseklik (m)

            # ---- tip bilgisi ----
            kind = s_data.get("kind",
                              s_data.get("type", "TWOWAY")).upper()

            slab_list.append({
                "sid": s_data.get("id", f"S{len(slab_list)+1}"),
                "x":   round(x, 6),
                "y":   round(y, 6),
                "w":   round(w, 6),
                "h":   round(h, 6),
                "kind": kind,
                "pd":  s_data.get("pd", 10.0),
                "b":   s_data.get("b", 1.0),
            })
        except (KeyError, IndexError, TypeError):
            continue

    return slab_list, set()
