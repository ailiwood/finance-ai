"""QuantSage License Key Generator — GUI for developer use.

Ed25519-signed, device-bound license keys.
Requires quantsage_private.key in the same directory or project root.

Self-contained — no imports from src/ needed. Works as .exe or .py.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from pathlib import Path
import json
import base64
import sys


# ═══════════════════════════════════════════════════════════════
# Inline key generation (self-contained, no src/ dependency)
# ═══════════════════════════════════════════════════════════════

def _find_private_key() -> Path:
    """Find quantsage_private.key in common locations."""
    exe_dir = Path(sys.executable).parent.resolve() if getattr(sys, 'frozen', False) else Path.cwd()
    candidates = [
        Path("quantsage_private.key"),                              # CWD
        exe_dir / "quantsage_private.key",                          # next to .exe / python
        exe_dir.parent / "quantsage_private.key",                   # one level up from .exe
        Path(__file__).resolve().parent.parent / "quantsage_private.key",  # project root (dev mode)
    ]
    # Also check _MEIPASS for PyInstaller onedir builds
    if hasattr(sys, '_MEIPASS'):
        candidates.append(Path(sys._MEIPASS) / "quantsage_private.key")
        candidates.append(Path(sys._MEIPASS).parent / "quantsage_private.key")

    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "找不到 quantsage_private.key。\n\n"
        "请将私钥文件放在以下任一位置后重试：\n"
        f"  1. Keygen.exe 所在目录: {exe_dir}\n"
        f"  2. 项目根目录: {Path(__file__).resolve().parent.parent}\n"
        f"  3. 当前工作目录: {Path.cwd()}"
    )


def generate_key(device_code: str, level: str = "pro", exp: str = "9999-12-31") -> str:
    """Generate an Ed25519-signed license key (compact base64url encoding)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key_path = _find_private_key()
    priv = Ed25519PrivateKey.from_private_bytes(key_path.read_bytes())

    # Use only 8 chars of device code (shorter key, still unique per device)
    payload = {"d": device_code[:16], "exp": exp, "lv": level}
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = priv.sign(payload_bytes)

    # Encode: 2-byte length prefix + payload + signature → base64url → groups of 4
    plen = len(payload_bytes).to_bytes(2, "big")
    combined = plen + payload_bytes + signature
    b64 = base64.urlsafe_b64encode(combined).decode("ascii").rstrip("=")
    groups = [b64[i:i+4] for i in range(0, len(b64), 4)]
    return "QS." + ".".join(groups)  # dot separator (base64url uses - and _)


# ═══════════════════════════════════════════════════════════════
# GUI
# ═══════════════════════════════════════════════════════════════


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
