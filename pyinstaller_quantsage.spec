# -*- mode: python ; coding: utf-8 -*-
"""QuantSage PyInstaller Spec File — single-file exe with all dependencies."""

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

spec_dir = SPECPATH  # noqa: F821
ta_cn_dir = os.path.join(os.path.dirname(spec_dir), 'TradingAgents-CN')

app_name = "QuantSage"
exe_name = "QuantSage_v1.0.0"

# ── Collect complete packages (code + static assets + metadata) ──
_all_datas = []
_all_binaries = []
_all_hidden = []

for _pkg in ["streamlit", "altair", "pydeck", "chromadb", "fpdf", "PIL", "akshare", "tushare", "baostock"]:
    try:
        d, b, h = collect_all(_pkg)
        _all_datas.extend(d)
        _all_binaries.extend(b)
        _all_hidden.extend(h)
    except Exception:
        pass  # Package not installed — skip

# ── Additional package metadata ──
_metadata_pkgs = [
    "streamlit", "altair", "numpy", "pandas",
    "langchain", "langchain-core", "fastapi", "starlette",
    "uvicorn", "pydantic", "jinja2", "cryptography",
    "fpdf2", "pillow", "pyarrow",
]
for _mp in _metadata_pkgs:
    _all_datas.extend(copy_metadata(_mp))

# ── Our own data files ──
_own_datas = [
    ("DISCLAIMER.md", "."),
    (".env.example", "."),
    (os.path.join(spec_dir, "src"), "src"),
    # User-provided assets
    (os.path.join(spec_dir, "src", "ui", "assets"), os.path.join("src", "ui", "assets")),
    # Bundle TradingAgents-CN (Apache 2.0 core) — no separate install needed
    (os.path.join(ta_cn_dir, "tradingagents"), "tradingagents"),
    # Bundle Kronos model code (MIT) — vendored deep learning K-line predictor
    (os.path.join(spec_dir, "src", "plugins", "kronos_service", "kronos_model"),
     os.path.join("src", "plugins", "kronos_service", "kronos_model")),
    # Bundle Kronos model weights (~400MB) — pre-downloaded from HuggingFace
    (os.path.join(spec_dir, "src", "plugins", "kronos_service", "kronos_model", "hf_cache"),
     os.path.join("src", "plugins", "kronos_service", "kronos_model", "hf_cache")),
]

# ── Hidden imports ──
_extra_hidden = [
    # FastAPI + Uvicorn
    "fastapi", "uvicorn", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.lifespan",
    "starlette", "pydantic", "pydantic.deprecated",
    "multipart", "python_multipart",

    # Cryptography
    "cryptography", "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.primitives", "cryptography.fernet",

    # LangChain
    "langchain", "langchain_openai", "langgraph", "langsmith",
    "langchain_core", "langchain_core.messages", "langchain_core.prompts",

    # TradingAgents-CN (bundled, Apache 2.0)
    "tradingagents", "tradingagents.graph", "tradingagents.graph.trading_graph",
    "tradingagents.default_config", "tradingagents.agents", "tradingagents.config",
    "tradingagents.constants", "tradingagents.dataflows", "tradingagents.llm_adapters",
    "tradingagents.llm_clients", "tradingagents.models", "tradingagents.tools",
    "tradingagents.utils", "tradingagents.api",

    # TA-CN data dependencies
    "yfinance", "stockstats", "pymongo", "tushare", "baostock",

    # QuantSage modules
    "src", "src.core", "src.core.config_manager",
    "src.ui", "src.ui.app", "src.ui.home",
    "src.ui.config_wizard", "src.ui.disclaimer_gate", "src.ui.plugin_manager",
    "src.report", "src.report.report_generator",
    "src.report.pdf_exporter", "src.report.templates",
    "src.compliance", "src.compliance.disclaimer", "src.compliance.phrase_checker",
    "src.compliance.report_reviewer",
    "src.plugins", "src.plugins.kronos_service", "src.plugins.kronos_service.service",
    "src.plugins.kronos_service.client", "src.plugins.kronos_service.config",
    "src.plugins.kronos_service.gpu_detector", "src.plugins.kronos_service.model_engine",
    "src.plugins.finbert_service", "src.plugins.finbert_service.service",
    "src.plugins.finbert_service.client", "src.plugins.finbert_service.config",
    "src.plugins.finbert_service.sentiment_engine",
    "src.deployment", "src.deployment.resource_path", "src.deployment.version",
    "src.llm", "src.llm.providers", "src.llm.client",
    "src.data", "src.data.market_data",
    "src.analysis", "src.analysis.indicators",
    "src.config", "src.config.sentiment_sources",
    "src.ui.data_inspection",

    # Utilities
    "pandas", "numpy", "requests", "httpx", "yaml", "jinja2",
    "tiktoken", "tenacity", "orjson", "packaging",

    # Report
    "fpdf", "markdown_it", "Pygments",
    # fpdf depends on unittest.mock for digital signatures
    "unittest", "unittest.mock",

    # Kronos deep learning model (MIT)
    "einops", "huggingface_hub", "huggingface_hub.hf_api",
    "src.plugins.kronos_service.kronos_model",
    "src.plugins.kronos_service.kronos_model.kronos",
    "src.plugins.kronos_service.kronos_model.module",
]

# === Analysis ===
a = Analysis(
    ["src/deployment/launcher.py"],

    pathex=[
        spec_dir,
        os.path.join(spec_dir, "src"),
        ta_cn_dir,
    ],

    binaries=_all_binaries,
    datas=_own_datas + _all_datas,

    hiddenimports=_all_hidden + _extra_hidden,

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        os.path.join(spec_dir, 'pyi_rthook_streamlit_static.py'),
    ],

    excludes=[
        # GPU / ML (optional plugin packs)
        "torch", "torchvision", "torchaudio",
        "transformers", "tokenizers", "safetensors",
        "huggingface_hub", "hf_xet",
        "accelerate", "datasets", "peft", "sentencepiece",

        # Large scientific (not needed at runtime)
        "scipy", "scikit-learn", "matplotlib", "cv2",

        # GUI toolkits (not needed)
        "tkinter", "PyQt5", "PySide2", "wx",

        # Testing
        "pytest",
        # NOTE: unittest is NOT excluded — fpdf needs unittest.mock

        # External database drivers (not directly needed)
        "psycopg2", "redis",
        # NOTE: pymongo is NOT excluded — TradingAgents-CN uses it
    ],
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="src/ui/assets/logo.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=exe_name,
)
