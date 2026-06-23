"""QuantSage License Key Generator — GUI for developer use.

Ed25519-signed, device-bound license keys.
Requires quantsage_private.key in the project root.

Usage: python scripts/keygen_gui.py
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is on path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(str(_project_root))

import tkinter as tk
from tkinter import ttk, messagebox

from src.core.license import generate_key


class KeygenApp:
    def __init__(self, root):
        self.root = root
        root.title("QuantSage License Key Generator")
        root.geometry("500x400")
        root.resizable(False, False)

        # Style
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="QuantSage 许可证密钥生成器", font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 15))
        ttk.Label(frame, text="Ed25519 签名 · 设备绑定 · 防伪", foreground="gray").pack(pady=(0, 20))

        # Device code
        ttk.Label(frame, text="设备码 (客户提供):").pack(anchor="w")
        self.device_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.device_var, width=50).pack(fill="x", pady=(2, 10))

        # Level
        ttk.Label(frame, text="等级:").pack(anchor="w")
        self.level_var = tk.StringVar(value="pro")
        level_frame = ttk.Frame(frame)
        level_frame.pack(fill="x", pady=(2, 10))
        ttk.Radiobutton(level_frame, text="Pro (专业版)", variable=self.level_var, value="pro").pack(side="left", padx=(0, 20))
        ttk.Radiobutton(level_frame, text="Free (免费版)", variable=self.level_var, value="free").pack(side="left")

        # Expiry
        ttk.Label(frame, text="有效期:").pack(anchor="w")
        exp_frame = ttk.Frame(frame)
        exp_frame.pack(fill="x", pady=(2, 10))

        self.exp_var = tk.StringVar(value="permanent")
        ttk.Radiobutton(exp_frame, text="永久", variable=self.exp_var, value="permanent").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(exp_frame, text="1年", variable=self.exp_var, value="1year").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(exp_frame, text="自定义:", variable=self.exp_var, value="custom").pack(side="left")

        self.custom_exp = tk.StringVar(value=(date.today() + timedelta(days=365)).strftime("%Y-%m-%d"))
        ttk.Entry(exp_frame, textvariable=self.custom_exp, width=12).pack(side="left", padx=(5, 0))

        # Generate button
        ttk.Button(frame, text="生成密钥", command=self.generate).pack(pady=15)

        # Result
        ttk.Label(frame, text="生成的密钥:").pack(anchor="w")
        self.result_var = tk.StringVar()
        result_entry = ttk.Entry(frame, textvariable=self.result_var, width=50, font=("Consolas", 10))
        result_entry.pack(fill="x", pady=(2, 5))

        # Copy button
        copy_btn = ttk.Button(frame, text="复制密钥", command=self.copy_result)
        copy_btn.pack(pady=(0, 15))

        ttk.Label(frame, text="私钥绝不外泄 · 仅开发者使用", foreground="red", font=("Microsoft YaHei", 8)).pack()

    def generate(self):
        device = self.device_var.get().strip()
        if not device:
            messagebox.showerror("错误", "请输入设备码")
            return

        level = self.level_var.get()

        if self.exp_var.get() == "permanent":
            exp = "9999-12-31"
        elif self.exp_var.get() == "1year":
            exp = (date.today() + timedelta(days=365)).strftime("%Y-%m-%d")
        else:
            exp = self.custom_exp.get().strip()
            if not exp:
                messagebox.showerror("错误", "请输入自定义过期日期 (YYYY-MM-DD)")
                return

        try:
            key = generate_key(device, level=level, exp=exp)
            self.result_var.set(key)
        except FileNotFoundError:
            messagebox.showerror("错误", "找不到 quantsage_private.key\n请确保在项目根目录运行")
        except Exception as e:
            messagebox.showerror("错误", f"生成失败: {e}")

    def copy_result(self):
        key = self.result_var.get()
        if key:
            self.root.clipboard_clear()
            self.root.clipboard_append(key)
            messagebox.showinfo("已复制", "密钥已复制到剪贴板")


if __name__ == "__main__":
    root = tk.Tk()
    app = KeygenApp(root)
    root.mainloop()
