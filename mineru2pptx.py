#!/usr/bin/env python3
"""mineru2pptx.py - MinerU 输出 -> 可编辑 PPT (纯图片+文字,无背景)

用法:
  mineru -p <input_dir> -o <mineru_output_dir> --backend pipeline
  python3 mineru2pptx.py <input_dir> <mineru_output_dir> <output.pptx>

字号: 三档分档 (大 30pt / 中 26pt / 小 22pt)
行距: 1.3 倍
文本框: 自动扩展宽度 (避免挤压文字到下一行)
"""
import json
import sys
from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.util import Emu, Pt


# 文本框扩展参数: 让文字框略宽, 避免挤压但不过度
TEXTBOX_PADDING_PX = 8       # 文本框四周扩展像素 (轻微 padding)
TEXTBOX_MIN_WIDTH_PX = 80    # 文本框最小宽度(像素)


def build_clean_pptx(jpeg_dir, mineru_dir, output_pptx, slide_w_inches=13.333):
    from font_estimator import estimate_font_size, LINE_SPACING

    prs = Presentation()
    blank = prs.slide_layouts[6]

    jpeg_dir = Path(jpeg_dir)
    mineru_dir = Path(mineru_dir)

    aspect = 16 / 9
    sw = int(slide_w_inches * 914400)
    sh = int(sw / aspect)

    image_ids = sorted([int(p.stem) for p in jpeg_dir.glob("*.jpeg") if p.stem.isdigit()])

    for img_id in image_ids:
        cl_path = mineru_dir / str(img_id) / "auto" / f"{img_id}_content_list.json"
        if not cl_path.exists():
            print(f"  skip {img_id}: not found")
            continue

        img = Image.open(jpeg_dir / f"{img_id}.jpeg")
        W, H = img.size

        prs.slide_width = Emu(sw)
        prs.slide_height = Emu(sh)
        slide = prs.slides.add_slide(blank)

        with open(cl_path) as f:
            blocks = json.load(f)

        for blk in blocks:
            btype = blk.get("type")
            bbox_norm = blk.get("bbox", [])

            if btype in ("page_header", "page_footer") and not blk.get("text", "").strip():
                continue
            if not bbox_norm or len(bbox_norm) != 4:
                continue

            x1 = bbox_norm[0] / 1000 * W
            y1 = bbox_norm[1] / 1000 * H
            x2 = bbox_norm[2] / 1000 * W
            y2 = bbox_norm[3] / 1000 * H
            w_px = x2 - x1
            h_px = y2 - y1

            if btype == "image":
                emu_x = Emu(int(x1 / W * sw))
                emu_y = Emu(int(y1 / H * sh))
                emu_w = Emu(int(w_px / W * sw))
                emu_h = Emu(int(h_px / H * sh))

                img_filename = Path(blk.get("img_path", "")).name
                cropped_img = mineru_dir / str(img_id) / "auto" / "images" / img_filename
                if cropped_img.exists():
                    slide.shapes.add_picture(str(cropped_img), emu_x, emu_y, emu_w, emu_h)

            elif btype in ("text", "title", "paragraph", "list", "page_header", "page_footer"):
                text = blk.get("text", "").strip()
                if not text:
                    continue

                font_pt = estimate_font_size(text, w_px, h_px)

                # 文本框: 轻微 padding (4 边各 +8px), 保证 min width
                cx = max(0, x1 - TEXTBOX_PADDING_PX)
                cy = max(0, y1 - TEXTBOX_PADDING_PX)
                cw = min(W - cx, w_px + TEXTBOX_PADDING_PX * 2)
                ch = min(H - cy, h_px + TEXTBOX_PADDING_PX * 2)
                cw = max(cw, TEXTBOX_MIN_WIDTH_PX)

                emu_x = Emu(int(cx / W * sw))
                emu_y = Emu(int(cy / H * sh))
                emu_w = Emu(int(cw / W * sw))
                emu_h = Emu(int(ch / H * sh))

                tb = slide.shapes.add_textbox(emu_x, emu_y, emu_w, emu_h)
                tf = tb.text_frame
                tf.word_wrap = True
                tf.margin_left = tf.margin_right = Emu(0)
                tf.margin_top = tf.margin_bottom = Emu(0)
                p = tf.paragraphs[0]
                p.text = text
                p.font.size = Pt(font_pt)
                p.line_spacing = LINE_SPACING
                if btype == "title":
                    p.font.bold = True

    prs.save(output_pptx)
    print(f"saved: {output_pptx}")
    print(f"  slides: {len(prs.slides)}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    build_clean_pptx(sys.argv[1], sys.argv[2], sys.argv[3])