"""Test: json_loader yeni cell_types formatını doğru okuyor mu?"""
import json
from json_loader import parse_slab_json

TEST_JSON = r"""
{
  "units": "cm",
  "axes": {
    "x_labels": ["1","2","3","4","5","6","7"],
    "y_labels": ["A","B","C","D","E","F"],
    "x_spans_cm": [280,250,410,540,260,250],
    "y_spans_cm": [580,480,390,250,550],
    "x_span_details": {"1-2":280,"2-3":250,"3-4":410,"4-5":540,"5-6":260,"6-7":250},
    "y_span_details": {"A-B":580,"B-C":480,"C-D":390,"D-E":250,"E-F":550}
  },
  "grid": {"dx_cm":10,"dx_m":0.1,"dy_m":0.1,"nx":199,"ny":225,
           "x_edges":[0,28,53,94,148,174,199],
           "y_edges":[0,58,106,145,170,225]},
  "slabs": [],
  "openings": [{"conf":0.985,"cell_ij":[4,3],"bbox_ij":[148,145,173,169],"bbox_px":[1524,1481,1689,1638]}],
  "cell_types": [
    [{"cell":"1A-2B","type":"void"},{"cell":"2A-3B","type":"void"},
     {"cell":"3A-4B","type":"void"},{"cell":"4A-5B","type":"slab"},
     {"cell":"5A-6B","type":"slab"},{"cell":"6A-7B","type":"void"}],
    [{"cell":"1B-2C","type":"slab"},{"cell":"2B-3C","type":"void"},
     {"cell":"3B-4C","type":"void"},{"cell":"4B-5C","type":"void"},
     {"cell":"5B-6C","type":"void"},{"cell":"6B-7C","type":"slab"}],
    [{"cell":"1C-2D","type":"slab"},{"cell":"2C-3D","type":"slab"},
     {"cell":"3C-4D","type":"slab"},{"cell":"4C-5D","type":"void"},
     {"cell":"5C-6D","type":"slab"},{"cell":"6C-7D","type":"void"}],
    [{"cell":"1D-2E","type":"void"},{"cell":"2D-3E","type":"slab"},
     {"cell":"3D-4E","type":"void"},{"cell":"4D-5E","type":"slab"},
     {"cell":"5D-6E","type":"opening"},{"cell":"6D-7E","type":"slab"}],
    [{"cell":"1E-2F","type":"void"},{"cell":"2E-3F","type":"void"},
     {"cell":"3E-4F","type":"void"},{"cell":"4E-5F","type":"slab"},
     {"cell":"5E-6F","type":"slab"},{"cell":"6E-7F","type":"slab"}]
  ],
  "notes": {"materials":"USER_INPUT","moments":"USER_INPUT","kind_default":"TWOWAY (change by rules if needed)"}
}
"""

def main():
    data = json.loads(TEST_JSON)
    slabs, beams = parse_slab_json(data)

    print(f"Toplam döşeme sayısı: {len(slabs)}")
    print(f"Kiriş kenarları: {len(beams)}")
    print()

    # Beklenen: cell_types'ta "slab" olanlar
    expected_slab_cells = [
        "4A-5B", "5A-6B",           # satır 0
        "1B-2C", "6B-7C",           # satır 1
        "1C-2D", "2C-3D", "3C-4D", "5C-6D",  # satır 2
        "2D-3E", "4D-5E", "6D-7E",  # satır 3
        "4E-5F", "5E-6F", "6E-7F",  # satır 4
    ]

    found_sids = [s["sid"] for s in slabs]

    print("Bulunan döşemeler:")
    for s in slabs:
        Ls = min(s["w"], s["h"])
        Ll = max(s["w"], s["h"])
        m = Ll / Ls if Ls > 0 else 0
        print(f'  {s["sid"]:10s}  x={s["x"]:.2f}  y={s["y"]:.2f}  '
              f'w={s["w"]:.2f}m  h={s["h"]:.2f}m  '
              f'm={m:.2f}  kind={s["kind"]}')

    print()

    # Doğrulama
    assert len(slabs) == len(expected_slab_cells), \
        f"Beklenen {len(expected_slab_cells)} döşeme, bulunan {len(slabs)}"

    for cell in expected_slab_cells:
        assert cell in found_sids, f"{cell} bulunamadı!"

    # Boyut doğrulamaları (cm → m)
    # 4A-5B: x_span 4-5 = 540cm = 5.4m, y_span A-B = 580cm = 5.8m
    s_4A5B = next(s for s in slabs if s["sid"] == "4A-5B")
    assert abs(s_4A5B["w"] - 5.40) < 0.01, f'4A-5B w beklenen 5.40, bulunan {s_4A5B["w"]}'
    assert abs(s_4A5B["h"] - 5.80) < 0.01, f'4A-5B h beklenen 5.80, bulunan {s_4A5B["h"]}'

    # 1B-2C: x_span 1-2 = 280cm = 2.8m, y_span B-C = 480cm = 4.8m
    s_1B2C = next(s for s in slabs if s["sid"] == "1B-2C")
    assert abs(s_1B2C["w"] - 2.80) < 0.01, f'1B-2C w beklenen 2.80, bulunan {s_1B2C["w"]}'
    assert abs(s_1B2C["h"] - 4.80) < 0.01, f'1B-2C h beklenen 4.80, bulunan {s_1B2C["h"]}'

    # Konum doğrulamaları
    # 4A-5B: x = sum(280+250+410) cm * 0.01 = 9.40m, y = 0
    assert abs(s_4A5B["x"] - 9.40) < 0.01, f'4A-5B x beklenen 9.40, bulunan {s_4A5B["x"]}'
    assert abs(s_4A5B["y"] - 0.00) < 0.01, f'4A-5B y beklenen 0.00, bulunan {s_4A5B["y"]}'

    # Kind doğrulaması: 4A-5B → w=5.4, h=5.8, m=5.8/5.4=1.07 → TWOWAY
    assert s_4A5B["kind"] == "TWOWAY", f'4A-5B kind beklenen TWOWAY, bulunan {s_4A5B["kind"]}'

    # 1B-2C → w=2.8, h=4.8, m=4.8/2.8=1.71 → TWOWAY
    assert s_1B2C["kind"] == "TWOWAY", f'1B-2C kind beklenen TWOWAY, bulunan {s_1B2C["kind"]}'

    print("✓ Tüm testler geçti!")


if __name__ == "__main__":
    main()
