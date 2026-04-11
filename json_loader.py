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

    # ── Kümülatif koordinatlar (m) ──
    # x_coords[i] = i. aksın X konumu (metre)
    x_coords = _cumulative([0.0], x_spans_m)
    y_coords = _cumulative([0.0], y_spans_m)

    # ── Etiket → indeks haritaları ──
    x_idx = {lbl: i for i, lbl in enumerate(x_labels)}
    y_idx = {lbl: i for i, lbl in enumerate(y_labels)}

    # ── Notlardan varsayılan kind ──
    notes = json_data.get("notes", {})
    kind_default_raw = notes.get("kind_default", "TWOWAY")
    # "TWOWAY (change by rules if needed)" gibi ifadedeki ilk kelimeyi al
    kind_default = kind_default_raw.split()[0].upper()

    slab_list: List[Dict[str, Any]] = []
    slab_counter = 0

    cell_types_rows = json_data.get("cell_types", [])

    for row in cell_types_rows:
        for cell_info in row:
            cell_name = cell_info.get("cell", "")
            cell_type = cell_info.get("type", "").lower()

            # Sadece "slab" tipindeki hücreleri döşeme olarak al
            if cell_type != "slab":
                continue

            # Hücre adını çözümle: "1A-2B" → x_start=1, y_start=A, x_end=2, y_end=B
            parsed = _parse_cell_name(cell_name)
            if parsed is None:
                continue

            x_start_lbl, y_start_lbl, x_end_lbl, y_end_lbl = parsed

            # Etiketlerin indekslerini bul
            xi0 = x_idx.get(x_start_lbl)
            yi0 = y_idx.get(y_start_lbl)
            xi1 = x_idx.get(x_end_lbl)
            yi1 = y_idx.get(y_end_lbl)

            if any(v is None for v in (xi0, yi0, xi1, yi1)):
                continue

            # Koordinatlar (m)
            x = x_coords[xi0]
            y = y_coords[yi0]
            w = x_coords[xi1] - x_coords[xi0]
            h = y_coords[yi1] - y_coords[yi0]

            if w <= 0 or h <= 0:
                continue

            # Döşeme tipi – varsayılan TWOWAY, m > 2 ise ONEWAY
            kind = _determine_kind(w, h, kind_default)

            slab_counter += 1
            sid = cell_name  # Hücre adını ID olarak kullan (ör: "4A-5B")

            slab_list.append({
                "sid":  sid,
                "x":    round(x, 6),
                "y":    round(y, 6),
                "w":    round(w, 6),
                "h":    round(h, 6),
                "kind": kind,
                "pd":   cell_info.get("pd", 10.0),
                "b":    cell_info.get("b", 1.0),
            })

    return slab_list, set()


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
