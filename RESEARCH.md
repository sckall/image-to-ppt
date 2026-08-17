# 联网调研记录 — PNG 转可编辑 PPT

> 调研时间:2026-08-15
> 目的:对比业界开源实现,选定最适合"中文课件 PNG → 可编辑 PPT"的方案

---

## 一、检索关键词与渠道

- GitHub API:`search/repositories?q=image+to+PPTX+OCR`
- GitHub API:`search/repositories?q=PNG+to+editable+PPT+font+preservation`
- GitHub API:`search/repositories?q=slide+reconstruction+image+OCR`
- 命中:10 个相关仓库,4 个核心候选

---

## 二、4 个核心项目详解

### 🥇 px-image2pptx (35⭐) — 当前选定

**仓库**: https://github.com/JadeLiu-tech/px-image2pptx
**作者**: JadeLiu-tech
**许可证**: MIT
**Demo**: https://huggingface.co/spaces/pxGenius/image2pptx

#### 架构
```
PNG → PaddleOCR(检测+识别) → text_regions
   → Textmask(经典 CV,adaptive threshold) → 文字像素 mask
   → Mask-clip (AND OCR bbox) → 仅文字区域 mask
   → LAMA 神经网络 inpaint → background.png
   → assemble (python-pptx) → .pptx
```

#### 关键文件
- `assemble.py:127 autoscale_font()` — 字号反推核心
- `assemble.py:131-150` — 宽度自适应循环(40 轮)
- `assemble.py:415-460` — PPTX 组装主流程
- `assemble.py:50 bbox_to_emu()` — 像素→EMU 单位换算

#### 字号公式
```python
line_h_pt = (bbox_h_px / ppi) * 72
# 1. 初值 = bbox像素高 → 通过 PPI 换算成磅
# 2. 宽度校验循环 (40 次):
#    - 文字宽度 > bbox 宽 94% → 缩字号
#    - 文字宽度 < bbox 宽 90% → 放字号
# 3. 限制在 [8pt, 72pt]
```

#### CJK 处理
- 用全角 em (1.0×) 测宽,而不是 Latin 的 0.5×
- `_load_reference_font()` 加载系统字体测宽,无字体时退化到字符宽度估算

#### 颜色识别
- `tight_mask` (紧贴文字) → 取 mask 内像素 RGB 众数
- 反向背景(白字深底)检测:取与背景差异最大的像素

#### Inpainting
- big-lama(Apache 2.0,~196MB)
- 默认不缩放;`--max-inpaint-size 2048` 可提速

#### 性能(M1 Pro 实测)
- 首次:8-16s/张(含模型加载)
- 缓存后:5-12s/张
- LAMA 4-8s 是瓶颈

#### 已知限制(README 自述)
- 复杂背景 LAMA 重建质量差
- 装饰性/手写字体无法还原(用 Arial 替代)
- 居中/两端对齐会丢(只支持左对齐)
- WebP 不支持(PaddleOCR v5 限制)
- 大图>4000px 慢

---

### 🥈 MinerU2PPT (193⭐) — 次选

**仓库**: https://github.com/JuniverseCoder/MinerU2PPT

#### 与 px 的关键差异
- **OCR 引擎不同**: 用 MinerU 而不是 PaddleOCR
- **字号公式不同**: `font_pt = bbox_h_px × scale_y`(scale = 渲染DPI/72)
- **聚类优化**: `generator.py:226 _optimize_groups_with_kmeans()` — KMeans 把字号归并成几个簇
- **无 inpainting**: 不擦除原文字,直接嵌入原图作为背景,文字层叠在上面

#### 代码细节
- `generator.py:580-583`: 字号计算核心
```python
if style_font_size:
    font_size_pts = max(6.0, float(style_font_size) * context.coords['scale_y'])
else:
    font_size_pts = max(6.0, (run_bbox[3] - run_bbox[1]) * context.coords['scale_y'])
```
- `generator.py:226-295`: KMeans 聚类(log scale)
- `ocr_merge.py:25 OCR_FONT_DISTANCE_THRESHOLD = 60.0`: OCR bbox 扩展阈值

#### 适合场景
- 你已经有 MinerU 部署,想统一 OCR 引擎
- 课件背景简单(纯色/浅色),不需要擦除文字
- 想要 GUI 客户端(它有 gui.py + pyinstaller 打包)

---

### 🥉 NBLM2PPTX (337⭐) — 样式最强

**仓库**: https://github.com/laihenyi/NBLM2PPTX

#### 独门武器: Gemini AI 视觉模型
- 直接问 Gemini "这块文字的字号/字重/颜色是多少"
- OCR Prompt 关键(`index.html:1280-1295`):
```
For each text block, provide:
- text: exact text content
- box_2d: bounding box [ymin, xmin, ymax, xmax] in 0-1000 coordinate system
- font_size_pt: estimated font size in points (typical range: 8-72)
- font_weight: "normal" or "bold"
- font_style: "normal" or "italic"
- text_align: "left", "center", or "right"
- color: hex color code
- line_height: multiplier (typically 1.0-2.0)
```

#### 双模式
- **Lite** (`gemini-2.5-flash-lite`): 省 API 额度 50%,**不识别样式**(所有文字统一字号)
- **Standard** (`gemini-2.5-flash`): 完整样式识别(字号/字重/颜色/对齐)

#### Inpainting
- 用 Gemini 图像生成能力擦除文字 + 重建背景
- Prompt: `"Remove all text from this image while preserving the background."`
- 温度: 0.4

#### 适合场景
- 你需要**完美还原**字号/字重/颜色
- 你愿意用 API(免费 15 RPM)
- 单 HTML 文件部署,无需后端

#### 限制
- 联网 + API Key(Google AI Studio 免费申请)
- 处理慢(2-5s/页,含 API 延迟)
- 完全无法离线

---

### ⚪ OCR-Arcade (3⭐) — 浏览器端

**仓库**: https://github.com/winterdrive/OCR-Arcade

- 用 Tesseract.js (WASM) + onnxruntime-web
- 浏览器内全部跑完,**完全离线**
- 但 OCR 精度比 PaddleOCR/MinerU 差一截
- 主要解决 NotebookLM 静态图无法编辑问题

---

## 三、关键技术决策对比

### 字号识别

| 项目 | 方法 | 精度 |
|------|------|------|
| px-image2pptx | bbox 像素高 → PPI × 72 + 宽度自适应 | ±2-3pt |
| MinerU2PPT | bbox × scale + KMeans 聚类 | ±2-4pt |
| NBLM2PPTX | AI 直接判断 | ±1-2pt(理论) |

### Inpainting (背景修复)

| 项目 | 方法 | 效果 |
|------|------|------|
| px-image2pptx | LAMA 神经网络 | 良好(复杂背景一般) |
| NBLM2PPTX | Gemini 图像编辑 | 优秀但慢 |
| MinerU2PPT | 不做,原图作底 | 文字残留可见 |

### OCR 引擎

| 项目 | 引擎 | 中英混排 |
|------|------|---------|
| px-image2pptx | PaddleOCR v5 | ✅ |
| MinerU2PPT | MinerU | ✅(MinerU 强项) |
| NBLM2PPTX | Gemini AI | ✅✅(AI 最强) |
| OCR-Arcade | Tesseract.js | ⚠️ |

---

## 四、为什么最终选 px-image2pptx

1. **流水线最完整**:OCR + Textmask + Inpaint + Assemble,一气呵成
2. **完全本地**:不需要联网/API Key,适合教育场景(隐私敏感)
3. **中文支持**:PaddleOCR v5 server 模型中文识别强
4. **实现透明**:470 行 assemble.py 可读,出问题能改
5. **依赖稳定**:Pillow + OpenCV + python-pptx + PyTorch 都是久经考验的库

MinerU2PPT 是次选 — 如果你后续要把这个工具集成到 MinerU 工作流,可以借鉴它的 converter 模块。

---

## 五、如果 px 路线不满足怎么办

| 痛点 | 切换到 |
|------|--------|
| 中文识别不够准 | MinerU2PPT |
| 字号/字重/颜色还原差 | NBLM2PPTX(用 AI) |
| 想要 GUI | MinerU2PPT(已有 PyInstaller 打包) |
| 想集成到现有 MinerU | 自研(基于你的 MinerU) |
| 需要浏览器端运行 | OCR-Arcade |