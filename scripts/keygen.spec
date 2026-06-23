# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for QuantSage Keygen GUI — standalone .exe for developer use."""

import os

spec_dir = SPECPATH  # noqa: F821
project_root = os.path.dirname(spec_dir)

a = Analysis(
    [os.path.join(spec_dir, 'keygen_gui.py')],
    pathex=[spec_dir],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter', 'cryptography', 'cryptography.hazmat.primitives.asymmetric.ed25519',
                   'json', 'datetime', 'pathlib', 'base64'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'transformers', 'pandas', 'numpy', 'streamlit', 'langchain',
              'matplotlib', 'PIL', 'scipy'],
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='QuantSage_Keygen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app, no console window
    disable_windowed_traceback=False,
    icon=os.path.join(project_root, 'src', 'ui', 'assets', 'logo.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QuantSage_Keygen',
)
