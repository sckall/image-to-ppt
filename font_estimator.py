"""
font_estimator.py - 字号反推(三档,基于真实数据分档)

经验规则(用户沉淀 + 25 张图实测分布):
- 大号字: 30 pt  (标题, bbox 高 >= 90px, ~10% 出现率)
- 中号字: 26 pt  (副标题, 50-90px, ~20%)
- 小号字: 22 pt  (正文, <50px, ~70%)
- 行距: 1.3 倍

依赖: Pillow (字体测宽备用)
"""
import os
from PIL import Image, ImageFont


# 三档字号经验值 (像素高 -> pt)
SIZE_TIERS = [
    (90, 30),    # 大号: 标题 (h >= 90)
    (50, 26),    # 中号: 副标题 (50 <= h < 90)
    (0,  22),    # 小号: 正文 (h < 50)
]


# 行距倍数
LINE_SPACING = 1.3


def classify_by_height(h_px: float) -> int:
    """按 bbox 像素高度分档,返回字号(pt)"""
    for min_h, size_pt in SIZE_TIERS:
        if h_px >= min_h:
            return size_pt
    return SIZE_TIERS[-1][1]


def estimate_font_size(
    text: str = "",
    bbox_w_px: float = 0,
    bbox_h_px: float = 0,
    img_w_px: int = 0,
    slide_w_inches: float = 13.333,
    snap: bool = False,
) -> int:
    """字号反推(按 bbox 像素高度三档分档)

    Args:
        text: 文字内容(此处不用,保留兼容接口)
        bbox_w_px: bbox 像素宽(此处不用)
        bbox_h_px: bbox 像素高 (主依据)
        img_w_px: 原图宽(此处不用)
        slide_w_inches: slide 宽(此处不用)
        snap: 是否把结果 snap 到候选池 (CANDIDATE_POOL),默认 False

    Returns:
        字号(pt): 30 / 26 / 22 (或 snap 后的值)
    """
    if bbox_h_px <= 0:
        size = SIZE_TIERS[-1][1]
        return snap_to_pool(size) if snap else size
    size = classify_by_height(bbox_h_px)
    return snap_to_pool(size) if snap else size


# === 兼容旧接口 (px 同款公式 + 宽度自适应, 备用) ===

CANDIDATE_POOL = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 54, 60, 66, 72, 80, 96]


def _load_font(size_pt: int):
    """跨平台字体加载:macOS / Linux / Windows 全覆盖"""
    candidates = [
        # macOS
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/Library/Fonts/Songti.ttc',
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        # Linux (Debian/Ubuntu/Arch 常见路径)
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        # Windows
        'C:/Windows/Fonts/msyh.ttc',       # Microsoft YaHei
        'C:/Windows/Fonts/msyh.ttf',
        'C:/Windows/Fonts/simhei.ttf',      # SimHei
        'C:/Windows/Fonts/simsun.ttc',      # SimSun
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/seguiemj.ttf',   # Segoe UI Emoji
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size_pt)
            except (OSError, IOError):
                continue
    # 最后兜底:PIL 自带位图字体(无中文但不会崩)
    return ImageFont.load_default()


def measure_text_width_pt(text: str, font_pt: int) -> float:
    if not text.strip():
        return 0
    font = _load_font(font_pt)
    bbox = font.getbbox(text)
    if bbox is None:
        return 0
    return bbox[2] - bbox[0]


def snap_to_pool(size_pt: float, pool=None) -> int:
    if pool is None:
        pool = CANDIDATE_POOL
    return min(pool, key=lambda x: abs(x - size_pt))


def estimate_font_size_precise(
    text: str,
    bbox_w_px: float,
    bbox_h_px: float,
    img_w_px: int,
    slide_w_inches: float = 13.333,
    min_pt: int = 8,
    max_pt: int = 96,
) -> int:
    """精确反推(px-image2pptx 兼容公式 + 宽度自适应)
    保留以备需要高精度时使用. 默认用 estimate_font_size (三档经验)."""
    if not text or bbox_h_px <= 0:
        return min_pt
    n_chars = len(text.strip())
    is_long = n_chars >= 20
    ppi = img_w_px / slide_w_inches
    pt_raw = bbox_h_px * 72 / ppi
    pt = max(min_pt, min(max_pt, round(pt_raw)))
    if bbox_w_px > 0 and text.strip():
        bbox_w_pt = bbox_w_px * 72 / ppi
        if is_long:
            target_min = bbox_w_pt * 0.95
            target_max = bbox_w_pt * 1.30
        else:
            target_min = bbox_w_pt * 0.88
            target_max = bbox_w_pt * 1.00
        for _ in range(40):
            w = measure_text_width_pt(text, pt)
            if w > target_max and pt > min_pt:
                pt -= 1
            elif w < target_min and pt < max_pt:
                pt += 1
            else:
                break
    return pt
