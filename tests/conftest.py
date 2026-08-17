"""让 pytest 能 import 仓库根目录的脚本(没有 src/ 布局的项目通用做法)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
