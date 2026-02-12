
import ezdxf
import os
from slab_model import SlabSystem, Slab
from dxf_out import export_to_dxf
from struct_design import RebarChoice

def create_test_system():
    # Monkeypatch size_m_gross for reproduction
    def mock_size_m_gross(self):
        return 8.0, 4.0 # 2 slabs of 4m width
    SlabSystem.size_m_gross = mock_size_m_gross

    # Create a 2x1 simple system
    system = SlabSystem(nx=2, ny=1)
    
    # Slab 1 (Left) - occupies cell (0,0)
    s1 = Slab("S1", 0, 0, 0, 0, "TWOWAY", 4.0, 4.0, 0.0, 0.0)
    system.add_slab(s1)
    
    # Slab 2 (Right) - occupies cell (1,0)
    s2 = Slab("S2", 1, 0, 1, 0, "TWOWAY", 4.0, 4.0, 0.0, 0.0)
    system.add_slab(s2)
    
    # Mock Design Cache
    # We need to simulate that "S1" has a Right neighbor "S2" and they are continuous
    # And "S2" has Left neighbor "S1".
    
    # Fake choices
    ch = RebarChoice(8, 200, 251) # 8/200
    
    design_cache = {
        "S1": {
            "kind": "TWOWAY", "cover_mm": 25.0,
            "choices": {
                "x_span_duz": ch, "x_span_pilye": ch,
                "x_support_extra": ch, # We want this to be drawn!
                "y_span_duz": ch, "y_span_pilye": ch,
                "y_support_extra": ch
            },
            "edge_continuity": {"L": False, "R": True, "T": False, "B": False}
        },
        "S2": {
            "kind": "TWOWAY", "cover_mm": 25.0,
            "choices": {
                "x_span_duz": ch, "x_span_pilye": ch,
                "x_support_extra": ch,
                "y_span_duz": ch, "y_span_pilye": ch,
                "y_support_extra": ch
            },
            "edge_continuity": {"L": True, "R": False, "T": False, "B": False}
        }
    }
    
    return system, design_cache

def analyze_dxf(filename):
    print(f"Analyzing {filename}...")
    try:
        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()
        
        # Count entities on REB_EK_MESNET layer
        hat_bars = msp.query('LWPOLYLINE[layer=="REB_EK_MESNET"]')
        print(f"Found {len(hat_bars)} support extra bars.")
        
        for i, poly in enumerate(hat_bars):
            points = poly.get_points()
            print(f"Bar {i+1} has {len(points)} points.")
            # We expect a Hat shape, so maybe > 4 points?
            # Start, CrankUp, Top, CrankDown, End -> 5 points minimum if simple
            # If we add hooks -> +4 points -> ~9 points?
            
        if len(points) == 6:
            print("  -> Has 6 points (Hat Shape verified).")
        else:
            print(f"  -> Has {len(points)} points (Expected 6 for Hat).")
                
        return len(hat_bars)
        
    except Exception as e:
        print(f"Error reading DXF: {e}")
        return 0

if __name__ == "__main__":
    sys, dc = create_test_system()
    out_file = "check_hat.dxf"
    export_to_dxf(sys, out_file, dc, bw_val=0.50) # 50cm beam
    
    count = analyze_dxf(out_file)
    # Start: Expect 2 (current faulty behavior - double draw) or 0 (if not implemented)
    # Target: Expect 1 (Owner rule)
