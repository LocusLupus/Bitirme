
"""
infer_to_calc_inputs.py
----------------------
Converts a formwork plan PNG into structured JSON inputs for a slab calculation pipeline.

It uses:
- Ultralytics YOLO (segment or detect) for geometry classes (axis_bubble, slab_area, opening_area, etc.)
- OCR (PaddleOCR if available) to read text (dimensions in cm, panel IDs like D11, balcony IDs like BL32, axis labels)

Outputs:
- <out_prefix>.json        : structured data (axes, spans, slabs with bbox_ij, openings)
- <out_prefix>_debug.png   : debug overlay showing parsed axes/spans/panel mappings

Expected YOLO class names (by id) default to:
  0 slab_area
  1 beam_area
  2 balcony_area
  3 axis_bubble
  4 dimension_text   (optional; OCR can work without this)
  5 panel_text       (optional; OCR can work without this)
  6 balcony_text     (optional; OCR can work without this)
  7 column_symbol
  8 opening_area

If your dataset uses different class indices, pass a custom mapping via --classes_json.

Usage (Windows example):
  python infer_to_calc_inputs.py ^
    --weights runs_formwork/seg_v1/weights/best.pt ^
    --image C:/Users/KURT/Model/sample.png ^
    --out_prefix C:/Users/KURT/Model/out/sample ^
    --dx_cm 10 ^
    --imgsz 1024 ^
    --conf 0.35
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

# Optional dependencies
try:
    import cv2  # type: ignore
except Exception as e:
    raise RuntimeError("OpenCV (cv2) is required. Install: pip install opencv-python") from e

try:
    from ultralytics import YOLO  # type: ignore
except Exception as e:
    raise RuntimeError("Ultralytics is required. Install: pip install ultralytics") from e


@dataclass
class Token:
    text: str
    cx: float
    cy: float
    conf: float
    bbox: Tuple[int, int, int, int]  # x1,y1,x2,y2


@dataclass
class Det:
    cls_id: int
    cls_name: str
    conf: float
    bbox: Tuple[float, float, float, float]  # x1,y1,x2,y2


# ----------------------------
# OCR
# ----------------------------
def ocr_tokens(image_bgr: np.ndarray, allowlist: str = None) -> List[Token]:
    """
    Returns OCR tokens with their center points in pixel space.
    Uses EasyOCR as the OCR engine.
    """
    try:
        import easyocr  # type: ignore

        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        
        if allowlist:
            result = reader.readtext(rgb, allowlist=allowlist)
        else:
            result = reader.readtext(rgb)

        tokens: List[Token] = []
        if result is None:
            return tokens

        for entry in result:
            pts, txt, cf = entry
            # pts = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x1, y1, x2, y2 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            norm_txt = str(txt).strip()
            if not norm_txt:
                continue
            tokens.append(Token(text=norm_txt, cx=cx, cy=cy, conf=float(cf), bbox=(x1, y1, x2, y2)))
        return tokens
    except ImportError as e:
        import tkinter.messagebox as messagebox
        messagebox.showwarning(
            "OCR Çalıştırılamadı",
            f"EasyOCR yüklü değil. Metin okuma adımı atlanıyor.\n\nHata detayı: {e}\n\nYüklemek için terminalde çalıştırın:\npip install easyocr\n\n(OCR olmadan sadece geometri eksenleri çalışır, etiketler eksik olur.)"
        )
        return []
    except Exception as e:
        import tkinter.messagebox as messagebox
        messagebox.showwarning(
            "OCR Hatası",
            f"OCR sırasında hata oluştu. Metin okuma adımı atlanıyor.\n\nHata detayı: {e}"
        )
        return []


# ----------------------------
# YOLO inference
# ----------------------------
DEFAULT_CLASSES = {
    0: "slab_area",
    1: "beam_area",
    2: "balcony_area",
    3: "axis_bubble",
    4: "dimension_text",
    5: "panel_text",
    6: "balcony_text",
    7: "column_symbol",
    8: "opening_area",
}

def run_yolo(weights: str, image_path: str, imgsz: int, conf: float, classes_map: Dict[int, str]) -> List[Det]:
    model = YOLO(weights)
    r = model(image_path, imgsz=imgsz, conf=conf, verbose=False)[0]
    dets: List[Det] = []

    if r.boxes is None or len(r.boxes) == 0:
        return dets

    xyxy = r.boxes.xyxy.cpu().numpy()
    clss = r.boxes.cls.cpu().numpy().astype(int)
    confs = r.boxes.conf.cpu().numpy()

    for bb, ci, cf in zip(xyxy, clss, confs):
        x1, y1, x2, y2 = map(float, bb)
        dets.append(
            Det(
                cls_id=int(ci),
                cls_name=classes_map.get(int(ci), f"class_{int(ci)}"),
                conf=float(cf),
                bbox=(x1, y1, x2, y2),
            )
        )
    return dets


# ----------------------------
# Parsing helpers
# ----------------------------
_AXIS_X_RE = re.compile(r"^\d{1,2}$")   # 1,2,3,10
_AXIS_Y_RE = re.compile(r"^[A-Z]$")     # A,B,C
_PANEL_RE  = re.compile(r"^D\d{2}$", re.IGNORECASE)
_BALC_RE   = re.compile(r"^BL\d{2}$", re.IGNORECASE)
_NUM_RE    = re.compile(r"^\d{2,5}$")   # 40..99999
_BEAM_LABEL_RE = re.compile(r"K\d", re.IGNORECASE)  # K1, K2, ...

def clean_token_text(s: str) -> str:
    s = s.strip().upper()
    s = s.replace(" ", "")
    s = s.replace("-", "")
    s = s.replace("_", "")
    return s

def extract_number_from_text(s: str) -> Optional[int]:
    """OCR metninden tek başına bir sayı çıkarmaya çalışır.
    Örnek: '480' → 480, '  430 ' → 430, 'K1 50/50' → None (kiriş etiketi), '50/50' → None
    """
    s = s.strip()
    # Kiriş isimleri veya kesir içeren metinleri filtrele
    if '/' in s or _BEAM_LABEL_RE.search(s):
        return None
    # Sadece rakamları çıkar
    digits = re.sub(r'[^\d]', '', s)
    if len(digits) < 2 or len(digits) > 5:
        return None
    val = int(digits)
    if val < 20 or val > 9999:
        return None
    return val

def token_is_panel(t: Token) -> bool:
    return bool(_PANEL_RE.fullmatch(clean_token_text(t.text)))

def token_is_axis_x_label(t: Token) -> bool:
    return bool(_AXIS_X_RE.fullmatch(clean_token_text(t.text)))

def token_is_axis_y_label(t: Token) -> bool:
    return bool(_AXIS_Y_RE.fullmatch(clean_token_text(t.text)))

def token_is_number_cm(t: Token) -> bool:
    return extract_number_from_text(t.text) is not None

def centroid_of_bbox(bb: Tuple[float,float,float,float]) -> Tuple[float,float]:
    x1,y1,x2,y2 = bb
    return (x1+x2)/2.0, (y1+y2)/2.0

def sort_unique(vals: List[float], tol: float = 8.0) -> List[float]:
    """Sort and merge close values (pixels) using clustering to avoid mean drift."""
    if not vals:
        return []
    vals = sorted(vals)
    groups = [[vals[0]]]
    for v in vals[1:]:
        if abs(v - groups[-1][-1]) <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    
    # Her grubun ortalamasını al
    return [sum(g) / len(g) for g in groups]


def build_axes_from_axis_bubbles(
    dets: List[Det],
    tokens: List[Token],
    img_w: int,
    img_h: int,
) -> Tuple[List[float], List[float], List[str], List[str]]:
    axis_bubbles = [d for d in dets if d.cls_name == "axis_bubble" and d.conf >= 0.25]
    if not axis_bubbles:
        raise RuntimeError("No axis_bubble detections. Improve axis_bubble training or add a fallback heuristic.")

    centers = [(centroid_of_bbox(d.bbox), d) for d in axis_bubbles]

    top = [c for c in centers if c[0][1] < img_h * 0.30]
    left = [c for c in centers if c[0][0] < img_w * 0.30]

    if len(top) < 2:
        top = sorted(centers, key=lambda z: z[0][1])[: max(2, len(centers)//2)]
    if len(left) < 2:
        left = sorted(centers, key=lambda z: z[0][0])[: max(2, len(centers)//2)]

    x_lines = sort_unique([c[0][0] for c in top])
    y_lines = sort_unique([c[0][1] for c in left])

    axis_tokens = [t for t in tokens if (token_is_axis_x_label(t) or token_is_axis_y_label(t)) and t.conf >= 0.3]

    def nearest_label(px: float, py: float, want: str) -> Optional[str]:
        best = None
        best_d = 1e18
        for t in axis_tokens:
            txt = clean_token_text(t.text)
            if want == "x" and not token_is_axis_x_label(t):
                continue
            if want == "y" and not token_is_axis_y_label(t):
                continue
            d = (t.cx - px) ** 2 + (t.cy - py) ** 2
            if d < best_d:
                best_d = d
                best = txt
        if best is not None and best_d <= (120.0 ** 2):
            return best
        return None

    x_labels: List[str] = []
    y_labels: List[str] = []

    for x in x_lines:
        lbl = nearest_label(x, img_h * 0.08, "x")
        x_labels.append(lbl if lbl else "")

    for y in y_lines:
        lbl = nearest_label(img_w * 0.08, y, "y")
        y_labels.append(lbl if lbl else "")

    if any(l == "" for l in x_labels):
        x_labels = [str(i + 1) for i in range(len(x_lines))]
    if any(l == "" for l in y_labels):
        y_labels = [chr(ord("A") + i) for i in range(len(y_lines))]

    return x_lines, y_lines, x_labels, y_labels


def build_axes_hybrid(
    dets: List[Det],
    tokens: List[Token],
    img_w: int,
    img_h: int,
    col_tol: float = 30.0,
) -> Tuple[List[float], List[float], List[str], List[str]]:
    """Kolonlar, döşeme sınırları ve aks balonlarını harmanlayarak aks sistemi oluşturur."""
    columns = [d for d in dets if d.cls_name == "column_symbol" and d.conf >= 0.25]
    slabs = [d for d in dets if d.cls_name == "slab_area" and d.conf >= 0.25]
    bubbles = [d for d in dets if d.cls_name == "axis_bubble" and d.conf >= 0.20]

    xs, ys = [], []
    # 1. Kolon merkezleri
    for d in columns:
        cx, cy = centroid_of_bbox(d.bbox)
        xs.append(cx); ys.append(cy)
    
    # 2. Döşeme sınırları (Eksik kolonları telafi eder)
    for d in slabs:
        x1, y1, x2, y2 = d.bbox
        xs.extend([x1, x2])
        ys.extend([y1, y2])
        
    # 3. Aks balonu merkezleri
    for d in bubbles:
        cx, cy = centroid_of_bbox(d.bbox)
        xs.append(cx); ys.append(cy)

    if not xs or not ys:
        # Hiç veri yoksa bubble metoduna düş (o da hata fırlatabilir)
        return build_axes_from_axis_bubbles(dets, tokens, img_w, img_h)

    # Grupla
    x_lines = sort_unique(xs, tol=col_tol)
    y_lines = sort_unique(ys, tol=col_tol)

    # OCR etiketleri
    axis_tokens = [t for t in tokens if (token_is_axis_x_label(t) or token_is_axis_y_label(t)) and t.conf >= 0.3]

    def nearest_label(px: float, py: float, want: str) -> Optional[str]:
        best, best_d = None, 1e18
        for t in axis_tokens:
            if want == "x" and not token_is_axis_x_label(t): continue
            if want == "y" and not token_is_axis_y_label(t): continue
            d = (t.cx - px) ** 2 + (t.cy - py) ** 2
            if d < best_d:
                best_d, best = d, clean_token_text(t.text)
        return best if best_d <= (160.0 ** 2) else None

    x_labels = [nearest_label(x, img_h*0.05, "x") or nearest_label(x, img_h*0.95, "x") or "" for x in x_lines]
    y_labels = [nearest_label(img_w*0.05, y, "y") or nearest_label(img_w*0.95, y, "y") or "" for y in y_lines]

    # Otomatik doldur
    if any(l=="" for l in x_labels): x_labels = [str(i+1) for i in range(len(x_lines))]
    if any(l=="" for l in y_labels): y_labels = [chr(ord("A")+i) for i in range(len(y_lines))]

    print(f"[HYBRID-AXES] X: {x_labels}, Y: {y_labels}")
    return x_lines, y_lines, x_labels, y_labels


def determine_cell_types(
    dets: List[Det],
    x_lines: List[float],
    y_lines: List[float],
    x_labels: List[str],
    y_labels: List[str],
    overlap_threshold: float = 0.15,
) -> List[List[dict]]:
    """Akslar arası her hücrenin tipini belirler.

    Her hücre bölgesinde slab_area tespiti varsa 'slab',
    opening_area varsa 'opening', hiçbiri yoksa 'void'.

    Returns:
        2D liste: cell_types[row][col] = {"cell": "1A-2B", "type": "slab"|"opening"|"void"}
    """
    slab_dets = [d for d in dets if d.cls_name == "slab_area" and d.conf >= 0.25]
    opening_dets = [d for d in dets if d.cls_name == "opening_area" and d.conf >= 0.25]

    def bbox_overlap_ratio(cell_bbox, det_bbox):
        """Hücre bbox'ı ile tespit bbox'ı arasındaki kesişim oranını hesaplar."""
        cx1, cy1, cx2, cy2 = cell_bbox
        dx1, dy1, dx2, dy2 = det_bbox
        ix1 = max(cx1, dx1)
        iy1 = max(cy1, dy1)
        ix2 = min(cx2, dx2)
        iy2 = min(cy2, dy2)
        if ix1 >= ix2 or iy1 >= iy2:
            return 0.0
        inter = (ix2 - ix1) * (iy2 - iy1)
        cell_area = (cx2 - cx1) * (cy2 - cy1)
        if cell_area <= 0:
            return 0.0
        return inter / cell_area

    num_rows = len(y_lines) - 1
    num_cols = len(x_lines) - 1
    cell_types: List[List[dict]] = []

    print(f"[CELL-TYPE] Grid boyutu: {num_rows} satır x {num_cols} sütun")
    print(f"[CELL-TYPE] Slab tespiti: {len(slab_dets)}, Opening tespiti: {len(opening_dets)}")

    for j in range(num_rows):
        row_cells: List[dict] = []
        for i in range(num_cols):
            cell_bbox = (x_lines[i], y_lines[j], x_lines[i + 1], y_lines[j + 1])
            cell_label = f"{x_labels[i]}{y_labels[j]}-{x_labels[i+1]}{y_labels[j+1]}"

            # Slab kontrolü
            is_slab = False
            for d in slab_dets:
                ratio = bbox_overlap_ratio(cell_bbox, d.bbox)
                if ratio >= overlap_threshold:
                    is_slab = True
                    break

            # Opening kontrolü
            is_opening = False
            for d in opening_dets:
                ratio = bbox_overlap_ratio(cell_bbox, d.bbox)
                if ratio >= overlap_threshold:
                    is_opening = True
                    break

            if is_opening:
                cell_type = "opening"
            elif is_slab:
                cell_type = "slab"
            else:
                cell_type = "void"

            row_cells.append({"cell": cell_label, "type": cell_type})
            print(f"  [{j},{i}] {cell_label} → {cell_type}")
        cell_types.append(row_cells)

    return cell_types


def _token_inside_bbox(t: Token, bbox: Tuple[float,float,float,float], margin: float = 15.0) -> bool:
    """Token merkezi bbox içinde mi (marjinli)?"""
    x1, y1, x2, y2 = bbox
    return (x1 - margin) <= t.cx <= (x2 + margin) and (y1 - margin) <= t.cy <= (y2 + margin)


def parse_spans_cm_from_ocr(
    tokens: List[Token], img_w: int, img_h: int,
    expected_x: int, expected_y: int,
    x_lines: List[float], y_lines: List[float],
    x_labels: List[str], y_labels: List[str],
    dim_dets: Optional[List[Det]] = None
) -> Tuple[List[int], List[int], dict, dict]:
    """OCR tokenları ve YOLO dimension_text tespitleri kullanarak
    X ve Y span değerlerini cm olarak çıkarır. Fiziksel ölçek doğrulaması yapar.
    """
    # Tüm sayısal OCR tokenlarını topla
    nums = []
    for t in tokens:
        val = extract_number_from_text(t.text)
        if val is None:
            continue
        nums.append({
            "val": val, 
            "cx": t.cx, "cy": t.cy, 
            "conf": t.conf, 
            "tok": t,
            "id": id(t)
        })

    print(f"[DIM-OCR] Toplam sayısal token: {len(nums)}")
    print(f"[DIM-OCR] Beklenen: x={expected_x}, y={expected_y}")

    def get_interval_between(pos: float, lines: List[float]) -> int:
        if len(lines) < 2: return -1
        for i in range(len(lines) - 1):
            if lines[i] - 20.0 <= pos <= lines[i+1] + 20.0:
                return i
        return -1

    # --- Ön-analiz: Tahmini ölçek (px/cm) hesabı ---
    # Bu adım, "2170" gibi devasa yanlış okumaları ayıklamak için referans oluşturur.
    scale_ratios = []
    for d in (dim_dets or []):
        dcx, dcy = centroid_of_bbox(d.bbox)
        for n in nums:
            if _token_inside_bbox(n["tok"], d.bbox, margin=20.0):
                # Bu token bir dimension_text kutusu içinde. Hangi akslar arasında?
                w_box = d.bbox[2] - d.bbox[0]
                h_box = d.bbox[3] - d.bbox[1]
                idx = -1
                px_dist = 1.0
                if w_box > h_box: # Yatay kutu (X ölçüsü olabilir)
                    idx = get_interval_between(dcx, x_lines)
                    if idx != -1: px_dist = x_lines[idx+1] - x_lines[idx]
                else: # Dikey kutu (Y ölçüsü olabilir)
                    idx = get_interval_between(dcy, y_lines)
                    if idx != -1: px_dist = y_lines[idx+1] - y_lines[idx]
                
                if idx != -1 and px_dist > 5:
                    scale_ratios.append(px_dist / n["val"])

    # Global medyan ölçek (piksel / cm)
    global_px_per_cm = 2.0 # Fallback
    if scale_ratios:
        global_px_per_cm = np.median(scale_ratios)
        print(f"[DIM-OCR] Tahmini global ölçek: {global_px_per_cm:.3f} px/cm")

    def is_physically_consistent(val_cm, px_dist, tolerance=0.5):
        """Ölçü değeri (cm), piksel mesafesiyle tutarlı mı?"""
        if global_px_per_cm is None: return True
        expected_cm = px_dist / global_px_per_cm
        ratio = val_cm / expected_cm if expected_cm > 0 else 999
        return (1.0 - tolerance) <= ratio <= (1.0 + tolerance)

    x_spans = [100] * expected_x
    y_spans = [100] * expected_y
    used_token_ids = set()

    # --- Method 1: YOLO Box + Scale Validation ---
    if dim_dets:
        from collections import defaultdict
        mapped = defaultdict(list) # idx -> [(val, token_id, axis_dist, is_x)]

        for d in dim_dets:
            dcx, dcy = centroid_of_bbox(d.bbox)
            w_box, h_box = d.bbox[2]-d.bbox[0], d.bbox[3]-d.bbox[1]
            
            for n in nums:
                if n["id"] in used_token_ids: continue
                if _token_inside_bbox(n["tok"], d.bbox, margin=25.0):
                    # X mi Y mi?
                    if w_box > h_box: # X ekseni adayı
                        idx = get_interval_between(dcx, x_lines)
                        if idx != -1:
                            px_w = x_lines[idx+1] - x_lines[idx]
                            if is_physically_consistent(n["val"], px_w):
                                mapped[('x', idx)].append((n["val"], n["id"], abs(dcy - img_h/2)))
                    else: # Y ekseni adayı
                        idx = get_interval_between(dcy, y_lines)
                        if idx != -1:
                            px_h = y_lines[idx+1] - y_lines[idx]
                            if is_physically_consistent(n["val"], px_h):
                                mapped[('y', idx)].append((n["val"], n["id"], abs(dcx - img_w/2)))

        for (axis, idx), cands in mapped.items():
            best = min(cands, key=lambda x: x[2]) # Merkeze en yakın olanı seç
            if axis == 'x': x_spans[idx] = best[0]
            else: y_spans[idx] = best[0]
            used_token_ids.add(best[1])

    # --- Method 2: Position Based + Scale Validation (Backup) ---
    # Sadece bariz dış bölgelerdeki (top/bottom/left/right %20) sayıları al
    for i in range(expected_x):
        if x_spans[i] != 100: continue
        px_w = x_lines[i+1] - x_lines[i]
        target_cx = (x_lines[i] + x_lines[i+1]) / 2
        
        candidates = []
        for n in nums:
            if n["id"] in used_token_ids: continue
            if n["cy"] < img_h * 0.25 or n["cy"] > img_h * 0.75:
                dist = abs(n["cx"] - target_cx)
                if dist < px_w * 0.4: # Aks merkezine yakınlık
                    if is_physically_consistent(n["val"], px_w, tolerance=0.3):
                        candidates.append(n)
        if candidates:
            best = min(candidates, key=lambda c: abs(c["cx"] - target_cx))
            x_spans[i] = best["val"]
            used_token_ids.add(best["id"])

    for j in range(expected_y):
        if y_spans[j] != 100: continue
        px_h = y_lines[j+1] - y_lines[j]
        target_cy = (y_lines[j] + y_lines[j+1]) / 2
        
        candidates = []
        for n in nums:
            if n["id"] in used_token_ids: continue
            if n["cx"] < img_w * 0.25 or n["cx"] > img_w * 0.75:
                dist = abs(n["cy"] - target_cy)
                if dist < px_h * 0.4:
                    if is_physically_consistent(n["val"], px_h, tolerance=0.3):
                        candidates.append(n)
        if candidates:
            best = min(candidates, key=lambda c: abs(c["cy"] - target_cy))
            y_spans[j] = best["val"]
            used_token_ids.add(best["id"])

    # Detaylı dict oluştur
    x_span_details = {f"{x_labels[i]}-{x_labels[i+1]}": x_spans[i] for i in range(expected_x)}
    y_span_details = {f"{y_labels[j]}-{y_labels[j+1]}": y_spans[j] for j in range(expected_y)}

    print(f"[DIM-OCR] Nihai X-Spans: {list(x_span_details.values())}")
    print(f"[DIM-OCR] Nihai Y-Spans: {list(y_span_details.values())}")

    return x_spans, y_spans, x_span_details, y_span_details


def build_edges_from_spans_cm(spans_cm: List[int], dx_cm: int) -> List[int]:
    """Span cm değerlerini grid indexlerine (edge) dönüştürür."""
    edges = [0]
    for s in spans_cm:
        # dx_cm biriminde kaç hücre?
        count = int(round(s / dx_cm))
        if count < 1: count = 1 # En az 1 hücre
        edges.append(edges[-1] + count)
    return edges



def cell_index_from_point(px: float, py: float, x_lines: List[float], y_lines: List[float]) -> Tuple[int, int]:
    i = None
    for k in range(len(x_lines) - 1):
        if x_lines[k] <= px < x_lines[k + 1]:
            i = k
            break
    if i is None:
        i = max(0, min(len(x_lines) - 2, int(np.searchsorted(x_lines, px) - 1)))

    j = None
    for k in range(len(y_lines) - 1):
        if y_lines[k] <= py < y_lines[k + 1]:
            j = k
            break
    if j is None:
        j = max(0, min(len(y_lines) - 2, int(np.searchsorted(y_lines, py) - 1)))

    return i, j


def build_slabs_from_panels(
    panel_tokens: List[Token],
    x_lines: List[float], y_lines: List[float],
    x_labels: List[str], y_labels: List[str],
    x_edges: List[int], y_edges: List[int],
    dx_m: float, dy_m: float,
) -> List[dict]:
    slabs = []
    for t in panel_tokens:
        pid = clean_token_text(t.text)
        i, j = cell_index_from_point(t.cx, t.cy, x_lines, y_lines)

        xspan = f"{x_labels[i]}-{x_labels[i+1]}"
        yspan = f"{y_labels[j]}-{y_labels[j+1]}"

        i0 = x_edges[i]
        i1 = x_edges[i + 1] - 1
        j0 = y_edges[j]
        j1 = y_edges[j + 1] - 1

        slabs.append({
            "id": pid,
            "kind": "TWOWAY",
            "axes": {"x_span": xspan, "y_span": yspan},
            "bbox_ij": [i0, j0, i1, j1],
            "dx": dx_m,
            "dy": dy_m
        })

    seen = set()
    out = []
    for s in slabs:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        out.append(s)
    return out


def assign_openings_to_cells(
    dets: List[Det],
    x_lines: List[float], y_lines: List[float],
    x_edges: List[int], y_edges: List[int],
) -> List[dict]:
    openings = []
    for d in dets:
        if d.cls_name != "opening_area" or d.conf < 0.35:
            continue
        cx, cy = centroid_of_bbox(d.bbox)
        i, j = cell_index_from_point(cx, cy, x_lines, y_lines)
        i0 = x_edges[i]; i1 = x_edges[i+1] - 1
        j0 = y_edges[j]; j1 = y_edges[j+1] - 1
        openings.append({
            "conf": d.conf,
            "cell_ij": [i, j],
            "bbox_ij": [i0, j0, i1, j1],
            "bbox_px": [int(d.bbox[0]), int(d.bbox[1]), int(d.bbox[2]), int(d.bbox[3])]
        })
    return openings


def draw_debug(
    image_bgr: np.ndarray,
    x_lines: List[float], y_lines: List[float],
    x_labels: List[str], y_labels: List[str],
    x_spans_cm: List[int], y_spans_cm: List[int],
    slabs: List[dict],
    openings: List[dict],
    out_path: str,
    cell_types: Optional[List[List[dict]]] = None,
    column_centers: Optional[List[Tuple[float, float]]] = None,
) -> None:
    img = image_bgr.copy()
    h, w = img.shape[:2]

    # Hücre tiplerini yarı saydam overlay olarak çiz
    if cell_types and len(x_lines) >= 2 and len(y_lines) >= 2:
        overlay = img.copy()
        for j, row_cells in enumerate(cell_types):
            for i, cell_info in enumerate(row_cells):
                cx1 = int(round(x_lines[i]))
                cy1 = int(round(y_lines[j]))
                cx2 = int(round(x_lines[i + 1]))
                cy2 = int(round(y_lines[j + 1]))
                ctype = cell_info["type"]
                if ctype == "slab":
                    color = (0, 180, 0)  # yeşil
                elif ctype == "opening":
                    color = (0, 0, 200)  # kırmızı
                else:  # void
                    color = (180, 180, 180)  # gri
                cv2.rectangle(overlay, (cx1, cy1), (cx2, cy2), color, -1)
                # Hücre etiketi
                label_txt = cell_info["type"][0].upper()  # S, O, V
                mid_x = (cx1 + cx2) // 2
                mid_y = (cy1 + cy2) // 2
                cv2.putText(overlay, label_txt, (mid_x - 8, mid_y + 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.25, img, 0.75, 0, img)

    # Aks çizgileri
    for x, lbl in zip(x_lines, x_labels):
        x = int(round(x))
        cv2.line(img, (x, 0), (x, h), (0, 200, 0), 1)
        cv2.putText(img, lbl, (x+3, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 160, 0), 2, cv2.LINE_AA)

    for y, lbl in zip(y_lines, y_labels):
        y = int(round(y))
        cv2.line(img, (0, y), (w, y), (0, 200, 0), 1)
        cv2.putText(img, lbl, (5, y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 160, 0), 2, cv2.LINE_AA)

    # Kolon merkezlerini turuncu noktalar olarak çiz
    if column_centers:
        for ccx, ccy in column_centers:
            cv2.circle(img, (int(round(ccx)), int(round(ccy))), 8, (0, 140, 255), -1)  # turuncu
            cv2.circle(img, (int(round(ccx)), int(round(ccy))), 8, (0, 80, 180), 2)    # koyu kenarlık

    cv2.putText(img, f"X spans (cm): {x_spans_cm}", (10, h-60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 200), 2, cv2.LINE_AA)
    cv2.putText(img, f"Y spans (cm): {y_spans_cm}", (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 200), 2, cv2.LINE_AA)

    for s in slabs:
        try:
            xs = s["axes"]["x_span"].split("-")
            ys = s["axes"]["y_span"].split("-")
            i = x_labels.index(xs[0])
            j = y_labels.index(ys[0])
            cx = int((x_lines[i] + x_lines[i+1]) / 2)
            cy = int((y_lines[j] + y_lines[j+1]) / 2)
        except Exception:
            continue
        cv2.putText(img, s["id"], (cx-25, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,0), 3, cv2.LINE_AA)
        cv2.putText(img, s["id"], (cx-25, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 1, cv2.LINE_AA)

    for op in openings:
        x1,y1,x2,y2 = op["bbox_px"]
        cv2.rectangle(img, (x1,y1), (x2,y2), (0,0,255), 2)

    cv2.imwrite(out_path, img)


def main_flow(args: dict) -> Tuple[dict, str]:
    classes_map = DEFAULT_CLASSES.copy()
    if args.get("classes_json"):
        with open(args["classes_json"], "r", encoding="utf-8") as f:
            user_map = json.load(f)
        classes_map = {int(k): str(v) for k, v in user_map.items()}

    img = cv2.imread(args["image"])
    if img is None:
        raise RuntimeError(f"Could not read image: {args['image']}")
    h, w = img.shape[:2]

    dets = run_yolo(args["weights"], args["image"], imgsz=args["imgsz"], conf=args["conf"], classes_map=classes_map)

    tokens = ocr_tokens(img)
    print(f"[OCR] Normal OCR token sayısı: {len(tokens)}")
    for t in tokens:
        print(f"  [OCR-N] '{t.text}'  pos=({t.cx:.0f},{t.cy:.0f})  conf={t.conf:.2f}")
    
    # --- YOLO dimension_text tespitlerini hedefli kırpma+OCR ile oku ---
    # Geliştirilmiş pipeline: çoklu ön-işleme + çoklu OCR geçişi + oylama
    dim_text_dets = [d for d in dets if d.cls_name == "dimension_text" and d.conf >= 0.20]
    print(f"[DIM-CROP] YOLO dimension_text tespit sayısı: {len(dim_text_dets)}")

    def _preprocess_variants(crop_bgr: np.ndarray) -> List[np.ndarray]:
        """Kırpıntıdan farklı ön-işleme varyantları oluşturur."""
        variants = []
        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)

        # Varyant 1: Orijinal (sadece büyütülmüş)
        variants.append(cv2.resize(crop_bgr, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC))

        # Varyant 2: CLAHE kontrast artırma
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)
        enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        variants.append(cv2.resize(enhanced_bgr, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC))

        # Varyant 3: Otsu binarizasyon
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Morfolojik temizleme (küçük gürültü noktalarını sil)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        otsu = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel)
        otsu_bgr = cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR)
        variants.append(cv2.resize(otsu_bgr, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_NEAREST))

        # Varyant 4: Adaptif eşikleme
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 15, 5)
        adaptive = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel)
        adaptive_bgr = cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR)
        variants.append(cv2.resize(adaptive_bgr, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_NEAREST))

        # Varyant 5: Keskinleştirme (sharpen) + büyütme
        sharpen_kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(crop_bgr, -1, sharpen_kernel)
        variants.append(cv2.resize(sharpened, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC))

        return variants

    def _multi_pass_ocr(crop_bgr: np.ndarray) -> Optional[int]:
        """Çoklu ön-işleme varyantlarıyla OCR çalıştırır ve oylama ile en güvenilir değeri seçer."""
        variants = _preprocess_variants(crop_bgr)
        all_readings = []  # (value, confidence) çiftleri

        for vi, variant in enumerate(variants):
            try:
                vtokens = ocr_tokens(variant, allowlist='0123456789')
                for vt in vtokens:
                    val = extract_number_from_text(vt.text)
                    if val is not None:
                        all_readings.append((val, vt.conf, vi))
            except Exception:
                continue

        if not all_readings:
            return None

        # Oylama: aynı değeri okuyan varyant sayısını say
        from collections import Counter
        value_counts = Counter()
        value_conf_sum = {}
        for val, conf, vi in all_readings:
            value_counts[val] += 1
            value_conf_sum[val] = value_conf_sum.get(val, 0) + conf

        # En çok okunan değeri seç; eşitlik varsa toplam güven skoruna bak
        best_val = max(value_counts.keys(),
                       key=lambda v: (value_counts[v], value_conf_sum.get(v, 0)))

        total_variants = len(variants)
        print(f"      [OCR-VOTE] Okumalar: {dict(value_counts)} → Seçilen: {best_val} "
              f"({value_counts[best_val]}/{total_variants} varyant)")

        return best_val

    def _round_to_structural(val: int) -> int:
        """Yapısal ölçü değerini en yakın 5'in katına yuvarla.
        Yapısal planlarda ölçüler genellikle 5 veya 10'un katlarıdır.
        Örnek: 152 → 150, 163 → 165, 498 → 500
        """
        return round(val / 5) * 5

    for d in dim_text_dets:
        x1, y1, x2, y2 = int(d.bbox[0]), int(d.bbox[1]), int(d.bbox[2]), int(d.bbox[3])
        # Güvenli sınırlar
        pad = 10
        x1c = max(0, x1 - pad)
        y1c = max(0, y1 - pad)
        x2c = min(w, x2 + pad)
        y2c = min(h, y2 + pad)
        
        crop = img[y1c:y2c, x1c:x2c]
        if crop.size == 0:
            continue
        
        crop_h, crop_w = crop.shape[:2]
        is_vertical = crop_h > crop_w * 1.3  # Dik mi?
        
        if is_vertical:
            # Dikey metin → 90° döndür
            crop = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
        
        # Çoklu ön-işleme + oylama ile OCR
        val = _multi_pass_ocr(crop)
        
        if val is not None:
            # Yapısal yuvarlama uygula
            rounded_val = _round_to_structural(val)
            if rounded_val != val:
                print(f"  [DIM-CROP] bbox=({x1},{y1},{x2},{y2}) OCR={val} → yuvarlandı={rounded_val}")
                val = rounded_val

            orig_cx = (x1 + x2) / 2.0
            orig_cy = (y1 + y2) / 2.0
            
            status = "DİKEY→YATAY" if is_vertical else "YATAY"
            print(f"  [DIM-CROP] bbox=({x1},{y1},{x2},{y2}) {status} val={val} (multi-pass)")

            # Bu bbox'taki eski tokenları kaldır
            x_b1, y_b1, x_b2, y_b2 = d.bbox
            tokens = [tk for tk in tokens if not (x_b1 <= tk.cx <= x_b2 and y_b1 <= tk.cy <= y_b2)]
            
            tokens.append(Token(
                text=str(val),
                cx=orig_cx,
                cy=orig_cy,
                conf=0.95,  # Multi-pass doğrulanmış → yüksek güven
                bbox=(x1, y1, x2, y2)
            ))
            print(f"    → Yeni token eklendi: {val} cm @ ({orig_cx:.0f},{orig_cy:.0f})")
    
    print(f"[OCR] Toplam birleştirilmiş token sayısı: {len(tokens)}")

    # normalize token text once
    tokens = [Token(text=clean_token_text(t.text), cx=t.cx, cy=t.cy, conf=t.conf, bbox=t.bbox) for t in tokens]

    # Önce Hibrit (Kolon + Döşeme sınırı) aks oluşturmayı dene
    axis_source = "unknown"
    try:
        x_lines, y_lines, x_labels, y_labels = build_axes_hybrid(dets, tokens, w, h)
        axis_source = "hybrid_geom"
        print(f"[AXES] Hibrit geometriden aks oluşturuldu: {len(x_lines)} dikey, {len(y_lines)} yatay")
    except Exception as hybrid_err:
        print(f"[AXES] Hibrit aks başarısız: {hybrid_err}")
        print(f"[AXES] Axis bubble tabanlı sisteme geri dönülüyor...")
        try:
            x_lines, y_lines, x_labels, y_labels = build_axes_from_axis_bubbles(dets, tokens, w, h)
            axis_source = "axis_bubbles"
            print(f"[AXES] Axis bubble'dan aks oluşturuldu: {len(x_lines)} dikey, {len(y_lines)} yatay")
        except Exception as e:
            import tkinter.messagebox as messagebox
            messagebox.showwarning("Akslar Bulunamadı", f"Hibrit hata: {hybrid_err}\nAxis bubble hatası: {e}")
            x_lines, y_lines, x_labels, y_labels = [], [], [], []
            axis_source = "none"

    expected_x_spans = max(1, len(x_labels) - 1)
    expected_y_spans = max(1, len(y_labels) - 1)

    # YOLO dimension_text tespitlerini topla
    dim_text_dets = [d for d in dets if d.cls_name == "dimension_text" and d.conf >= 0.20]

    try:
        x_spans_cm, y_spans_cm, x_span_details, y_span_details = parse_spans_cm_from_ocr(
            tokens, w, h, expected_x_spans, expected_y_spans, 
            x_lines, y_lines, x_labels, y_labels, dim_dets=dim_text_dets
        )
    except Exception as e:
        import tkinter.messagebox as messagebox
        messagebox.showwarning(
            "Ölçü Okunamadı",
            f"OCR ile ölçü değerleri tam olarak okunamadı veya haritalanamadı, varsayılan 100 cm kullanılıyor.\n\nDetay: {e}"
        )
        x_spans_cm = [100] * expected_x_spans
        y_spans_cm = [100] * expected_y_spans
        x_span_details = {}
        y_span_details = {}

    # ── OCR span tutarlılık kontrolü ──
    # OCR bazen "340" → "3400" gibi hatalar yapar. Her span'in cm/piksel
    # oranını karşılaştırıp aykırı olanları düzeltiriz.
    def _sanitize_spans(spans_cm: List[int], lines_px: List[float], axis_name: str) -> List[int]:
        n = len(spans_cm)
        if n < 2 or len(lines_px) < n + 1:
            return spans_cm

        # Her span için cm/piksel oranını hesapla
        ratios = []
        for i in range(n):
            px_w = lines_px[i + 1] - lines_px[i]
            if px_w > 5:
                # 100 değeri genellikle 'okunamadı' filler değeridir, medyanı bozmasın.
                # Sadece OCR'dan gerçek gelmiş olabilecek değerleri medyan için kullan.
                is_reliable = (spans_cm[i] != 100)
                ratios.append((i, spans_cm[i] / px_w, px_w, is_reliable))
            else:
                ratios.append((i, None, px_w, False))

        reliable_ratios = [r[1] for r in ratios if r[3] and r[1] is not None]
        
        # Eğer güvenilir veri yoksa tüm veriyi (100'ler dahil) kullan
        if reliable_ratios:
            median_r = np.median(reliable_ratios)
        else:
            all_valid = [r[1] for r in ratios if r[1] is not None]
            if not all_valid: return spans_cm
            median_r = np.median(all_valid)

        print(f"  [SANITIZE-{axis_name}] Medyan ölçek (cm/px): {1/median_r:.3f} px/cm")

        corrected = list(spans_cm)
        for idx, r, pw, is_rel in ratios:
            if r is None: continue
            # Eğer değer medyanın çok dışındaysa veya veri 'filler' (100) ise ve medyanla uyumsuzsa düzelt
            if r > median_r * 2.5 or r < median_r / 2.5 or (not is_rel and abs(r-median_r) > median_r * 0.4):
                new_val = round(pw * median_r)
                # 5 veya 10'un katına yuvarla
                new_val = round(new_val / 5) * 5
                if new_val > 0:
                    if corrected[idx] != new_val:
                        print(f"    -> Span {idx}: {corrected[idx]} → {new_val} cm (oran {r:.4f} vs medyan {median_r:.4f})")
                        corrected[idx] = new_val
        return corrected

    x_spans_cm = _sanitize_spans(x_spans_cm, x_lines, "X")
    y_spans_cm = _sanitize_spans(y_spans_cm, y_lines, "Y")
    print(f"[SANITIZE] Son X-Spans: {x_spans_cm}")
    print(f"[SANITIZE] Son Y-Spans: {y_spans_cm}")

    x_edges = build_edges_from_spans_cm(x_spans_cm, args["dx_cm"])
    y_edges = build_edges_from_spans_cm(y_spans_cm, args["dx_cm"])
    dx_m = args["dx_cm"] / 100.0
    dy_m = args["dx_cm"] / 100.0

    panel_tokens = [t for t in tokens if token_is_panel(t) and t.conf >= 0.25]
    if not panel_tokens:
        import tkinter.messagebox as messagebox
        messagebox.showinfo("Bilgi", "OCR tarafından panel kimliği (D11, D12 vb.) bulunamadı. Paneller boş bırakılıyor.")

    slabs = build_slabs_from_panels(panel_tokens, x_lines, y_lines, x_labels, y_labels, x_edges, y_edges, dx_m, dy_m)
    openings = assign_openings_to_cells(dets, x_lines, y_lines, x_edges, y_edges)

    # Hücre tiplerini belirle (slab / opening / void)
    cell_types = []
    if len(x_lines) >= 2 and len(y_lines) >= 2:
        cell_types = determine_cell_types(dets, x_lines, y_lines, x_labels, y_labels)

    # ── Balkon döşemesi tespitleri ──
    balcony_dets = [d for d in dets if d.cls_name == "balcony_area" and d.conf >= 0.25]
    balcony_text_tokens = [t for t in tokens if _BALC_RE.fullmatch(t.text)]
    print(f"[BALCONY] balcony_area tespiti: {len(balcony_dets)}, balcony_text OCR: {len(balcony_text_tokens)}")

    # Tüm sayısal OCR tokenlarını topla
    num_tokens_all = []
    for t in tokens:
        val = extract_number_from_text(t.text)
        if val is not None:
            num_tokens_all.append((val, t))

    balconies = []
    for bd in balcony_dets:
        bcx, bcy = centroid_of_bbox(bd.bbox)
        bx1, by1, bx2, by2 = bd.bbox
        b_width_px = bx2 - bx1
        b_height_px = by2 - by1

        # En yakın BL etiketini bul
        bl_label = None
        best_dist = 1e18
        for bt in balcony_text_tokens:
            d2 = (bt.cx - bcx) ** 2 + (bt.cy - bcy) ** 2
            if d2 < best_dist and _token_inside_bbox(bt, bd.bbox, margin=50.0):
                best_dist = d2
                bl_label = bt.text

        # ── Kenar belirleme: grid sınırlarına göre ──
        edge = None
        adj_slab_id = None

        if len(x_lines) >= 2 and len(y_lines) >= 2:
            grid_x_min = x_lines[0]
            grid_x_max = x_lines[-1]
            grid_y_min = y_lines[0]
            grid_y_max = y_lines[-1]

            # Balkon merkezinin grid'e göre konumunu belirle
            if bcy < grid_y_min: edge = "top"
            elif bcy > grid_y_max: edge = "bottom"
            elif bcx < grid_x_min: edge = "left"
            elif bcx > grid_x_max: edge = "right"
            else:
                dist_top = abs(bcy - grid_y_min); dist_bottom = abs(bcy - grid_y_max)
                dist_left = abs(bcx - grid_x_min); dist_right = abs(bcx - grid_x_max)
                edge_dists = {"top": dist_top, "bottom": dist_bottom, "left": dist_left, "right": dist_right}
                edge = min(edge_dists, key=edge_dists.get)

            print(f"  [BALCONY] bbox=({int(bx1)},{int(by1)},{int(bx2)},{int(by2)}) center=({int(bcx)},{int(bcy)}) → edge={edge}")

            # Komşu döşemeyi bul
            if slabs:
                min_dist_s = 1e18
                for s in slabs:
                    try:
                        xs = s["axes"]["x_span"].split("-")
                        ys = s["axes"]["y_span"].split("-")
                        si = x_labels.index(xs[0])
                        sj = y_labels.index(ys[0])
                        sx1, sx2 = x_lines[si], x_lines[si + 1]
                        sy1, sy2 = y_lines[sj], y_lines[sj + 1]
                        dist = (bcx - (sx1+sx2)/2) ** 2 + (bcy - (sy1+sy2)/2) ** 2
                        if dist < min_dist_s:
                            min_dist_s = dist
                            adj_slab_id = s["id"]
                    except Exception: continue

        # ── Balkon ölçülerini dimension_text'lerden oku ──
        # Dim_text aramasında bulunan değerlerin piksel boyutuyla tutarlı olduğunu doğruluyoruz.
        depth_cm = 0
        width_cm = 0
        margin_px = 60.0

        # Mevcut grid spans'tan ölçek tahmini (X ve Y için ayrı)
        _px_per_cm_x = sum(x_lines[i+1]-x_lines[i] for i in range(len(x_spans_cm))) / sum(x_spans_cm) if sum(x_spans_cm) > 0 else 2.0
        _px_per_cm_y = sum(y_lines[j+1]-y_lines[j] for j in range(len(y_spans_cm))) / sum(y_spans_cm) if sum(y_spans_cm) > 0 else 2.0

        def _validate_dim(val_cm, px_size, px_per_cm, label=""):
            if px_per_cm <= 0 or px_size <= 0: return True
            expected_cm = px_size / px_per_cm
            ratio = val_cm / expected_cm if expected_cm > 0 else 999
            # Tolerance: %50 sapma kabul edilebilir (balkon bbox'ları kaba olabilir)
            ok = 0.5 <= ratio <= 2.0 
            if not ok:
                print(f"    [BALCONY] {label} dim_text REDDEDILDI: {val_cm}cm (beklenen ~{expected_cm:.0f}cm, oran={ratio:.2f})")
            return ok

        if edge in ("top", "bottom"):
            # Genişlik: yatay, Derinlik: dikey
            # Genişlik (width) - En iyi hizalanmış olanı seç
            width_candidates = []
            for val, t in num_tokens_all:
                if (bx1 - margin_px) <= t.cx <= (bx2 + margin_px):
                    if (edge == "bottom" and t.cy > by2 + 5) or (edge == "top" and t.cy < by1 - 5):
                        if _validate_dim(val, b_width_px, _px_per_cm_x, "Genişlik"):
                            dist_to_center = abs(t.cx - bcx)
                            width_candidates.append((val, dist_to_center))
            if width_candidates:
                # Merkeze (yatayda) en yakın olanı al (770 yerine 440'ı seçmek için)
                width_cm = min(width_candidates, key=lambda x: x[1])[0]

            # Derinlik (depth)
            depth_candidates = []
            for val, t in num_tokens_all:
                if (by1 - margin_px) <= t.cy <= (by2 + margin_px):
                    if t.cx > bx2 + 5 or t.cx < bx1 - 5:
                        if _validate_dim(val, b_height_px, _px_per_cm_y, "Derinlik"):
                            dist_to_center = abs(t.cy - bcy)
                            depth_candidates.append((val, dist_to_center))
            if depth_candidates:
                depth_cm = min(depth_candidates, key=lambda x: x[1])[0]

        elif edge in ("left", "right"):
            # Genişlik: dikey, Derinlik: yatay
            # Genişlik (width)
            width_candidates = []
            for val, t in num_tokens_all:
                if (by1 - margin_px) <= t.cy <= (by2 + margin_px):
                    if (edge == "right" and t.cx > bx2 + 5) or (edge == "left" and t.cx < bx1 - 5):
                        if _validate_dim(val, b_height_px, _px_per_cm_y, "Genişlik"):
                            dist_to_center = abs(t.cy - bcy)
                            width_candidates.append((val, dist_to_center))
            if width_candidates:
                width_cm = min(width_candidates, key=lambda x: x[1])[0]

            # Derinlik (depth)
            depth_candidates = []
            for val, t in num_tokens_all:
                if (bx1 - margin_px) <= t.cx <= (bx2 + margin_px):
                    if t.cy > by2 + 5 or t.cy < by1 - 5:
                        if _validate_dim(val, b_width_px, _px_per_cm_x, "Derinlik"):
                            dist_to_center = abs(t.cx - bcx)
                            depth_candidates.append((val, dist_to_center))
            if depth_candidates:
                depth_cm = min(depth_candidates, key=lambda x: x[1])[0]


        # Fallback: dimension_text'ten okunamazsa hücre overlap analizi ile hesapla
        # YOLO bbox'ı genellikle gerçek balkon sınırlarından daha geniş olur.
        # Eski yöntem (bbox kenarlarını akslara snap) tüm aksların span'larını
        # topluyordu ve yanlış sonuç veriyordu (ör. 2170 yerine 600 olmalı).
        # Yeni yöntem: her hücre ile balkon bbox overlap'ini kontrol eder,
        # sadece %50'den fazla kaplanan hücrelerin span'larını toplar.
        if (depth_cm == 0 or width_cm == 0) and len(x_lines) >= 2 and len(x_spans_cm) >= 1:
            px_per_cm_x = (x_lines[-1] - x_lines[0]) / sum(x_spans_cm) if sum(x_spans_cm) > 0 else 1.0
            px_per_cm_y = (y_lines[-1] - y_lines[0]) / sum(y_spans_cm) if sum(y_spans_cm) > 0 else 1.0

            if width_cm == 0:
                if edge in ("top", "bottom"):
                    # Yatay genişlik → balkon bbox'ının x-hücreleri ile overlap kontrolü
                    covered_spans = []
                    for ci in range(len(x_lines) - 1):
                        cell_left = x_lines[ci]
                        cell_right = x_lines[ci + 1]
                        cell_w = cell_right - cell_left
                        if cell_w <= 0:
                            continue
                        overlap_left = max(bx1, cell_left)
                        overlap_right = min(bx2, cell_right)
                        overlap = max(0, overlap_right - overlap_left)
                        if overlap > cell_w * 0.5:  # Hücrenin >%50'si kaplanıyorsa dahil et
                            covered_spans.append(ci)

                    if covered_spans and all(i < len(x_spans_cm) for i in covered_spans):
                        width_cm = sum(x_spans_cm[i] for i in covered_spans)
                        print(f"    [BALCONY] Genişlik (hücre overlap): {width_cm}cm (cells {covered_spans})")
                    else:
                        width_cm = round(b_width_px / px_per_cm_x) if px_per_cm_x > 0 else 0
                        print(f"    [BALCONY] Genişlik (piksel fallback): {width_cm}cm")
                elif edge in ("left", "right"):
                    # Dikey genişlik → balkon bbox'ının y-hücreleri ile overlap kontrolü
                    covered_spans = []
                    for ci in range(len(y_lines) - 1):
                        cell_top = y_lines[ci]
                        cell_bottom = y_lines[ci + 1]
                        cell_h = cell_bottom - cell_top
                        if cell_h <= 0:
                            continue
                        overlap_top = max(by1, cell_top)
                        overlap_bottom = min(by2, cell_bottom)
                        overlap = max(0, overlap_bottom - overlap_top)
                        if overlap > cell_h * 0.5:  # Hücrenin >%50'si kaplanıyorsa dahil et
                            covered_spans.append(ci)

                    if covered_spans and all(i < len(y_spans_cm) for i in covered_spans):
                        width_cm = sum(y_spans_cm[i] for i in covered_spans)
                        print(f"    [BALCONY] Genişlik (hücre overlap): {width_cm}cm (cells {covered_spans})")
                    else:
                        width_cm = round(b_height_px / px_per_cm_y) if px_per_cm_y > 0 else 0
                        print(f"    [BALCONY] Genişlik (piksel fallback): {width_cm}cm")

            if depth_cm == 0:
                if edge in ("top", "bottom"):
                    depth_cm = round(b_height_px / px_per_cm_y) if px_per_cm_y > 0 else 0
                elif edge in ("left", "right"):
                    depth_cm = round(b_width_px / px_per_cm_x) if px_per_cm_x > 0 else 0
                print(f"    [BALCONY] Derinlik (piksel fallback): {depth_cm}cm")

        balcony_entry = {
            "id": bl_label if bl_label else f"BL_unknown_{len(balconies)+1}",
            "conf": round(bd.conf, 3),
            "slab_id": adj_slab_id,
            "edge": edge,
            "depth_cm": depth_cm,
            "width_cm": width_cm,
            "bbox_px": [int(bx1), int(by1), int(bx2), int(by2)],
        }
        if depth_cm > 0 and width_cm > 0:
            balcony_entry["area_m2"] = round(depth_cm * width_cm / 10000, 2)

        balconies.append(balcony_entry)
        print(f"  [BALCONY] {balcony_entry['id']} → slab={adj_slab_id}, edge={edge}, depth={depth_cm}cm, width={width_cm}cm")

    out = {
        "units": "cm",
        "axes": {
            "x_labels": x_labels,
            "y_labels": y_labels,
            "x_spans_cm": x_spans_cm,
            "y_spans_cm": y_spans_cm,
            "x_span_details": x_span_details,
            "y_span_details": y_span_details,
            "x_lines_px": [round(v, 1) for v in x_lines],
            "y_lines_px": [round(v, 1) for v in y_lines],
            "source": axis_source,
        },
        "grid": {
            "dx_cm": args["dx_cm"],
            "dx_m": dx_m,
            "dy_m": dy_m,
            "nx": x_edges[-1] if x_edges else 0,
            "ny": y_edges[-1] if y_edges else 0,
            "x_edges": x_edges,
            "y_edges": y_edges,
        },
        "slabs": slabs,
        "balconies": balconies,
        "openings": openings,
        "cell_types": cell_types,
        "notes": {
            "materials": "USER_INPUT",
            "moments": "USER_INPUT",
            "kind_default": "TWOWAY (change by rules if needed)"
        }
    }

    out_dir = os.path.dirname(args["out_prefix"])
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    json_path = args["out_prefix"] + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    debug_path = args["out_prefix"] + "_debug.png"
    # Kolon merkezlerini debug çizimine gönder
    column_centers_px = []
    col_dets = [d for d in dets if d.cls_name == "column_symbol" and d.conf >= 0.25]
    for d in col_dets:
        column_centers_px.append(centroid_of_bbox(d.bbox))
    draw_debug(img, x_lines, y_lines, x_labels, y_labels, x_spans_cm, y_spans_cm, slabs, openings, debug_path,
               cell_types=cell_types, column_centers=column_centers_px)

    return out, debug_path


def run_pipeline_test(root, model_path: str = None):
    """
    Tkinter arayüzünden doğrudan tetiklenmek için giriş fonksiyonu.
    Görsel seçtirip pipeline'ı (YOLO + OCR) koşturur.
    """
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import threading

    if not model_path or not os.path.exists(model_path):
        model_path = os.path.join(os.path.dirname(__file__), "best.pt")
    
    if not os.path.exists(model_path):
        messagebox.showerror("Hata", f"Model dosyası bulunamadı:\n{model_path}")
        return

    image_path = filedialog.askopenfilename(
        title="Görsel Seç (Pipeline Test)",
        filetypes=[("Görseller", "*.png *.jpg *.jpeg")]
    )
    if not image_path:
        return

    # Kullanıcıdan Güven Eşiği (Conf) iste
    dlg = tk.Toplevel(root)
    dlg.title("Güven Eşiği (Conf)")
    dlg.geometry("300x160")
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.grab_set()

    conf_result = {"val": None}

    tk.Label(dlg, text="YOLO Nesne Tespiti Güven Eşiği:\n(Düşük eşik = daha çok nesne, yüksek eşik = daha az hata)", 
             font=("Segoe UI", 9), justify=tk.CENTER).pack(pady=10)
    
    val_var = tk.DoubleVar(value=0.35)
    lbl_val = tk.Label(dlg, text="35%", font=("Segoe UI", 10, "bold"), fg="#2563eb")
    lbl_val.pack()

    def _on_slide(v):
        lbl_val.config(text=f"{float(v):.0%}")

    slider = ttk.Scale(dlg, from_=0.01, to=0.95, orient="horizontal", variable=val_var, command=_on_slide)
    slider.pack(fill=tk.X, padx=30, pady=5)

    def _on_ok():
        conf_result["val"] = round(val_var.get(), 2)
        dlg.destroy()

    ttk.Button(dlg, text="Uygula ve Başlat ▶", command=_on_ok, style="Accent.TButton").pack(pady=5)
    
    # Pencerenin kapanmasını bekle
    root.wait_window(dlg)

    if conf_result["val"] is None:
        return  # Kullanıcı pencereyi çarpıdan kapattıysa iptal et
    
    selected_conf = conf_result["val"]

    loading = tk.Toplevel(root)
    loading.title("Hesaplanıyor...")
    loading.geometry("350x120")
    tk.Label(loading, text=f"YOLO (conf={selected_conf:.2f}) ve OCR çalışıyor...\nLütfen bekleyin...", font=("Segoe UI", 10)).pack(expand=True)
    loading.update()

    def process():
        try:
            out_prefix = os.path.splitext(image_path)[0] + "_pipeline"
            args_dict = {
                "weights": model_path,
                "image": image_path,
                "out_prefix": out_prefix,
                "dx_cm": 10,
                "imgsz": 1024,
                "conf": selected_conf,
                "classes_json": ""
            }
            res_json, res_img_path = main_flow(args_dict)

            loading.destroy()
            root.after(0, lambda: show_pipeline_results(root, res_json, res_img_path))
        except Exception as e:
            loading.destroy()
            root.after(0, lambda: messagebox.showerror("Pipeline Hatası", str(e)))

    t = threading.Thread(target=process)
    t.start()


def show_pipeline_results(root, json_data: dict, debug_img_path: str):
    """
    Pipeline'dan çıkan sonucu arayüzde gösterir (JSON ve Debug Resmi).
    """
    import tkinter as tk
    from tkinter import ttk
    try:
        from PIL import Image, ImageTk
    except ImportError:
        pass

    win = tk.Toplevel(root)
    win.title("⚖️ Hesaplama Pipeline Çıktısı")
    win.geometry("1400x800")
    win.configure(bg="#f8fafc")

    # Layout: Sol = Debug Image, Sağ = JSON
    paned = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
    paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Sol
    fr_left = tk.Frame(paned, bg="#ffffff", bd=1, relief="solid")
    paned.add(fr_left, weight=2)
    tk.Label(fr_left, text="Debug Çizimi (Akslar, Paneller, Açıklıklar)", bg="#f1f5f9", font=("Segoe UI", 11, "bold")).pack(fill=tk.X)
    
    canvas = tk.Canvas(fr_left, bg="#e2e8f0")
    canvas.pack(fill=tk.BOTH, expand=True)

    try:
        from PIL import Image, ImageTk
        img = Image.open(debug_img_path)
        img.thumbnail((900, 900))
        tk_img = ImageTk.PhotoImage(img)
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas.image = tk_img  # keep ref
    except Exception as e:
        canvas.create_text(100, 100, text=f"Resim yüklenemedi: {e}")

    # Sağ
    fr_right = tk.Frame(paned, bg="#ffffff", bd=1, relief="solid")
    paned.add(fr_right, weight=1)
    tk.Label(fr_right, text="Kazanılan Yapısal Veri (JSON)", bg="#f1f5f9", font=("Segoe UI", 11, "bold")).pack(fill=tk.X)

    txt = tk.Text(fr_right, font=("Consolas", 10), wrap=tk.NONE, bg="#0f172a", fg="#10b981")
    txt.pack(fill=tk.BOTH, expand=True)
    
    formatted_json = json.dumps(json_data, indent=2, ensure_ascii=False)
    txt.insert("1.0", formatted_json)
    txt.config(state="disabled")

    btn_fr = tk.Frame(win, bg="#f8fafc")
    btn_fr.pack(fill=tk.X, pady=5)

    def save_json():
        from tkinter import filedialog, messagebox
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Dosyaları", "*.json"), ("Tüm Dosyalar", "*.*")],
            title="JSON Çıktısını Kaydet"
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(formatted_json)
                messagebox.showinfo("Başarılı", f"JSON dosyası kaydedildi:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Hata", f"Kaydetme sırasında hata oluştu:\n{e}")

    ttk.Button(btn_fr, text="Kapat", command=win.destroy).pack(side=tk.RIGHT, padx=10)
    ttk.Button(btn_fr, text="JSON Kaydet", command=save_json).pack(side=tk.RIGHT, padx=5)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, help="Path to trained YOLO weights (best.pt)")
    ap.add_argument("--image", required=True, help="Input plan PNG path")
    ap.add_argument("--out_prefix", required=True, help="Output prefix (without extension)")
    ap.add_argument("--dx_cm", type=int, default=10, help="Uniform grid resolution in cm for i/j indexing")
    ap.add_argument("--imgsz", type=int, default=1024)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--classes_json", default="", help="Optional JSON file mapping class_id->class_name")
    args_p = ap.parse_args()
    main_flow(vars(args_p))
