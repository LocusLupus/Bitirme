
import ezdxf
from slab_model import Slab, SlabSystem
from struct_design import RebarChoice
from dxf_out import export_to_dxf
import os

def create_mock_design_cache_oneway(sid, continuity, auto_dir="X"):
    ch_main = RebarChoice(10, 200, 393)
    ch_dist = RebarChoice(8, 250, 201)
    
    # Mock OneWay choices: specifically support extra
    ch_ek = RebarChoice(10, 200, 393)
    
    dcache = {
        "kind": "ONEWAY",
        "cover_mm": 25.0,
        "auto_dir": auto_dir,
        "choices": {
            "duz": ch_main,
            "pilye": ch_main,
            "dist": ch_dist,
            "mesnet_ek_start": ch_ek,
            "mesnet_ek_end": ch_ek,
            # Also need internal support for short continuous edges?
            "ic_mesnet_start": ch_main,
            "ic_mesnet_end": ch_main
        },
        "edge_continuity": continuity
    }
    return dcache

def verify_oneway_drawing():
    system = SlabSystem(2, 2)
    
    # Slab 1: OneWay X-dir (Short edges L/R, Long edges T/B)
    # Continuous on Top/Bottom (Long edges are continuous) -> Should draw Mesnet Ek (Vertical)
    s1 = Slab("S1", 0, 0, 0, 0, "ONEWAY", dx=4.0, dy=5.0, pd=10.0, b=1.0)
    system.add_slab(s1)
    
    # Slab 2: OneWay Y-dir (Short edges T/B, Long edges L/R)
    # Continuous on Left/Right -> Should draw Mesnet Ek (Horizontal)
    s2 = Slab("S2", 1, 0, 1, 0, "ONEWAY", dx=5.0, dy=4.0, pd=10.0, b=1.0)
    system.add_slab(s2)

    # Continuity for S1 (Vertical Mesnet Ek)
    # "uzun_start" -> Top. "uzun_end" -> Bottom.
    # Short edges: "kisa_start" -> Left. "kisa_end" -> Right.
    c1 = {
        "uzun_start": True, "uzun_end": True, 
        "kisa_start": False, "kisa_end": False 
    }
    dc1 = create_mock_design_cache_oneway("S1", c1, auto_dir="X")
    
    # Continuity for S2 (Horizontal Mesnet Ek)
    # "uzun_start" -> Left. "uzun_end" -> Right.
    c2 = {
        "uzun_start": True, "uzun_end": True,
        "kisa_start": False, "kisa_end": False
    }
    dc2 = create_mock_design_cache_oneway("S2", c2, auto_dir="Y")
    
    design_cache = {"S1": dc1, "S2": dc2}
    
    filename = "verify_oneway_test.dxf"
    if os.path.exists(filename):
        os.remove(filename)
        
    print(f"Generating {filename}...")
    try:
        real_slabs = {
            "S1": type('obj', (object,), {'x':0, 'y':0, 'w':4.0, 'h':5.0}),
            "S2": type('obj', (object,), {'x':5.0, 'y':0, 'w':5.0, 'h':4.0})
        }
        
        export_to_dxf(system, filename, design_cache, bw_val=0.25, real_slabs=real_slabs)
        print("DXF generated successfully.")
        
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            print("PASS: DXF file created.")
        else:
            print("FAIL: DXF file not created or empty.")
            
    except Exception as e:
        print(f"FAIL: Error during DXF export: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_oneway_drawing()
