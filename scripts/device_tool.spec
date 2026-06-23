# -*- mode: python ; coding: utf-8 -*-
"""Standalone device code tool — tiny EXE for installer use."""

import os
spec_dir = SPECPATH  # noqa: F821

a = Analysis(
    [os.path.join(spec_dir, 'get_device_code.py')],
    pathex=[spec_dir],
    binaries=[],
    datas=[],
    hiddenimports=['winreg', 'hashlib', 'uuid', 'platform'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='qs_device_code',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # We need stdout!
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='qs_device_code',
)
