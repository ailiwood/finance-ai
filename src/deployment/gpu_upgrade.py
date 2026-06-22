"""GPU upgrade module — user-triggered CUDA torch installation.

Principles:
- Never auto-install — user must explicitly trigger
- Show clear pre-flight info (size, time, driver requirements)
- Failed upgrade must NOT break existing CPU-torch environment
- Progress feedback throughout the process
"""

from __future__ import annotations

import subprocess
import sys
from typing import Callable, Optional


# CUDA version to install (should match most users' drivers)
_CUDA_TAG = "cu124"
# Approximate download size
_DOWNLOAD_SIZE_GB = 2.5


def _run_pip(args: list[str], timeout: int = 600) -> tuple[int, str]:
    """Run pip with the given args, return (exit_code, output)."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip"] + args,
            capture_output=True, text=True, timeout=timeout,
            creationflags=0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return r.returncode, r.stdout + "\n" + r.stderr
    except subprocess.TimeoutExpired:
        return -1, "pip install timed out after {}s".format(timeout)
    except FileNotFoundError:
        return -1, "pip not found — is Python installed correctly?"
    except Exception as e:
        return -1, f"pip execution failed: {e}"


def check_upgrade_prerequisites() -> tuple[bool, str]:
    """Check whether GPU upgrade is possible.

    Returns (ready: bool, message: str).
    """
    from src.plugins.kronos_service.gpu_detector import detect_hardware

    hw = detect_hardware()

    if not hw.has_nvidia:
        return False, "未检测到 NVIDIA 显卡。GPU 升级需要 NVIDIA 独立显卡。"
    if hw.torch_build == "cuda":
        return False, f"已启用 GPU 加速 ({hw.gpu_name})。无需升级。"
    if hw.torch_build == "not_installed":
        return False, "PyTorch 未安装。请先安装 CPU 版 torch。"
    return True, (
        f"检测到 {hw.gpu_name}\n"
        f"当前: CPU 版 PyTorch {hw.torch_version}\n"
        f"可升级至 CUDA 版 (cu{_CUDA_TAG})"
    )


def _upgrade_progress(msg: str, pct: int = -1) -> None:
    """Log upgrade progress to stderr (visible in Streamlit logs)."""
    marker = f"[{pct}%] " if pct >= 0 else ""
    print(f"[GPU升级] {marker}{msg}", file=sys.stderr, flush=True)


def upgrade_to_gpu(
    progress_callback: Optional[Callable[[str, float], None]] = None,
    force_cuda_tag: Optional[str] = None,
) -> tuple[bool, str]:
    """Install CUDA version of PyTorch.

    Args:
        progress_callback: Optional callback(msg: str, fraction: float) for UI updates
        force_cuda_tag: Override the CUDA version tag (e.g., "cu121")

    Returns:
        (success: bool, message: str) — Chinese message suitable for UI display.
    """
    cuda_tag = force_cuda_tag or _CUDA_TAG
    index_url = f"https://download.pytorch.org/whl/{cuda_tag}"

    def _progress(msg: str, pct: float = 0.0):
        _upgrade_progress(msg)
        if progress_callback:
            progress_callback(msg, pct)

    # 1) Pre-flight check
    ready, pre_msg = check_upgrade_prerequisites()
    if not ready:
        return False, pre_msg

    _progress("检查通过，开始升级...", 0.05)

    # 2) Uninstall CPU torch first (clean start)
    _progress("正在移除 CPU 版 PyTorch...", 0.10)
    exit_code, output = _run_pip(["uninstall", "torch", "torchvision", "torchaudio", "-y"], timeout=120)
    if exit_code != 0:
        _progress(f"移除旧 torch 时出现警告（可忽略）: {output[-200:]}", 0.15)

    # 3) Install CUDA torch
    _progress(f"正在下载 CUDA 版 PyTorch ({_DOWNLOAD_SIZE_GB}GB)...", 0.20)
    exit_code, output = _run_pip([
        "install", "torch", "torchvision", "torchaudio",
        "--index-url", index_url,
    ], timeout=600)

    if exit_code != 0:
        # 3a) Failed — rollback to CPU torch
        _progress("CUDA 版安装失败，正在回退到 CPU 版...", 0.5)
        rollback_code, rollback_out = _run_pip([
            "install", "torch", "torchvision",
            "--index-url", "https://download.pytorch.org/whl/cpu",
        ], timeout=300)
        if rollback_code != 0:
            return False, (
                f"GPU 升级失败且回退 CPU 版也失败。\n\n"
                f"升级错误:\n{output[-500:]}\n\n"
                f"回退错误:\n{rollback_out[-200:]}\n\n"
                f"请手动执行: pip install torch torchvision"
            )
        return False, (
            f"GPU 升级失败，已回退到 CPU 版（功能正常不受影响）。\n\n"
            f"可能原因：\n"
            f"• NVIDIA 驱动版本过旧（需要较新版本）\n"
            f"• 网络连接不稳定\n"
            f"• CUDA {cuda_tag} 与您的驱动不兼容\n\n"
            f"错误详情:\n{output[-300:]}"
        )

    _progress("安装完成，正在验证...", 0.80)

    # 4) Verify CUDA is now available
    try:
        import torch
        if torch.cuda.is_available():
            _progress(f"验证成功！GPU 加速已启用 ({torch.cuda.get_device_name(0)})", 1.0)
            return True, (
                f"GPU 升级成功！\n\n"
                f"显卡: {torch.cuda.get_device_name(0)}\n"
                f"CUDA: {torch.version.cuda}\n"
                f"PyTorch: {torch.__version__}\n\n"
                f"请重启应用以启用 GPU 加速。"
            )
        else:
            _progress("torch.cuda.is_available() = False — 安装但不可用", 0.95)
            return False, (
                "CUDA 版 PyTorch 已安装，但 CUDA 不可用。\n"
                "可能原因：NVIDIA 驱动版本过旧。\n"
                "请升级驱动后重试: https://www.nvidia.com/drivers\n"
                "当前 CPU 版功能不受影响。"
            )
    except ImportError:
        return False, "安装后无法导入 torch。请重新安装 CPU 版。"
    except Exception as e:
        return False, f"验证 CUDA 时出错: {e}"


def get_upgrade_info() -> dict:
    """Return upgrade-related information for UI display."""
    from src.plugins.kronos_service.gpu_detector import detect_hardware

    hw = detect_hardware()
    info = {
        "compute_mode": hw.compute_mode,
        "gpu_name": hw.gpu_name,
        "torch_build": hw.torch_build,
        "torch_version": hw.torch_version,
        "can_upgrade": hw.compute_mode == "cpu_upgradable",
        "download_size_gb": _DOWNLOAD_SIZE_GB,
        "cuda_tag": _CUDA_TAG,
    }

    # UI display labels for each mode
    mode_labels = {
        "cpu_only": "CPU 模式（适用于所有电脑）",
        "cpu_upgradable": f"检测到 {hw.gpu_name}，当前 CPU 模式。可升级 GPU 版获得更快预测速度",
        "gpu_enabled": f"GPU 加速已启用（{hw.gpu_name}）",
    }
    info["mode_label"] = mode_labels.get(hw.compute_mode, "未知")

    return info
