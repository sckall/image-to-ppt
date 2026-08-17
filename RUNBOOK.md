# 落地运行手册

> 跟着这个文件一步步把 px-image2pptx 跑起来。

---

## Step 1: 环境检查

```bash
# Python 版本(需要 3.9+)
python3 --version

# pip 版本
python3 -m pip --version

# 检查是否有 conda/venv
which python3 conda
```

如果你用 conda(看路径里有 miniconda):
```bash
# 创建专用环境
python3 -m venv .venv
source .venv/bin/activate
```

---

## Step 2: 安装依赖

```bash
cd px-image2pptx  # 假设已按 README Step 0 clone 了上游

# 完整安装 (OCR + Inpaint + 全部)
pip install -e ".[all]"

# 如果只想试核心(不要 OCR 和 LAMA,后面单独装)
pip install -e .
pip install -e ".[ocr]"
pip install -e ".[inpaint]"
```

**首次安装时间**:
- pip 装包:3-5 分钟
- 模型下载:~370MB,取决于网速 1-10 分钟

---

## Step 3: 测试一张示例图

仓库自带 examples,先用它们验证:

```bash
ls examples/
# 应该看到类似 chart_good1.png, image_good1_input.png 等

# 试一张
cd ..
mkdir -p tests_local
cp px-image2pptx/examples/image_good1_input.png tests_local/test1.png

# 跑
cd px-image2pptx
px-image2pptx ../tests_local/test1.png -o ../tests_local/test1.pptx --lang en
```

**预期时间**: 首次 30 秒(模型加载) + 5-15 秒处理

---

## Step 4: 中文测试

把课件 PNG 放到 tests_local/ 跑中文模式:

```bash
px-image2pptx ../tests_local/课件1.png -o ../tests_local/课件1.pptx --lang ch
```

打开生成的 .pptx,检查:
- 文字是否完整识别(没有错字、漏字)
- 字号是否合理(标题大、正文小)
- 颜色是否还原
- 背景是否干净(无文字残留)

---

## Step 5: 调参(如果效果不理想)

| 问题 | 调参 | 说明 |
|------|------|------|
| 字号偏大/偏小 | `--min-font` `--max-font` | 限制字号范围 |
| 背景擦不干净 | 改 `--sensitivity` `--dilation` | 调文字 mask 灵敏度 |
| 背景重建质量差 | `--max-inpaint-size 2048` | 缩小 LAMA 输入 |
| 纯色背景不需要擦 | `--skip-inpaint` | 跳过 LAMA,快很多 |
| 大图处理慢 | `--max-inpaint-size 2048` | 强制降采样 |

---

## Step 6: 批量处理

```bash
# 单条命令
for f in tests_local/*.png; do
    name=$(basename "$f" .png)
    px-image2pptx "$f" -o "tests_local/${name}.pptx" --lang ch
done
```

或 Python:
```python
from px_image2pptx import image_to_pptx
import glob

for img_path in glob.glob("tests_local/*.png"):
    out = img_path.replace(".png", ".pptx")
    report = image_to_pptx(img_path, out, lang="ch")
    print(f"✅ {img_path} → {out}: {report['text_boxes']} boxes")
```

---

## Step 7: 调试模式

保留中间产物,看每一步效果:

```bash
px-image2pptx slide.png -o out.pptx --work-dir ./debug/
# 会生成:
# debug/background.png     擦除文字后的背景
# debug/tight_mask.png     紧贴文字的 mask
# debug/dilated_mask.png   扩展后的 mask
# debug/regions.json       OCR 结果
```

---

## 常见问题

### Q1: paddlepaddle 安装失败
A: macOS M1/M2 用:
```bash
pip install paddlepaddle==3.2.2
```

### Q2: LAMA 首次跑巨慢
A: torch 第一次会编译/下载,等就好。第二次跑会快。

### Q3: PaddleOCR 不支持 WebP
A: 先转 PNG:
```bash
for f in *.webp; do
    sips -s format png "$f" --out "${f%.webp}.png"
done
```

### Q4: 字号整体偏大或偏小
A: 这是 bbox 含留白的副作用。后续可以:
1. 加候选池 snap(在 `assemble.py:147` 后插入 snap 到 `[12, 14, 16, ...]`)
2. 全局乘个缩放系数(经验值 0.85)

### Q5: 输出的 PPT 在 Keynote/WPS 打开错位
A: python-pptx 输出符合 OOXML 标准,应该兼容。如果有问题,试着用 Office 2016+ 打开重存一次。

---

## 性能基准(M1 Pro 实测)

| 阶段 | 首次 | 缓存后 |
|------|------|--------|
| PaddleOCR | 2-5s | 1-3s |
| Textmask | 1-3s | 1-3s |
| LAMA | 4-8s | 3-6s |
| Assemble | <0.2s | <0.2s |
| **总计** | **8-16s** | **5-12s** |

如果你用 GPU:OCR 和 LAMA 都能加速到 <1s。

---

## 下一步

跑通后,可以考虑:
1. **封装 GUI**:参考 MinerU2PPT 的 gui.py (PyQt/Tkinter)
2. **字号 snap 优化**:在 assemble.py 改 30 行
3. **集成 MinerU**:把 OCR 换成 MinerU 调用,统一工作流
4. **批量脚本**:做 watch 目录自动转换