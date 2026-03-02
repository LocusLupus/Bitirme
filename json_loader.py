import json
from typing import Dict, List, Tuple, Any


def parse_slab_json(json_data: Dict[str, Any]):
    """
    Kalıp planı JSON çıktısını okuyup RealSlab oluşturmaya uygun
    sözlük listesine dönüştürür.

    Beklenen format:
    {
      "units": "cm",
      "grid": {
          "dx_m": 0.1,
          "dy_m": 0.1,
          "x_edges": [...],   # hücre indeksi cinsinden
          "y_edges": [...],
          ...
      },
      "slabs": [
          {
              "id": "D31",
              "kind": "TWOWAY",
              "bbox_ij": [i0, j0, i1, j1],
              "dx": 0.1,
              "dy": 0.1,
              ...
          },
          ...
      ],
      "openings": [...],
      ...
    }

    Dönüş: (slab_list, beam_edges_set)
      slab_list : list of dict  →  her biri {"sid","x","y","w","h","kind","pd","b"}
      beam_edges_set : set       →  şimdilik boş
    """

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
