"""Plugin Manager for QuantSage optional GPU components.

Manages discovery, download, verification (SHA-256), installation, and
activation of GPU-accelerated plugins (Kronos, FinBERT).

Plugin storage layout:
    ~/.quantsage/plugins/
    ├── installed.json          # {plugins: {id: {version, sha256, installed_at}}}
    ├── kronos_gpu/             # Kronos plugin files
    │   └── plugin.json         # Plugin metadata
    └── finbert_gpu/            # FinBERT plugin files
        └── plugin.json         # Plugin metadata
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from urllib.request import urlopen, Request


# === Plugin directory ===

def _plugin_dir() -> Path:
    """Return ~/.quantsage/plugins/, creating if needed."""
    d = Path.home() / ".quantsage" / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d


# === Manifest ===

MANIFEST_URLS = [
    "https://raw.githubusercontent.com/ailiwood/finance-ai/main/plugin_manifest.json",
    "https://gitee.com/ailiwood/finance-ai/raw/main/plugin_manifest.json",
]

LOCAL_MANIFEST_PATH = _plugin_dir() / "plugin_manifest.json"
INSTALLED_JSON_PATH = _plugin_dir() / "installed.json"


@dataclass
class PluginFile:
    """A file within a plugin pack."""
    url: str
    mirror_url: str = ""
    sha256: str = ""
    size_mb: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "PluginFile":
        return cls(
            url=d.get("url", ""),
            mirror_url=d.get("mirror_url", ""),
            sha256=d.get("sha256", ""),
            size_mb=float(d.get("size_mb", 0)),
        )


@dataclass
class PluginInfo:
    """Metadata for a single plugin."""
    plugin_id: str
    name: str
    description: str
    version: str
    required_disk_mb: float = 0.0
    required_gpu: bool = False
    min_vram_gb: float = 0.0
    files: List[PluginFile] = field(default_factory=list)
    installed: bool = False
    installed_version: str = ""

    @classmethod
    def from_dict(cls, plugin_id: str, d: dict) -> "PluginInfo":
        return cls(
            plugin_id=plugin_id,
            name=d.get("name", plugin_id),
            description=d.get("description", ""),
            version=d.get("version", "0.0.0"),
            required_disk_mb=float(d.get("required_disk_mb", 0)),
            required_gpu=d.get("required_gpu", False),
            min_vram_gb=float(d.get("min_vram_gb", 0)),
            files=[PluginFile.from_dict(f) for f in d.get("files", [])],
        )


class PluginManager:
    """Manages optional plugin packages for QuantSage.

    Responsibilities:
    - Fetch and parse the plugin manifest
    - Detect installed plugins from local state
    - Download, verify (SHA-256), and install plugins
    - Report plugin status (available, installed, compatible)
    """

    def __init__(self, plugin_dir: Optional[Path] = None):
        self._plugin_dir = plugin_dir or _plugin_dir()
        self._manifest: Optional[Dict[str, Any]] = None

    # -- Manifest --

    def fetch_manifest(self, force: bool = False) -> Dict[str, Any]:
        """Fetch the plugin manifest, with local cache (24h TTL).

        Tries URLs in order (primary, then mirrors). Caches result locally.
        """
        if self._manifest is not None and not force:
            return self._manifest

        # Check local cache first
        if not force and LOCAL_MANIFEST_PATH.exists():
            cache_age = time.time() - LOCAL_MANIFEST_PATH.stat().st_mtime
            if cache_age < 86400:  # 24 hours
                try:
                    self._manifest = json.loads(LOCAL_MANIFEST_PATH.read_text("utf-8"))
                    return self._manifest
                except (json.JSONDecodeError, OSError):
                    pass

        # Fetch from network
        for url in MANIFEST_URLS:
            try:
                req = Request(url, headers={"User-Agent": "QuantSage-PluginManager/1.0"})
                with urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self._manifest = data
                # Cache locally
                LOCAL_MANIFEST_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), "utf-8"
                )
                return self._manifest
            except Exception:
                continue

        # Network failed, try stale cache
        if LOCAL_MANIFEST_PATH.exists():
            try:
                self._manifest = json.loads(LOCAL_MANIFEST_PATH.read_text("utf-8"))
                return self._manifest
            except (json.JSONDecodeError, OSError):
                pass

        # No manifest available; return empty
        return {"plugins": {}}

    def get_available_plugins(self) -> List[PluginInfo]:
        """Return all plugins from the manifest, annotated with install status."""
        manifest = self.fetch_manifest()
        installed = self._read_installed()
        plugins: List[PluginInfo] = []

        for plugin_id, info_dict in manifest.get("plugins", {}).items():
            info = PluginInfo.from_dict(plugin_id, info_dict)
            if plugin_id in installed:
                info.installed = True
                info.installed_version = installed[plugin_id].get("version", "")
            plugins.append(info)

        return plugins

    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """Get a single plugin by ID."""
        for p in self.get_available_plugins():
            if p.plugin_id == plugin_id:
                return p
        return None

    # -- Install status --

    def is_installed(self, plugin_id: str) -> bool:
        """Check if a plugin is installed."""
        installed = self._read_installed()
        return plugin_id in installed

    def _read_installed(self) -> Dict[str, dict]:
        """Read installed.json."""
        if not INSTALLED_JSON_PATH.exists():
            return {}
        try:
            data = json.loads(INSTALLED_JSON_PATH.read_text("utf-8"))
            return data.get("plugins", {})
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_installed(self, plugins: Dict[str, dict]) -> None:
        """Write installed.json."""
        INSTALLED_JSON_PATH.write_text(
            json.dumps({
                "updated": datetime.now(timezone.utc).isoformat(),
                "plugins": plugins,
            }, ensure_ascii=False, indent=2),
            "utf-8",
        )

    # -- Download & Install --

    def download_plugin(
        self,
        plugin_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """Download and install a plugin package.

        Args:
            plugin_id: Plugin identifier (e.g. "kronos_gpu")
            progress_callback: Called with (ratio, status_msg) during download

        Returns:
            True if installed successfully
        """
        plugin = self.get_plugin(plugin_id)
        if plugin is None:
            if progress_callback:
                progress_callback(0.0, f"插件 '{plugin_id}' 不在清单中")
            return False

        if plugin.installed:
            if progress_callback:
                progress_callback(1.0, f"{plugin.name} 已安装")
            return True

        if not plugin.files:
            if progress_callback:
                progress_callback(0.0, f"插件 '{plugin_id}' 无可用下载")
            return False

        if progress_callback:
            progress_callback(0.0, f"正在准备下载 {plugin.name}...")

        # Download primary file
        pfile = plugin.files[0]
        url = pfile.url
        mirror_url = pfile.mirror_url

        # Try primary URL, fall back to mirror
        downloaded = False
        for attempt_url in [url, mirror_url]:
            if not attempt_url:
                continue
            try:
                self._do_download(plugin, pfile, attempt_url, progress_callback)
                downloaded = True
                break
            except Exception as e:
                if progress_callback:
                    progress_callback(0.0, f"下载失败: {e}. 尝试备用源...")
                continue

        if not downloaded:
            if progress_callback:
                progress_callback(0.0, "所有下载源均失败。请检查网络后重试。")
            return False

        # Verify SHA-256
        if progress_callback:
            progress_callback(0.95, "正在校验文件完整性...")
        if pfile.sha256 and not self._verify_plugin(plugin_id, pfile.sha256):
            if progress_callback:
                progress_callback(0.0, "SHA-256 校验失败！文件可能损坏。")
            return False

        # Mark installed
        installed = self._read_installed()
        installed[plugin_id] = {
            "version": plugin.version,
            "sha256": pfile.sha256,
            "installed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_installed(installed)

        if progress_callback:
            progress_callback(1.0, f"{plugin.name} 安装完成！")

        return True

    def _do_download(
        self,
        plugin: PluginInfo,
        pfile: PluginFile,
        url: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> None:
        """Download a plugin archive and extract it."""
        plugin_dir = self._plugin_dir / plugin.plugin_id

        # Check disk space
        free_gb = shutil.disk_usage(self._plugin_dir).free / (1024**3)
        required_gb = pfile.size_mb / 1024 * 1.2  # 20% buffer
        if free_gb < required_gb:
            raise OSError(
                f"磁盘空间不足：需要 {required_gb:.1f} GB，"
                f"可用 {free_gb:.1f} GB"
            )

        if progress_callback:
            progress_callback(0.05, f"正在连接 {url.split('/')[2]}...")

        # Download to temp file
        req = Request(url, headers={"User-Agent": "QuantSage-PluginManager/1.0"})
        with urlopen(req, timeout=300) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunks: List[bytes] = []

            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if total and progress_callback:
                    ratio = 0.05 + 0.85 * (downloaded / total)
                    mb_done = downloaded / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    progress_callback(ratio, f"下载中... {mb_done:.0f}/{mb_total:.0f} MB")

            data = b"".join(chunks)

        # Extract to plugin directory
        if progress_callback:
            progress_callback(0.90, "正在解压...")

        # Save archive temporarily
        tmp_zip = Path(tempfile.gettempdir()) / f"quantsage_{plugin.plugin_id}.zip"
        tmp_zip.write_bytes(data)

        try:
            # Extract
            import zipfile
            # Clean existing plugin dir
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            plugin_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(tmp_zip, "r") as zf:
                zf.extractall(plugin_dir)
        finally:
            tmp_zip.unlink(missing_ok=True)

    def _verify_plugin(self, plugin_id: str, expected_sha256: str) -> bool:
        """Verify all files in a plugin directory against the expected SHA-256.

        Computes a combined hash of all files (sorted by path).
        """
        plugin_dir = self._plugin_dir / plugin_id
        if not plugin_dir.exists():
            return False

        sha = hashlib.sha256()
        for fp in sorted(plugin_dir.rglob("*")):
            if fp.is_file():
                sha.update(fp.read_bytes())
        computed = sha.hexdigest()
        return computed == expected_sha256.lower()

    # -- Uninstall --

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Remove an installed plugin."""
        plugin_dir = self._plugin_dir / plugin_id
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)

        installed = self._read_installed()
        installed.pop(plugin_id, None)
        self._write_installed(installed)
        return True

    # -- GPU Compatibility --

    def get_gpu_status(self) -> dict:
        """Get GPU information for plugin compatibility checking.

        Returns dict with keys: available, name, vram_gb, fp8_supported, cuda_version.
        """
        try:
            from src.plugins.kronos_service.gpu_detector import detect_gpu
            gpu = detect_gpu()
            return {
                "available": gpu.available,
                "name": gpu.name,
                "vram_gb": gpu.vram_gb,
                "fp8_supported": gpu.fp8_supported,
                "cuda_version": gpu.cuda_version,
            }
        except Exception:
            return {
                "available": False,
                "name": "未检测到",
                "vram_gb": 0.0,
                "fp8_supported": False,
                "cuda_version": "",
            }

    def is_plugin_compatible(self, plugin: PluginInfo) -> tuple[bool, str]:
        """Check if a plugin is compatible with the current system.

        Returns:
            (compatible: bool, reason: str)
        """
        if not plugin.required_gpu:
            return True, ""

        gpu = self.get_gpu_status()
        if not gpu["available"]:
            return False, "未检测到 NVIDIA GPU"

        if gpu["vram_gb"] < plugin.min_vram_gb:
            return False, (
                f"显存不足：需要 {plugin.min_vram_gb:.0f} GB，"
                f"当前 {gpu['vram_gb']:.1f} GB"
            )

        return True, ""

    # -- Config integration --

    def activate_plugin(self, plugin_id: str) -> bool:
        """Enable a plugin in the QuantSage configuration.

        Sets the appropriate *_enabled flag in config.
        """
        try:
            from src.core.config_manager import load_config, save_config

            config = load_config()
            if plugin_id == "kronos_gpu":
                config["kronos_enabled"] = True
            elif plugin_id == "finbert_gpu":
                config["finbert_enabled"] = True
            else:
                return False

            save_config(config)
            return True
        except Exception:
            return False

    def deactivate_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin in the configuration."""
        try:
            from src.core.config_manager import load_config, save_config

            config = load_config()
            if plugin_id == "kronos_gpu":
                config["kronos_enabled"] = False
            elif plugin_id == "finbert_gpu":
                config["finbert_enabled"] = False
            else:
                return False

            save_config(config)
            return True
        except Exception:
            return False


# === Module-level convenience ===

_default_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get or create the default PluginManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = PluginManager()
    return _default_manager
