#!/usr/bin/env python3
"""gui.py - 简单 Tkinter 包装(调用 px2pptx_batch.py)

依赖: tkinter (Python 内置, 不需要额外 pip install)
启动: python3 gui.py
"""
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("image-to-ppt 转换器")
        self.root.geometry("700x520")
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 6, "pady": 4}

        # === 输入行 ===
        frm_input = ttk.Frame(self.root)
        frm_input.pack(fill=tk.X, **pad)
        ttk.Label(frm_input, text="输入:").pack(side=tk.LEFT)
        self.input_var = tk.StringVar()
        ttk.Entry(frm_input, textvariable=self.input_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(frm_input, text="选文件", command=self._pick_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(frm_input, text="选目录", command=self._pick_dir).pack(side=tk.LEFT, padx=2)

        # === 输出行 ===
        frm_output = ttk.Frame(self.root)
        frm_output.pack(fill=tk.X, **pad)
        ttk.Label(frm_output, text="输出:").pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        ttk.Entry(frm_output, textvariable=self.output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(frm_output, text="选目录", command=self._pick_outdir).pack(side=tk.LEFT, padx=2)

        # === 选项行 ===
        frm_opts = ttk.Frame(self.root)
        frm_opts.pack(fill=tk.X, **pad)
        ttk.Label(frm_opts, text="语言:").pack(side=tk.LEFT)
        self.lang_var = tk.StringVar(value="ch")
        ttk.Combobox(
            frm_opts, textvariable=self.lang_var,
            values=("ch", "en"), width=8, state="readonly",
        ).pack(side=tk.LEFT, padx=4)

        # === 运行按钮 ===
        frm_run = ttk.Frame(self.root)
        frm_run.pack(fill=tk.X, **pad)
        self.run_btn = ttk.Button(frm_run, text="开始转换", command=self._run)
        self.run_btn.pack(side=tk.LEFT)
        ttk.Label(frm_run, text="(首次运行会下载 ~370MB 模型, 之后秒级)").pack(side=tk.LEFT, padx=8)

        # === 日志区 ===
        frm_log = ttk.Frame(self.root)
        frm_log.pack(fill=tk.BOTH, expand=True, **pad)
        ttk.Label(frm_log, text="日志:").pack(anchor=tk.W)
        self.log_widget = scrolledtext.ScrolledText(frm_log, wrap=tk.WORD, height=14, state=tk.NORMAL)
        self.log_widget.pack(fill=tk.BOTH, expand=True)

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="选 PNG / JPG 文件",
            filetypes=[("Image", "*.png *.jpg *.jpeg"), ("All", "*.*")],
        )
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                self.output_var.set(str(Path(path).with_suffix(".pptx")))

    def _pick_dir(self):
        path = filedialog.askdirectory(title="选图片目录")
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                self.output_var.set(str(Path(path)) + "_pptx")

    def _pick_outdir(self):
        path = filedialog.askdirectory(title="选输出目录")
        if path:
            self.output_var.set(path)

    def _log(self, msg):
        self.log_widget.insert(tk.END, msg + "\n")
        self.log_widget.see(tk.END)
        self.root.update_idletasks()

    def _run(self):
        inp = self.input_var.get().strip()
        out = self.output_var.get().strip()
        if not inp:
            messagebox.showerror("错误", "请先选输入文件或目录")
            return
        if not Path(inp).exists():
            messagebox.showerror("错误", f"输入路径不存在:\n{inp}")
            return
        self.run_btn.config(state=tk.DISABLED, text="运行中...")
        threading.Thread(target=self._run_worker, args=(inp, out), daemon=True).start()

    def _run_worker(self, inp, out):
        try:
            cmd = [
                sys.executable,
                str(Path(__file__).parent / "px2pptx_batch.py"),
                inp, out or "",
                "--lang", self.lang_var.get(),
            ]
            self.root.after(0, self._log, f"$ {' '.join(cmd)}")
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(Path(__file__).parent),
            )
            for line in proc.stdout:
                self.root.after(0, self._log, line.rstrip())
            proc.wait()
            if proc.returncode == 0:
                self.root.after(0, self._log, "✅ 转换完成")
                self.root.after(0, lambda: messagebox.showinfo("完成", "转换完成"))
            else:
                self.root.after(0, self._log, f"❌ 失败 (exit {proc.returncode})")
                self.root.after(0, lambda: messagebox.showerror("失败", f"退出码 {proc.returncode}"))
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            err = str(e)
            self.root.after(0, self._log, f"❌ 异常: {err}")
            self.root.after(0, lambda err=err: messagebox.showerror("异常", err))
        finally:
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL, text="开始转换"))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
