# 测试结果 — 2026-08-15

> 在工作目录 `<项目根目录>` 完成

---

## 测试环境

| 项目 | 详情 |
|------|------|
| macOS | (M 系列 ARM) |
| Python | 3.11.14 (venv) |
| 依赖 | uv 装在 `/tmp/uv-cache`(避开 ~/.cache 权限) |
| 模型缓存 | `/tmp/paddlex` `/tmp/torch-cache` `/tmp/ms-cache` |
| PaddleOCR | PP-OCRv5_server_det + PP-OCRv5_server_rec + en_PP-OCRv5_mobile_rec |
| LAMA | big-lama.pt (196MB) |

---

## 踩过的坑(都解决了)

### 1. `~/.local` 写不进去

```
ERROR: Could not install packages due to an OSError: [Errno 1] Operation not permitted
'~/.local/lib/python3.13/site-packages/__editable___px_image2pptx_0_1_0_finder.py'
```

**解决**: 用 `uv venv --python 3.11 .venv` 建专用 venv,绕开 conda base

### 2. uv 默认 cache 也写不进去

```
Failed to initialize cache at `~/.cache/uv`
```

**解决**: `UV_CACHE_DIR=/tmp/uv-cache uv ...`

### 3. PaddleOCR 下不到模型

```
Encounter exception when download model from bos. No model source is available!
```
HF SSL 握手失败;AIStudio 403。

**解决**:
1. `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` 跳过预检
2. `PADDLE_PDX_CACHE_HOME=/tmp/paddlex` 把缓存指到 /tmp
3. 用 ModelScope (`MODELSCOPE_CACHE=/tmp/ms-cache`)手动下载所需模型到 `PADDLE_PDX_CACHE_HOME` 下:
   - `PP-OCRv5_server_det` (87.9MB)
   - `PP-OCRv5_server_rec` (84.4MB)
   - `PP-LCNet_x1_0_textline_ori` (6.7MB)

### 4. simple_lama 也要写 ~/.cache

```
PermissionError: [Errno 1] Operation not permitted: '~/.cache/torch'
```

**解决**: `TORCH_HOME=/tmp/torch-cache` (torch.hub.get_dir() 跟 TORCH_HOME 走)

---

## 解决方案:`px2pptx.sh` 一键脚本

封装所有环境变量到脚本里,日常使用只关心:

```bash
./px2pptx.sh slide.png                       # 默认输出 slide.pptx, lang=ch
./px2pptx.sh slide.png out.pptx en           # 英文
./px2pptx.sh slide.png out.pptx ch --skip-inpaint  # 跳过 LAMA
```

脚本位置:`px2pptx.sh`(已在工作目录)

---

## 测试结果汇总

| 测试图 | OCR 区域 | 文字框 | 字号分布(pt) | 耗时(s) | 备注 |
|--------|---------|--------|-------------|---------|------|
| test1 (英文单图) | 7 | 5 | 18 / 49-51 | 9.1 | 标题 49-51pt,正文 18pt ✅ |
| test2 (英文密集) | 22+ | 17 | 10/12/22/39-40 | 10.9 | 多层级还原好 ✅ |
| test3 (英文 chart) | 14+ | 13 | 27-35 | 7.7 | 标题 35pt,正文 27pt ✅ |
| test4 (中英混排) | 22 | 21 | 18-34 | 8.6 | **中文识别完美** ✅ |

---

## 验证 test1 (英文) 字号反推

```
Slide: 13.33 x 7.50 inches (16:9)
Shape 2: sz=49pt  text="Yet, the road from a single"       (标题)
Shape 3: sz=51pt  text="perfect drive to mass-market"      (标题)
Shape 4: sz=50pt  text="autonomy is long."                 (标题)
Shape 5: sz=18pt  text="The challenge is not just..."      (正文)
Shape 6: sz=18pt  text="but consistently delivering it..."  (正文)
```

**结论**: ✅ 标题 ~50pt,正文 ~18pt,**完全符合 PPT 视觉层级**

---

## 验证 test4 (中英混排) 字号反推

```
[中] sz=34pt "应用前景I:构建真正"活着"的NPC世界"     ← 主标题
[中] sz=20-21pt "开放世界RPG" / "叙事驱动游戏"          ← 副标题
[EN] sz=23pt "(e.g., The Witcher, Elden Ring)"        ← 英文注释
[中] sz=18-19pt "我们的模拟证明:..." (正文)            ← 正文
```

**结论**: ✅ 中文识别完全正确,字号层级分明,中英混排 OK

---

## 性能数据(M 系列 Mac, CPU)

| 阶段 | 耗时 |
|------|------|
| OCR | 4-8s (首次下模型 30s+) |
| Textmask | <0.1s |
| **LAMA** | **3-7s** (瓶颈) |
| Assemble | <0.1s |
| **总计** | **5-12s** (缓存后) |

优化建议:
- `--max-inpaint-size 2048` 强制降采样 LAMA 输入,提速 30%
- `--skip-inpaint` 跳过 LAMA,适合纯色背景(<1s)

---

## 文件清单

```
PNG2PPT/
├── README.md            (目录索引)
├── SCHEME.md            (方案文档)
├── RESEARCH.md          (联网调研)
├── RUNBOOK.md           (原落地手册,需更新)
├── TEST_RESULTS.md      (本文档)
├── px2pptx.sh           (一键脚本)✅
├── px-image2pptx/       (源码)
└── tests_local/         (测试输出)
    ├── test1.png        (~300KB,英文)
    ├── test1.pptx       (验证 OK)
    ├── test2.png
    ├── test2.pptx
    ├── test3_chart.png
    ├── test3_chart.pptx
    ├── test4_texture.png
    ├── test4_texture.pptx  (中文 OK) ✅
    └── test1_via_script.pptx  (脚本验证)
```

---

## 下一步

- [ ] 拿你自己的真实课件 PNG 测一下(关键!)
- [ ] 如果有大量错字: 调整 `--sensitivity` `--dilation`
- [ ] 如果字号普遍偏大/偏小: 加候选池 snap(自研补丁)
- [ ] 集成到现有 MinerU 工作流(可选)

---

## 给后来人的话

如果你在新机器上跑这套,需要做的:

1. `cd /path/to/PNG2PPT`
2. `uv venv --python 3.11 .venv`
3. `source .venv/bin/activate`
4. `UV_CACHE_DIR=/tmp/uv-cache uv pip install -e "px-image2pptx[all]"`
5. 用 `px2pptx.sh` 跑图

模型首次会下到 `/tmp/paddlex` 和 `/tmp/torch-cache`,**重装系统或换机器要重新下**(除非你把这些目录持久化)。