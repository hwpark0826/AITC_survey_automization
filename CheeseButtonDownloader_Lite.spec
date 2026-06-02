# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_dir = Path(SPECPATH)
python_dir = Path(sys.executable).parent

datas = collect_data_files("playwright")
datas += [(str(python_dir / "tcl"), "tcl")]
binaries = [
    (str(python_dir / "DLLs" / "_tkinter.pyd"), "."),
    (str(python_dir / "DLLs" / "tcl86t.dll"), "."),
    (str(python_dir / "DLLs" / "tk86t.dll"), "."),
]
hiddenimports = collect_submodules("playwright") + ["tkinter"]


a = Analysis(
    ["cheese_button_gui.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(project_dir / "pyinstaller_hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CheeseButtonDownloader_Lite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CheeseButtonDownloader_Lite",
)
