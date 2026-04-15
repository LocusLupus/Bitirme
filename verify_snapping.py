import json
from json_loader import parse_slab_json

TEST_DATA = {
    "units": "cm",
    "axes": {
        "x_labels": ["1", "2", "3", "4"],
        "y_labels": ["A", "B"],
        "x_spans_cm": [300, 30, 400], # 30cm gap between ax 2 and 3
        "y_spans_cm": [500]
    },
    "cell_types": [
        [
            {"cell": "1A-2B", "type": "slab"},
            {"cell": "2A-3B", "type": "void"}, # This is the gap
            {"cell": "3A-4B", "type": "slab"}
        ]
    ]
}

def test():
    slabs, beams = parse_slab_json(TEST_DATA)
    
    print(f"Slabs found: {len(slabs)}")
    for s in slabs:
        print(f"  {s['sid']}: x={s['x']}, w={s['w']}")

    s1 = next(s for s in slabs if s['sid'] == "1A-2B")
    s2 = next(s for s in slabs if s['sid'] == "3A-4B")
    
    # s1 ends at x=3.0. 
    # Gap 2-3 is collapsed (30cm < 60cm).
    # So s2 should start at x=3.0 instead of 3.3.
    
    print(f"\nSlab 1 right edge: {s1['x'] + s1['w']}")
    print(f"Slab 2 left edge: {s2['x']}")
    
    if abs((s1['x'] + s1['w']) - s2['x']) < 0.0001:
        print("\nSUCCESS: Slabs are contiguous (gap collapsed)!")
    else:
        print("\nFAILURE: Gaps were not collapsed.")

    print(f"\nBeams found: {len(beams)}")
    for b in beams:
        print(f"  Beam: {b}")

    # Expected beam at x=3.0 from y=0 to y=5.0
    expected_beam = (3.0, 0.0, 3.0, 5.0)
    if any(b == expected_beam for b in beams):
        print("\nSUCCESS: Beam correctly added at snapped boundary!")
    else:
        print("\nFAILURE: No beam added at boundary.")

if __name__ == "__main__":
    test()
