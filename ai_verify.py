"""
AI OCR University Identification System
Requires Tesseract OCR engine:
  macOS: brew install tesseract tesseract-lang
"""
import os

def verify_document(filepath, universities):
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return None, "Pillow/pytesseract not installed"
    
    if not os.path.exists(filepath):
        return None, "File not found"
    
    try:
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        if not text.strip():
            return None, "No text detected"
        
        for uni in universities:
            if uni in text:
                return True, uni
        
        return False, text[:500]
    except pytesseract.TesseractNotFoundError:
        return None, "Tesseract OCR not installed. Run: brew install tesseract tesseract-lang"
    except Exception as e:
        return None, str(e)
