
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from slab_model import SlabSystem, Slab
from oneway_slab import compute_oneway_report
from dxf_out import export_to_dxf

def test_hooks():
    print("Initializing SlabSystem...")
    system = SlabSystem(5, 5)
    
    # Create a simple one-way slab
    # 4x4m slab
    s = Slab("S101", 0, 0, 1, 1, "ONEWAY", dx=4.0, dy=4.0, pd=10.0, b_width=1.0)
    system.add_slab(s)
    
    bw = 0.30
    h = 120.0
    cover = 25.0
    conc = "C25/30"
    steel = "B420C"
    
    print("Computing One-Way Report...")
    # Mock result from compute_oneway_per_slab for testing report generation
    # We need a valid 'res' dictionary.
    # Let's actually run the computation to get a real 'res'
    try:
        res, steps = system.compute_oneway_per_slab("S101", bw)
    except Exception as e:
        print(f"Error in computation: {e}")
        # manual mock if needed
        res = {
            "auto_dir": "X", "chain": ["S101"], 
            "Mpos_max": 15.0, "Mneg_min": -10.0,
            "w": 10.0
        }
    
    # Run the report generation
    design_res, report_lines = compute_oneway_report(
        system, "S101", res, conc, steel, h, cover, bw
    )
    
    # Verify report content
    full_report = "\n".join(report_lines)
    print("\n--- Report Output ---")
    print(full_report)
    print("---------------------\n")
    
    expected_hook_add = 4.0 * bw * 1000.0 # 1200 mm
    expected_str_1 = f"L_net + {expected_hook_add:.0f} mm kanca payı"
    expected_str_2 = f"bw={bw*100:.0f}cm giriş"
    expected_str_3 = f"bw={bw*100:.0f}cm aşağı kanca"
    
    if expected_str_1 in full_report and expected_str_2 in full_report and expected_str_3 in full_report:
        print("✅ Report verification PASSED: Hook details found.")
    else:
        print("❌ Report verification FAILED: Hook details NOT found.")
        if expected_str_1 not in full_report: print(f"Missing: {expected_str_1}")
        if expected_str_2 not in full_report: print(f"Missing: {expected_str_2}")
        
    
    # Verify DXF Export (Runtime check)
    print("\nTesting DXF Export...")
    # We need 'last_design' cache for DXF
    design_cache = {"S101": design_res}
    try:
        export_to_dxf(system, "test_hooks.dxf", design_cache, bw)
        print("✅ DXF Export PASSED (Runtime). Check test_hooks.dxf visually.")
    except Exception as e:
        print(f"❌ DXF Export CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hooks()
