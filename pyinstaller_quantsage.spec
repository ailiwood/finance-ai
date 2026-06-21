# -*- mode: python ; coding: utf-8 -*-
"""QuantSage PyInstaller Spec File.

Builds the base QuantSage.exe without GPU dependencies.
GPU plugins (torch, transformers) are separate optional components.

Build command:
    pyinstaller pyinstaller_quantsage.spec --clean --noconfirm
"""

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

# SPECPATH is a built-in PyInstaller variable pointing to the .spec file directory
spec_dir = SPECPATH  # noqa: F821

app_name = "QuantSage"
exe_name = "QuantSage_v1.0.0"

# ── Collect complete packages (code + static assets + metadata) ──
# Using collect_all ensures frontend static files (HTML/JS/CSS) are bundled.
# Without these, Streamlit's browser UI shows "NOT FOUND".
_all_datas = []
_all_binaries = []
_all_hidden = []

for _pkg in ["streamlit", "altair", "pydeck"]:
    d, b, h = collect_all(_pkg)
    _all_datas.extend(d)
    _all_binaries.extend(b)
    _all_hidden.extend(h)

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
    (os.path.join(spec_dir, "run_app.py"), "."),
    (os.path.join(spec_dir, "st_test.py"), "."),
    (os.path.join(spec_dir, "src"), "src"),
]

# ── Hidden imports that collect_all may miss ──
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

    # QuantSage modules
    "src", "src.core", "src.core.config_manager",
    "src.ui", "src.ui.app", "src.ui.home",
    "src.ui.config_wizard", "src.ui.disclaimer_gate", "src.ui.plugin_manager",
    "src.report", "src.report.report_generator",
    "src.report.pdf_exporter", "src.report.templates",
    "src.compliance", "src.compliance.disclaimer", "src.compliance.phrase_checker",
    "src.plugins", "src.plugins.kronos_service", "src.plugins.kronos_service.service",
    "src.plugins.kronos_service.client", "src.plugins.kronos_service.config",
    "src.plugins.kronos_service.gpu_detector", "src.plugins.kronos_service.model_engine",
    "src.plugins.finbert_service", "src.plugins.finbert_service.service",
    "src.plugins.finbert_service.client", "src.plugins.finbert_service.config",
    "src.plugins.finbert_service.sentiment_engine",
    "src.deployment", "src.deployment.resource_path", "src.deployment.version",

    # Utilities
    "pandas", "numpy", "requests", "httpx", "yaml", "jinja2",
    "tiktoken", "tenacity", "orjson", "packaging",

    # Report
    "fpdf", "markdown_it", "Pygments",
]

# === Analysis ===
a = Analysis(
    ["src/deployment/launcher.py"],

    pathex=[
        spec_dir,
        os.path.join(spec_dir, "src"),
    ],

    binaries=_all_binaries,
    datas=_own_datas + _all_datas,

    hiddenimports=_all_hidden + _extra_hidden,

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        os.path.join(spec_dir, 'pyi_rthook_streamlit_static.py'),
    ],

    # Exclude GPU-heavy packages from base exe
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

        # Testing (not needed at runtime)
        "pytest", "unittest",

        # External database drivers (not needed)
        "psycopg2", "pymongo", "redis",
    ],
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="installer/assets/quantsage.ico",
)
