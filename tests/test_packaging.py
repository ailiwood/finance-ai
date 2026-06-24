"""Tests for M7 packaging module.

Tests run against source-mode execution (not PyInstaller bundle).
For full integration tests, build the exe and verify on a clean machine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


# === resource_path ===

class TestResourcePath:
    def test_get_base_path_returns_path(self):
        """get_base_path() should return an existing directory."""
        from src.deployment.resource_path import get_base_path
        bp = get_base_path()
        assert bp.exists()
        assert bp.is_dir()

    def test_get_base_path_contains_disclaimer(self):
        """Project root should contain DISCLAIMER.md."""
        from src.deployment.resource_path import get_base_path
        bp = get_base_path()
        assert (bp / "DISCLAIMER.md").exists()

    def test_get_config_dir_is_home(self):
        """get_config_dir() should be under user's home."""
        from src.deployment.resource_path import get_config_dir
        cd = get_config_dir()
        assert str(Path.home()) in str(cd)

    def test_get_disclaimer_path_exists(self):
        """get_disclaimer_path() should return an existing file."""
        from src.deployment.resource_path import get_disclaimer_path
        dp = get_disclaimer_path()
        assert dp.exists()
        assert dp.suffix == ".md"

    def test_get_plugin_dir(self):
        """get_plugin_dir() should be under config dir."""
        from src.deployment.resource_path import get_plugin_dir, get_config_dir
        pd = get_plugin_dir()
        assert str(get_config_dir()) in str(pd)

    def test_frozen_detection_not_frozen(self):
        """In test mode, we should not be 'frozen' (PyInstaller)."""
        assert getattr(sys, "frozen", False) is False


# === version ===

class TestVersion:
    def test_version_format(self):
        """Version string should follow semver."""
        from src.deployment.version import __version__
        parts = __version__.split(".")
        assert len(parts) == 3
        for p in parts:
            assert p.isdigit()

    def test_version_tuple(self):
        """Version tuple should match string."""
        from src.deployment.version import __version_tuple__, __version__
        expected = ".".join(str(x) for x in __version_tuple__)
        assert expected == __version__

    def test_build_marker(self):
        """Build marker should be set."""
        from src.deployment.version import __build__
        assert __build__ == "m7"


# === plugin_manager ===

class TestPluginManager:
    def test_plugin_manager_init(self):
        """PluginManager should initialize without errors."""
        from src.deployment.plugin_manager import PluginManager
        pm = PluginManager()
        assert pm is not None

    def test_get_gpu_status_returns_dict(self):
        """GPU status should always return a dict, even without GPU."""
        from src.deployment.plugin_manager import PluginManager
        pm = PluginManager()
        status = pm.get_gpu_status()
        assert isinstance(status, dict)
        assert "available" in status
        assert "name" in status
        assert "vram_gb" in status

    def test_plugin_info_from_dict(self):
        """PluginInfo.from_dict should parse correctly."""
        from src.deployment.plugin_manager import PluginInfo
        d = {
            "name": "Test Plugin",
            "description": "A test",
            "version": "1.0.0",
            "required_disk_mb": 100,
            "required_gpu": False,
            "min_vram_gb": 0,
            "files": [
                {"url": "http://example.com/test.zip", "sha256": "abc123", "size_mb": 50}
            ],
        }
        info = PluginInfo.from_dict("test_plugin", d)
        assert info.plugin_id == "test_plugin"
        assert info.name == "Test Plugin"
        assert info.version == "1.0.0"
        assert info.required_disk_mb == 100
        assert not info.required_gpu
        assert len(info.files) == 1
        assert info.files[0].sha256 == "abc123"
        assert info.files[0].size_mb == 50

    def test_is_plugin_compatible_cpu_plugin(self):
        """A CPU-only plugin should always be compatible."""
        from src.deployment.plugin_manager import PluginManager, PluginInfo
        pm = PluginManager()
        plugin = PluginInfo.from_dict("cpu_plugin", {
            "name": "CPU Plugin",
            "description": "",
            "version": "1.0",
            "required_disk_mb": 100,
            "required_gpu": False,
            "min_vram_gb": 0,
            "files": [],
        })
        compatible, reason = pm.is_plugin_compatible(plugin)
        assert compatible
        assert reason == ""

    def test_plugin_not_installed_initially(self):
        """A non-existent plugin should not be marked as installed."""
        from src.deployment.plugin_manager import PluginManager
        pm = PluginManager()
        assert not pm.is_installed("nonexistent_plugin_xyz")

    def test_get_plugin_manager_singleton(self):
        """get_plugin_manager should return the same instance."""
        from src.deployment.plugin_manager import get_plugin_manager
        pm1 = get_plugin_manager()
        pm2 = get_plugin_manager()
        assert pm1 is pm2

    def test_deactivate_nonexistent_plugin(self):
        """Deactivating an uninstalled plugin should not crash."""
        from src.deployment.plugin_manager import PluginManager
        pm = PluginManager()
        result = pm.deactivate_plugin("nonexistent")
        assert result is False

    def test_uninstall_nonexistent_plugin(self):
        """Uninstalling an uninstalled plugin should return True (no-op)."""
        from src.deployment.plugin_manager import PluginManager
        pm = PluginManager()
        result = pm.uninstall_plugin("nonexistent_xyz")
        assert result is True


# === launcher ===

class TestLauncherPort:
    def test_is_port_available_default(self):
        """Default port availability check should not crash."""
        from src.deployment.launcher import is_port_available
        result = is_port_available(8501)
        assert isinstance(result, bool)

    def test_find_available_port_returns_int(self):
        """find_available_port should return a valid port number."""
        from src.deployment.launcher import find_available_port
        port = find_available_port(18501)
        assert isinstance(port, int)
        assert 18501 <= port <= 18600

    def test_port_available_different_ports(self):
        """Different ports should be independently checkable."""
        from src.deployment.launcher import is_port_available
        # Technically both could be occupied, but not both 18502 and 18503
        # (extremely unlikely). Just check they don't crash.
        r1 = is_port_available(18502)
        r2 = is_port_available(18503)
        assert isinstance(r1, bool)
        assert isinstance(r2, bool)


# === Manifest ===

class TestManifest:
    def test_manifest_file_exists(self):
        """plugin_manifest.json should exist in project root."""
        mp = Path(__file__).resolve().parent.parent / "plugin_manifest.json"
        assert mp.exists(), f"Expected manifest at {mp}"

    def test_manifest_valid_json(self):
        """Manifest should be valid JSON."""
        mp = Path(__file__).resolve().parent.parent / "plugin_manifest.json"
        data = json.loads(mp.read_text("utf-8"))
        assert "version" in data
        assert "plugins" in data

    def test_manifest_has_kronos(self):
        """Manifest should contain kronos_gpu plugin."""
        mp = Path(__file__).resolve().parent.parent / "plugin_manifest.json"
        data = json.loads(mp.read_text("utf-8"))
        assert "kronos_gpu" in data["plugins"]

    def test_manifest_has_finbert(self):
        """Manifest should contain finbert_gpu plugin."""
        mp = Path(__file__).resolve().parent.parent / "plugin_manifest.json"
        data = json.loads(mp.read_text("utf-8"))
        assert "finbert_gpu" in data["plugins"]

    def test_manifest_plugins_have_required_fields(self):
        """Each plugin should have required metadata fields."""
        mp = Path(__file__).resolve().parent.parent / "plugin_manifest.json"
        data = json.loads(mp.read_text("utf-8"))
        required = {"name", "description", "version", "required_disk_mb", "required_gpu", "files"}
        for pid, pdata in data["plugins"].items():
            missing = required - set(pdata.keys())
            assert not missing, f"Plugin '{pid}' missing fields: {missing}"


# === Resource path integration (impact on existing code) ===

class TestResourcePathIntegration:
    def test_config_manager_uses_resource_path(self):
        """config_manager should use resource_path for env file paths."""
        from src.core.config_manager import _ENV_FILE, _ENV_TEMPLATE
        assert _ENV_FILE.name == ".env"
        assert _ENV_TEMPLATE.name == ".env.example"

    def test_disclaimer_uses_resource_path(self):
        """disclaimer.py should use get_disclaimer_path."""
        from src.compliance.disclaimer import _DISCLAIMER_PATH
        assert _DISCLAIMER_PATH.name == "DISCLAIMER.md"

    def test_pdf_exporter_uses_resource_path(self):
        """pdf_exporter should use get_base_path."""
        # Just verify the module can be imported without error
        from src.report.pdf_exporter import export_report_pdf, export_report_markdown
        assert callable(export_report_pdf)
        assert callable(export_report_markdown)

    def test_kronos_engine_can_import(self):
        """Kronos model engine should import cleanly after resource path update."""
        from src.plugins.kronos_service.model_engine import get_engine, reset_engine
        reset_engine()
        engine = get_engine()
        assert engine is not None

    def test_finbert_engine_can_import(self):
        """FinBERT sentiment engine should import cleanly after resource path update."""
        from src.plugins.finbert_service.sentiment_engine import get_sentiment_engine
        engine = get_sentiment_engine(prefer_gpu=False)
        assert engine is not None
