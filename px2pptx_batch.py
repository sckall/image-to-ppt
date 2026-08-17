#!/usr/bin/env python3
"""px2pptx_batch.py - batch image to PPTX with model reuse"""

import argparse
import logging
import sys
import tempfile
import time
from pathlib import Path
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

MAX_OCR_WIDTH = 1500
OCR_LIMIT_SIDE = 960
LAMA_MAX_SIZE = 1536

def setup_env():
    import os
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", "/tmp/paddlex")
    os.environ.setdefault("TORCH_HOME", "/tmp/torch-cache")
    os.environ.setdefault("MODELSCOPE_CACHE", "/tmp/ms-cache")
def resize_for_ocr(src, work_dir):
    img = Image.open(src)
    w, h = img.size
    if w <= MAX_OCR_WIDTH:
        return src, 1.0
    ratio = MAX_OCR_WIDTH / w
    new_size = (MAX_OCR_WIDTH, int(h * ratio))
    out_path = work_dir / ("resized_" + src.name)
    img.resize(new_size, Image.LANCZOS).save(out_path)
    return out_path, ratio


class Pipeline:
    def __init__(self, lang):
        from px_image2pptx.textmask import compute_masks
        from px_image2pptx.inpaint import inpaint
        from px_image2pptx.assemble import assemble_pptx
        logger.info("loading OCR (%s)...", lang)
        t0 = time.time()
        # 用 mobile 模型,速度比 server 模型快 ~10x,精度足够课件场景
        # px 默认用 server,中文课件场景 mobile 完全够用
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(
            lang=lang,
            text_detection_model_name='PP-OCRv5_mobile_det',
            text_recognition_model_name='PP-OCRv5_mobile_rec',
            use_textline_orientation=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
        )
        logger.info("OCR ready (%.1fs)", time.time() - t0)
        self.compute_masks = compute_masks
        self.inpaint = inpaint
        self.assemble_pptx = assemble_pptx

    def process(self, image_path, output_path, work_dir):
        t_start = time.time()
        # OCR
        t0 = time.time()
        ocr_results = list(self.ocr.predict(str(image_path), text_det_limit_side_len=OCR_LIMIT_SIDE))
        regions = self._parse_ocr(ocr_results)
        t_ocr = time.time() - t0
        # Textmask
        t0 = time.time()
        import cv2
        image_bgr = cv2.imread(str(image_path))
        tight, clipped, dilated = self.compute_masks(image_bgr, regions)
        t_textmask = time.time() - t0
        # Inpaint
        t0 = time.time()
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        background_path = work_dir / "background.png"
        lama_mask = (dilated > 0).astype(np.uint8) * 255
        self.inpaint(image_rgb, lama_mask, max_size=LAMA_MAX_SIZE)
        Image.fromarray(image_rgb).save(background_path)
        t_inpaint = time.time() - t0
        # Assemble
        t0 = time.time()
        tight_mask_uint8 = (tight > 0).astype(np.uint8) * 255
        report = self.assemble_pptx(
            image_path=str(image_path),
            ocr_regions=regions,
            output_path=str(output_path),
            background_path=str(background_path),
            tight_mask=tight_mask_uint8,
        )
        t_assemble = time.time() - t0
        total = time.time() - t_start
        return {
            "ocr_time": t_ocr,
            "textmask_time": t_textmask,
            "inpaint_time": t_inpaint,
            "assemble_time": t_assemble,
            "total_time": total,
            "text_boxes": len(regions),
        }

    @staticmethod
    def _parse_ocr(results):
        regions = []
        idx = 0
        for page in results:
            polys = page.get("dt_polys", [])
            texts = page.get("rec_texts", [])
            scores = page.get("rec_scores", [])
            for poly, text, conf in zip(polys, texts, scores):
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                regions.append({
                    "id": idx,
                    "text": text,
                    "confidence": round(float(conf), 4),
                    "bbox": {
                        "x1": int(min(xs)),
                        "y1": int(min(ys)),
                        "x2": int(max(xs)),
                        "y2": int(max(ys)),
                    },
                })
                idx += 1
        return regions


def process_one(pipeline, input_path, output_path):
    logger.info(">> %s -> %s", input_path.name, output_path.name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        resized, ratio = resize_for_ocr(input_path, work_dir)
        if ratio < 1.0:
            logger.info("  resize %.2fx", ratio)
        try:
            report = pipeline.process(resized, output_path, work_dir)
            logger.info("OK %d boxes | OCR=%.1fs Inpaint=%.1fs Total=%.1fs",
                        report["text_boxes"], report["ocr_time"],
                        report["inpaint_time"], report["total_time"])
            return report
        except Exception as e:
            logger.error("FAIL: %s", e)
            import traceback
            traceback.print_exc()
            return None


def main():
    parser = argparse.ArgumentParser(description="batch png to pptx (model reuse)")
    parser.add_argument("input", help="input PNG file or dir")
    parser.add_argument("output", nargs="?", default=None, help="output PPTX file or dir")
    parser.add_argument("--lang", default="ch", choices=["ch", "en"])
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认 INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    setup_env()
    sys.path.insert(0, str(Path(__file__).parent / "px-image2pptx"))
    in_path = Path(args.input)
    if not in_path.exists():
        logger.error("input not found: %s", in_path)
        sys.exit(1)
    if in_path.is_file():
        pipeline = Pipeline(args.lang)
        out_path = Path(args.output) if args.output else in_path.with_suffix(".pptx")
        process_one(pipeline, in_path, out_path)
        return
    if not in_path.is_dir():
        logger.error("not a dir: %s", in_path)
        sys.exit(1)
    out_dir = Path(args.output) if args.output else in_path.parent / (in_path.name + "_pptx")
    out_dir.mkdir(parents=True, exist_ok=True)
    pngs = sorted(in_path.glob("*.png")) + sorted(in_path.glob("*.jpg")) + sorted(in_path.glob("*.jpeg"))
    if not pngs:
        logger.error("no png/jpg in %s", in_path)
        sys.exit(1)
    pipeline = Pipeline(args.lang)
    logger.info("Found %d images -> %s", len(pngs), out_dir)
    t_start = time.time()
    ok = 0
    for png in pngs:
        out_pptx = out_dir / (png.stem + ".pptx")
        if process_one(pipeline, png, out_pptx):
            ok += 1
    elapsed = time.time() - t_start
    logger.info("=== Done: %d/%d, total %.1fs (%.1fs/page) ===",
                ok, len(pngs), elapsed, elapsed / len(pngs))


if __name__ == "__main__":
    main()

