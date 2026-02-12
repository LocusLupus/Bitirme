
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from dxf_out import _DXFWriter, _pilye_polyline, _draw_straight_hit_polyline

def verify_mirroring():
    max_h = 1000.0
    w = _DXFWriter(max_height=max_h)
    
    print(f"Max Height (DXF Y-Origin): {max_h}")

    # Case 1: Pilye Bar (Horizontal)
    # Start: (100, 100) (Top)
    # End: (500, 100) (Top)
    # Crank down: d=50
    # In GUI (Y-down): y0=100. Lower part (span) is y0=100.
    # Upper part (support) is usually offset. Where?
    # _pilye_polyline logic:
    # want_start (Left/Top supp? No, Left):
    # pts.append((x0 + Ln5 - d, y0)) # High?
    # pts.append((x0 + Ln5, y0 - d)) # Low?
    # Wait. y0 is the "base" Y.
    # If y0-d is used, it's UP in GUI.
    # If y0 is used, it's DOWN relative to y0-d.
    print("\n--- Test Pilye (Horizontal) ---")
    x0, y0 = 100.0, 100.0
    x1, y1 = 500.0, 100.0
    d = 50.0
    
    pts = _pilye_polyline(x0, y0, x1, y1, d=d, kink="both", hook_len=20.0, beam_ext=20.0)
    print("GUI Points (Y-down):")
    for p in pts:
        print(f"  {p}")
        
    # Check max/min Y in GUI
    ys = [p[1] for p in pts]
    min_y_gui = min(ys)
    max_y_gui = max(ys)
    print(f"  GUI Y-Range: [{min_y_gui}, {max_y_gui}]")
    if min_y_gui < y0:
        print("  Result: Crank extends UP (Negative Y) in GUI.")
    elif max_y_gui > y0:
        print("  Result: Crank extends DOWN (Positive Y) in GUI.")
    else:
        print("  Result: Flat.")

    # Convert to DXF
    print("DXF Points (Y-up, H-y):")
    dxf_pts = [(p[0], w._fy(p[1])) for p in pts]
    for p in dxf_pts:
        print(f"  {p}")
        
    ys_dxf = [p[1] for p in dxf_pts]
    min_y_dxf = min(ys_dxf)
    max_y_dxf = max(ys_dxf)
    base_y_dxf = w._fy(y0)
    print(f"  DXF Base Y: {base_y_dxf}")
    print(f"  DXF Y-Range: [{min_y_dxf}, {max_y_dxf}]")
    
    if max_y_dxf > base_y_dxf:
        print("  Result: Crank extends UP (Positive Y) in DXF.")
    elif min_y_dxf < base_y_dxf:
        print("  Result: Crank extends DOWN (Negative Y) in DXF.")
    else:
        print("  Result: Flat.")

    # Case 2: Hook (Upwards)
    print("\n--- Test Hook (Upwards in GUI) ---")
    # Provide a hook that goes "Up" (Negative Y) in GUI
    # e.g. Start at y=100. End at y=80.
    # Using _draw_straight_hit_polyline for vertical bar? No, hook logic.
    # Let's manual check logic: y - hook_len
    hook_len = 30.0
    y_hook_tip_gui = y0 - hook_len
    print(f"  GUI Hook Tip: {y_hook_tip_gui} (Base {y0}) -> Diff: {y_hook_tip_gui - y0}")
    
    y_hook_tip_dxf = w._fy(y_hook_tip_gui)
    base_dxf = w._fy(y0)
    print(f"  DXF Hook Tip: {y_hook_tip_dxf} (Base {base_dxf}) -> Diff: {y_hook_tip_dxf - base_dxf}")
    
    if y_hook_tip_dxf > base_dxf:
        print("  Result: Hook points UP (Positive Y) in DXF.")
    else:
        print("  Result: Hook points DOWN (Negative Y) in DXF.")

if __name__ == "__main__":
    verify_mirroring()
