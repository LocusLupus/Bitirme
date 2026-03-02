import json_loader

# Kullanıcının gerçek JSON verisi
test_json = {
  "units": "cm",
  "grid": {
    "dx_cm": 10, "dx_m": 0.1, "dy_m": 0.1,
    "nx": 290, "ny": 147,
    "x_edges": [0, 42, 100, 245, 290],
    "y_edges": [0, 2, 44, 89, 147]
  },
  "slabs": [
    {"id": "D21", "kind": "TWOWAY", "bbox_ij": [0, 0, 41, 1], "dx": 0.1, "dy": 0.1},
    {"id": "D31", "kind": "TWOWAY", "bbox_ij": [0, 2, 41, 43], "dx": 0.1, "dy": 0.1},
    {"id": "D32", "kind": "TWOWAY", "bbox_ij": [42, 2, 99, 43], "dx": 0.1, "dy": 0.1},
    {"id": "D41", "kind": "TWOWAY", "bbox_ij": [0, 44, 41, 88], "dx": 0.1, "dy": 0.1},
    {"id": "D43", "kind": "TWOWAY", "bbox_ij": [100, 44, 244, 88], "dx": 0.1, "dy": 0.1},
  ],
  "openings": []
}

slabs, _ = json_loader.parse_slab_json(test_json)

print(f"Toplam {len(slabs)} doseme yuklendi:\n")
for s in slabs:
    print(f"  {s['sid']:5s}  x={s['x']:6.2f}  y={s['y']:6.2f}  "
          f"w={s['w']:6.2f}m  h={s['h']:6.2f}m  ({s['kind']})")
