
import ezdxf
from slab_model import Slab, SlabSystem
from struct_design import RebarChoice
from dxf_out import export_to_dxf
import os

def create_mock_design_cache(sid, kind, continuity):
    """
    Mock design results to test drawing logic without running full analysis.
    continuity: dict with L, R, T, B booleans
    """
    # Common rebar choices
    ch_main = RebarChoice(10, 200, 393)
    ch_dist = RebarChoice(8, 250, 201)
    
    dcache = {
        "kind": kind,
        "cover_mm": 25.0,
        "choices": {},
        "edge_continuity": continuity
    }
    
    if kind == "TWOWAY":
        dcache["choices"] = {
            "x_span_duz": ch_main,
            "x_span_pilye": ch_main,
            "y_span_duz": ch_main,
            "y_span_pilye": ch_main,
        }
        # Add labels for span info (optional for drawing but good for completeness)
        dcache["choices"]["x_span"] = ch_main
        dcache["choices"]["y_span"] = ch_main
        
    elif kind == "BALCONY":
        dcache["choices"] = {
            "main": ch_main,
            "dist": ch_dist
        }
        # Determine fixed edge from continuity (True means connected/fixed)
        if continuity.get("L"): dcache["fixed_edge"] = "L"
        elif continuity.get("R"): dcache["fixed_edge"] = "R"
        elif continuity.get("T"): dcache["fixed_edge"] = "T"
        elif continuity.get("B"): dcache["fixed_edge"] = "B"
        
    return dcache

def verify_drawing():
    # 1. Setup System
    system = SlabSystem(3, 1) # 3 columns, 1 row
    
    # Slab 1: TWOWAY, Continuous on Right only (Left Discontinuous)
    s1 = Slab("S1", 0, 0, 0, 0, "TWOWAY", dx=4.0, dy=5.0, pd=10.0, b=1.0)
    system.add_slab(s1)
    
    # Slab 2: TWOWAY, Continuous on Left and Right
    s2 = Slab("S2", 1, 0, 1, 0, "TWOWAY", dx=4.0, dy=5.0, pd=10.0, b=1.0)
    system.add_slab(s2)
    
    # Slab 3: BALCONY, Fixed on Left (Continuous), Free on Right
    s3 = Slab("S3", 2, 0, 2, 0, "BALCONY", dx=1.5, dy=5.0, pd=10.0, b=1.0)
    system.add_slab(s3)
    
    # 2. Mock Design Results
    # S1: Left=False (Disc), Right=True (Cont), Top=False, Bottom=False
    c1 = {"L": False, "R": True, "T": False, "B": False}
    dc1 = create_mock_design_cache("S1", "TWOWAY", c1)
    
    # S2: Left=True (Cont), Right=True (Cont), Top=False, Bottom=False
    c2 = {"L": True, "R": True, "T": False, "B": False}
    dc2 = create_mock_design_cache("S2", "TWOWAY", c2)
    
    # S3: Left=True (Fixed), Right=False (Free), Top=False, Bottom=False
    c3 = {"L": True, "R": False, "T": False, "B": False}
    dc3 = create_mock_design_cache("S3", "BALCONY", c3)
    
    design_cache = {
        "S1": dc1,
        "S2": dc2,
        "S3": dc3
    }
    
    # 3. Export DXF
    filename = "verify_twoway.dxf"
    if os.path.exists(filename):
        os.remove(filename)
        
    print(f"Generating {filename}...")
    try:
        # Mocking real_slabs for coordinate placement
        real_slabs = {
            "S1": type('obj', (object,), {'x':0, 'y':0, 'w':4.0, 'h':5.0}),
            "S2": type('obj', (object,), {'x':4.0, 'y':0, 'w':4.0, 'h':5.0}),
            "S3": type('obj', (object,), {'x':8.0, 'y':0, 'w':1.5, 'h':5.0})
        }
        
        export_to_dxf(system, filename, design_cache, bw_val=0.25, real_slabs=real_slabs)
        print("DXF generated successfully.")
        
        # 4. Basic Validation (Check if file exists and has content)
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            print("PASS: DXF file created.")
        else:
            print("FAIL: DXF file not created or empty.")
            
    except Exception as e:
        print(f"FAIL: Error during DXF export: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_drawing()
