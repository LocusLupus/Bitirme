
import sys
from slab_model import SlabSystem, Slab
from dxf_out import export_to_dxf
from oneway_slab import compute_oneway_per_slab, compute_oneway_report

def verify_oneway_extensions():
    system = SlabSystem(100, 100)
    
    # Slabs with different spans: 5m and 2m
    system.add_slab(Slab("d2", 0, 0, 5, 24, "ONEWAY", dx=1.0, dy=1.0, pd=10, b=1.0))
    system.add_slab(Slab("d3", 5, 0, 7, 24, "ONEWAY", dx=1.0, dy=1.0, pd=10, b=1.0))
    
    bw = 0.3
    design_cache = {}
    
    for sid in ["d2", "d3"]:
        res_per, steps = compute_oneway_per_slab(system, sid, bw)
        design_res, report_lines = compute_oneway_report(system, sid, res_per, "C25", "S420", 120, 25, bw)
        
        # Inject continuity for drawing test
        edge_cont = {
            "uzun_start": False, "uzun_end": False,
            "kisa_start": (sid == "d3"), # d3'ün solu dolu
            "kisa_end": (sid == "d2")    # d2'nin sağı dolu
        }
        design_res["edge_continuity"] = edge_cont
        design_res["kind"] = "ONEWAY"
        design_cache[sid] = design_res
        
    filename = "verify_tail_output.dxf"
    real_slabs = {
        "d2": type('obj', (object,), {'x':0, 'y':0, 'w':5, 'h':24}),
        "d3": type('obj', (object,), {'x':5, 'y':0, 'w':2, 'h':24})
    }
    
    export_to_dxf(system, filename, design_cache, bw*1000, real_slabs=real_slabs)
    print(f"DXF exported to {filename}")
    print("Verification complete. Check tails: 5m slab -> 500mm tail, 2m slab -> 200mm tail.")

if __name__ == "__main__":
    verify_oneway_extensions()
