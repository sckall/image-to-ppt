# PNG 图片课件 → 可编辑 PPT 方案

> **目标**:把纯图片课件(PNG)转成可编辑的 PPT,保留**文字内容、位置、字号、颜色**,原图作为背景层或被擦除文字后重建。
>
> **工作目录**:本仓库根目录(PNG2PPT)
>
> **更新日期**:2026-08-15

---

## 一、最终选定的方案

经过联网调研业界 4 个对口开源项目,选定 **方案 B**:`px-image2pptx`(35⭐,最完整流水线,开箱即用)。

### 为什么选它

| 对比项 | px-image2pptx ✅ | MinerU2PPT | NBLM2PPTX | OCR-Arcade |
|--------|----------------|-----------|-----------|-----------|
| OCR 引擎 | PaddleOCR v5 | MinerU | Gemini API | Tesseract.js |
| 字号识别 | ✅ 几何法 + 宽度自适应 | ✅ bbox+聚类 | ✅ AI 直出 | ⚠️ 简单 |
| 颜色识别 | ✅ 像素众数 | ⚠️ 基础 | ✅ AI 直出 | ❌ |
| 背景修复 | ✅ LAMA 神经网络 | ❌ 无 | ✅ Gemini | ❌ 无 |
| 中英文混排 | ✅ | ✅ | ✅ | ⚠️ |
| 模型本地化 | ✅ 完全本地 | ✅ 完全本地 | ❌ 需联网+API Key | ✅ 浏览器 |
| 开箱即用 | ✅ 一行命令 | ⚠️ 需 MinerU | ⚠️ 需 API | ⚠️ 前端 |
| **综合** | **首选** | 次选 | 样式最强 | 浏览器用 |

---

## 二、核心管线(px-image2pptx 已实现)

```
PNG 输入
  │
  ├─→ [1] OCR (PaddleOCR PP-OCRv5)
  │      输入: PNG 图片
  │      输出: text_regions = [{id, text, confidence, bbox: {x1,y1,x2,y2}}, ...]
  │
  ├─→ [2] Textmask (经典 CV)
  │      输入: PNG 图片 + OCR bbox
  │      输出: tight mask (紧贴文字笔画) + dilated mask (扩展后)
  │      关键: AND 操作只 mask OCR 框内的文字像素,保护图标/边框
  │
  ├─→ [3] Inpaint (LAMA 神经网络)
  │      输入: PNG + dilated mask
  │      输出: background.png (文字被擦除,背景重建)
  │
  └─→ [4] Assemble (python-pptx)
         输入: PNG + background.png + text_regions + tight_mask
         输出: output.pptx (16:9 16:10 或原比例幻灯片,每页含:
                 - 背景图 (背景层)
                 - 文字框 (可编辑层,位置/字号/颜色还原)
```

---

## 三、字号识别原理(技术核心)

### 公式

```python
# px-image2pptx 的几何法 (autoscale_font in assemble.py:127)
line_h_pt = (bbox_h_px / ppi) * 72
font_pt = round(line_h_pt)
# 然后跑宽度自适应循环 (40 轮):
#   - 文字宽度 > bbox 宽度的 94% 就缩小字号
#   - 文字宽度 < bbox 宽度的 90% 就放大字号
# 最终字号落在 [8pt, 72pt] 区间
```

### `ppi` 怎么算

```python
# SlideMapper in assemble.py
ppi = img_w / slide_w_inches
# 例:图片 1920px 宽,PPT slide 宽 10 英寸
#    ppi = 192 → 1 像素 = 1/192 英寸 = 0.375 pt
```

### 候选池优化(可选,我们自研时再加)

`px-image2pptx` 用连续值,但实际**常用字号是离散的**:
```python
CANDIDATE_POOL = [9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 54, 60, 72]
# 把估算结果 snap 到最近候选,可减少 ±1-2pt 误差
```

### 误差分析

| 误差源 | 大小 | 缓解 |
|--------|------|------|
| OCR bbox 含上下留白 | ±2-4pt | 宽度自适应循环(px 已用) |
| 字体度量差异(宋体/黑体) | ±1-2pt | CJK 用全角 em |
| DPI 不准 | ±5%+ | 用实际图片宽/slide宽算 ppi |
| 字号本身离散 | ±1-2pt | 候选池 snap |

**综合精度**:±2-3pt,**够 PPT 编辑用**(肉眼分辨不出 16pt vs 18pt 差 2pt)。

---

## 四、依赖与安装

### 系统依赖

- Python 3.9+
- macOS / Linux / Windows 均可
- **px-image2pptx 已是 git submodule**, clone 时用 `--recurse-submodules` 一次拉齐

### Python 包(px-image2pptx 拆分可选装)

```bash
# 核心 (文字 mask + 组装 PPTX)
pip install pillow numpy opencv-python python-pptx

# OCR (PaddleOCR)
pip install paddleocr paddlepaddle

# Inpainting (LAMA)
pip install torch simple-lama-inpainting
```

**总模型大小**:~370MB(首次运行自动下载)

| 模型 | 大小 | 用途 | 存储位置 |
|------|------|------|---------|
| PP-OCRv5_server_det | 84 MB | 文字检测 | ~/.paddlex/official_models/ |
| PP-OCRv5_server_rec | 81 MB | 文字识别 | ~/.paddlex/official_models/ |
| big-lama | 196 MB | 背景修复 | ~/.cache/torch/hub/checkpoints/ |

---

## 五、当前落地状态

### 已完成 ✅

- [x] **联网调研**:4 个开源项目对比分析
- [x] **选定方案**:px-image2pptx
- [x] **拉取仓库**:`git clone` 到工作目录
- [x] **方案文档**:本文件 (SCHEME.md)

### 待执行 ⏳

- [ ] **安装依赖**:Python 包 + 模型下载
- [ ] **准备测试样本**:找 1-2 张典型课件 PNG
- [ ] **跑通测试**:`px-image2pptx slide.png -o out.pptx`
- [ ] **结果验证**:
  - [ ] 文字是否正确识别
  - [ ] 字号是否还原准确(肉眼对比)
  - [ ] 颜色是否还原
  - [ ] 背景是否被正确擦除+重建
- [ ] **中文测试**:`--lang ch`
- [ ] **批量测试**:`examples/` 里的样例图

### 进阶(可选) ⏳

- [ ] **字号 snap 候选池优化**(自研补丁)
- [ ] **粗体识别增强**(像素密度判定)
- [ ] **集成到现有 MinerU 工作流**(如果你想统一)
- [ ] **GUI 封装**(参考 MinerU2PPT 的 gui.py,1098 行)

---

## 六、目录结构

```
PNG2PPT/                                  ← 工作目录
├── SCHEME.md                             ← 本文件 (方案文档)
├── px-image2pptx/                        ← 拉取的第三方实现
│   ├── px_image2pptx/                    ← 核心代码
│   │   ├── __init__.py
│   │   ├── pipeline.py                   ← 主入口 image_to_pptx()
│   │   ├── ocr.py                        ← PaddleOCR 封装
│   │   ├── textmask.py                   ← 文字 mask (经典 CV)
│   │   ├── inpaint.py                    ← LAMA 封装
│   │   ├── assemble.py                   ← python-pptx 组装(含字号反推)
│   │   └── cli.py                        ← 命令行入口
│   ├── examples/                         ← 示例图片
│   ├── tests/
│   ├── README.md
│   ├── README_zh.md
│   └── pyproject.toml
└── (后续会生成)
    ├── tests_local/                      ← 我的本地测试
    │   ├── slide1.png                    ← 测试输入
    │   ├── slide1_out.pptx               ← 测试输出
    │   └── report.json                   ← 运行报告
    └── docs/                             ← 我的本地笔记
        ├── BUG_FIXES.md
        └── TUNING.md
```

---

## 七、命令速查

```bash
# 进入工作目录
cd <项目根目录>  # 把仓库 clone 下来后 cd 进去即可

# 1. 安装(完整流水线)
cd px-image2pptx
pip install -e ".[all]"

# 2. 命令行调用
px-image2pptx slide.png -o output.pptx
px-image2pptx slide.png -o output.pptx --lang ch           # 中文
px-image2pptx slide.png -o output.pptx --skip-inpaint      # 跳过 LAMA (适合纯色背景)
px-image2pptx slide.png -o output.pptx --min-font 10 --max-font 60  # 限制字号范围
px-image2pptx slide.png -o output.pptx --work-dir ./debug/  # 保留中间产物

# 3. Python API
python3 -c "
from px_image2pptx import image_to_pptx
report = image_to_pptx('slide.png', 'output.pptx', lang='ch')
print(report)
"

# 4. 批量(自己写循环)
for f in tests_local/*.png; do
    px-image2pptx "$f" -o "tests_local/$(basename $f .png).pptx" --lang ch
done
```

---

## 八、参考项目

| 项目 | URL | ⭐ | 关键借鉴 |
|------|-----|----|---------|
| **px-image2pptx** | https://github.com/JadeLiu-tech/px-image2pptx | 35 | **当前主线** |
| MinerU2PPT | https://github.com/JuniverseCoder/MinerU2PPT | 193 | KMeans 字号聚类 |
| NBLM2PPTX | https://github.com/laihenyi/NBLM2PPTX | 337 | AI 样式识别 prompt |
| OCR-Arcade | https://github.com/winterdrive/OCR-Arcade | 3 | 浏览器端 ONNX |

---

## 九、风险与限制

| 风险 | 说明 | 缓解 |
|------|------|------|
| 字号误差 ±2-3pt | bbox 含留白 | 宽度自适应循环 |
| 字体不还原 | px 用 Arial/Helvetica | 后续可加字体识别 |
| LAMA 慢(4-8s/张) | 神经网络 inpaint | `--max-inpaint-size 2048` |
| WebP 不支持 | PaddleOCR v5 限制 | 先转 PNG/JPG |
| 中文混合排版 | 全角 em 已处理 | 测试验证 |
| 复杂背景 | LAMA 重建质量下降 | `--skip-inpaint` 或接受 |

---

## 十、备选方案速查(若 px 路线不满足)

### 方案 C(自研,基于你的 MinerU)

```
PNG → MinerU → middle.json → [新写] png2pptx.py → .pptx
                              复用 MinerU2PPT 的 converter/ 模块
                              约 300-500 行 Python
```

**何时切换**:你希望 OCR 引擎统一(都用 MinerU),或 px 对中文/复杂课件效果不佳

### 方案 D(AI 增强)

```
PNG → Gemini 2.5 Flash (AI) → {文字块+字号+字重+颜色+位置} → PptxGenJS → .pptx
```

**何时切换**:你需要**完全还原**字号、字重、颜色,且愿意付 API 费用(免费额度 15 RPM)

---

> 📌 **下一步**: 在工作目录跑 `pip install -e ".[all]"`,然后用 `examples/` 里的小图测试。