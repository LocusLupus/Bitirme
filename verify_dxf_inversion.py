
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from dxf_out import _DXFWriter

def verify_inversion():
    max_h = 1000.0
    w = _DXFWriter(max_height=max_h)
    
    # Test point at y=0 (Top in GUI) -> Should be y=1000 (Top in DXF)
    y_in = 0.0
    y_out = w._fy(y_in)
    print(f"Input: {y_in} -> Output: {y_out}")
    if abs(y_out - 1000.0) < 1e-6:
        print("PASS: Top (0) -> Top (1000)")
    else:
        print("FAIL: Top (0) -> ?")

    # Test point at y=1000 (Bottom in GUI) -> Should be y=0 (Bottom in DXF)
    y_in = 1000.0
    y_out = w._fy(y_in)
    print(f"Input: {y_in} -> Output: {y_out}")
    if abs(y_out - 0.0) < 1e-6:
        print("PASS: Bottom (1000) -> Bottom (0)")
    else:
        print("FAIL: Bottom (1000) -> ?")

    # Test point at y=250 (Quarter way down in GUI) -> Should be y=750 (Quarter way up in DXF)
    y_in = 250.0
    y_out = w._fy(y_in)
    print(f"Input: {y_in} -> Output: {y_out}")
    if abs(y_out - 750.0) < 1e-6:
        print("PASS: Quarter (250) -> Quarter (750)")
    else:
        print("FAIL: Quarter (250) -> ?")

if __name__ == "__main__":
    try:
        verify_inversion()
        print("Verification completed successfully.")
    except Exception as e:
        print(f"Verification failed with error: {e}")
