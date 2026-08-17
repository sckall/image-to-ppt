"""
image_detector_v2.py — 图片区域检测 v2

结合多种策略:
1. 文字 mask 反向找"空白矩形" (空白处)
2. 用色彩复杂度找"有图"的块
3. 把高密度色彩块合并为图区域

比 v1 更鲁棒,能检测到非连通区域
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def detect_image_regions_v2(
    image_path: str | Path,
    text_regions: list[dict],
    block_size: int = 40,
    color_threshold: float = 30.0,
    text_density_max: float = 0.3,
    padding: int = 10,
    min_blocks: int = 5,
    exclude_top_right: bool = True,  # 过滤公众号水印(右上角)
) -> list[dict]:
    """检测图片/图表区域(改进版)

    Args:
        image_path: 输入图片
        text_regions: OCR 文字区域
        block_size: 分析块大小
        color_threshold: 块色彩 std 阈值(>此值算有图)
        text_density_max: 块内文字密度上限
        padding: bbox 扩展像素
    """
    img = Image.open(image_path).convert('RGB')
    W, H = img.size
    arr = np.array(img)
    img_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 1. 文字 mask
    text_mask = np.zeros((H, W), dtype=np.uint8)
    for r in text_regions:
        b = r['bbox']
        pad = 10
        text_mask[max(0,b['y1']-pad):min(H,b['y2']+pad), max(0,b['x1']-pad):min(W,b['x2']+pad)] = 255

    # 2. 分块分析: 每块是否"有图"
    ny = (H + block_size - 1) // block_size
    nx = (W + block_size - 1) // block_size
    block_has_content = np.zeros((ny, nx), dtype=np.uint8)

    for by in range(ny):
        for bx in range(nx):
            ys = by * block_size
            ye = min((by+1) * block_size, H)
            xs = bx * block_size
            xe = min((bx+1) * block_size, W)

            sub = arr[ys:ye, xs:xe]
            text_in = text_mask[ys:ye, xs:xe].sum() / max(1, (ye-ys)*(xe-xs))

            # 文字密度高的区域不算图
            if text_in > text_density_max:
                continue

            # 边缘密度 + 色彩 std
            color_std = float(sub.std())
            # 用 Sobel 检测内容
            sub_gray = gray[ys:ye, xs:xe]
            sobel = cv2.Sobel(sub_gray, cv2.CV_64F, 1, 1, ksize=3)
            edge_density = float(np.abs(sobel).mean())

            # 同时满足: 有色彩 OR 有边缘
            if color_std > color_threshold or edge_density > 15:
                block_has_content[by, bx] = 1

    # 3. 直接连通(不膨胀 — 避免把大块连成整图)
    block_mask = block_has_content.astype(np.uint8) * 255
    # 轻微腐蚀去噪
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(block_mask)

    regions = []
    for i in range(1, n):
        bx, by, bw, bh, area = stats[i]
        if area < min_blocks:
            continue

        # 转像素坐标
        x1 = bx * block_size
        y1 = by * block_size
        x2 = min(W, (bx + bw) * block_size)
        y2 = min(H, (by + bh) * block_size)

        # 过滤水印/标题区(顶部 1/3 高度 且 跨 >50% 宽)
        if y2 < H * 0.35 and (x2 - x1) > W * 0.5:
            continue

        # 过滤右上角水印区(常见公众号水印位置:右上 210x210)
        if exclude_top_right and x1 > W * 0.75 and y2 < H * 0.35:
            continue

        # 检查文字占比(放宽到 50% — 容忍图上叠加的文字)
        text_in_region = text_mask[y1:y2, x1:x2].sum() / max(1, (y2-y1)*(x2-x1))
        if text_in_region > 0.5:
            continue  # 文字太多的区域不算图

        # 扩展
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(W, x2 + padding)
        y2 = min(H, y2 + padding)

        # 进一步: 区域内必须有真实图内容(色彩 std > 30)
        roi = arr[y1:y2, x1:x2]
        color_std = float(roi.std())
        if color_std < color_threshold:
            continue

        # 区域占整图比例
        area_pct = (x2-x1) * (y2-y1) / (W * H)
        if area_pct < 0.01:  # 太小(<1%)
            continue
        if area_pct > 0.85:  # 太大(>85%) - 可能是整张背景
            continue

        # 类型判断
        hsv = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)
        avg_sat = float(hsv[:, :, 1].mean())
        rtype = 'image' if avg_sat > 50 and color_std > 40 else 'chart'

        regions.append({
            'bbox': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2},
            'area': (x2-x1) * (y2-y1),
            'color_std': round(color_std, 1),
            'saturation': round(avg_sat, 1),
            'type': rtype,
            'blocks': int(area),
        })

    regions.sort(key=lambda r: -r['area'])
    return regions


def crop_region(image_path, bbox, out_path=None):
    img = Image.open(image_path).convert('RGB')
    cropped = img.crop((bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']))
    if out_path:
        cropped.save(out_path)
    return cropped
