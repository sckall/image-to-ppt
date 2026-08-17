"""
image_detector.py — 从图片中检测图片/图表区域(用于 px-image2pptx 增强)

策略:
1. OCR 识别文字区域(已知)
2. 用 cv2 的连通组件分析,在"非文字区域"里找大块连通区域 = 可能是图片/图表
3. 阈值过滤: 最小面积 + 最小宽高 + 长宽比合理
4. 返回图片区域列表 [{bbox, type: 'image'|'chart', confidence}]

不依赖 ML,纯 CV,速度 <100ms
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path
from typing import Any


def detect_image_regions(
    image_path: str | Path,
    text_regions: list[dict],
    min_area_ratio: float = 0.02,  # 最小占图比例(2%)
    min_dim: int = 50,  # 最小宽/高(像素)
    padding: int = 10,  # bbox 扩展像素
) -> list[dict]:
    """检测图片中的"图片/图表"区域

    Args:
        image_path: 输入图片路径
        text_regions: OCR 文字区域 [{bbox: {x1,y1,x2,y2}}, ...]
        min_area_ratio: 区域占整图比例下限
        min_dim: 区域宽/高下限(像素)
        padding: 检测到的 bbox 向外扩展像素

    Returns:
        列表 [{bbox, area, type, confidence}, ...]
        type: 'image' (实物照片) / 'chart' (图表,启发式区分)
    """
    img = Image.open(image_path).convert('RGB')
    W, H = img.size
    img_arr = np.array(img)
    img_bgr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    total_area = W * H
    min_area = int(total_area * min_area_ratio)

    # 1. 文字 mask(从 OCR 结果)
    text_mask = np.zeros((H, W), dtype=np.uint8)
    for r in text_regions:
        b = r['bbox']
        cv2.rectangle(
            text_mask,
            (max(0, b['x1'] - padding), max(0, b['y1'] - padding)),
            (min(W, b['x2'] + padding), min(H, b['y2'] + padding)),
            255, -1
        )

    # 2. 检测"非纯色区域" (有内容,不是空白)
    # 用 Sobel 检测变化
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    gradient = np.sqrt(sobel_x**2 + sobel_y**2)
    gradient = (gradient / gradient.max() * 255).astype(np.uint8) if gradient.max() > 0 else gradient.astype(np.uint8)

    # 二值化: 边缘明显的区域
    _, edge_binary = cv2.threshold(gradient, 20, 255, cv2.THRESH_BINARY)
    # 膨胀: 连成大块
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    edge_dilated = cv2.dilate(edge_binary, kernel, iterations=2)
    # 闭运算: 填洞
    edge_closed = cv2.morphologyEx(edge_dilated, cv2.MORPH_CLOSE, kernel)

    # 3. 排除文字区域
    edge_closed[text_mask == 255] = 0

    # 4. 连通组件
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(edge_closed, connectivity=8)

    regions = []
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if area < min_area or w < min_dim or h < min_dim:
            continue

        # 进一步过滤: 这个区域是否真的有"图"?
        # 计算色彩复杂度(标准差越大,越可能是图不是单色背景)
        roi = img_arr[y:y+h, x:x+w]
        color_std = float(roi.std())
        # 平均颜色饱和度(HSV)
        hsv = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)
        avg_sat = float(hsv[:, :, 1].mean())

        # 启发式分类: 图表通常高对比+大量黑线;照片通常高色彩
        if color_std > 50 and avg_sat > 40:
            rtype = 'image'  # 彩色图片
        elif color_std > 30:
            rtype = 'chart'  # 图表/示意图
        else:
            continue  # 太单调,可能是渐变背景,跳过

        # bbox 扩展
        bbox = {
            'x1': max(0, x - padding),
            'y1': max(0, y - padding),
            'x2': min(W, x + w + padding),
            'y2': min(H, y + h + padding),
        }
        confidence = min(1.0, color_std / 80)

        regions.append({
            'bbox': bbox,
            'area': area,
            'type': rtype,
            'color_std': round(color_std, 1),
            'saturation': round(avg_sat, 1),
            'confidence': round(confidence, 3),
        })

    # 按面积降序排
    regions.sort(key=lambda r: -r['area'])
    return regions


def crop_image_region(image_path: str | Path, bbox: dict, out_path: str | Path | None = None) -> Image.Image:
    """按 bbox 抠图"""
    img = Image.open(image_path).convert('RGB')
    cropped = img.crop((bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']))
    if out_path:
        cropped.save(out_path)
    return cropped


def visualize_regions(
    image_path: str | Path,
    text_regions: list[dict],
    image_regions: list[dict],
    out_path: str | Path,
) -> Image.Image:
    """可视化: 文字框红,图片框蓝"""
    img = Image.open(image_path).convert('RGB')
    draw = ImageDraw.Draw(img)
    for r in text_regions:
        b = r['bbox']
        draw.rectangle([b['x1'], b['y1'], b['x2'], b['y2']], outline='red', width=2)
    for r in image_regions:
        b = r['bbox']
        draw.rectangle([b['x1'], b['y1'], b['x2'], b['y2']], outline='blue', width=4)
        label = f"{r['type']} ({r['area']//1000}K)"
        draw.text((b['x1']+5, b['y1']+5), label, fill='blue')
    if out_path:
        img.save(out_path)
    return img