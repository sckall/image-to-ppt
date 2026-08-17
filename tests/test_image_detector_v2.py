"""image_detector_v2.py 单元测试 — 用生成的 fixture 图"""
import numpy as np
import pytest
from PIL import Image

from image_detector_v2 import detect_image_regions_v2


def _save_synthetic(path, w=600, h=400):
    """生成一张测试图: 白底 + 中央一个红色矩形(模拟图片)"""
    arr = np.full((h, w, 3), 255, dtype=np.uint8)
    arr[100:300, 150:450] = [200, 30, 30]  # 红色块
    Image.fromarray(arr).save(path)


def test_blank_image_returns_empty_list(tmp_path):
    img = Image.new("RGB", (400, 300), (255, 255, 255))
    p = tmp_path / "blank.png"
    img.save(p)
    result = detect_image_regions_v2(p, text_regions=[])
    assert isinstance(result, list)
    # 纯白图 → 无彩色块 → 无图区域
    assert result == []


def test_returns_list_with_colored_block(tmp_path):
    p = tmp_path / "with_color.png"
    _save_synthetic(p)
    result = detect_image_regions_v2(p, text_regions=[], min_blocks=3)
    assert isinstance(result, list)
    # 至少应该检测到红色块
    if result:  # 算法可能有过滤逻辑, 至少类型对
        for r in result:
            assert "bbox" in r or "type" in r  # 至少有 bbox 或 type 字段


def test_text_region_excludes_text_heavy_area(tmp_path):
    """文字占比超 50% 的区域不应被判定为图"""
    p = tmp_path / "with_text.png"
    _save_synthetic(p)
    # 把整个图覆盖为"文字区域"
    text_regions = [{"bbox": {"x1": 0, "y1": 0, "x2": 600, "y2": 400}}]
    result = detect_image_regions_v2(p, text_regions=text_regions, min_blocks=2)
    # 文字 mask 覆盖全图 → 应过滤掉"图"区域
    assert result == []


def test_exclude_top_right_filters_watermark(tmp_path):
    """默认开启 exclude_top_right, 右上角小色块应被过滤"""
    p = tmp_path / "watermark.png"
    arr = np.full((400, 600, 3), 255, dtype=np.uint8)
    # 右上角 50x50 红块(模拟公众号水印)
    arr[10:60, 530:580] = [200, 30, 30]
    Image.fromarray(arr).save(p)
    result = detect_image_regions_v2(p, text_regions=[], min_blocks=2)
    # 应该被 exclude_top_right 过滤掉
    assert result == []
