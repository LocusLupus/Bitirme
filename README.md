# Reinforced Concrete Slab Design (TS500)

This application is a GUI-based tool for the design and analysis of reinforced concrete slabs (One-Way, Two-Way, and Cantilever/Balcony) according to TS500 standards.

It allows you to:
- Visually place slabs on a grid.
- Define slab properties (loads, materials, dimensions).
- Automatically calculate moments (coefficients method).
- Design reinforcement (select bars and spacing).
- Export the reinforcement plan to DXF (compatible with AutoCAD).

## Structure

The project is modularized into the following files:

- **`main.py`**: The entry point of the application.
- **`gui.py`**: Handles the Graphical User Interface (Tkinter).
- **`slab_model.py`**: logical model for the slab system and calculations.
- **`struct_design.py`**: Engineering formulas and reinforcement selection logic.
- **`constants.py`**: Material tables (concrete/steel) and coefficients.
- **`dxf_out.py`**: Custom DXF exporter.

## Requirements

- Python 3.x
- `tkinter` (usually included with Python)

No external libraries (like `ezdxf` or `pandas`) are required; the application uses a custom minimal DXF writer and standard data structures.

## How to Run

1. Open a terminal/command prompt in the project directory.
2. Run the following command:

   ```bash
   python main.py
   ```

3. The application window will open.

## Usage Guide

1. **Parameters**: Set your default slab parameters (dx, dy, loads, materials) on the top panel.
2. **Placement**: Select a mode (e.g., "Yerleştir: ONEWAY") and drag on the grid to create a slab.
3. **Beams**: Use "Dikey Kiriş (V)" or "Yatay Kiriş (H)" to define beams on grid lines.
4. **Calculate**: Click "Hesapla" to run the analysis. The step-by-step report will appear in the right panel.
5. **Export**: Click "DXF" to generate a `.dxf` drawing of the placed reinforcement.
