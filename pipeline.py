import os
# Guncel koddan taşıdığın inference modülü
from infer_to_calc_inputs import main_flow
# Bitirme kodundaki json okuyucu
from json_loader import parse_slab_json

def process_image_to_slabs(image_path, model_weights_path="best.pt"):
    """
    1. Görseli alır, YOLO+OCR pipeline'ına sokar.
    2. Çıkan JSON dict'i doğrudan json_loader'a besler.
    3. Döşeme listesini ve kiriş sınırlarını döndürür.
    """
    print(f"YOLO ve OCR Pipeline başlatılıyor: {image_path}")
    
    out_prefix = os.path.splitext(image_path)[0] + "_pipeline"
    
    # main_flow'un beklediği argüman sözlüğü
    args_dict = {
        "weights": model_weights_path,
        "image": image_path,
        "out_prefix": out_prefix,
        "dx_cm": 10,
        "imgsz": 1024,
        "conf": 0.35,
        "classes_json": ""
    }

    try:
        # Adım 1: Pipeline'ı çalıştır ve sonucu RAM'e al
        # main_flow(args_dict) şu an json_data (dict) ve debug_img_path döndürüyor
        json_data, debug_img_path = main_flow(args_dict)
        
        # Adım 2: Çıktıyı doğrudan bitirme loader'ına gönder
        # parse_slab_json bitirme projesindeki Slab nesnelerini ve kiriş setini döner
        slab_list, beam_edges_set = parse_slab_json(json_data)
        
        print(f"Başarılı! Toplam {len(slab_list)} adet döşeme/balkon tespit edildi.")
        return slab_list, beam_edges_set, debug_img_path
        
    except Exception as e:
        print(f"Pipeline çalıştırılırken hata oluştu: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None
