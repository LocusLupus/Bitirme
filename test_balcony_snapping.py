
import json
from json_loader import parse_slab_json

def test_balcony_snapping():
    test_json = {
        "units": "cm",
        "axes": {
            "x_labels": ["1", "2"],
            "y_labels": ["A", "B"],
            "x_spans_cm": [500],
            "y_spans_cm": [600],
            "x_lines_px": [100, 600],
            "y_lines_px": [100, 700]
        },
        "cell_types": [
            [{"cell": "1A-2B", "type": "slab"}]
        ],
        "balconies": [
            {
                "id": "B1",
                "edge": "top",
                "depth_cm": 150,
                "width_cm": 400,
                "bbox_px": [150, 50, 550, 100]  # ymax is 100, close to y_lines_px[0] (building top)
            }
        ]
    }
    
    slabs, beams = parse_slab_json(test_json)
    
    # Building slab: x=0, y=0, w=5.0, h=6.0
    # Balcony B1 at top: ymax_px=100 -> snaps to y_lines_px[0]=100 -> building top (y=0 in meters)
    # xmin_px=150, xmax_px=550. Building x_lines_px=[100, 600].
    # xmin_px=150 is close to 100 (xi=0). xmax_px=550 is close to 600 (xi=1).
    # So it should snap to x=x_coords[0]=0 and w=x_coords[1]-x_coords[0]=5.0m
    
    print(f"Loaded {len(slabs)} slabs")
    for s in slabs:
        print(f"Slab {s['sid']}: x={s['x']}, y={s['y']}, w={s['w']}, h={s['h']}, kind={s['kind']}, fixed={s.get('fixed_edge')}")
        
    b1 = next(s for s in slabs if s["sid"] == "B1")
    assert b1["x"] == 0.0
    assert b1["w"] == 5.0
    assert b1["y"] == -1.5  # 0.0 building top - 1.5 depth
    assert b1["fixed_edge"] == "B"
    print("Test passed!")

if __name__ == "__main__":
    test_balcony_snapping()
