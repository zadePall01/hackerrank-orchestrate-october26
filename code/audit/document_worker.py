"""One bounded document extraction job. No shell, network API, or action tools."""
from __future__ import annotations
import json
from pathlib import Path
import sys


def extract_document(path: Path) -> tuple[str,int]:
    if path.stat().st_size>64*1024*1024: raise ValueError('Document size budget')
    if path.suffix=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(path)
        if len(reader.pages)>100: raise ValueError('PDF page budget')
        text='\n'.join(page.extract_text() or '' for page in reader.pages)
        calls=0
    elif path.suffix=='.png':
        from PIL import Image
        with Image.open(path) as image:
            if image.width*image.height>20_000_000: raise ValueError('Image pixel budget')
        import rapidocr
        from rapidocr import RapidOCR
        models=Path(rapidocr.__file__).parent/'models'
        required={'Det.model_path':models/'PP-OCRv6_det_small.onnx','Rec.model_path':models/'PP-OCRv6_rec_small.onnx','Cls.model_path':models/'ch_ppocr_mobile_v2.0_cls_mobile.onnx'}
        if any(not item.is_file() for item in required.values()): raise ImportError('Bundled OCR models missing')
        params={k:str(v) for k,v in required.items()}
        params.update({'Global.log_level':'error','EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':1})
        output=RapidOCR(params=params)(str(path))
        text='\n'.join(output.txts or []);calls=1
    else: raise ValueError('Unsupported document type')
    if not text.strip() or len(text)>2_000_000: raise ValueError('Empty or oversized extracted text')
    return text,calls


def main() -> int:
    try:
        if len(sys.argv)!=2: raise ValueError('One path required')
        text,calls=extract_document(Path(sys.argv[1]))
        print(json.dumps(dict(text=text,ocr_calls=calls),ensure_ascii=True))
        return 0
    except Exception as exc:
        # Parser messages can contain artifact text or credentials: disclose type only.
        print(json.dumps(dict(error=type(exc).__name__)))
        return 2


if __name__=='__main__': raise SystemExit(main())
