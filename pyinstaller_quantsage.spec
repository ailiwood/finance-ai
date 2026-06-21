# -*- mode: python ; coding: utf-8 -*-
"""QuantSage PyInstaller Spec File.

Builds the base QuantSage.exe without GPU dependencies.
GPU plugins (torch, transformers) are separate optional components.

Build command:
    pyinstaller pyinstaller_quantsage.spec --clean --noconfirm
"""

import os
import sys

from PyInstaller.utils.hooks import copy_metadata

# SPECPATH is a built-in PyInstaller variable pointing to the .spec file directory
spec_dir = SPECPATH  # noqa: F821

app_name = "QuantSage"
exe_name = "QuantSage_v1.0.0"

# === Analysis ===
a = Analysis(
    # Entry point: desktop launcher
    ['src/deployment/launcher.py'],

    pathex=[
        spec_dir,
        os.path.join(spec_dir, 'src'),
    ],

    binaries=[],

    # Data files bundled into the exe
    datas=[
        ('DISCLAIMER.md', '.'),
        ('.env.example', '.'),
        # Bundle src/ as data so Streamlit can find app.py at runtime
        (os.path.join(spec_dir, 'src'), 'src'),
        # Copy package metadata for packages that use importlib.metadata.version()
        *copy_metadata('streamlit'),
        *copy_metadata('altair'),
        *copy_metadata('numpy'),
        *copy_metadata('pandas'),
        *copy_metadata('langchain'),
        *copy_metadata('langchain-core'),
        *copy_metadata('fastapi'),
        *copy_metadata('starlette'),
        *copy_metadata('uvicorn'),
        *copy_metadata('pydantic'),
        *copy_metadata('jinja2'),
        *copy_metadata('cryptography'),
        *copy_metadata('fpdf2'),
        *copy_metadata('pillow'),
        *copy_metadata('pyarrow'),
    ],

    # Hidden imports that PyInstaller can't auto-detect
    hiddenimports=[
        # Streamlit internals
        'streamlit',
        'streamlit.web.bootstrap',
        'streamlit.runtime',
        'streamlit.runtime.scriptrunner',
        'streamlit.runtime.state',
        'streamlit.runtime.caching',
        'streamlit.commands',
        'streamlit.elements',
        'streamlit.proto',
        'streamlit.watcher',
        'streamlit.config',
        'streamlit.config_option',
        'streamlit.logger',
        'streamlit.env_util',
        'streamlit.file_util',
        'streamlit.string_util',
        'streamlit.url_util',
        'streamlit.error_util',
        'streamlit.platform',
        'streamlit.net_util',

        # LangChain
        'langchain',
        'langchain_openai',
        'langgraph',
        'langsmith',
        'langchain_core',
        'langchain_core.messages',
        'langchain_core.prompts',

        # FastAPI + Uvicorn (for Kronos/FinBERT services)
        'fastapi',
        'uvicorn',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.lifespan',
        'starlette',
        'pydantic',
        'pydantic.deprecated',
        'multipart',
        'python_multipart',

        # Cryptography
        'cryptography',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.primitives',
        'cryptography.fernet',

        # QuantSage internal modules
        'src',
        'src.core',
        'src.core.config_manager',
        'src.ui',
        'src.ui.app',
        'src.ui.home',
        'src.ui.config_wizard',
        'src.ui.disclaimer_gate',
        'src.report',
        'src.report.report_generator',
        'src.report.pdf_exporter',
        'src.report.templates',
        'src.compliance',
        'src.compliance.disclaimer',
        'src.compliance.phrase_checker',
        'src.plugins',
        'src.plugins.kronos_service',
        'src.plugins.kronos_service.service',
        'src.plugins.kronos_service.client',
        'src.plugins.kronos_service.config',
        'src.plugins.kronos_service.gpu_detector',
        'src.plugins.kronos_service.model_engine',
        'src.plugins.finbert_service',
        'src.plugins.finbert_service.service',
        'src.plugins.finbert_service.client',
        'src.plugins.finbert_service.config',
        'src.plugins.finbert_service.sentiment_engine',
        'src.deployment',
        'src.deployment.resource_path',
        'src.deployment.version',

        # Data/utility
        'pandas',
        'numpy',
        'requests',
        'httpx',
        'yaml',
        'jinja2',
        'altair',
        'pydeck',
        'git',
        'tiktoken',
        'tenacity',
        'orjson',
        'packaging',

        # Report export
        'fpdf',
        'markdown_it',
        'Pygments',
    ],

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],

    # Exclude GPU-heavy packages from base exe
    # These are in the optional GPU plugin components
    excludes=[
        # GPU / ML (optional plugin packs)
        'torch',
        'torchvision',
        'torchaudio',
        'transformers',
        'tokenizers',
        'safetensors',
        'huggingface_hub',
        'hf_xet',
        'accelerate',
        'datasets',
        'peft',
        'sentencepiece',

        # Large scientific (not needed)
        'scipy',
        'scikit-learn',
        'matplotlib',
        'PIL',
        'Pillow',
        'cv2',

        # GUI toolkits (not needed)
        'tkinter',
        'PyQt5',
        'PySide2',
        'wx',

        # Testing (not needed at runtime)
        'pytest',
        'unittest',

        # Database drivers (not needed for MVP)
        'sqlite3',
        'psycopg2',
        'pymongo',
        'redis',
    ],
)

# Filter out excluded modules
pyz = PYZ(a.pure, a.zipped_data)

# Single-file exe with console output (helpful for debugging)
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
    console=True,          # Show console for server status output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='installer/assets/quantsage.ico',             # QuantSage tech-finance icon
)
