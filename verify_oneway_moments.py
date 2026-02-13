
import sys
from oneway_slab import compute_oneway_per_slab, compute_oneway_report
from slab_model import SlabSystem, Slab

def verify_oneway_moments():
    # Mocking a slab system with 4 spans like the user's screenshot
    # Slabs are along X axis (START=Left, END=Right)
    # Each slab is 24m high (Y)
    system = SlabSystem(100, 100)
    
    # Grid coordinates: (i0, j0, i1, j1)
    # d2: width=5m -> i0=0, i1=4
    # d3: width=2m -> i0=5, i1=6
    # d4: width=2m -> i0=7, i1=8
    # d5: width=2m -> i0=9, i1=10
    
    system.add_slab(Slab("d2", 0, 0, 4, 24, "ONEWAY", dx=1.0, dy=1.0, pd=10, b=1.0))
    system.add_slab(Slab("d3", 5, 0, 6, 24, "ONEWAY", dx=1.0, dy=1.0, pd=10, b=1.0))
    system.add_slab(Slab("d4", 7, 0, 8, 24, "ONEWAY", dx=1.0, dy=1.0, pd=10, b=1.0))
    system.add_slab(Slab("d5", 9, 0, 10, 24, "ONEWAY", dx=1.0, dy=1.0, pd=10, b=1.0))
    
    # Analyze d3
    sid = "d3"
    bw = 0.3
    res, steps = compute_oneway_per_slab(system, sid, bw)
    
    print(f"--- Analysis for {sid} ---")
    print(f"Chain found: {res['chain']}")
    
    if 'Mneg_start' not in res:
         print("FAIL: Mneg_start key missing!")
         return

    print(f"Mneg_start: {res['Mneg_start']:.3f}")
    print(f"Mneg_end:   {res['Mneg_end']:.3f}")
    
    if abs(res['Mneg_start']) < 1e-3:
         print("FAIL: Mneg_start is zero. Chain/Continuity detection issue.")
         return

    if abs(res['Mneg_start'] - res['Mneg_end']) < 1.0:
        print("FAIL: START and END moments are too close or identical!")
    else:
        print("PASS: START and END moments are significantly different.")

    # Reporting
    design_res, report_lines = compute_oneway_report(system, sid, res, "C25", "S420", 120, 25, bw)
    
    print("\n--- Report Fragment ---")
    found_lines = 0
    for line in report_lines:
        if "START tarafı" in line or "END tarafı" in line:
            print(line.strip())
            found_lines += 1
    
    if found_lines >= 2:
        print("\nPASS: Report correctly shows separate moments.")
    else:
        print("\nFAIL: Report does not show separate moments.")

if __name__ == "__main__":
    verify_oneway_moments()
