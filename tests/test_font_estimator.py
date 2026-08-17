"""font_estimator.py 单元测试 — 纯逻辑, 无 I/O"""
import pytest

from font_estimator import (
    CANDIDATE_POOL,
    LINE_SPACING,
    SIZE_TIERS,
    classify_by_height,
    estimate_font_size,
    snap_to_pool,
)


class TestClassifyByHeight:
    def test_large_title(self):
        assert classify_by_height(120) == 30
        assert classify_by_height(90) == 30  # boundary inclusive

    def test_medium_subtitle(self):
        assert classify_by_height(60) == 26
        assert classify_by_height(50) == 26  # boundary inclusive

    def test_small_body(self):
        assert classify_by_height(30) == 22
        assert classify_by_height(1) == 22  # 任何 >0 且 <50 都算小号

    def test_returns_int(self):
        for h in [10, 50, 100, 200]:
            assert isinstance(classify_by_height(h), int)


class TestEstimateFontSize:
    def test_three_tier_mapping(self):
        # bbox_h_px → font_pt 主路径
        assert estimate_font_size(bbox_h_px=100) == 30
        assert estimate_font_size(bbox_h_px=60) == 26
        assert estimate_font_size(bbox_h_px=20) == 22

    def test_empty_or_negative_returns_smallest(self):
        assert estimate_font_size(bbox_h_px=0) == 22
        assert estimate_font_size(bbox_h_px=-1) == 22

    def test_compat_args_ignored(self):
        # text, bbox_w_px, img_w_px, slide_w_inches 在主路径里不参与计算
        assert estimate_font_size(
            text="hello", bbox_w_px=200, img_w_px=1920,
            slide_w_inches=13.333, bbox_h_px=80,
        ) == 26

    def test_snap_default_off(self):
        # 默认 snap=False, 返回三档之一
        assert estimate_font_size(bbox_h_px=100) == 30
        assert estimate_font_size(bbox_h_px=60) == 26
        assert estimate_font_size(bbox_h_px=20) == 22

    def test_snap_enabled_rounds_to_pool(self):
        # snap=True 后, 分档值(30/26/22)不在 pool 里, 落到最近的有效字号
        # 30 → 28 或 32
        assert estimate_font_size(bbox_h_px=100, snap=True) in (28, 32)
        # 26 → 24 或 28
        assert estimate_font_size(bbox_h_px=60, snap=True) in (24, 28)
        # 22 → 20 或 24
        assert estimate_font_size(bbox_h_px=20, snap=True) in (20, 24)

    def test_snap_with_zero_bbox(self):
        # bbox_h=0 → 默认小号 22, snap 后到 20 或 24
        assert estimate_font_size(bbox_h_px=0, snap=True) in (20, 24)

    def test_snap_result_in_pool(self):
        """snap=True 时, 任意输入都应返回 CANDIDATE_POOL 中的值"""
        for h in [0, 10, 30, 50, 60, 80, 90, 100, 150, 200]:
            result = estimate_font_size(bbox_h_px=h, snap=True)
            assert result in CANDIDATE_POOL, f"h={h} → {result} not in pool"


class TestSnapToPool:
    def test_exact_match(self):
        assert snap_to_pool(18) == 18
        assert snap_to_pool(24) == 24

    def test_snaps_to_nearest(self):
        # 17 离 18 比 16 近 (距离 1 vs 1, 但 18 也在 pool 里, 取第一个 key 满足)
        assert snap_to_pool(17) in (16, 18)
        assert snap_to_pool(13) in (12, 14)

    def test_below_min(self):
        assert snap_to_pool(0) == 8
        assert snap_to_pool(5) == 8

    def test_above_max(self):
        assert snap_to_pool(200) == 96
        assert snap_to_pool(100) == 96

    def test_custom_pool(self):
        assert snap_to_pool(15, pool=[10, 20, 30]) in (10, 20)


class TestConstants:
    def test_line_spacing(self):
        assert LINE_SPACING == 1.3

    def test_size_tiers_sorted_descending(self):
        # tiers 阈值从大到小: 90, 50, 0
        thresholds = [t[0] for t in SIZE_TIERS]
        assert thresholds == sorted(thresholds, reverse=True)

    def test_candidate_pool_ascending_no_dupes(self):
        assert CANDIDATE_POOL == sorted(set(CANDIDATE_POOL))
        assert len(CANDIDATE_POOL) >= 10  # 不能太少
