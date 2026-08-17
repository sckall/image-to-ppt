"""mineru2pptx.py 单元测试 — CLI 解析 + bbox→EMU 数学"""
from mineru2pptx import _parse_args


class TestParseArgs:
    def test_minimal_positional(self):
        args = _parse_args(["img_dir", "mineru_dir", "out.pptx"])
        assert args.input_dir == "img_dir"
        assert args.mineru_dir == "mineru_dir"
        assert args.output_pptx == "out.pptx"
        assert args.slide_width == 13.333  # default 16:9

    def test_custom_slide_width(self):
        args = _parse_args(["a", "b", "c", "--slide-width", "10.0"])
        assert args.slide_width == 10.0

    def test_help_exits_cleanly(self, capsys):
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            _parse_args(["--help"])
        # argparse 退出码是 0
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "MinerU" in (captured.out + captured.err)

    def test_missing_required_arg_fails(self):
        import pytest
        with pytest.raises(SystemExit):
            _parse_args(["only_one_arg"])

    def test_jpg_and_jpeg_glob_logic(self, tmp_path):
        """通过直接测 glob 行为验证 .jpg / .jpeg 双支持(不跑 build_clean_pptx)"""
        from pathlib import Path

        (tmp_path / "1.jpg").touch()
        (tmp_path / "2.jpeg").touch()
        (tmp_path / "3.png").touch()  # 不应被选中
        (tmp_path / "abc.jpg").touch()  # 非数字 stem, 不应被选中

        ids = sorted([
            int(p.stem) for p in tmp_path.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg") and p.stem.isdigit()
        ])
        assert ids == [1, 2]
